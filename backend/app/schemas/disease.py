from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SupportedDiseaseClass(BaseModel):
    key: str
    name: str


class DiseaseModelStatus(BaseModel):
    service_status: str
    model_status: str
    model_version: str
    target_crop: Literal["tomato"]
    supported_classes: list[SupportedDiseaseClass]
    input_size: int
    confidence_threshold: float | None
    internal_metrics_summary: dict
    external_metrics_summary: dict
    validation_status: Literal["validated_on_public_dataset", "under_evaluation", "not_validated"]
    local_calibration_status: Literal["not_calibrated"]
    limitations: list[str]


class TopPrediction(BaseModel):
    class_key: str
    class_name: str
    confidence: float = Field(ge=0, le=1)


class DiseaseIdentification(BaseModel):
    record_id: int
    recognition_status: Literal["recognized", "review_required", "low_confidence", "model_unavailable"]
    predicted_class: str | None
    predicted_class_name: str | None
    confidence: float | None = Field(default=None, ge=0, le=1)
    top3_predictions: list[TopPrediction]
    model_version: str
    target_crop: Literal["tomato"] = "tomato"
    validation_status: Literal["validated_on_public_dataset", "under_evaluation", "not_validated"]
    local_calibration_status: Literal["not_calibrated"] = "not_calibrated"
    limitations: list[str]
    safety_notice: str
    duplicate_image: bool = False


class DiseaseRecordData(BaseModel):
    id: int
    greenhouse_id: int
    crop_batch_id: int
    crop_type: str
    image_path: str
    image_sha256: str
    original_filename: str
    predicted_class: str | None
    predicted_class_name: str | None
    confidence: float | None
    top3_predictions: list[TopPrediction]
    recognition_status: str
    model_version: str
    model_status: str
    validation_status: str
    local_calibration_status: str
    review_status: str
    reviewed_class: str | None
    review_note: str | None
    created_at: datetime
    updated_at: datetime


class DiseaseReviewRequest(BaseModel):
    review_status: Literal["confirmed", "corrected", "rejected"]
    reviewed_class: str | None = None
    review_note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def corrected_requires_class(self):
        if self.review_status == "corrected" and not self.reviewed_class:
            raise ValueError("修正识别结果时必须选择类别")
        return self
