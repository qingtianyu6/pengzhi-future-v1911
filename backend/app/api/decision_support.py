from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.decision_support import DecisionSupport
from app.services.decision_support_service import get_decision_support


router = APIRouter(tags=["方案证据与模拟"])
Database = Annotated[Session, Depends(get_db)]
Level = Literal["none", "low", "medium", "high"]


@router.get("/warnings/{warning_id}/decision-support", response_model=ApiResponse[DecisionSupport])
def decision_support(warning_id: int, db: Database,
                     max_energy_level: Level = Query(default="high"),
                     max_labor_level: Level = Query(default="high")):
    return ApiResponse(data=get_decision_support(
        db, warning_id, max_energy_level=max_energy_level,
        max_labor_level=max_labor_level))
