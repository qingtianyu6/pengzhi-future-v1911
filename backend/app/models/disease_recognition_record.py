from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.greenhouse import utc_now


class DiseaseRecognitionRecord(Base):
    __tablename__ = "disease_recognition_records"
    __table_args__ = (
        CheckConstraint(
            "recognition_status IN ('recognized', 'low_confidence', 'invalid_image', 'model_unavailable')",
            name="ck_disease_records_recognition_status",
        ),
        CheckConstraint(
            "review_status IN ('unreviewed', 'confirmed', 'corrected', 'rejected')",
            name="ck_disease_records_review_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    greenhouse_id: Mapped[int] = mapped_column(ForeignKey("greenhouses.id"), nullable=False, index=True)
    crop_batch_id: Mapped[int] = mapped_column(ForeignKey("crop_batches.id"), nullable=False, index=True)
    crop_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    image_path: Mapped[str] = mapped_column(String(255), nullable=False)
    image_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    predicted_class: Mapped[str | None] = mapped_column(String(60))
    predicted_class_name: Mapped[str | None] = mapped_column(String(80))
    confidence: Mapped[float | None] = mapped_column(Float)
    top3_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    recognition_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    model_status: Mapped[str] = mapped_column(String(30), nullable=False)
    local_calibration_status: Mapped[str] = mapped_column(String(40), nullable=False)
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unreviewed", index=True)
    reviewed_class: Mapped[str | None] = mapped_column(String(60))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    greenhouse = relationship("Greenhouse")
    crop_batch = relationship("CropBatch")
