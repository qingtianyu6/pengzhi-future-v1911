"""Forecast snapshots kept for local, greenhouse-level verification."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.greenhouse import utc_now


class ForecastAudit(Base):
    __tablename__ = "forecast_audits"
    __table_args__ = (
        UniqueConstraint("greenhouse_id", "input_end_time", "target_at", "model_version",
                         name="uq_forecast_audit_version_target"),
        Index("ix_forecast_audit_greenhouse_target", "greenhouse_id", "target_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    greenhouse_id: Mapped[int] = mapped_column(ForeignKey("greenhouses.id"), nullable=False)
    input_end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    target_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    horizon_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    predicted_temperature: Mapped[float | None] = mapped_column(Float)
    predicted_humidity: Mapped[float | None] = mapped_column(Float)
    temperature_lower: Mapped[float | None] = mapped_column(Float)
    temperature_upper: Mapped[float | None] = mapped_column(Float)
    humidity_lower: Mapped[float | None] = mapped_column(Float)
    humidity_upper: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
