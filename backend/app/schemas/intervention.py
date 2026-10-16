from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CandidateData(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    greenhouse_id: int
    warning_event_id: int
    action_code: str
    title: str
    description: str
    action_type: str
    action_params_json: dict[str, Any]
    expected_response_minutes: int | None
    energy_level: str
    labor_level: str
    evidence_note: str
    status: str
    created_at: datetime


class SelectCandidateRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=1000)


class ObservationRequest(BaseModel):
    offset_minutes: Literal[30, 60]
    manual_status: str | None = Field(default=None, max_length=80)
    risk_resolved: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)


class ObservationData(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    intervention_id: int
    observation_type: str
    observed_at: datetime
    target_at: datetime | None = None
    sample_delta_seconds: int | None = None
    offset_minutes: int
    sensor_record_id: int | None
    temperature: float | None
    humidity: float | None
    soil_moisture: float | None
    co2: float | None
    risk_score: float | None
    manual_status: str | None
    risk_resolved: bool | None
    notes: str | None
    created_at: datetime


class InterventionData(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    greenhouse_id: int
    warning_event_id: int
    candidate_id: int
    task_id: int | None
    action_type: str
    action_params_json: dict[str, Any]
    operator_id: int
    selection_reason: str
    status: str
    selected_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    before_snapshot_json: dict[str, Any]
    observations: list[ObservationData] = Field(default_factory=list)
    causality_notice: str = "处置前后变化仅供效果跟踪，不代表已证明处置产生了该变化。"
