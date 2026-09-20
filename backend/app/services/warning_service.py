from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.algorithms.crop_rule_registry import get_operational_rule, get_rule_profile, thresholds_for
from app.algorithms.warning_rules import WarningCandidate, build_forecast_warning_candidates, clamp_score, metric_risk, risk_level
from app.models import CropBatch, DecisionRecommendation, Greenhouse, SensorData, WarningEvent
from app.schemas.warning import WarningDetailData, WarningEvaluationData, WarningEventData, WarningListData, WarningSummaryData
from app.services.crop_batch_service import get_active_batch
from app.services.decision_service import ensure_recommendation, to_recommendation_data
from app.services.errors import ServiceError
from app.services.forecast_risk_service import evaluate_future_risks, inspect_data_quality
from app.services.risk_service import assess_current_risk
from app.services.sensor_service import VALID_BUSINESS_SOURCES, to_sensor_view


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _fingerprint(greenhouse_id:int,batch_id:int|None,crop_type:str,candidate:WarningCandidate,rule_version:str,latest_at:datetime|None)->str:
    bucket=candidate["forecast_start_at"] or latest_at
    token=bucket.replace(minute=0,second=0,microsecond=0).isoformat() if bucket else "no-data"
    raw=f"{greenhouse_id}|{batch_id}|{crop_type}|{candidate['warning_code']}|{candidate['warning_type']}|{token}|{rule_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _current_candidates(latest:SensorData|None,growth_stage:str|None,crop_type:str,current_risk:dict[str,Any])->list[WarningCandidate]:
    if latest is None or growth_stage is None or get_operational_rule(crop_type) is None:return []
    timestamp=_as_utc(latest.recorded_at);local_hour=timestamp.astimezone(timezone(timedelta(hours=8))).hour if timestamp else 12;thresholds=thresholds_for(crop_type,growth_stage,local_hour)
    if thresholds is None:return []
    candidates=[]
    specs=[("temperature",latest.temperature,"温度","current"),("air_humidity",latest.air_humidity,"空气湿度","current")]
    active=[]
    for metric,value,label,prefix in specs:
        if value is None:continue
        low,high=thresholds[metric]  # type: ignore[literal-required]
        direction="low" if value<low else "high" if value>high else None
        if direction is None:continue
        score=max(30.0,metric_risk(float(value),(low,high),10.0 if metric=="temperature" else 25.0));warning_type=f"{direction}_{metric}";active.append(warning_type)
        candidates.append({"warning_code":f"{prefix}_{warning_type}","warning_type":warning_type,"risk_score":score,"severity":risk_level(score),"certainty":"expected","title":f"当前{label}{'偏低' if direction=='low' else '偏高'}预警","description":f"当前{label} {value:g}，适宜范围 {low:g}～{high:g}","forecast_start_at":_as_utc(latest.recorded_at),"forecast_end_at":_as_utc(latest.recorded_at),"evidence":{"current_environment":jsonable_encoder(to_sensor_view(latest)),"threshold":{metric:[low,high]},"trigger_reasons":[f"当前{label}越过生育期适宜范围"],"current_risk":current_risk}})
    if "high_temperature" in active and "high_air_humidity" in active:
        score=clamp_score(max(item["risk_score"] for item in candidates)+20)
        candidates.append({"warning_code":"current_temperature_humidity_combination","warning_type":"temperature_humidity_combination","risk_score":score,"severity":risk_level(score),"certainty":"expected","title":"当前温湿度组合预警","description":"当前高温与高湿同时出现","forecast_start_at":_as_utc(latest.recorded_at),"forecast_end_at":_as_utc(latest.recorded_at),"evidence":{"current_environment":jsonable_encoder(to_sensor_view(latest)),"trigger_reasons":["当前高温与高湿同时出现"],"current_risk":current_risk}})
    if current_risk.get("overall_score") is not None and float(current_risk["overall_score"])>=30 and not candidates:
        score=float(current_risk["overall_score"]);candidates.append({"warning_code":"current_environment_rule_risk","warning_type":"current_environment","risk_score":score,"severity":risk_level(score),"certainty":"expected","title":"当前环境规则风险","description":"；".join(current_risk.get("reasons",[])),"forecast_start_at":_as_utc(latest.recorded_at),"forecast_end_at":_as_utc(latest.recorded_at),"evidence":{"current_environment":jsonable_encoder(to_sensor_view(latest)),"trigger_reasons":current_risk.get("reasons",[]),"current_risk":current_risk}})
    return candidates


def _quality_candidate(issues:list[str],latest:SensorData|None)->WarningCandidate|None:
    if latest is None:
        return None
    ignored_prefixes = ("未来预测暂不可用", "没有活跃种植批次", "当前作物规则不可用")
    actionable=[issue for issue in issues if not issue.startswith(ignored_prefixes)]
    if not actionable:return None
    critical=any("缺失" in item or "没有环境" in item or "不连续" in item for item in actionable);score=65.0 if critical else 40.0
    return {"warning_code":"data_quality","warning_type":"data_quality","risk_score":score,"severity":risk_level(score),"certainty":"insufficient","title":"环境数据质量预警","description":"；".join(actionable),"forecast_start_at":_as_utc(latest.recorded_at) if latest else None,"forecast_end_at":_as_utc(latest.recorded_at) if latest else None,"evidence":{"trigger_reasons":actionable,"quality_flag":latest.quality_flag if latest else None}}


def _upsert(db:Session,greenhouse_id:int,batch_id:int|None,crop_type:str,crop_rule_version:str,crop_match_status:str,expert_calibration_required:bool,candidate:WarningCandidate,*,latest_at:datetime|None,forecast_version:str|None,methods:dict[str,Any],data_source:str|None)->tuple[WarningEvent,str]:
    fingerprint=_fingerprint(greenhouse_id,batch_id,crop_type,candidate,crop_rule_version,latest_at);now=datetime.now(UTC);existing=db.scalar(select(WarningEvent).where(WarningEvent.fingerprint==fingerprint))
    evidence=jsonable_encoder(candidate["evidence"])
    if existing is None:
        record=WarningEvent(greenhouse_id=greenhouse_id,crop_batch_id=batch_id,crop_type=crop_type,crop_rule_version=crop_rule_version,crop_match_status=crop_match_status,cross_region_warning=True,expert_calibration_required=expert_calibration_required,warning_code=candidate["warning_code"],warning_type=candidate["warning_type"],severity=candidate["severity"],risk_score=candidate["risk_score"],certainty=candidate["certainty"],title=candidate["title"],description=candidate["description"],evidence_json={**evidence,"updates":[]},forecast_start_at=candidate["forecast_start_at"],forecast_end_at=candidate["forecast_end_at"],status="open",fingerprint=fingerprint,rule_version=crop_rule_version,forecast_service_version=forecast_version,forecast_methods_json=jsonable_encoder(methods),data_source=data_source,calibration_status="legacy_not_applicable",first_triggered_at=now,last_triggered_at=now)
        db.add(record);db.flush();return record,"created"
    if existing.status in {"resolved","dismissed"}:return existing,"skipped"
    history=list(existing.evidence_json.get("updates",[]));history.append({"at":now.isoformat(),"previous_score":existing.risk_score,"new_score":candidate["risk_score"],"previous_severity":existing.severity,"new_severity":candidate["severity"]})
    existing.risk_score=candidate["risk_score"];existing.severity=candidate["severity"];existing.certainty=candidate["certainty"];existing.description=candidate["description"];existing.evidence_json={**evidence,"updates":history};existing.forecast_end_at=candidate["forecast_end_at"];existing.last_triggered_at=now;existing.forecast_methods_json=jsonable_encoder(methods)
    return existing,"updated"


def evaluate_greenhouse(db:Session,greenhouse_id:int,*,as_of:datetime|None=None)->WarningEvaluationData:
    greenhouse=db.get(Greenhouse,greenhouse_id)
    if greenhouse is None:raise ServiceError(404,"大棚不存在")
    batch=get_active_batch(db,greenhouse_id);stage=batch.growth_stage if batch else None
    crop_type=batch.crop_type if batch else "unknown";profile=get_rule_profile(crop_type);crop_rule_version=profile.rule_version if profile else "rules_unavailable";crop_match_status="matched_public_tomato" if crop_type=="tomato" else "mismatched"
    issues,latest,_=inspect_data_quality(db,greenhouse_id,as_of=as_of,growth_stage=stage,crop_type=crop_type)
    current=assess_current_risk(to_sensor_view(latest) if latest else None,stage,crop_type).model_dump()
    prediction,future=evaluate_future_risks(db,greenhouse_id,stage,crop_type=crop_type,as_of=as_of)
    if prediction.status!="ready":issues.append(f"未来预测暂不可用：{prediction.status}")
    candidates=_current_candidates(latest,stage,crop_type,current)+build_forecast_warning_candidates(future)
    quality=_quality_candidate(issues,latest)
    if quality:candidates.append(quality)
    methods={f"h{point.horizon}":point.methods for point in prediction.predictions};records=[];recommendations=[];counts={"created":0,"updated":0,"skipped":0}
    for candidate in candidates:
        record,result=_upsert(db,greenhouse_id,batch.id if batch else None,crop_type,crop_rule_version,crop_match_status,profile.expert_calibration_required if profile else True,candidate,latest_at=latest.recorded_at if latest else None,forecast_version=prediction.model_version,methods=methods,data_source=latest.source if latest else None);counts[result]+=1;records.append(record)
        if result!="skipped":recommendation,_=ensure_recommendation(db,record);recommendations.append(recommendation)
    db.commit()
    for record in records:db.refresh(record)
    for item in recommendations:db.refresh(item)
    return WarningEvaluationData(greenhouse_id=greenhouse_id,crop_batch_id=batch.id if batch else None,crop_type=crop_type,crop_rule_version=crop_rule_version,crop_match_status=crop_match_status,cross_region_warning=True,expert_calibration_required=profile.expert_calibration_required if profile else True,growth_stage=stage,current_risk=jsonable_encoder(current),future_risks=future,forecast_status=prediction.status,data_quality_issues=issues,created_count=counts["created"],updated_count=counts["updated"],skipped_count=counts["skipped"],warnings=[WarningEventData.model_validate(item) for item in records],recommendations=[to_recommendation_data(item) for item in recommendations],data_source=latest.source if latest else None,cross_crop_warning=prediction.cross_crop_warning,evaluated_at=datetime.now(UTC))


def list_warnings(db:Session,*,greenhouse_id:int|None,severity:str|None,status:str|None,warning_type:str|None,start_time:datetime|None,end_time:datetime|None,page:int,page_size:int)->WarningListData:
    filters=[WarningEvent.data_source.in_(VALID_BUSINESS_SOURCES)]
    if greenhouse_id is not None:filters.append(WarningEvent.greenhouse_id==greenhouse_id)
    if severity is not None:filters.append(WarningEvent.severity==severity)
    if status is not None:filters.append(WarningEvent.status==status)
    if warning_type is not None:filters.append(WarningEvent.warning_type==warning_type)
    if start_time is not None:filters.append(WarningEvent.last_triggered_at>=start_time)
    if end_time is not None:filters.append(WarningEvent.last_triggered_at<=end_time)
    total=db.scalar(select(func.count()).select_from(WarningEvent).where(*filters)) or 0
    severity_order=case((WarningEvent.severity=="critical",4),(WarningEvent.severity=="warning",3),(WarningEvent.severity=="attention",2),else_=1)
    items=list(db.scalars(select(WarningEvent).where(*filters).order_by(severity_order.desc(),WarningEvent.last_triggered_at.desc()).offset((page-1)*page_size).limit(page_size)))
    return WarningListData(items=[WarningEventData.model_validate(item) for item in items],total=total,page=page,page_size=page_size)


def get_warning_detail(db:Session,warning_id:int)->WarningDetailData:
    record=db.scalar(select(WarningEvent).where(WarningEvent.id==warning_id,WarningEvent.data_source.in_(VALID_BUSINESS_SOURCES)).options(selectinload(WarningEvent.recommendations),selectinload(WarningEvent.greenhouse),selectinload(WarningEvent.crop_batch)))
    if record is None:raise ServiceError(404,"预警不存在")
    base=WarningEventData.model_validate(record).model_dump();return WarningDetailData(**base,greenhouse_name=record.greenhouse.name,batch_code=record.crop_batch.batch_code if record.crop_batch else None,growth_stage=record.crop_batch.growth_stage if record.crop_batch else None,recommendations=[to_recommendation_data(item) for item in record.recommendations])


def change_warning_status(db:Session,warning_id:int,target:str,operator:str,note:str)->WarningEventData:
    record=db.scalar(select(WarningEvent).where(WarningEvent.id==warning_id,WarningEvent.data_source.in_(VALID_BUSINESS_SOURCES)))
    if record is None:raise ServiceError(404,"预警不存在")
    now=datetime.now(UTC)
    if target=="acknowledged":
        if record.status!="open":raise ServiceError(409,"只有待处理预警可以确认")
        record.status=target;record.acknowledged_at=now;record.acknowledged_by=operator;record.acknowledgement_note=note
    elif target=="resolved":
        if record.status not in {"open","acknowledged"}:raise ServiceError(409,"当前预警不可解除")
        record.status=target;record.resolved_at=now;record.resolved_by=operator;record.resolution_note=note
    elif target=="dismissed":
        if record.status not in {"open","acknowledged"}:raise ServiceError(409,"当前预警不可忽略")
        record.status=target;record.dismissed_at=now;record.dismissed_reason=f"{operator}：{note}"
    else:raise ValueError(target)
    db.commit();db.refresh(record);return WarningEventData.model_validate(record)


def warning_summary(db:Session)->WarningSummaryData:
    active=["open","acknowledged"]
    def count(*conditions:Any)->int:return int(db.scalar(select(func.count()).select_from(WarningEvent).where(*conditions)) or 0)
    source_filter = WarningEvent.data_source.in_(VALID_BUSINESS_SOURCES)
    latest=db.scalar(select(WarningEvent).where(source_filter).order_by(WarningEvent.last_triggered_at.desc()).limit(1));today=datetime.now(UTC).replace(hour=0,minute=0,second=0,microsecond=0)
    distribution=dict(db.execute(select(Greenhouse.name,func.count(WarningEvent.id)).join(WarningEvent).where(source_filter,WarningEvent.status.in_(active)).group_by(Greenhouse.name)).all())
    return WarningSummaryData(open_total=count(source_filter,WarningEvent.status=="open"),attention_total=count(source_filter,WarningEvent.status.in_(active),WarningEvent.severity=="attention"),warning_total=count(source_filter,WarningEvent.status.in_(active),WarningEvent.severity=="warning"),critical_total=count(source_filter,WarningEvent.status.in_(active),WarningEvent.severity=="critical"),acknowledged_total=count(source_filter,WarningEvent.status=="acknowledged"),resolved_today=count(source_filter,WarningEvent.status=="resolved",WarningEvent.resolved_at>=today),latest_warning=WarningEventData.model_validate(latest) if latest else None,greenhouse_distribution=distribution)
