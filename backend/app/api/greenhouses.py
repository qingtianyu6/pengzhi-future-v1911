from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ApiResponse, PaginatedData
from app.schemas.greenhouse import GreenhouseCreate, GreenhouseData, GreenhouseUpdate
from app.services import greenhouse_service
from app.services import greenhouse_management
from app.models.greenhouse_device import GreenhouseDevice
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, Field, ConfigDict
from app.services.errors import ServiceError


router = APIRouter(prefix="/greenhouses", tags=["大棚管理"])
Database = Annotated[Session, Depends(get_db)]


class DeviceBinding(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    device_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.:-]+$")
    name: str = Field(min_length=1, max_length=80)
    kind: Literal["environment", "soil", "light", "co2", "other"] = "environment"


@router.get("/management-summary", summary="大棚接入概况")
def management_summary(db: Database):
    return ApiResponse(data=greenhouse_management.summary(db))


@router.get("/{greenhouse_id}/devices", summary="设备登记与上报状态")
def list_devices(greenhouse_id: int, db: Database):
    greenhouse_management.greenhouse_or_404(db, greenhouse_id)
    return ApiResponse(data=greenhouse_management.device_rows(db, greenhouse_id))


@router.post("/{greenhouse_id}/devices", summary="绑定设备编号")
def bind_device(greenhouse_id: int, payload: DeviceBinding, db: Database):
    greenhouse_management.greenhouse_or_404(db, greenhouse_id)
    binding = db.scalar(select(GreenhouseDevice).where(
        GreenhouseDevice.greenhouse_id == greenhouse_id, GreenhouseDevice.device_id == payload.device_id))
    if binding is None:
        binding = GreenhouseDevice(greenhouse_id=greenhouse_id, **payload.model_dump())
        db.add(binding)
    else:
        binding.name, binding.kind = payload.name, payload.kind
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ServiceError(409, "设备登记冲突，请刷新后重试")
    return ApiResponse(message="设备已登记，待设备实际上传数据后更新在线状态", data=payload.model_dump())


@router.delete("/{greenhouse_id}/devices/{device_id}", summary="移除设备登记（保留历史数据）")
def unbind_device(greenhouse_id: int, device_id: str, db: Database):
    greenhouse_management.greenhouse_or_404(db, greenhouse_id)
    binding = db.scalar(select(GreenhouseDevice).where(
        GreenhouseDevice.greenhouse_id == greenhouse_id, GreenhouseDevice.device_id == device_id))
    if binding:
        db.delete(binding)
        db.commit()
    return ApiResponse(message="登记已移除，历史上报记录保留", data=None)


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
