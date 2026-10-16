from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.v2_decision import (DecisionPlanData, EvaluateTaskRequest, ExecuteDecisionRequest,
                                     ExecuteDecisionResponse, GenerateDecisionRequest,
                                     GreenhouseProfileData, GreenhouseRiskResponse,
                                     RecalculateRiskRequest, RiskEventData, SimulationData,
                                     SimulationRequest, TreatmentEvaluationData)
from app.services import v2_decision_service


Database = Annotated[Session, Depends(get_db)]

risk_router = APIRouter(prefix="/risk", tags=["V2.0 病害时间机"])
decision_router = APIRouter(prefix="/decision", tags=["V2.0 智能处置方案"])
simulation_router = APIRouter(prefix="/simulation", tags=["V2.0 3D决策沙盘"])
profile_router = APIRouter(prefix="/greenhouses", tags=["V2.0 大棚画像"])
evaluation_router = APIRouter(prefix="/tasks", tags=["V2.0 处置效果评估"])


@risk_router.get("/greenhouse/{greenhouse_id}", response_model=ApiResponse[GreenhouseRiskResponse])
def get_greenhouse_risk(greenhouse_id: int, db: Database):
    return ApiResponse(data=v2_decision_service.greenhouse_risk(db, greenhouse_id))


@risk_router.post("/recalculate", response_model=ApiResponse[RiskEventData])
def recalculate_risk(payload: RecalculateRiskRequest, db: Database):
    return ApiResponse(message="风险事件已重新计算", data=v2_decision_service.recalculate_risk(
        db, payload.greenhouse_id, crop_type=payload.crop_type, growth_stage=payload.growth_stage))


@risk_router.get("/events", response_model=ApiResponse[list[RiskEventData]])
def get_risk_events(db: Database, greenhouse_id: int | None = Query(default=None, gt=0), limit: int = Query(default=20, ge=1, le=100)):
    return ApiResponse(data=v2_decision_service.list_risk_events(db, greenhouse_id, limit))


@decision_router.post("/generate", response_model=ApiResponse[list[DecisionPlanData]])
def generate_decisions(payload: GenerateDecisionRequest, db: Database):
    return ApiResponse(message="候选处置方案已生成", data=v2_decision_service.generate_decision_plans(db, payload.risk_event_id))


@decision_router.get("", response_model=ApiResponse[list[DecisionPlanData]])
def list_decisions(db: Database, risk_event_id: int = Query(gt=0)):
    from sqlalchemy import select
    from app.models import DecisionPlan
    return ApiResponse(data=list(db.scalars(select(DecisionPlan).where(DecisionPlan.risk_event_id == risk_event_id).order_by(DecisionPlan.score.desc()))))


@decision_router.get("/{plan_id}", response_model=ApiResponse[DecisionPlanData])
def get_decision(plan_id: int, db: Database):
    return ApiResponse(data=v2_decision_service.get_decision_plan(db, plan_id))


@decision_router.post("/{plan_id}/execute", response_model=ApiResponse[ExecuteDecisionResponse])
def execute_decision(plan_id: int, payload: ExecuteDecisionRequest, db: Database):
    plan, task = v2_decision_service.execute_decision_plan(db, plan_id, payload.operator)
    return ApiResponse(message="已生成农事任务草稿", data=ExecuteDecisionResponse(plan=plan, task=task))


@simulation_router.post("/run", response_model=ApiResponse[SimulationData])
def run_simulation(payload: SimulationRequest, db: Database):
    return ApiResponse(message="模拟推演完成", data=v2_decision_service.run_simulation(db, payload))


@evaluation_router.get("/{task_id}/evaluation", response_model=ApiResponse[TreatmentEvaluationData | None])
def get_task_evaluation(task_id: int, db: Database):
    return ApiResponse(data=v2_decision_service.get_task_evaluation(db, task_id))


@evaluation_router.post("/{task_id}/evaluate", response_model=ApiResponse[TreatmentEvaluationData])
def evaluate_task(task_id: int, _payload: EvaluateTaskRequest, db: Database):
    return ApiResponse(message="处置效果评估已生成", data=v2_decision_service.evaluate_task(db, task_id))


@profile_router.get("/{greenhouse_id}/profile", response_model=ApiResponse[GreenhouseProfileData])
def get_greenhouse_profile(greenhouse_id: int, db: Database):
    return ApiResponse(data=v2_decision_service.get_or_update_profile(db, greenhouse_id))
