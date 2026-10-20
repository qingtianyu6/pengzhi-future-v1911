"""Versioned agronomy work products and field observations."""
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.greenhouse import utc_now


class AgronomyRecord(Base):
    __tablename__ = "agronomy_records"
    __table_args__ = (Index("ix_agronomy_context", "greenhouse_id", "crop_batch_id", "kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    greenhouse_id: Mapped[int] = mapped_column(ForeignKey("greenhouses.id"), index=True)
    crop_batch_id: Mapped[int | None] = mapped_column(ForeignKey("crop_batches.id"))
    kind: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(24), default="draft")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    __mapper_args__ = {"version_id_col": version}


class CropObservation(Base):
    __tablename__ = "crop_observations"
    __table_args__ = (Index("ix_crop_observation_context", "greenhouse_id", "crop_batch_id", "observed_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    greenhouse_id: Mapped[int] = mapped_column(ForeignKey("greenhouses.id"), index=True)
    crop_batch_id: Mapped[int] = mapped_column(ForeignKey("crop_batches.id"))
    study_id: Mapped[int | None] = mapped_column(ForeignKey("agronomy_records.id"))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    phase: Mapped[str] = mapped_column(String(16), default="routine")
    zone: Mapped[str] = mapped_column(String(80), default="全棚")
    note: Mapped[str] = mapped_column(Text)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
