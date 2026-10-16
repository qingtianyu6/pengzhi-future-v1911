from typing import Literal

from pydantic import BaseModel, Field


class CandidateEvidence(BaseModel):
    candidate_id: int
    action_code: str
    title: str
    applicability: Literal["suitable", "needs_site_check", "unknown"]
    applicability_note: str
    energy_level: str
    labor_level: str
    historical_case_count: int
    measured_60min_count: int
    observed_risk_decrease_count: int
    manually_resolved_count: int
    median_temperature_change_c: float | None
    median_humidity_change_pct: float | None
    evidence_level: str


class ScenarioPoint(BaseModel):
    offset_minutes: Literal[30, 60]
    temperature_c: float | None
    humidity_pct: float | None
    risk_score: float | None
    risk_lower: float | None
    risk_upper: float | None


class Scenario(BaseModel):
    action_code: str
    title: str
    basis: Literal["historical_median", "rule_assumption", "recent_trend"]
    supporting_cases: int
    points: list[ScenarioPoint]
    note: str


class OutcomeEstimate(BaseModel):
    action_code: str
    title: str
    measured_cases: int
    observed_risk_change_mean: float | None
    smoothed_risk_change: float | None
    observed_difference_vs_observe: float | None
    observed_resolution_rate: float | None
    energy_level: str
    labor_level: str
    within_cost_limit: bool
    comparison_score: float | None
    note: str


class DecisionSupport(BaseModel):
    warning_event_id: int
    status: Literal["ready", "insufficient_context"]
    current_risk_score: float | None
    candidate_evidence: list[CandidateEvidence] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list)
    outcome_model_status: Literal["insufficient_data", "observational_estimates"]
    outcome_estimates: list[OutcomeEstimate] = Field(default_factory=list)
    max_energy_level: str
    max_labor_level: str
    explanation: str
