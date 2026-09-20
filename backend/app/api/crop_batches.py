from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.crop_batch import CropBatchCreate, CropBatchData, CropBatchUpdate
from app.services import crop_batch_service


router = APIRouter(tags=["种植批次"])
Database = Annotated[Session, Depends(get_db)]


@router.get(
    "/greenhouses/{greenhouse_id}/crop-batches",
    response_model=ApiResponse[list[CropBatchData]],
    summary="获取大棚种植批次",
)
def list_batches(greenhouse_id: int, db: Database) -> ApiResponse[list[CropBatchData]]:
    return ApiResponse(data=crop_batch_service.list_batches(db, greenhouse_id))


@router.post(
    "/greenhouses/{greenhouse_id}/crop-batches",
    response_model=ApiResponse[CropBatchData],
    status_code=status.HTTP_201_CREATED,
    summary="创建种植批次",
)
def create_batch(
    greenhouse_id: int, payload: CropBatchCreate, db: Database
) -> ApiResponse[CropBatchData]:
    return ApiResponse(
        code=201,
        message="种植批次创建成功",
        data=crop_batch_service.create_batch(db, greenhouse_id, payload),
    )


@router.get(
    "/crop-batches/{batch_id}",
    response_model=ApiResponse[CropBatchData],
    summary="获取种植批次详情",
)
def get_batch(batch_id: int, db: Database) -> ApiResponse[CropBatchData]:
    return ApiResponse(data=crop_batch_service.get_batch(db, batch_id))


@router.put(
    "/crop-batches/{batch_id}",
    response_model=ApiResponse[CropBatchData],
    summary="修改种植批次",
)
def update_batch(
    batch_id: int, payload: CropBatchUpdate, db: Database
) -> ApiResponse[CropBatchData]:
    return ApiResponse(
        message="种植批次更新成功",
        data=crop_batch_service.update_batch(db, batch_id, payload),
    )
