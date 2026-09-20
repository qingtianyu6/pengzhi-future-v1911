from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EnvironmentPredictionRequest(BaseModel):
    greenhouse_id: int = Field(gt=0, description="大棚主键")
    forecast_hours: int = Field(default=6, ge=1, le=6, description="预测时长")


PredictionStatus = Literal["ready", "not_trained", "insufficient_data", "schema_mismatch", "under_evaluation"]
ModelStatus = Literal["baseline_ready", "ready", "under_evaluation", "not_trained", "schema_mismatch"]


class HistoryPoint(BaseModel):
    timestamp: datetime
    temperature_c: float
    air_humidity_pct: float


class PredictionPoint(BaseModel):
    forecast_time: datetime
    horizon: int
    temperature_c: float | None = None
    air_humidity_pct: float | None = None
    par_umol_m2_s: float | None = None
    lower_bounds: dict[str, float] = Field(default_factory=dict)
    upper_bounds: dict[str, float] = Field(default_factory=dict)
    forecast_method: str
    method_version: str
    methods: dict[str, str] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)


class EnvironmentPredictionData(BaseModel):
    greenhouse_id: int
    status: PredictionStatus
    forecast_service_status: PredictionStatus
    forecast_method: str | None = None
    forecast_method_labels: list[str] = Field(default_factory=list)
    model_status: ModelStatus
    effective_model_status: Literal["hybrid_ready", "baseline_ready", "under_evaluation", "not_trained"] = "hybrid_ready"
    ml_candidate_status: Literal["ready", "under_evaluation"]
    forecast_strategy: Literal["per_target_per_horizon_hybrid"] = "per_target_per_horizon_hybrid"
    ml_output_count: int = 0
    total_output_count: int = 12
    crop: str | None = None
    crop_type: str = "unknown"
    crop_match_status: Literal["matched_public_tomato", "mismatched"] = "mismatched"
    model_name: str | None = None
    model_type: str | None = None
    model_version: str | None = None
    training_crop: str = "cherry_tomato"
    training_region: str = "Bleiswijk, Netherlands"
    training_domain: str
    validation_status: Literal["validated_on_public_dataset", "under_evaluation", "not_validated"]
    # Retained for old clients and existing SQLite records; it no longer gates service.
    calibration_status: str = "legacy_not_applicable"
    local_calibration_status: Literal["not_calibrated"] = "not_calibrated"
    decision_scope: Literal["decision_support"] = "decision_support"
    cross_crop_warning: bool = False
    cross_region_warning: bool = True
    input_data_source: str | None = None
    input_end_time: datetime | None = None
    history_hours: int
    horizon_hours: int
    predictions: list[PredictionPoint] = Field(default_factory=list)
    history: list[HistoryPoint] = Field(default_factory=list)
    rules_status: Literal["tomato_rule_active", "rules_unavailable"]
    warnings: list[str] = Field(default_factory=list)
    generated_at: datetime


PredictionStatusData = EnvironmentPredictionData
