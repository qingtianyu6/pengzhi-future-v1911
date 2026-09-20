from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ApiResponse, PaginatedData
from app.schemas.greenhouse import GreenhouseCreate, GreenhouseData, GreenhouseUpdate
from app.services import greenhouse_service


router = APIRouter(prefix="/greenhouses", tags=["大棚管理"])
Database = Annotated[Session, Depends(get_db)]


@router.get("", response_model=ApiResponse[PaginatedData[GreenhouseData]], summary="获取大棚列表")
def list_greenhouses(
    db: Database,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status_value: Annotated[
        Literal["active", "paused", "closed"] | None, Query(alias="status")
    ] = None,
    keyword: Annotated[str | None, Query(max_length=80)] = None,
) -> ApiResponse[PaginatedData[GreenhouseData]]:
    return ApiResponse(
        data=greenhouse_service.list_greenhouses(
            db, page, page_size, status_value, keyword
        )
    )


@router.post(
    "",
    response_model=ApiResponse[GreenhouseData],
    status_code=status.HTTP_201_CREATED,
    summary="创建大棚",
)
def create_greenhouse(
    payload: GreenhouseCreate, db: Database
) -> ApiResponse[GreenhouseData]:
    return ApiResponse(code=201, message="大棚创建成功", data=greenhouse_service.create_greenhouse(db, payload))


@router.get("/{greenhouse_id}", response_model=ApiResponse[GreenhouseData], summary="获取大棚详情")
def get_greenhouse(greenhouse_id: int, db: Database) -> ApiResponse[GreenhouseData]:
    return ApiResponse(data=greenhouse_service.get_greenhouse(db, greenhouse_id))


@router.put("/{greenhouse_id}", response_model=ApiResponse[GreenhouseData], summary="修改大棚")
def update_greenhouse(
    greenhouse_id: int, payload: GreenhouseUpdate, db: Database
) -> ApiResponse[GreenhouseData]:
    return ApiResponse(
        message="大棚更新成功",
        data=greenhouse_service.update_greenhouse(db, greenhouse_id, payload),
    )


@router.delete("/{greenhouse_id}", response_model=ApiResponse[None], summary="删除大棚")
def delete_greenhouse(greenhouse_id: int, db: Database) -> ApiResponse[None]:
    greenhouse_service.delete_greenhouse(db, greenhouse_id)
    return ApiResponse(message="大棚删除成功", data=None)
