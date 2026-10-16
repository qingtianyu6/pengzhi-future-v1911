from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.intervention import (CandidateData, InterventionData,
                                      ObservationRequest, SelectCandidateRequest)
from app.services import intervention_service


router = APIRouter(tags=["处置效果跟踪"])
Database = Annotated[Session, Depends(get_db)]


@router.get("/warnings/{warning_id}/candidates", response_model=ApiResponse[list[CandidateData]])
def candidates(warning_id: int, db: Database):
    return ApiResponse(data=intervention_service.ensure_candidates(db, warning_id))


@router.post("/candidates/{candidate_id}/select", response_model=ApiResponse[InterventionData])
def select_candidate(candidate_id: int, payload: SelectCandidateRequest, db: Database):
    return ApiResponse(data=intervention_service.select_candidate(db, candidate_id, payload.reason))


@router.get("/interventions", response_model=ApiResponse[list[InterventionData]])
def interventions(db: Database, greenhouse_id: int = Query(gt=0)):
    return ApiResponse(data=intervention_service.list_interventions(db, greenhouse_id))


@router.get("/interventions/{intervention_id}", response_model=ApiResponse[InterventionData])
def intervention(intervention_id: int, db: Database):
    return ApiResponse(data=intervention_service.get_intervention(db, intervention_id))


@router.post("/interventions/{intervention_id}/observations", response_model=ApiResponse[InterventionData])
def observation(intervention_id: int, payload: ObservationRequest, db: Database):
    return ApiResponse(data=intervention_service.record_observation(db, intervention_id, payload))
