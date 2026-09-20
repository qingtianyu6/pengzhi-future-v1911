from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Greenhouse
from app.schemas.common import ApiResponse
from app.schemas.sensor_data import (
    SensorBatchRequest,
    SensorBatchResult,
    SensorDataInput,
    SensorIngestRequest,
    SensorIngestStatus,
)
from app.services import sensor_service
from app.services.errors import ServiceError


router = APIRouter(prefix="/v1/ingest", tags=["设备数据接入"])
Database = Annotated[Session, Depends(get_db)]


def _check_sensor_key(value: str | None) -> None:
    expected = get_settings().sensor_ingest_key
    if not expected:
        return
    if not value or not hmac.compare_digest(value, expected):
        raise ServiceError(401, "传感器接入密钥无效")


@router.get(
    "/status",
    response_model=ApiResponse[SensorIngestStatus],
    summary="查询传感器接入能力",
)
def ingest_status() -> ApiResponse[SensorIngestStatus]:
    settings = get_settings()
    return ApiResponse(data=SensorIngestStatus(
        endpoint="/api/v1/ingest/sensor-data",
        auth_required=bool(settings.sensor_ingest_key),
        accepted_metrics=[
            "temperature",
            "air_humidity",
            "soil_moisture",
            "light_intensity",
            "co2_concentration",
        ],
    ))


@router.post(
    "/sensor-data",
    response_model=ApiResponse[SensorBatchResult],
    summary="传感器批量上报环境数据",
    description="第三方设备按大棚编码上报环境数据。生产部署可通过 X-Sensor-Key 请求头鉴权。",
)
def ingest_sensor_data(
    payload: SensorIngestRequest,
    db: Database,
    sensor_key: Annotated[str | None, Header(alias="X-Sensor-Key")] = None,
) -> ApiResponse[SensorBatchResult]:
    _check_sensor_key(sensor_key)
    codes = {item.greenhouse_code.strip() for item in payload.items}
    rows = db.execute(
        select(Greenhouse.code, Greenhouse.id).where(Greenhouse.code.in_(codes))
    )
    greenhouse_map = {code: greenhouse_id for code, greenhouse_id in rows}
    missing = sorted(codes - greenhouse_map.keys())
    if missing:
        raise ServiceError(404, f"未找到大棚编码：{missing}")

    items = [
        SensorDataInput(
            greenhouse_id=greenhouse_map[item.greenhouse_code.strip()],
            device_id=item.device_id.strip(),
            recorded_at=item.recorded_at,
            temperature=item.temperature,
            air_humidity=item.air_humidity,
            soil_moisture=item.soil_moisture,
            light_intensity=item.light_intensity,
            co2_concentration=item.co2_concentration,
            source="sensor",
            quality_flag=item.quality_flag,
        )
        for item in payload.items
    ]
    result = sensor_service.batch_insert(db, SensorBatchRequest(items=items))
    return ApiResponse(message="传感器数据已接收", data=result)
