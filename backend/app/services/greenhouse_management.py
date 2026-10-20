"""Aggregate registered devices with actual reports without creating observations."""
from datetime import UTC, datetime, timedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models import Greenhouse, SensorData
from app.models.greenhouse_device import GreenhouseDevice
from app.services.errors import ServiceError


def greenhouse_or_404(db: Session, greenhouse_id: int):
    greenhouse = db.scalar(select(Greenhouse).where(Greenhouse.id == greenhouse_id))
    if greenhouse is None:
        raise ServiceError(404, "大棚不存在")
    return greenhouse


def utc(value):
    return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value


def is_online(value):
    return bool(value and datetime.now(UTC) - timedelta(hours=2) <= utc(value) <= datetime.now(UTC) + timedelta(minutes=5))


def device_rows(db: Session, greenhouse_id: int | None = None):
    # Explicit join also scopes column aggregates to the current organization.
    observations = select(SensorData.greenhouse_id, SensorData.device_id, func.max(SensorData.recorded_at)).join(
        Greenhouse, Greenhouse.id == SensorData.greenhouse_id).where(
        SensorData.source == "sensor", SensorData.device_id.is_not(None), SensorData.device_id != ""
    ).group_by(SensorData.greenhouse_id, SensorData.device_id)
    bindings = select(GreenhouseDevice).join(Greenhouse, Greenhouse.id == GreenhouseDevice.greenhouse_id)
    if greenhouse_id is not None:
        observations = observations.where(SensorData.greenhouse_id == greenhouse_id)
        bindings = bindings.where(GreenhouseDevice.greenhouse_id == greenhouse_id)
    rows = {}
    for gid, device_id, seen in db.execute(observations):
        rows[(gid, device_id)] = dict(greenhouse_id=gid, device_id=device_id, name=device_id,
            kind="environment", registered=False, last_seen=utc(seen), online=is_online(seen))
    for binding in db.scalars(bindings):
        key = (binding.greenhouse_id, binding.device_id)
        rows.setdefault(key, dict(greenhouse_id=binding.greenhouse_id, device_id=binding.device_id,
            last_seen=None, online=False))
        rows[key].update(name=binding.name, kind=binding.kind, registered=True)
    return sorted(rows.values(), key=lambda row: (not row["online"], row["device_id"]))


def summary(db: Session):
    total = db.scalar(select(func.count(Greenhouse.id))) or 0
    connected = db.scalar(select(func.count(func.distinct(SensorData.greenhouse_id))).join(
        Greenhouse, Greenhouse.id == SensorData.greenhouse_id)) or 0
    rows = device_rows(db)
    return dict(total=total, connected=connected, device_count=len(rows),
        online_devices=sum(row["online"] for row in rows), online_window_minutes=120)
