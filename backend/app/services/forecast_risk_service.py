from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.algorithms.crop_rule_registry import get_operational_rule
from app.algorithms.warning_rules import assess_forecast_point
from app.models import SensorData
from app.schemas.prediction import EnvironmentPredictionData
from app.services.prediction_service import predict_environment
from app.services.sensor_service import VALID_BUSINESS_SOURCES


def _naive_utc(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


def inspect_data_quality(db: Session, greenhouse_id: int, *, as_of: datetime | None, growth_stage: str | None,crop_type:str) -> tuple[list[str], SensorData | None, list[SensorData]]:
    query=select(SensorData).where(SensorData.greenhouse_id==greenhouse_id, SensorData.source.in_(VALID_BUSINESS_SOURCES))
    if as_of is not None:query=query.where(SensorData.recorded_at<=_naive_utc(as_of))
    latest=db.scalar(query.order_by(SensorData.recorded_at.desc()).limit(1));issues=[]
    if latest is None:return ["没有环境监测记录"],None,[]
    records=list(db.scalars(select(SensorData).where(SensorData.greenhouse_id==greenhouse_id,SensorData.source.in_(VALID_BUSINESS_SOURCES),SensorData.recorded_at>=latest.recorded_at-timedelta(hours=23),SensorData.recorded_at<=latest.recorded_at).order_by(SensorData.recorded_at.asc())))
    if len(records)<24:issues.append(f"最近24小时仅有{len(records)}条记录")
    if len(records)>=2 and any((after.recorded_at-before.recorded_at)!=timedelta(hours=1) for before,after in zip(records,records[1:])):issues.append("最近24小时时间序列不连续")
    reference=_naive_utc(as_of) if as_of else datetime.now(UTC).replace(tzinfo=None)
    if reference-latest.recorded_at>timedelta(hours=4):issues.append("最新环境数据距离评估时刻超过4小时")
    if latest.quality_flag=="missing":issues.append("最新记录质量标记为missing")
    if latest.quality_flag=="suspect":issues.append("最新记录质量标记为suspect")
    missing=[name for name,value in {"temperature":latest.temperature,"air_humidity":latest.air_humidity}.items() if value is None]
    if missing:issues.append(f"预测必要字段缺失：{','.join(missing)}")
    if growth_stage is None:issues.append("没有活跃种植批次")
    elif get_operational_rule(crop_type) is None:issues.append("当前作物规则不可用")
    return issues,latest,records


def evaluate_future_risks(db: Session,greenhouse_id:int,growth_stage:str|None,*,crop_type:str="tomato",as_of:datetime|None=None)->tuple[EnvironmentPredictionData,list[dict[str,Any]]]:
    prediction=predict_environment(db,greenhouse_id,6,as_of=as_of)
    if prediction.status!="ready":return prediction,[]
    risks=[assess_forecast_point(point.model_dump(),growth_stage,data_source=prediction.input_data_source,calibration_status=prediction.calibration_status,crop_type=crop_type) for point in prediction.predictions]
    return prediction,risks
