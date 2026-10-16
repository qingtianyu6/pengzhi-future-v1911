"""Evaluate stored forecasts against nearest valid later measurements."""

from datetime import UTC, datetime, timedelta
from math import sqrt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ForecastAudit, Greenhouse, SensorData
from app.schemas.model_health import MetricHealth, ModelHealth
from app.schemas.prediction import EnvironmentPredictionData
from app.services.errors import ServiceError
from app.services.sensor_service import VALID_BUSINESS_SOURCES


def _naive(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


def save_forecast(db: Session, prediction: EnvironmentPredictionData) -> None:
    if prediction.status != "ready" or prediction.input_end_time is None:
        return
    input_end = _naive(prediction.input_end_time)
    version = prediction.model_version or "unknown"
    for point in prediction.predictions:
        target = _naive(point.forecast_time)
        exists = db.scalar(select(ForecastAudit.id).where(
            ForecastAudit.greenhouse_id == prediction.greenhouse_id,
            ForecastAudit.input_end_time == input_end,
            ForecastAudit.target_at == target,
            ForecastAudit.model_version == version))
        if exists is not None:
            continue
        db.add(ForecastAudit(
            greenhouse_id=prediction.greenhouse_id, input_end_time=input_end,
            target_at=target, horizon_hours=point.horizon, model_version=version,
            predicted_temperature=point.temperature_c,
            predicted_humidity=point.air_humidity_pct,
            temperature_lower=point.lower_bounds.get("air_temperature_c"),
            temperature_upper=point.upper_bounds.get("air_temperature_c"),
            humidity_lower=point.lower_bounds.get("air_humidity_pct"),
            humidity_upper=point.upper_bounds.get("air_humidity_pct"),
        ))
    db.commit()


def _metric(rows: list[tuple[float, float, float | None, float | None]]) -> MetricHealth:
    if not rows:
        return MetricHealth(sample_count=0, mae=None, rmse=None, bias=None,
                            interval_coverage=None, drift_bias_shift=None)
    errors = [forecast - actual for forecast, actual, _, _ in rows]
    covered = [lower <= actual <= upper for _, actual, lower, upper in rows
               if lower is not None and upper is not None]
    shift = None
    if len(errors) >= 10:
        midpoint = len(errors) // 2
        shift = sum(errors[midpoint:]) / len(errors[midpoint:]) - sum(errors[:midpoint]) / midpoint
    return MetricHealth(
        sample_count=len(rows), mae=round(sum(abs(error) for error in errors) / len(errors), 3),
        rmse=round(sqrt(sum(error * error for error in errors) / len(errors)), 3),
        bias=round(sum(errors) / len(errors), 3),
        interval_coverage=round(sum(covered) / len(covered), 3) if covered else None,
        drift_bias_shift=round(shift, 3) if shift is not None else None,
    )


def get_model_health(db: Session, greenhouse_id: int) -> ModelHealth:
    if db.get(Greenhouse, greenhouse_id) is None:
        raise ServiceError(404, "大棚不存在")
    now = datetime.now(UTC).replace(tzinfo=None)
    audits = list(db.scalars(select(ForecastAudit).where(
        ForecastAudit.greenhouse_id == greenhouse_id,
        ForecastAudit.target_at <= now,
        ForecastAudit.target_at >= now - timedelta(days=60),
    ).order_by(ForecastAudit.target_at.desc()).limit(500)))
    temperature = []
    humidity = []
    for audit in reversed(audits):
        nearby = list(db.scalars(select(SensorData).where(
            SensorData.greenhouse_id == greenhouse_id,
            SensorData.recorded_at >= audit.target_at - timedelta(minutes=10),
            SensorData.recorded_at <= audit.target_at + timedelta(minutes=10),
            SensorData.quality_flag == "valid",
            SensorData.source.in_(VALID_BUSINESS_SOURCES),
        )))
        if not nearby:
            continue
        actual = min(nearby, key=lambda item: abs((_naive(item.recorded_at) - _naive(audit.target_at)).total_seconds()))
        if audit.predicted_temperature is not None and actual.temperature is not None:
            temperature.append((audit.predicted_temperature, actual.temperature,
                                audit.temperature_lower, audit.temperature_upper))
        if audit.predicted_humidity is not None and actual.air_humidity is not None:
            humidity.append((audit.predicted_humidity, actual.air_humidity,
                             audit.humidity_lower, audit.humidity_upper))
    t_metric = _metric(temperature)
    h_metric = _metric(humidity)
    count = min(t_metric.sample_count, h_metric.sample_count)
    drift = (t_metric.drift_bias_shift is not None and abs(t_metric.drift_bias_shift) > 2.0) or (
        h_metric.drift_bias_shift is not None and abs(h_metric.drift_bias_shift) > 8.0)
    status = "no_verified_samples" if count == 0 else "limited" if count < 20 else "drift_attention" if drift else "monitoring"
    return ModelHealth(
        greenhouse_id=greenhouse_id, status=status,
        model_version=audits[0].model_version if audits else None,
        temperature=t_metric, humidity=h_metric,
        updated_at=audits[0].target_at if audits else None,
        explanation="按最近 60 天已到期预测与目标时刻前后 10 分钟的有效实测计算；样本少时指标仅供参考。",
    )
