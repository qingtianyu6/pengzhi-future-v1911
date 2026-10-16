from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Greenhouse, SensorData
from app.schemas.sensor_data import (
    SensorBatchRequest,
    SensorBatchResult,
    SensorDataView,
    SensorHistoryData,
)
from app.services.errors import ServiceError

VALID_BUSINESS_SOURCES = ("sensor", "import")


def normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def to_sensor_view(record: SensorData) -> SensorDataView:
    recorded_at = record.recorded_at
    if recorded_at.tzinfo is None:
        recorded_at = recorded_at.replace(tzinfo=UTC)
    return SensorDataView(
        id=record.id,
        greenhouse_id=record.greenhouse_id,
        recorded_at=recorded_at,
        device_id=record.device_id,
        temperature=record.temperature,
        air_humidity=record.air_humidity,
        soil_moisture=record.soil_moisture,
        light_intensity=record.light_intensity,
        co2_concentration=record.co2_concentration,
        source=record.source,
        quality_flag=record.quality_flag,
    )


def ensure_greenhouse(db: Session, greenhouse_id: int) -> None:
    if db.get(Greenhouse, greenhouse_id) is None:
        raise ServiceError(404, "大棚不存在")


def get_latest_record(db: Session, greenhouse_id: int) -> SensorData | None:
    ensure_greenhouse(db, greenhouse_id)
    return db.scalar(
        select(SensorData)
        .where(SensorData.greenhouse_id == greenhouse_id, SensorData.source.in_(VALID_BUSINESS_SOURCES))
        .order_by(SensorData.recorded_at.desc())
        .limit(1)
    )


def get_latest(db: Session, greenhouse_id: int) -> SensorDataView | None:
    record = get_latest_record(db, greenhouse_id)
    return to_sensor_view(record) if record else None


def get_history(
    db: Session,
    greenhouse_id: int,
    start_time: datetime,
    end_time: datetime,
    page: int,
    page_size: int,
) -> SensorHistoryData:
    ensure_greenhouse(db, greenhouse_id)
    start = normalize_timestamp(start_time)
    end = normalize_timestamp(end_time)
    if start >= end:
        raise ServiceError(422, "开始时间必须早于结束时间")
    filters = (
        SensorData.greenhouse_id == greenhouse_id,
        SensorData.source.in_(VALID_BUSINESS_SOURCES),
        SensorData.recorded_at >= start,
        SensorData.recorded_at <= end,
    )
    total = db.scalar(select(func.count()).select_from(SensorData).where(*filters)) or 0
    records = list(
        db.scalars(
            select(SensorData)
            .where(*filters)
            .order_by(SensorData.recorded_at.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return SensorHistoryData(
        items=[to_sensor_view(record) for record in records],
        total=total,
        page=page,
        page_size=page_size,
        start_time=start.replace(tzinfo=UTC),
        end_time=end.replace(tzinfo=UTC),
    )


def batch_insert(db: Session, payload: SensorBatchRequest) -> SensorBatchResult:
    greenhouse_ids = {item.greenhouse_id for item in payload.items}
    existing_greenhouses = set(
        db.scalars(select(Greenhouse.id).where(Greenhouse.id.in_(greenhouse_ids)))
    )
    missing_greenhouses = greenhouse_ids - existing_greenhouses
    if missing_greenhouses:
        raise ServiceError(404, f"大棚不存在：{sorted(missing_greenhouses)}")

    metrics = ("temperature", "air_humidity", "soil_moisture", "light_intensity", "co2_concentration")
    keys={(item.greenhouse_id,normalize_timestamp(item.recorded_at)) for item in payload.items}
    records={}
    for gid in greenhouse_ids:
        times=[ts for g,ts in keys if g==gid]
        for row in db.scalars(select(SensorData).where(SensorData.greenhouse_id==gid, SensorData.recorded_at.in_(times))):
            records[(gid,row.recorded_at)]=row
    accepted=skipped=0
    for item in payload.items:
        ts=normalize_timestamp(item.recorded_at);key=(item.greenhouse_id,ts)
        row=records.get(key)
        if row is None:
            row=SensorData(**item.model_dump(exclude={"recorded_at"}),recorded_at=ts)
            db.add(row);records[key]=row;accepted+=1
            continue
        # A time point is an aggregate: complementary device metrics may fill gaps.
        # Already present metrics are immutable, making retrying a batch idempotent.
        filled=False
        for metric in metrics:
            incoming=getattr(item,metric)
            if incoming is not None and getattr(row,metric) is None:
                setattr(row,metric,incoming);filled=True
        if filled:
            devices=sorted(set((row.device_id or "").split("+")+([item.device_id] if item.device_id else []))-{''})
            row.device_id="+".join(devices)[:80] or None
            if row.quality_flag != 'suspect' and item.quality_flag != 'suspect':
                row.quality_flag='valid' if all(getattr(row,k) is not None for k in metrics) else 'missing'
            else:row.quality_flag='suspect'
            accepted+=1
        else:skipped+=1
    try:db.commit()
    except IntegrityError as exc:
        db.rollback();raise ServiceError(409,"同一时间点发生并发写入，请重试批次") from exc
    return SensorBatchResult(success_count=accepted,skipped_count=skipped,failed_count=0,
        message="已写入或合并互补指标；已有指标不覆盖，重复上报安全跳过")
