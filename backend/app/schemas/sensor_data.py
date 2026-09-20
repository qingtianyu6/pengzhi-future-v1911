from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SensorSource = Literal["sensor", "import"]
QualityFlag = Literal["valid", "suspect", "missing"]


class SensorDataInput(BaseModel):
    greenhouse_id: int = Field(gt=0)
    recorded_at: datetime
    device_id: str | None = Field(default=None, min_length=1, max_length=80)
    temperature: float | None = Field(default=None, ge=-20, le=60)
    air_humidity: float | None = Field(default=None, ge=0, le=100)
    soil_moisture: float | None = Field(default=None, ge=0, le=100)
    light_intensity: float | None = Field(default=None, ge=0, le=150)
    co2_concentration: float | None = Field(default=None, ge=200, le=5000)
    source: SensorSource
    quality_flag: QualityFlag = "valid"

    @model_validator(mode="after")
    def mark_incomplete_values(self) -> "SensorDataInput":
        values = (
            self.temperature,
            self.air_humidity,
            self.soil_moisture,
            self.light_intensity,
            self.co2_concentration,
        )
        if any(value is None for value in values) and self.quality_flag == "valid":
            self.quality_flag = "missing"
        return self


class SensorBatchRequest(BaseModel):
    items: list[SensorDataInput] = Field(min_length=1, max_length=5000)


class SensorDataView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    greenhouse_id: int
    recorded_at: datetime
    device_id: str | None = Field(default=None, min_length=1, max_length=80)
    temperature: float | None
    air_humidity: float | None
    soil_moisture: float | None
    light_intensity: float | None
    co2_concentration: float | None
    source: SensorSource
    quality_flag: QualityFlag


class SensorHistoryData(BaseModel):
    items: list[SensorDataView]
    total: int
    page: int
    page_size: int
    start_time: datetime
    end_time: datetime
    source_note: str = "环境数据来源包括传感器接入或文件导入。"


class SensorBatchResult(BaseModel):
    success_count: int
    skipped_count: int
    failed_count: int
    message: str


class ImportPreviewSample(BaseModel):
    recorded_at: datetime | None
    temperature: float | None = None
    air_humidity: float | None = None
    soil_moisture: float | None = None
    light_intensity: float | None = None
    co2_concentration: float | None = None


class EnvironmentImportPreview(BaseModel):
    filename: str
    total_rows: int
    recognized_columns: dict[str, str]
    available_metrics: list[str]
    time_start: datetime | None
    time_end: datetime | None
    interval_minutes: float | None
    duplicate_time_rows: int
    invalid_time_rows: int
    out_of_range_rows: int
    completeness_rate: float
    continuity_rate: float
    valid_range_rate: float
    quality_score: int
    quality_level: str
    import_ready: bool
    issues: list[str]
    sample_rows: list[ImportPreviewSample]


class SensorIngestItem(BaseModel):
    greenhouse_code: str = Field(min_length=1, max_length=50)
    device_id: str = Field(min_length=1, max_length=80)
    recorded_at: datetime
    temperature: float | None = Field(default=None, ge=-20, le=60)
    air_humidity: float | None = Field(default=None, ge=0, le=100)
    soil_moisture: float | None = Field(default=None, ge=0, le=100)
    light_intensity: float | None = Field(default=None, ge=0, le=150)
    co2_concentration: float | None = Field(default=None, ge=200, le=5000)
    quality_flag: QualityFlag = "valid"

    @model_validator(mode="after")
    def mark_incomplete_values(self) -> "SensorIngestItem":
        values = (
            self.temperature,
            self.air_humidity,
            self.soil_moisture,
            self.light_intensity,
            self.co2_concentration,
        )
        if any(value is None for value in values) and self.quality_flag == "valid":
            self.quality_flag = "missing"
        return self


class SensorIngestRequest(BaseModel):
    items: list[SensorIngestItem] = Field(min_length=1, max_length=1000)


class SensorIngestStatus(BaseModel):
    endpoint: str
    auth_required: bool
    header_name: str = "X-Sensor-Key"
    accepted_metrics: list[str]
    max_batch_size: int = 1000
