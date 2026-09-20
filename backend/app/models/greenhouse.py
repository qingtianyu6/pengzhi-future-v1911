from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class Greenhouse(Base):
    __tablename__ = "greenhouses"
    __table_args__ = (
        CheckConstraint("area_mu > 0", name="ck_greenhouses_area_positive"),
        CheckConstraint(
            "status IN ('active', 'paused', 'closed')",
            name="ck_greenhouses_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    location: Mapped[str] = mapped_column(String(160), nullable=False)
    area_mu: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    manager_name: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    crop_batches = relationship("CropBatch", back_populates="greenhouse")
    sensor_data = relationship("SensorData", back_populates="greenhouse")
    warning_events = relationship("WarningEvent", back_populates="greenhouse")
