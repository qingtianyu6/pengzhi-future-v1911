from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.database.session import engine
from app.schemas.common import ApiResponse
from app.schemas.health import HealthData


router = APIRouter(tags=["系统状态"])


@router.get("/health", response_model=ApiResponse[HealthData], summary="健康检查")
def health_check() -> ApiResponse[HealthData]:
    settings = get_settings()
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return ApiResponse(
        data=HealthData(
            service=settings.app_name,
            status="healthy",
            version=settings.app_version,
            database="connected",
        )
    )
