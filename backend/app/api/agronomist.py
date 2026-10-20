from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.database import get_db
from app.schemas.agronomist import GoalCreate, ObservationCreate, RecordAction, RecordData, ScenarioCreate, StudyCreate
from app.schemas.common import ApiResponse
from app.services import agronomist_service as service
from app.services.errors import ServiceError

router = APIRouter(prefix="/agronomist", tags=["AI农艺师研究台"])
Database = Annotated[Session, Depends(get_db)]


@router.get("/archive")
def archive(db: Database, greenhouse_id: int = Query(gt=0), crop_batch_id: int | None = Query(default=None, gt=0)):
    return ApiResponse(data=service.archive(db, greenhouse_id, crop_batch_id))


@router.get("/records")
def records(db: Database, greenhouse_id: int = Query(gt=0), crop_batch_id: int | None = Query(default=None, gt=0)):
    return ApiResponse(data=service.goal_progress(db, greenhouse_id, crop_batch_id))


@router.post("/observations", status_code=201)
def observation(payload: ObservationCreate, db: Database):
    return ApiResponse(data=service.add_observation(db, payload))


@router.post("/scenarios", status_code=201, response_model=ApiResponse[RecordData])
def scenario(payload: ScenarioCreate, db: Database):
    return ApiResponse(data=service.compare(db, payload))


@router.post("/studies", status_code=201, response_model=ApiResponse[RecordData])
def study(payload: StudyCreate, db: Database):
    return ApiResponse(data=service.create_study(db, payload))


@router.post("/goals", status_code=201, response_model=ApiResponse[RecordData])
async def goal(payload: GoalCreate, db: Database):
    return ApiResponse(data=await service.create_ai_goal(db, payload) if payload.use_ai else service.create_goal(db, payload))


@router.post("/records/{record_id}/actions", response_model=ApiResponse[RecordData])
def action(record_id: int, payload: RecordAction, db: Database):
    try:
        return ApiResponse(data=service.apply_action(db, record_id, payload))
    except StaleDataError as exc:
        db.rollback()
        raise ServiceError(409, "记录已更新，请刷新后操作") from exc
