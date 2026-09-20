from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


RecommendationStatus = Literal["pending_review", "accepted", "rejected", "superseded"]
Priority = Literal["low", "medium", "high", "urgent"]


class RecommendationReviewRequest(BaseModel):
    operator: str = Field(min_length=1, max_length=60)
    note: str | None = Field(default=None, max_length=500)


class RecommendationRejectRequest(RecommendationReviewRequest):
    note: str = Field(min_length=1, max_length=500)


class TaskDraft(BaseModel):
    title: str
    greenhouse_id: int
    crop_batch_id: int | None
    crop_type: str
    crop_rule_version: str
    priority: Priority
    action_type: str
    description: str
    suggested_execute_before: datetime | None
    source_warning_id: int
    source_recommendation_id: int
    requires_manual_confirmation: bool = True


class DecisionRecommendationData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    warning_event_id: int
    greenhouse_id: int
    crop_batch_id: int | None
    crop_type: str
    crop_rule_version: str
    recommendation_code: str
    priority: Priority
    action_type: str
    title: str
    rationale: str
    action_steps_json: list[str]
    execute_before: datetime | None
    safety_note: str
    status: RecommendationStatus
    rule_version: str
    generated_at: datetime
    reviewed_at: datetime | None
    review_note: str | None
    task_draft: TaskDraft | None = None


class CurrentDecisionData(BaseModel):
    greenhouse_id: int
    crop_batch_id: int | None
    crop_type: str
    growth_stage: str | None
    data_source: str | None
    calibration_status: str
    crop_rule_version: str = "rules_unavailable"
    crop_match_status: str = "mismatched"
    cross_crop_warning: bool = True
    cross_region_warning: bool = True
    validation_status: str = "validated_on_public_dataset"
    local_calibration_status: str = "not_calibrated"
    decision_scope: str = "decision_support"
    forecast_strategy: str = "per_target_per_horizon_hybrid"
    current_risk_level: str | None
    future_risk_timeline: list[dict[str, object]] = Field(default_factory=list)
    recommendations: list[DecisionRecommendationData] = Field(default_factory=list)
    disclaimer: str = "本建议由规则系统根据环境监测和预测结果生成，仅供辅助决策，不代表设备已执行。"
