from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.inference.predictor_v02 import (
    PredictionInputError,
    get_environment_predictor_v02,
    shanghai_naive_to_utc,
)
from app.models import CropBatch, Greenhouse, SensorData
from app.schemas.prediction import EnvironmentPredictionData, HistoryPoint, PredictionPoint
from app.services.errors import ServiceError
from app.services.sensor_service import VALID_BUSINESS_SOURCES


def predict_environment(db: Session, greenhouse_id: int, horizon_hours: int, as_of: datetime | None = None) -> EnvironmentPredictionData:
    greenhouse = db.get(Greenhouse, greenhouse_id)
    if greenhouse is None: raise ServiceError(404, "大棚不存在")
    predictor = get_environment_predictor_v02()
    batch = db.scalar(select(CropBatch).where(CropBatch.greenhouse_id == greenhouse_id, CropBatch.status == "growing"))
    crop = batch.variety if batch else None
    crop_type=batch.crop_type if batch else "unknown"
    base = EnvironmentPredictionData(
        status=predictor.status, forecast_service_status=predictor.status, model_status=predictor.metadata.get("model_status", "not_trained"), effective_model_status="hybrid_ready" if predictor.status=="ready" else ("under_evaluation" if predictor.status=="under_evaluation" else "not_trained"), ml_candidate_status=predictor.metadata.get("ml_candidate_status", "under_evaluation"), greenhouse_id=greenhouse_id, crop=crop,crop_type=crop_type,crop_match_status="matched_public_tomato" if crop_type=="tomato" else "mismatched",
        model_name=predictor.metadata.get("model_name"), model_type="per_target_champion_registry", model_version=predictor.metadata.get("model_version"),
        training_domain=predictor.metadata.get("training_domain", "public_real_greenhouse_tomato"),
        validation_status=("validated_on_public_dataset" if predictor.status == "ready"
                           else "under_evaluation" if predictor.status == "under_evaluation"
                           else "not_validated"),
        history_hours=24, horizon_hours=horizon_hours, rules_status="tomato_rule_active" if crop_type=="tomato" else "rules_unavailable", generated_at=datetime.now(UTC),
    )
    if crop_type!="tomato":
        base.cross_crop_warning = True
        base.warnings.append("当前批次并非番茄；公共番茄模型存在跨作物风险。")
    else:base.warnings.append("预测结果仅供管理人员参考，请结合现场情况确认。")
    if predictor.status in {"not_trained", "under_evaluation", "schema_mismatch"}:
        base.warnings.append("V0.2预测方法不可用。")
        return base
    latest_query = select(SensorData.recorded_at).where(SensorData.greenhouse_id == greenhouse_id, SensorData.source.in_(VALID_BUSINESS_SOURCES))
    if as_of is not None:
        cutoff = as_of.astimezone(UTC).replace(tzinfo=None) if as_of.tzinfo else as_of
        latest_query = latest_query.where(SensorData.recorded_at <= cutoff)
    latest = db.scalar(latest_query.order_by(SensorData.recorded_at.desc()).limit(1))
    if latest is None:
        base.status="insufficient_data"
        base.warnings.append("最近数据不足，需要至少连续24小时环境数据。")
        return base
    records = list(db.scalars(select(SensorData).where(SensorData.greenhouse_id == greenhouse_id, SensorData.source.in_(VALID_BUSINESS_SOURCES), SensorData.recorded_at >= latest - timedelta(hours=48)).order_by(SensorData.recorded_at.asc())))
    payload=[{"recorded_at":r.recorded_at,"temperature":r.temperature,"air_humidity":r.air_humidity,"source":r.source} for r in records]
    try: result=predictor.predict(payload,horizon_hours)
    except PredictionInputError as exception:
        base.status=exception.status; base.warnings.append(str(exception)); return base
    result_source = result["source"]
    if result_source not in {*VALID_BUSINESS_SOURCES, "mixed"}:
        base.status = "insufficient_data"
        base.warnings.append("预测输入来源无效。")
        return base
    base.status=base.forecast_service_status="ready"; base.forecast_method=result["forecast_method"];base.forecast_method_labels=result["forecast_method_labels"]; base.input_data_source=result_source; base.input_end_time=result["input_end_time"]
    base.predictions=[PredictionPoint(**point) for point in result["predictions"]]
    base.ml_output_count=sum(method != "seasonal_24" for point in base.predictions for method in point.methods.values())
    base.total_output_count=len(base.predictions)*2
    base.history=[HistoryPoint(timestamp=shanghai_naive_to_utc(row.timestamp),temperature_c=float(row.air_temperature_c),air_humidity_pct=float(row.air_humidity_pct)) for row in result["history"].itertuples()]
    return base
