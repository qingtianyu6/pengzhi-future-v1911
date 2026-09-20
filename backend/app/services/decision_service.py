from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.algorithms.decision_templates import recommendation_for_warning
from app.models import CropBatch, DecisionRecommendation, WarningEvent
from app.schemas.decision import CurrentDecisionData, DecisionRecommendationData, TaskDraft
from app.services.errors import ServiceError
from app.services.sensor_service import VALID_BUSINESS_SOURCES


def to_recommendation_data(record: DecisionRecommendation) -> DecisionRecommendationData:
    data = DecisionRecommendationData.model_validate(record)
    data.task_draft = TaskDraft(
        title=record.title, greenhouse_id=record.greenhouse_id, crop_batch_id=record.crop_batch_id,
        crop_type=record.crop_type, crop_rule_version=record.crop_rule_version,
        priority=record.priority, action_type=record.action_type, description="；".join(record.action_steps_json),
        suggested_execute_before=record.execute_before, source_warning_id=record.warning_event_id,
        source_recommendation_id=record.id, requires_manual_confirmation=True,
    )
    return data


def ensure_recommendation(db: Session, warning: WarningEvent) -> tuple[DecisionRecommendation, bool]:
    payload = recommendation_for_warning(warning.warning_type, warning.evidence_json)
    existing = db.scalar(select(DecisionRecommendation).where(DecisionRecommendation.warning_event_id == warning.id, DecisionRecommendation.recommendation_code == payload["code"]))
    if existing is not None: return existing, False
    record = DecisionRecommendation(
        warning_event_id=warning.id, greenhouse_id=warning.greenhouse_id, crop_batch_id=warning.crop_batch_id,
        crop_type=warning.crop_type,crop_rule_version=warning.crop_rule_version,
        recommendation_code=payload["code"], priority=payload["priority"], action_type=payload["action_type"],
        title=payload["title"], rationale=payload["rationale"], action_steps_json=payload["steps"],
        execute_before=warning.forecast_start_at, safety_note=payload["safety_note"], status="pending_review",
        rule_version=payload["rule_version"],
    )
    db.add(record); db.flush(); return record, True


def get_recommendation(db: Session, recommendation_id: int) -> DecisionRecommendationData:
    record = db.scalar(select(DecisionRecommendation).join(WarningEvent).where(
        DecisionRecommendation.id == recommendation_id,
        WarningEvent.data_source.in_(VALID_BUSINESS_SOURCES),
    ))
    if record is None: raise ServiceError(404, "建议不存在")
    return to_recommendation_data(record)


def review_recommendation(db: Session, recommendation_id: int, status: str, operator: str, note: str | None) -> DecisionRecommendationData:
    record = db.scalar(select(DecisionRecommendation).join(WarningEvent).where(
        DecisionRecommendation.id == recommendation_id,
        WarningEvent.data_source.in_(VALID_BUSINESS_SOURCES),
    ))
    if record is None: raise ServiceError(404, "建议不存在")
    if record.status not in {"pending_review", "accepted", "rejected"}: raise ServiceError(409, "当前建议状态不可审核")
    record.status=status;record.reviewed_at=datetime.now(UTC);record.review_note=f"{operator}：{note or '未填写备注'}";db.commit();db.refresh(record)
    return to_recommendation_data(record)


def get_current_decisions(db: Session, greenhouse_id: int) -> CurrentDecisionData:
    records=list(db.scalars(select(DecisionRecommendation).join(WarningEvent).where(DecisionRecommendation.greenhouse_id==greenhouse_id,WarningEvent.data_source.in_(VALID_BUSINESS_SOURCES),WarningEvent.status.in_(["open","acknowledged"]),DecisionRecommendation.status.in_(["pending_review","accepted"])).options(selectinload(DecisionRecommendation.warning_event)).order_by(DecisionRecommendation.generated_at.desc())))
    batch=db.scalar(select(CropBatch).where(CropBatch.greenhouse_id==greenhouse_id,CropBatch.status=="growing"))
    timeline=[];source=None;calibration="legacy_not_applicable";current_level=None
    for record in records:
        warning=record.warning_event;source=source or warning.data_source;calibration=warning.calibration_status
        if current_level is None:current_level=warning.severity
        timeline.extend(warning.evidence_json.get("forecast_risks",[]))
    unique={str(item.get("forecast_time")):item for item in timeline}
    crop_type=batch.crop_type if batch else "unknown"
    crop_rule_version=records[0].crop_rule_version if records else ("tomato-rule-v0.1" if crop_type=="tomato" else "rules_unavailable")
    return CurrentDecisionData(greenhouse_id=greenhouse_id,crop_batch_id=batch.id if batch else None,crop_type=crop_type,crop_rule_version=crop_rule_version,crop_match_status="matched_public_tomato" if crop_type=="tomato" else "mismatched",cross_crop_warning=crop_type!="tomato",growth_stage=batch.growth_stage if batch else None,data_source=source,calibration_status=calibration,current_risk_level=current_level,future_risk_timeline=list(unique.values()),recommendations=[to_recommendation_data(item) for item in records])
