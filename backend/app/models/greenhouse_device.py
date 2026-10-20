"""Device registration metadata; online state comes from sensor reports."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.models.greenhouse import utc_now


class GreenhouseDevice(Base):
    __tablename__ = "greenhouse_devices"
    __table_args__ = (UniqueConstraint("greenhouse_id", "device_id", name="uq_greenhouse_device"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    greenhouse_id: Mapped[int] = mapped_column(ForeignKey("greenhouses.id"), index=True)
    device_id: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(30), default="environment")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
