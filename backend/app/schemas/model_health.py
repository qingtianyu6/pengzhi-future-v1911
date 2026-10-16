from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class MetricHealth(BaseModel):
    sample_count: int
    mae: float | None
    rmse: float | None
    bias: float | None
    interval_coverage: float | None
    drift_bias_shift: float | None


class ModelHealth(BaseModel):
    greenhouse_id: int
    status: Literal["no_verified_samples", "limited", "monitoring", "drift_attention"]
    model_version: str | None
    matched_tolerance_minutes: int = 10
    temperature: MetricHealth
    humidity: MetricHealth
    updated_at: datetime | None
    explanation: str
