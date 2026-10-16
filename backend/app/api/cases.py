from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.case_memory import CaseData, CasePage, SimilarCaseResult
from app.schemas.common import ApiResponse
from app.services import case_service


router = APIRouter(tags=["案例经验"])
Database = Annotated[Session, Depends(get_db)]


@router.get("/cases", response_model=ApiResponse[CasePage])
def cases(db: Database, greenhouse_id: int | None = Query(default=None, gt=0),
          page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100)):
    return ApiResponse(data=case_service.list_cases(db, greenhouse_id, page, page_size))


@router.get("/cases/{case_id}", response_model=ApiResponse[CaseData])
def case(case_id: int, db: Database):
    return ApiResponse(data=case_service.get_case(db, case_id))


@router.get("/warnings/{warning_id}/similar-cases", response_model=ApiResponse[SimilarCaseResult])
def similar_cases(warning_id: int, db: Database, top_k: int = Query(default=5, ge=1, le=20)):
    return ApiResponse(data=case_service.get_similar_cases(db, warning_id, top_k))
