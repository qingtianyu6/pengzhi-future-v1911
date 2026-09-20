from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard_service import get_dashboard_summary


router = APIRouter(prefix="/dashboard", tags=["智慧驾驶舱"])
Database = Annotated[Session, Depends(get_db)]


@router.get(
    "/summary",
    response_model=ApiResponse[DashboardSummary],
    summary="获取智慧驾驶舱摘要",
)
def dashboard_summary(
    greenhouse_id: Annotated[int, Query(gt=0)], db: Database
) -> ApiResponse[DashboardSummary]:
    return ApiResponse(data=get_dashboard_summary(db, greenhouse_id))
