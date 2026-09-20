from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.greenhouse import utc_now


class CropBatch(Base):
    __tablename__ = "crop_batches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('growing', 'harvested', 'closed')",
            name="ck_crop_batches_status",
        ),
        CheckConstraint(
            "expected_harvest_at IS NULL OR planted_at <= expected_harvest_at",
            name="ck_crop_batches_dates",
        ),
        Index(
            "uq_crop_batches_one_growing_per_greenhouse",
            "greenhouse_id",
            unique=True,
            sqlite_where=text("status = 'growing'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    greenhouse_id: Mapped[int] = mapped_column(
        ForeignKey("greenhouses.id"), nullable=False, index=True
    )
    batch_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    variety: Mapped[str] = mapped_column(String(80), nullable=False)
    crop_type: Mapped[str] = mapped_column(String(20), nullable=False, default="tomato", server_default="unknown")
    planted_at: Mapped[date] = mapped_column(Date, nullable=False)
    expected_harvest_at: Mapped[date | None] = mapped_column(Date)
    growth_stage: Mapped[str] = mapped_column(String(30), nullable=False)
    stage_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    is_stage_manually_set: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="growing")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    greenhouse = relationship("Greenhouse", back_populates="crop_batches")
    warning_events = relationship("WarningEvent", back_populates="crop_batch")
