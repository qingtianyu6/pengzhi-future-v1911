from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.decision import DecisionRecommendationData


RiskLevel = Literal["normal", "attention", "warning", "critical"]
WarningStatus = Literal["open", "acknowledged", "resolved", "dismissed"]
Certainty = Literal["expected", "possible", "normal", "insufficient"]


class WarningEvaluateRequest(BaseModel):
    greenhouse_id: int = Field(gt=0)
    as_of: datetime | None = None


class WarningActionRequest(BaseModel):
    operator: str = Field(min_length=1, max_length=60)
    note: str | None = Field(default=None, max_length=500)


class WarningDismissRequest(BaseModel):
    operator: str = Field(min_length=1, max_length=60)
    reason: str = Field(min_length=1, max_length=500)


class ForecastRiskPointData(BaseModel):
    horizon: int
    forecast_time: datetime
    risk_score: float | None
    risk_level: RiskLevel
    risk_type: str
    triggered: bool
    trigger_reasons: list[str]
    evidence: dict[str, Any]
    growth_stage: str | None
    rule_version: str
    evaluated_at: datetime
    data_source: str | None
    calibration_status: str
    certainty: Certainty
    partial_data: bool


class WarningEventData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    greenhouse_id: int
    crop_batch_id: int | None
    crop_type: str
    crop_rule_version: str
    crop_match_status: str
    cross_region_warning: bool
    expert_calibration_required: bool
    warning_code: str
    warning_type: str
    severity: RiskLevel
    risk_score: float
    certainty: Certainty
    title: str
    description: str
    evidence_json: dict[str, Any]
    forecast_start_at: datetime | None
    forecast_end_at: datetime | None
    status: WarningStatus
    fingerprint: str
    rule_version: str
    forecast_service_version: str | None
    forecast_methods_json: dict[str, Any]
    data_source: str | None
    calibration_status: str
    first_triggered_at: datetime
    last_triggered_at: datetime
    acknowledged_at: datetime | None
    acknowledged_by: str | None
    acknowledgement_note: str | None
    resolved_at: datetime | None
    resolved_by: str | None
    resolution_note: str | None
    dismissed_at: datetime | None
    dismissed_reason: str | None
    created_at: datetime
    updated_at: datetime


class WarningDetailData(WarningEventData):
    greenhouse_name: str
    batch_code: str | None
    growth_stage: str | None
    recommendations: list[DecisionRecommendationData] = Field(default_factory=list)


class WarningListData(BaseModel):
    items: list[WarningEventData]
    total: int
    page: int
    page_size: int


class WarningEvaluationData(BaseModel):
    greenhouse_id: int
    crop_batch_id: int | None
    crop_type: str
    crop_rule_version: str
    crop_match_status: str
    cross_region_warning: bool
    expert_calibration_required: bool
    growth_stage: str | None
    current_risk: dict[str, Any]
    future_risks: list[ForecastRiskPointData]
    forecast_status: str
    data_quality_issues: list[str]
    created_count: int
    updated_count: int
    skipped_count: int
    warnings: list[WarningEventData]
    recommendations: list[DecisionRecommendationData]
    data_source: str | None
    calibration_status: str = "legacy_not_applicable"
    validation_status: str = "validated_on_public_dataset"
    decision_scope: str = "decision_support"
    cross_crop_warning: bool = True
    evaluated_at: datetime


class WarningSummaryData(BaseModel):
    open_total: int
    attention_total: int
    warning_total: int
    critical_total: int
    acknowledged_total: int
    resolved_today: int
    latest_warning: WarningEventData | None
    greenhouse_distribution: dict[str, int]
