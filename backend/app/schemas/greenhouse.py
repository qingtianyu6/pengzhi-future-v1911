from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.crop_batch import CropBatchData


GreenhouseStatus = Literal["active", "paused", "closed"]


class GreenhouseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=80)
    location: str = Field(min_length=1, max_length=160)
    area_mu: Decimal = Field(gt=0, max_digits=8, decimal_places=2)
    status: GreenhouseStatus = "active"
    manager_name: str | None = Field(default=None, max_length=40)


class GreenhouseUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=80)
    location: str | None = Field(default=None, min_length=1, max_length=160)
    area_mu: Decimal | None = Field(
        default=None, gt=0, max_digits=8, decimal_places=2
    )
    status: GreenhouseStatus | None = None
    manager_name: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "GreenhouseUpdate":
        required_fields = {"code", "name", "location", "area_mu", "status"}
        null_fields = [
            field for field in required_fields
            if field in self.model_fields_set and getattr(self, field) is None
        ]
        if null_fields:
            raise ValueError(f"以下字段不能为 null：{', '.join(sorted(null_fields))}")
        return self


class GreenhouseData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    location: str
    area_mu: Decimal
    status: GreenhouseStatus
    manager_name: str | None
    created_at: datetime
    updated_at: datetime
    active_batch: CropBatchData | None = None
