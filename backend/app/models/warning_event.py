from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.greenhouse import utc_now


class WarningEvent(Base):
    __tablename__ = "warning_events"
    __table_args__ = (
        CheckConstraint("severity IN ('normal','attention','warning','critical')", name="ck_warning_severity"),
        CheckConstraint("certainty IN ('expected','possible','normal','insufficient')", name="ck_warning_certainty"),
        CheckConstraint("status IN ('open','acknowledged','resolved','dismissed')", name="ck_warning_status"),
        Index("ix_warning_greenhouse", "greenhouse_id"),
        Index("ix_warning_status", "status"),
        Index("ix_warning_severity", "severity"),
        Index("uq_warning_fingerprint", "fingerprint", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    greenhouse_id: Mapped[int] = mapped_column(ForeignKey("greenhouses.id"), nullable=False)
    crop_batch_id: Mapped[int | None] = mapped_column(ForeignKey("crop_batches.id"))
    crop_type: Mapped[str] = mapped_column(String(20),nullable=False,default="unknown",server_default="unknown")
    crop_rule_version: Mapped[str] = mapped_column(String(40),nullable=False,default="rules_unavailable",server_default="rules_unavailable")
    crop_match_status: Mapped[str] = mapped_column(String(40),nullable=False,default="mismatched",server_default="mismatched")
    cross_region_warning: Mapped[bool] = mapped_column(Boolean,nullable=False,default=True,server_default="1")
    expert_calibration_required: Mapped[bool] = mapped_column(Boolean,nullable=False,default=True,server_default="1")
    warning_code: Mapped[str] = mapped_column(String(80), nullable=False)
    warning_type: Mapped[str] = mapped_column(String(60), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    certainty: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    forecast_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    forecast_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(40), nullable=False)
    forecast_service_version: Mapped[str | None] = mapped_column(String(40))
    forecast_methods_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    data_source: Mapped[str | None] = mapped_column(String(20))
    calibration_status: Mapped[str] = mapped_column(String(40), nullable=False)
    first_triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[str | None] = mapped_column(String(60))
    acknowledgement_note: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(String(60))
    resolution_note: Mapped[str | None] = mapped_column(Text)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    greenhouse = relationship("Greenhouse", back_populates="warning_events")
    crop_batch = relationship("CropBatch", back_populates="warning_events")
    recommendations = relationship("DecisionRecommendation", back_populates="warning_event")
