from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.task import FarmTaskData


class RiskItem(BaseModel):
    disease_type: str
    disease_name: str
    current_score: float
    risk_24h: float
    risk_48h: float
    risk_72h: float
    risk_level: str
    trend: str
    factors: dict[str, Any]
    explanation: str


class RiskEventData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    greenhouse_id: int
    crop_batch_id: int | None
    risk_type: str
    disease_type: str
    crop_type: str
    growth_stage: str | None
    current_score: float
    risk_24h: float
    risk_48h: float
    risk_72h: float
    risk_level: str
    trend: str
    factors_json: dict[str, Any]
    explanation: str
    status: str
    created_at: datetime


class GreenhouseRiskResponse(BaseModel):
    greenhouse_id: int
    crop_type: str
    growth_stage: str | None
    data_status: str
    current_environment: dict[str, Any]
    risks: list[RiskItem]
    top_event: RiskEventData | None


class RecalculateRiskRequest(BaseModel):
    greenhouse_id: int = Field(gt=0)
    crop_type: str | None = Field(default=None, max_length=40)
    growth_stage: str | None = Field(default=None, max_length=40)


class DecisionPlanData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    risk_event_id: int
    greenhouse_id: int
    task_id: int | None
    plan_name: str
    actions_json: list[dict[str, Any]]
    expected_result_json: dict[str, Any]
    score: float
    status: str
    rationale: str
    created_at: datetime


class GenerateDecisionRequest(BaseModel):
    risk_event_id: int = Field(gt=0)


class ExecuteDecisionRequest(BaseModel):
    operator: str = Field(default="系统演示员", min_length=1, max_length=60)


class ExecuteDecisionResponse(BaseModel):
    plan: DecisionPlanData
    task: FarmTaskData


class SimulationRequest(BaseModel):
    greenhouse_id: int = Field(gt=0)
    decision_plan_id: int | None = Field(default=None, gt=0)
    action_type: Literal["ventilation", "shading", "irrigation", "dehumidify"] = "ventilation"
    intensity: int = Field(default=30, ge=0, le=100)
    duration_minutes: int = Field(default=30, ge=10, le=180)


class SimulationData(BaseModel):
    id: int | None = None
    greenhouse_id: int
    action_type: str
    intensity: int
    duration_minutes: int
    baseline: dict[str, Any]
    timeline: list[dict[str, Any]]
    estimated_risk_after: float | None = None
    note: str


class TreatmentEvaluationData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    greenhouse_id: int
    risk_event_id: int | None
    decision_plan_id: int | None
    before_snapshot_json: dict[str, Any]
    after_snapshot_json: dict[str, Any]
    environment_change_json: dict[str, Any]
    risk_change: float
    effect_score: float
    effect_level: str
    recommendation: str
    created_at: datetime


class EvaluateTaskRequest(BaseModel):
    operator: str = Field(default="系统演示员", min_length=1, max_length=60)


class GreenhouseProfileData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    greenhouse_id: int
    heat_response: float
    cooling_response: float
    humidity_response: float
    ventilation_response: float
    risk_sensitivity: float
    sample_count: int
    traits_json: dict[str, Any]
    updated_at: datetime
