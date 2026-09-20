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

    grouped_times: dict[int, list[datetime]] = defaultdict(list)
    normalized_items = []
    seen: set[tuple[int, datetime]] = set()
    skipped = 0
    for item in payload.items:
        recorded_at = normalize_timestamp(item.recorded_at)
        key = (item.greenhouse_id, recorded_at)
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        grouped_times[item.greenhouse_id].append(recorded_at)
        normalized_items.append((item, recorded_at))

    existing_keys: set[tuple[int, datetime]] = set()
    for greenhouse_id, times in grouped_times.items():
        rows = db.execute(
            select(SensorData.greenhouse_id, SensorData.recorded_at).where(
                SensorData.greenhouse_id == greenhouse_id,
                SensorData.recorded_at.in_(times),
            )
        )
        existing_keys.update((row[0], row[1]) for row in rows)

    records = []
    for item, recorded_at in normalized_items:
        if (item.greenhouse_id, recorded_at) in existing_keys:
            skipped += 1
            continue
        records.append(
            SensorData(**item.model_dump(exclude={"recorded_at"}), recorded_at=recorded_at)
        )
    db.add_all(records)
    try:
        db.commit()
    except IntegrityError as exception:
        db.rollback()
        raise ServiceError(409, "批量数据与已有时间点冲突，整个批次未写入") from exception
    return SensorBatchResult(
        success_count=len(records),
        skipped_count=skipped,
        failed_count=0,
        message="批量写入完成；重复时间点已安全跳过",
    )
