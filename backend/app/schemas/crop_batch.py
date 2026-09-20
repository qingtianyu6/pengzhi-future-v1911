from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.algorithms.crop_rule_registry import CropType
from app.algorithms.growth_stage_rules import GROWTH_STAGES
from app.algorithms.tomato_growth_stage_rules import TOMATO_GROWTH_STAGES


BatchStatus = Literal["growing", "harvested", "closed"]
GrowthStage = Literal["苗期", "营养生长期", "伸蔓期", "开花坐果期", "果实膨大期", "成熟采收期", "规则不可用"]


class CropBatchCreate(BaseModel):
    batch_code: str = Field(min_length=1, max_length=40)
    variety: str = Field(min_length=1, max_length=80)
    crop_type: CropType = "tomato"
    planted_at: date
    expected_harvest_at: date | None = None
    growth_stage: GrowthStage | None = Field(
        default=None, description="留空时按定植日期自动计算；填写表示人工修正"
    )
    status: BatchStatus = "growing"

    @model_validator(mode="after")
    def validate_dates(self) -> "CropBatchCreate":
        if self.expected_harvest_at and self.planted_at > self.expected_harvest_at:
            raise ValueError("定植日期不能晚于预计采收日期")
        return self


class CropBatchUpdate(BaseModel):
    batch_code: str | None = Field(default=None, min_length=1, max_length=40)
    variety: str | None = Field(default=None, min_length=1, max_length=80)
    crop_type: CropType | None = None
    planted_at: date | None = None
    expected_harvest_at: date | None = None
    growth_stage: GrowthStage | None = None
    status: BatchStatus | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "CropBatchUpdate":
        required_fields = {"batch_code", "variety", "crop_type", "planted_at", "growth_stage", "status"}
        null_fields = [
            field for field in required_fields
            if field in self.model_fields_set and getattr(self, field) is None
        ]
        if null_fields:
            raise ValueError(f"以下字段不能为 null：{', '.join(sorted(null_fields))}")
        return self


class CropBatchData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    greenhouse_id: int
    batch_code: str
    variety: str
    crop_type: CropType
    planted_at: date
    expected_harvest_at: date | None
    growth_stage: GrowthStage
    growth_day: int
    stage_updated_at: datetime
    is_stage_manually_set: bool
    status: BatchStatus
    created_at: datetime
    updated_at: datetime


assert set(GROWTH_STAGES) == {
    "苗期", "伸蔓期", "开花坐果期", "果实膨大期", "成熟采收期"
}
assert set(TOMATO_GROWTH_STAGES) == {"苗期", "营养生长期", "开花坐果期", "果实膨大期", "成熟采收期"}
