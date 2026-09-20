from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import DecisionRecommendation, FarmTask, Greenhouse, SensorData, WarningEvent
from app.schemas.dashboard import (DashboardSummary, DashboardTaskSummary,
                                   DashboardWarningSummary, MetricChanges)
from app.schemas.task import FarmTaskData
from app.schemas.greenhouse import GreenhouseData
from app.services.crop_batch_service import get_active_batch, to_batch_data
from app.services.errors import ServiceError
from app.services.risk_service import assess_current_risk
from app.services.sensor_service import VALID_BUSINESS_SOURCES, to_sensor_view
from app.services.task_service import task_summary


SOURCE_LABELS = {
    "sensor": "传感器数据",
    "import": "导入数据",
}


def _difference(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    return round(current - previous, 2)


def get_dashboard_summary(db: Session, greenhouse_id: int) -> DashboardSummary:
    greenhouse = db.get(Greenhouse, greenhouse_id)
    if greenhouse is None:
        raise ServiceError(404, "大棚不存在")
    active = get_active_batch(db, greenhouse_id)
    greenhouse_data = GreenhouseData.model_validate(greenhouse)
    greenhouse_data.active_batch = to_batch_data(active) if active else None

    latest_records = list(
        db.scalars(
            select(SensorData)
            .where(SensorData.greenhouse_id == greenhouse_id, SensorData.source.in_(VALID_BUSINESS_SOURCES))
            .order_by(SensorData.recorded_at.desc())
            .limit(2)
        )
    )
    latest = latest_records[0] if latest_records else None
    previous = latest_records[1] if len(latest_records) > 1 else None
    latest_view = to_sensor_view(latest) if latest else None
    changes = None
    if latest and previous:
        changes = MetricChanges(
            temperature=_difference(latest.temperature, previous.temperature),
            air_humidity=_difference(latest.air_humidity, previous.air_humidity),
            soil_moisture=_difference(latest.soil_moisture, previous.soil_moisture),
            light_intensity=_difference(latest.light_intensity, previous.light_intensity),
            co2_concentration=_difference(latest.co2_concentration, previous.co2_concentration),
        )

    now_utc = datetime.now(UTC)
    trend_start = now_utc.replace(tzinfo=None) - timedelta(hours=24)
    trend = list(
        db.scalars(
            select(SensorData)
            .where(
                SensorData.greenhouse_id == greenhouse_id,
                SensorData.source.in_(VALID_BUSINESS_SOURCES),
                SensorData.recorded_at >= trend_start,
            )
            .order_by(SensorData.recorded_at.asc())
        )
    )
    shanghai = timezone(timedelta(hours=8), name="Asia/Shanghai")
    local_start = now_utc.astimezone(shanghai).replace(hour=0, minute=0, second=0, microsecond=0)
    utc_start = local_start.astimezone(UTC).replace(tzinfo=None)
    abnormal_count = db.scalar(
        select(func.count()).select_from(SensorData).where(
            SensorData.greenhouse_id == greenhouse_id,
            SensorData.source.in_(VALID_BUSINESS_SOURCES),
            SensorData.recorded_at >= utc_start,
            or_(
                SensorData.quality_flag != "valid",
                SensorData.temperature > 40,
                SensorData.air_humidity > 90,
                SensorData.soil_moisture < 35,
            ),
        )
    ) or 0
    risk = assess_current_risk(latest_view, active.growth_stage if active else None,active.crop_type if active else "unknown")
    active_warnings = list(db.scalars(
        select(WarningEvent).where(
            WarningEvent.greenhouse_id == greenhouse_id,
            WarningEvent.data_source.in_(VALID_BUSINESS_SOURCES),
            WarningEvent.status.in_(["open", "acknowledged"]),
        ).order_by(WarningEvent.last_triggered_at.desc())
    ))
    severity_rank = {"normal": 0, "attention": 1, "warning": 2, "critical": 3}
    highest = max((item.severity for item in active_warnings), key=lambda value: severity_rank.get(value, 0), default="normal")
    latest_warning = active_warnings[0] if active_warnings else None
    latest_recommendation = db.scalar(
        select(DecisionRecommendation).join(WarningEvent).where(
            DecisionRecommendation.greenhouse_id == greenhouse_id,
            WarningEvent.data_source.in_(VALID_BUSINESS_SOURCES),
        ).order_by(DecisionRecommendation.generated_at.desc()).limit(1)
    )
    tasks = list(db.scalars(select(FarmTask).where(FarmTask.greenhouse_id == greenhouse_id)
                           .order_by(FarmTask.updated_at.desc(), FarmTask.id.desc()).limit(5)))
    source_distribution = dict(db.execute(
        select(FarmTask.source_type, func.count(FarmTask.id))
        .where(FarmTask.greenhouse_id == greenhouse_id)
        .group_by(FarmTask.source_type)
    ).all())
    task_counts = task_summary(db, greenhouse_id)
    future_timeline = latest_warning.evidence_json.get("forecast_risks", []) if latest_warning else []
    db.commit()
    return DashboardSummary(
        greenhouse=greenhouse_data,
        active_batch=to_batch_data(active) if active else None,
        latest_environment=latest_view,
        changes=changes,
        risk=risk,
        today_abnormal_count=abnormal_count,
        trend_24h=[to_sensor_view(record) for record in trend],
        data_source=latest.source if latest else None,
        data_source_label=SOURCE_LABELS.get(latest.source) if latest else None,
        data_updated_at=latest_view.recorded_at if latest_view else None,
        empty_state=latest is None,
        warning_summary=DashboardWarningSummary(highest_risk_level=highest,open_warning_count=len(active_warnings),latest_warning_id=latest_warning.id if latest_warning else None,latest_warning_title=latest_warning.title if latest_warning else None,future_risk_timeline=future_timeline,latest_recommendation_id=latest_recommendation.id if latest_recommendation else None,latest_recommendation_title=latest_recommendation.title if latest_recommendation else None),
        task_summary=DashboardTaskSummary(
            **task_counts.model_dump(),
            recent_tasks=[FarmTaskData.model_validate(item) for item in tasks],
            source_distribution=source_distribution,
        ),
    )
