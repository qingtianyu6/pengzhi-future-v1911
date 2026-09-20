from fastapi import APIRouter

from app.schemas.common import ApiResponse
from app.services.model_overview_service import get_model_overview


router = APIRouter(prefix="/models", tags=["模型中心"])


@router.get("/overview", response_model=ApiResponse[dict], summary="获取模型运行概览")
def overview() -> ApiResponse[dict]:
    return ApiResponse(data=get_model_overview())
