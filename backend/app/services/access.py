"""Request scoped authorization for greenhouse business records."""

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy import event, select
from sqlalchemy.orm import Session, with_loader_criteria

from app.database import get_db
from app.models import (AIConversation, ActionCandidate, DecisionPlan, GreenhouseProfile, Intervention, OutcomeObservation,
                        ForecastAudit,
                        CropBatch, DecisionRecommendation,
                        DiseaseRecognitionRecord, FarmTask, Greenhouse, SensorData,
                        RiskEvent, SimulationRecord, TaskEvent, TaskFeedback, TreatmentEvaluation, WarningEvent)
from app.services.auth_service import authenticate
from app.services.errors import ServiceError
from app.models.agronomist import AgronomyRecord, CropObservation
from app.models.greenhouse_device import GreenhouseDevice


@dataclass(frozen=True)
class Principal:
    id: int
    organization_id: int
    role: str
    display_name: str


CURRENT_USER: ContextVar[Principal | None] = ContextVar("current_business_user", default=None)
SCOPED_MODELS = (GreenhouseDevice, AgronomyRecord, CropObservation, ActionCandidate, Intervention, OutcomeObservation, ForecastAudit, CropBatch,
                 DecisionRecommendation, DiseaseRecognitionRecord, FarmTask,
                 SensorData, WarningEvent, GreenhouseProfile, RiskEvent, DecisionPlan,
                 TreatmentEvaluation, SimulationRecord)


def actor() -> Principal:
    user = CURRENT_USER.get()
    if user is None:
        raise ServiceError(401, "请先登录")
    return user


def require_role(*roles: str) -> Principal:
    user = actor()
    if user.role not in roles:
        raise ServiceError(403, "当前角色无权执行此操作")
    return user


async def business_access(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
):
    user, _ = authenticate(db, authorization)
    if user.organization_id is None:
        raise ServiceError(403, "账号尚未分配组织")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        path = request.url.path
        # Personal conversations and read-only agent queries are available to readers.
        # Every business-writing tool still rechecks the actor in agent.guard.
        personal_ai = path.startswith("/api/v1/ai/") or path == "/api/agent/chat" or (
            path.startswith("/api/agent/runs/") and path.endswith("/cancel"))
        personal_content = (path.startswith("/api/community/forum") and "/moderation" not in path) or path.startswith("/api/community/news/preferences") or path.startswith("/api/community/news/bookmarks") or path.startswith("/api/community/news/digests")
        roles = {"admin", "agronomist", "executor", "observer"} if personal_ai or personal_content else (
            {"admin", "agronomist", "executor"} if (
                path.startswith("/api/tasks") or path.startswith("/api/interventions")
            ) else {"admin", "agronomist"})
        if user.role not in roles:
            raise ServiceError(403, "当前角色无权执行此操作")
    token = CURRENT_USER.set(Principal(id=user.id, organization_id=user.organization_id,
                                       role=user.role, display_name=user.display_name))
    try:
        yield
    finally:
        CURRENT_USER.reset(token)


@event.listens_for(Session, "do_orm_execute")
def _scope_reads(state):
    user = CURRENT_USER.get()
    if user is None or not state.is_select:
        return
    org_id = user.organization_id
    user_id = user.id
    state.statement = state.statement.options(
        with_loader_criteria(Greenhouse, lambda cls: cls.organization_id == org_id,
                             include_aliases=True),
        with_loader_criteria(AIConversation,
                             lambda cls: cls.owner_user_id == user_id,
                             include_aliases=True),
    )
    for model in SCOPED_MODELS:
        state.statement = state.statement.options(
            with_loader_criteria(model,
                lambda cls: cls.greenhouse_id.in_(
                    select(Greenhouse.id).where(Greenhouse.organization_id == org_id)),
                include_aliases=True),
        )


@event.listens_for(Session, "before_flush")
def _scope_writes(session, _context, _instances):
    user = CURRENT_USER.get()
    if user is None:
        return
    for item in session.new.union(session.dirty):
        if isinstance(item, FarmTask) and item in session.new and item.created_by_user_id is None:
            item.created_by_user_id = user.id
        if isinstance(item, (TaskEvent, TaskFeedback)) and item.operator_user_id is None:
            item.operator_user_id = user.id
        if isinstance(item, DecisionRecommendation) and item.reviewed_at is not None and item.reviewed_by_user_id is None:
            item.reviewed_by_user_id = user.id
        if isinstance(item, DiseaseRecognitionRecord) and item.review_status != "unreviewed" and item.reviewed_by_user_id is None:
            item.reviewed_by_user_id = user.id
        if isinstance(item, WarningEvent) and item.status in {"acknowledged", "resolved", "dismissed"}:
            item.last_operator_user_id = user.id
        if isinstance(item, Greenhouse):
            if item in session.new and item.organization_id is None:
                item.organization_id = user.organization_id
            if item.organization_id != user.organization_id:
                raise ServiceError(403, "大棚不属于当前组织")
        elif isinstance(item, AIConversation):
            if item in session.new and item.owner_user_id is None:
                item.owner_user_id = user.id
            if item.owner_user_id != user.id:
                raise ServiceError(403, "对话不属于当前用户")
        elif isinstance(item, SCOPED_MODELS):
            greenhouse_id = item.greenhouse_id
            if greenhouse_id is None:
                raise ServiceError(403, "业务记录缺少大棚归属")
            owner = session.scalar(select(Greenhouse.organization_id).where(
                Greenhouse.id == greenhouse_id))
            if owner != user.organization_id:
                raise ServiceError(403, "业务记录不属于当前组织")
