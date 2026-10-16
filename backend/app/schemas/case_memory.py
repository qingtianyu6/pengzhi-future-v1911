from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.intervention import ObservationData


class CaseContext(BaseModel):
    greenhouse_id: int
    greenhouse_name: str
    crop_type: str
    growth_stage: str | None
    risk_type: str
    temperature_c: float | None
    air_humidity_pct: float | None
    co2_ppm: float | None
    soil_moisture_pct: float | None
    risk_score: float | None
    recorded_at: datetime | None


class CaseCandidate(BaseModel):
    id: int
    action_code: str
    title: str
    energy_level: str
    labor_level: str
    selected: bool


class CaseExecution(BaseModel):
    task_id: int | None
    task_status: str | None
    started_at: datetime | None
    finished_at: datetime | None
    duration_minutes: float | None
    assignee_name: str | None
    execution_operator_user_id: int | None
    feedback_notes: list[str] = Field(default_factory=list)


class CaseData(BaseModel):
    id: int
    case_code: str
    warning_event_id: int
    warning_title: str
    warning_status: str
    context: CaseContext
    candidates: list[CaseCandidate]
    selected_candidate_id: int
    selected_action_code: str
    selected_action_title: str
    selection_reason: str
    selected_by_user_id: int
    selected_at: datetime
    intervention_status: str
    execution: CaseExecution
    before_snapshot: dict[str, Any]
    observations: list[ObservationData]
    complete: bool
    quality_flags: list[str]
    causality_notice: str = "历史结果为观察记录，不能据此断言某方案造成了改善。"


class CasePage(BaseModel):
    items: list[CaseData]
    total: int
    page: int
    page_size: int


class SimilarCase(BaseModel):
    case: CaseData
    distance: float
    feature_coverage: float
    matched_features: list[str]


class ActionEvidence(BaseModel):
    action_code: str
    action_title: str
    case_count: int
    with_60min_measurement: int
    observed_risk_decrease_count: int
    manually_resolved_count: int
    median_temperature_change_c: float | None
    median_humidity_change_pct: float | None
    evidence_level: Literal["none", "limited", "emerging", "moderate"]


class SimilarCaseResult(BaseModel):
    warning_event_id: int
    status: Literal["ready", "insufficient_context"]
    query_context: CaseContext
    total_eligible_cases: int
    matches: list[SimilarCase]
    action_evidence: list[ActionEvidence]
    explanation: str
