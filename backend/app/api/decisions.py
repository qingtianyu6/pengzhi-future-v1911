from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.decision import CurrentDecisionData, DecisionRecommendationData, RecommendationRejectRequest, RecommendationReviewRequest
from app.services import decision_service


router=APIRouter(prefix="/decisions",tags=["智能决策"])
Database=Annotated[Session,Depends(get_db)]


@router.get("/current",response_model=ApiResponse[CurrentDecisionData],summary="当前辅助决策建议")
def current_decisions(db:Database,greenhouse_id:int=Query(gt=0))->ApiResponse[CurrentDecisionData]:return ApiResponse(data=decision_service.get_current_decisions(db,greenhouse_id))


@router.get("/{recommendation_id}",response_model=ApiResponse[DecisionRecommendationData],summary="建议详情")
def recommendation_detail(recommendation_id:int,db:Database)->ApiResponse[DecisionRecommendationData]:return ApiResponse(data=decision_service.get_recommendation(db,recommendation_id))


@router.post("/{recommendation_id}/accept",response_model=ApiResponse[DecisionRecommendationData],summary="人工接受建议")
def accept_recommendation(recommendation_id:int,request:RecommendationReviewRequest,db:Database)->ApiResponse[DecisionRecommendationData]:return ApiResponse(data=decision_service.review_recommendation(db,recommendation_id,"accepted",request.operator,request.note))


@router.post("/{recommendation_id}/reject",response_model=ApiResponse[DecisionRecommendationData],summary="人工拒绝建议")
def reject_recommendation(recommendation_id:int,request:RecommendationRejectRequest,db:Database)->ApiResponse[DecisionRecommendationData]:return ApiResponse(data=decision_service.review_recommendation(db,recommendation_id,"rejected",request.operator,request.note))
