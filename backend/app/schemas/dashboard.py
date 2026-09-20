from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.crop_batch import CropBatchData
from app.schemas.greenhouse import GreenhouseData
from app.schemas.sensor_data import SensorDataView
from app.schemas.task import FarmTaskData, TaskSummaryData


class MetricChanges(BaseModel):
    temperature: float | None = None
    air_humidity: float | None = None
    soil_moisture: float | None = None
    light_intensity: float | None = None
    co2_concentration: float | None = None


class RiskAssessment(BaseModel):
    data_status: str
    growth_stage: str | None
    component_scores: dict[str, float]
    overall_score: float | None
    level: str
    reasons: list[str]
    rule_version: str
    crop_type: str = "unknown"
    rule_scope: str = "rules_unavailable"
    expert_calibration_required: bool = False
    disclaimer: str = "风险评估基于环境监测与作物生育期规则，建议由管理人员结合现场情况确认。"


class DashboardSummary(BaseModel):
    greenhouse: GreenhouseData
    active_batch: CropBatchData | None
    latest_environment: SensorDataView | None
    changes: MetricChanges | None
    risk: RiskAssessment
    today_abnormal_count: int
    trend_24h: list[SensorDataView]
    data_source: str | None
    data_source_label: str | None
    data_updated_at: datetime | None
    empty_state: bool
    warning_summary: "DashboardWarningSummary"
    task_summary: "DashboardTaskSummary"


class DashboardWarningSummary(BaseModel):
    highest_risk_level: str = "normal"
    open_warning_count: int = 0
    latest_warning_id: int | None = None
    latest_warning_title: str | None = None
    future_risk_timeline: list[dict[str, object]] = Field(default_factory=list)
    latest_recommendation_id: int | None = None
    latest_recommendation_title: str | None = None
    forecast_strategy: str = "per_target_per_horizon_hybrid"
    validation_status: str = "validated_on_public_dataset"
    cross_region_warning: bool = True


class DashboardTaskSummary(TaskSummaryData):
    recent_tasks: list[FarmTaskData] = Field(default_factory=list)
    source_distribution: dict[str, int] = Field(default_factory=dict)
