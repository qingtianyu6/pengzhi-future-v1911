from datetime import UTC, datetime, timedelta
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (AIConversation, AIMessage, AIToolCall, ActionCandidate,
                        Intervention, OutcomeObservation, CropBatch,
                        DecisionRecommendation, DiseaseRecognitionRecord, FarmTask,
                        Greenhouse, SensorData, TaskEvent, TaskFeedback, WarningEvent,
                        RiskEvent, DecisionPlan, TreatmentEvaluation, SimulationRecord, GreenhouseProfile, ForecastAudit)
from app.schemas.common import PaginatedData
from app.schemas.greenhouse import GreenhouseCreate, GreenhouseData, GreenhouseUpdate
from app.services.crop_batch_service import get_active_batch, to_batch_data
from app.services.errors import ServiceError



def _to_greenhouse_data(db: Session, greenhouse: Greenhouse) -> GreenhouseData:
    active = get_active_batch(db, greenhouse.id)
    latest = db.scalar(select(SensorData).where(SensorData.greenhouse_id == greenhouse.id).order_by(SensorData.recorded_at.desc()).limit(1))
    device_count = db.scalar(select(func.count(func.distinct(SensorData.device_id))).where(SensorData.greenhouse_id == greenhouse.id, SensorData.source == "sensor", SensorData.device_id.is_not(None))) or 0
    timestamp = latest.recorded_at.replace(tzinfo=UTC) if latest and latest.recorded_at.tzinfo is None else latest.recorded_at if latest else None
    state = "no_data" if not latest else "historical" if datetime.now(UTC)-timestamp > timedelta(hours=2) else "suspect" if latest.quality_flag != "valid" else "current"
    return GreenhouseData(
        last_recorded_at=timestamp, data_status=state, device_count=device_count,
        id=greenhouse.id,
        code=greenhouse.code,
        name=greenhouse.name,
        location=greenhouse.location,
        area_mu=greenhouse.area_mu,
        status=greenhouse.status,
        manager_name=greenhouse.manager_name,
        created_at=greenhouse.created_at,
        updated_at=greenhouse.updated_at,
        active_batch=to_batch_data(active) if active else None,
    )


def list_greenhouses(
    db: Session, page: int, page_size: int, status: str | None, keyword: str | None
) -> PaginatedData[GreenhouseData]:
    filters = []
    if status:
        filters.append(Greenhouse.status == status)
    if keyword:
        term = f"%{keyword.strip()}%"
        filters.append(
            or_(Greenhouse.code.ilike(term), Greenhouse.name.ilike(term), Greenhouse.location.ilike(term))
        )
    total = db.scalar(select(func.count()).select_from(Greenhouse).where(*filters)) or 0
    records = list(
        db.scalars(
            select(Greenhouse)
            .where(*filters)
            .order_by(Greenhouse.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    items = [_to_greenhouse_data(db, item) for item in records]
    db.commit()
    return PaginatedData(items=items, total=total, page=page, page_size=page_size)


def create_greenhouse(db: Session, payload: GreenhouseCreate) -> GreenhouseData:
    greenhouse = Greenhouse(**payload.model_dump())
    db.add(greenhouse)
    try:
        db.commit()
    except IntegrityError as exception:
        db.rollback()
        raise ServiceError(409, "大棚编号已存在") from exception
    db.refresh(greenhouse)
    return _to_greenhouse_data(db, greenhouse)


def get_greenhouse(db: Session, greenhouse_id: int) -> GreenhouseData:
    greenhouse = db.get(Greenhouse, greenhouse_id)
    if greenhouse is None:
        raise ServiceError(404, "大棚不存在")
    data = _to_greenhouse_data(db, greenhouse)
    db.commit()
    return data


def update_greenhouse(
    db: Session, greenhouse_id: int, payload: GreenhouseUpdate
) -> GreenhouseData:
    greenhouse = db.get(Greenhouse, greenhouse_id)
    if greenhouse is None:
        raise ServiceError(404, "大棚不存在")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(greenhouse, field, value)
    try:
        db.commit()
    except IntegrityError as exception:
        db.rollback()
        raise ServiceError(409, "大棚编号已存在") from exception
    db.refresh(greenhouse)
    return _to_greenhouse_data(db, greenhouse)


def delete_greenhouse(db: Session, greenhouse_id: int) -> None:
    greenhouse = db.get(Greenhouse, greenhouse_id)
    if greenhouse is None:
        raise ServiceError(404, "大棚不存在")
    try:
        from app.models import AgentRun, AgentApproval, AgentRecheck, AgentStep, AgentToolCall
        from sqlalchemy import or_
        run_ids = list(db.scalars(select(AgentRun.id).where(or_(
            AgentRun.greenhouse_id == greenhouse_id,
            AgentRun.id.in_(select(AgentRecheck.run_id).where(AgentRecheck.greenhouse_id == greenhouse_id))))))
        if db.scalar(select(AgentRun.id).where(AgentRun.id.in_(run_ids),
                AgentRun.status.not_in(["COMPLETED", "FAILED", "CANCELLED"])).limit(1)):
            raise ServiceError(409, "请先取消该棚的活动Agent运行")
        for model in (AgentApproval, AgentRecheck, AgentStep, AgentToolCall):
            db.execute(delete(model).where(model.run_id.in_(run_ids)))
        db.execute(delete(AgentRun).where(AgentRun.id.in_(run_ids)))
        conversation_ids = select(AIConversation.id).where(
            AIConversation.greenhouse_id == greenhouse_id
        )
        message_ids = select(AIMessage.id).where(
            AIMessage.conversation_id.in_(conversation_ids)
        )
        db.execute(delete(AIToolCall).where(AIToolCall.conversation_id.in_(conversation_ids)))
        db.execute(delete(AIMessage).where(AIMessage.id.in_(message_ids)))
        db.execute(delete(AIConversation).where(AIConversation.id.in_(conversation_ids)))
        task_ids = select(FarmTask.id).where(FarmTask.greenhouse_id == greenhouse_id)
        intervention_ids = select(Intervention.id).where(Intervention.greenhouse_id == greenhouse_id)
        db.execute(delete(OutcomeObservation).where(OutcomeObservation.intervention_id.in_(intervention_ids)))
        db.execute(delete(Intervention).where(Intervention.greenhouse_id == greenhouse_id))
        db.execute(delete(ActionCandidate).where(ActionCandidate.greenhouse_id == greenhouse_id))
        db.execute(delete(TaskFeedback).where(TaskFeedback.task_id.in_(task_ids)))
        db.execute(delete(TaskEvent).where(TaskEvent.task_id.in_(task_ids)))
        for model in (SimulationRecord, TreatmentEvaluation, DecisionPlan, RiskEvent, GreenhouseProfile, ForecastAudit):
            db.execute(delete(model).where(model.greenhouse_id == greenhouse_id))
        db.execute(delete(FarmTask).where(FarmTask.greenhouse_id == greenhouse_id))
        db.execute(delete(DecisionRecommendation).where(DecisionRecommendation.greenhouse_id == greenhouse_id))
        db.execute(delete(DiseaseRecognitionRecord).where(DiseaseRecognitionRecord.greenhouse_id == greenhouse_id))
        db.execute(delete(WarningEvent).where(WarningEvent.greenhouse_id == greenhouse_id))
        db.execute(delete(SensorData).where(SensorData.greenhouse_id == greenhouse_id))
        db.execute(delete(CropBatch).where(CropBatch.greenhouse_id == greenhouse_id))
        db.delete(greenhouse)
        db.commit()
    except Exception:
        db.rollback()
        raise
