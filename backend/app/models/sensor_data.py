from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.greenhouse import utc_now


class SensorData(Base):
    __tablename__ = "sensor_data"
    __table_args__ = (
        UniqueConstraint("greenhouse_id", "recorded_at", name="uq_sensor_greenhouse_time"),
        CheckConstraint(
            "source IN ('sensor', 'import')", name="ck_sensor_source"
        ),
        CheckConstraint(
            "quality_flag IN ('valid', 'suspect', 'missing')",
            name="ck_sensor_quality",
        ),
        Index("ix_sensor_greenhouse_recorded", "greenhouse_id", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    greenhouse_id: Mapped[int] = mapped_column(
        ForeignKey("greenhouses.id"), nullable=False, index=True
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    device_id: Mapped[str | None] = mapped_column(String(80), index=True)
    temperature: Mapped[float | None] = mapped_column(Float)
    air_humidity: Mapped[float | None] = mapped_column(Float)
    soil_moisture: Mapped[float | None] = mapped_column(Float)
    light_intensity: Mapped[float | None] = mapped_column(Float)
    co2_concentration: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    quality_flag: Mapped[str] = mapped_column(String(20), nullable=False, default="valid")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    greenhouse = relationship("Greenhouse", back_populates="sensor_data")
