from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import CropBatch, Greenhouse
from app.models.greenhouse import utc_now
from app.schemas.crop_batch import CropBatchCreate, CropBatchData, CropBatchUpdate
from app.services.errors import ServiceError
from app.services.growth_stage_service import calculate_growth_day, calculate_growth_stage


def _get_greenhouse(db: Session, greenhouse_id: int) -> Greenhouse:
    greenhouse = db.get(Greenhouse, greenhouse_id)
    if greenhouse is None:
        raise ServiceError(404, "大棚不存在")
    return greenhouse


def _refresh_automatic_stage(batch: CropBatch) -> None:
    if batch.is_stage_manually_set:
        return
    stage = calculate_growth_stage(batch.planted_at,crop_type=batch.crop_type)
    if stage != batch.growth_stage:
        batch.growth_stage = stage
        batch.stage_updated_at = utc_now()


def to_batch_data(batch: CropBatch) -> CropBatchData:
    return CropBatchData(
        id=batch.id,
        greenhouse_id=batch.greenhouse_id,
        batch_code=batch.batch_code,
        variety=batch.variety,
        crop_type=batch.crop_type,
        planted_at=batch.planted_at,
        expected_harvest_at=batch.expected_harvest_at,
        growth_stage=batch.growth_stage,
        growth_day=calculate_growth_day(batch.planted_at),
        stage_updated_at=batch.stage_updated_at,
        is_stage_manually_set=batch.is_stage_manually_set,
        status=batch.status,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


def get_active_batch(db: Session, greenhouse_id: int) -> CropBatch | None:
    batch = db.scalar(
        select(CropBatch).where(
            CropBatch.greenhouse_id == greenhouse_id, CropBatch.status == "growing"
        )
    )
    if batch:
        _refresh_automatic_stage(batch)
        db.flush()
    return batch


def list_batches(db: Session, greenhouse_id: int) -> list[CropBatchData]:
    _get_greenhouse(db, greenhouse_id)
    batches = list(
        db.scalars(
            select(CropBatch)
            .where(CropBatch.greenhouse_id == greenhouse_id)
            .order_by(CropBatch.planted_at.desc())
        )
    )
    for batch in batches:
        _refresh_automatic_stage(batch)
    db.commit()
    return [to_batch_data(batch) for batch in batches]


def create_batch(
    db: Session, greenhouse_id: int, payload: CropBatchCreate
) -> CropBatchData:
    _get_greenhouse(db, greenhouse_id)
    if payload.status == "growing" and get_active_batch(db, greenhouse_id):
        raise ServiceError(409, "同一个大棚最多只能有一个生长中的批次")
    manual = payload.growth_stage is not None
    batch = CropBatch(
        greenhouse_id=greenhouse_id,
        **payload.model_dump(exclude={"growth_stage"}),
        growth_stage=payload.growth_stage or calculate_growth_stage(payload.planted_at,crop_type=payload.crop_type),
        is_stage_manually_set=manual,
        stage_updated_at=utc_now(),
    )
    db.add(batch)
    try:
        db.commit()
    except IntegrityError as exception:
        db.rollback()
        raise ServiceError(409, "批次编号重复或活跃批次冲突") from exception
    db.refresh(batch)
    return to_batch_data(batch)


def get_batch(db: Session, batch_id: int) -> CropBatchData:
    batch = db.get(CropBatch, batch_id)
    if batch is None:
        raise ServiceError(404, "种植批次不存在")
    _refresh_automatic_stage(batch)
    db.commit()
    return to_batch_data(batch)


def update_batch(db: Session, batch_id: int, payload: CropBatchUpdate) -> CropBatchData:
    batch = db.get(CropBatch, batch_id)
    if batch is None:
        raise ServiceError(404, "种植批次不存在")
    changes = payload.model_dump(exclude_unset=True)
    planted_at = changes.get("planted_at", batch.planted_at)
    harvest_at = changes.get("expected_harvest_at", batch.expected_harvest_at)
    if harvest_at and planted_at > harvest_at:
        raise ServiceError(422, "定植日期不能晚于预计采收日期")
    if changes.get("status") == "growing" and batch.status != "growing":
        if get_active_batch(db, batch.greenhouse_id):
            raise ServiceError(409, "同一个大棚最多只能有一个生长中的批次")
    for field, value in changes.items():
        setattr(batch, field, value)
    if "growth_stage" in changes:
        batch.is_stage_manually_set = True
        batch.stage_updated_at = utc_now()
    elif ({"planted_at","crop_type"}&changes.keys()) and not batch.is_stage_manually_set:
        batch.growth_stage = calculate_growth_stage(batch.planted_at,crop_type=batch.crop_type)
        batch.stage_updated_at = utc_now()
    try:
        db.commit()
    except IntegrityError as exception:
        db.rollback()
        raise ServiceError(409, "批次编号重复或活跃批次冲突") from exception
    db.refresh(batch)
    return to_batch_data(batch)
