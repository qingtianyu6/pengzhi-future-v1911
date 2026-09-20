from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.prediction import EnvironmentPredictionData, EnvironmentPredictionRequest
from app.services import prediction_service


router = APIRouter(prefix="/predictions", tags=["环境预测"])


@router.post(
    "/environment",
    response_model=ApiResponse[EnvironmentPredictionData],
    status_code=status.HTTP_200_OK,
    summary="环境预测（兼容POST）",
    description="读取最近24小时数据并调用统一预测服务；不会返回随机或写死预测。",
)
def predict_environment(
    request: EnvironmentPredictionRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[EnvironmentPredictionData]:
    return ApiResponse(data=prediction_service.predict_environment(db, request.greenhouse_id, request.forecast_hours))


@router.get("/environment", response_model=ApiResponse[EnvironmentPredictionData], summary="未来1—6小时环境预测")
def get_environment_prediction(
    greenhouse_id: int = Query(gt=0),
    horizon_hours: int = Query(default=6, ge=1, le=6),
    db: Session = Depends(get_db),
) -> ApiResponse[EnvironmentPredictionData]:
    return ApiResponse(data=prediction_service.predict_environment(db, greenhouse_id, horizon_hours))
