from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.sensor_data import (
    SensorBatchRequest,
    SensorBatchResult,
    SensorDataView,
    SensorHistoryData,
    EnvironmentImportPreview,
)
from app.services import sensor_service
from app.services.sensor_import_service import import_environment_file, preview_environment_file


router = APIRouter(prefix="/sensors", tags=["环境监测"])
Database = Annotated[Session, Depends(get_db)]


@router.get(
    "/latest",
    response_model=ApiResponse[SensorDataView | None],
    summary="获取最新环境数据",
)
def get_latest(
    greenhouse_id: Annotated[int, Query(gt=0)], db: Database
) -> ApiResponse[SensorDataView | None]:
    return ApiResponse(data=sensor_service.get_latest(db, greenhouse_id))


@router.get(
    "/history",
    response_model=ApiResponse[SensorHistoryData],
    summary="获取历史环境数据",
)
def get_history(
    greenhouse_id: Annotated[int, Query(gt=0)],
    start_time: datetime,
    end_time: datetime,
    db: Database,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> ApiResponse[SensorHistoryData]:
    return ApiResponse(
        data=sensor_service.get_history(
            db, greenhouse_id, start_time, end_time, page, page_size
        )
    )


@router.post(
    "/batch",
    response_model=ApiResponse[SensorBatchResult],
    summary="批量写入环境数据",
    description="为后续传感器上报或 CSV 导入预留；整批先校验，重复时间点安全跳过。",
)
def batch_insert(
    payload: SensorBatchRequest, db: Database
) -> ApiResponse[SensorBatchResult]:
    return ApiResponse(data=sensor_service.batch_insert(db, payload))


@router.post(
    "/import-preview",
    response_model=ApiResponse[EnvironmentImportPreview],
    summary="预检环境数据文件",
)
async def import_preview(
    file: Annotated[UploadFile, File(...)],
) -> ApiResponse[EnvironmentImportPreview]:
    preview = await preview_environment_file(file)
    return ApiResponse(message="数据文件预检完成", data=preview)


@router.post(
    "/import-file",
    response_model=ApiResponse[dict],
    summary="导入环境历史数据",
)
async def import_file(
    db: Database,
    greenhouse_id: Annotated[int, Form(gt=0)],
    file: Annotated[UploadFile, File(...)],
) -> ApiResponse[dict]:
    result = await import_environment_file(db, greenhouse_id, file)
    return ApiResponse(message="环境数据导入完成", data=result)
