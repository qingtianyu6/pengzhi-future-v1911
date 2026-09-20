from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.warning import WarningActionRequest, WarningDetailData, WarningDismissRequest, WarningEvaluationData, WarningEvaluateRequest, WarningEventData, WarningListData, WarningSummaryData
from app.services import warning_service


router=APIRouter(prefix="/warnings",tags=["预警中心"])
Database=Annotated[Session,Depends(get_db)]


@router.post("/evaluate",response_model=ApiResponse[WarningEvaluationData],summary="评估当前与未来环境风险")
def evaluate_warning(request:WarningEvaluateRequest,db:Database)->ApiResponse[WarningEvaluationData]:
    return ApiResponse(data=warning_service.evaluate_greenhouse(db,request.greenhouse_id,as_of=request.as_of))


@router.get("/summary",response_model=ApiResponse[WarningSummaryData],summary="预警摘要")
def get_warning_summary(db:Database)->ApiResponse[WarningSummaryData]:return ApiResponse(data=warning_service.warning_summary(db))


@router.get("",response_model=ApiResponse[WarningListData],summary="分页查询预警")
def get_warnings(db:Database,greenhouse_id:int|None=Query(default=None,gt=0),severity:Literal["normal","attention","warning","critical"]|None=None,status:Literal["open","acknowledged","resolved","dismissed"]|None=None,warning_type:str|None=None,start_time:datetime|None=None,end_time:datetime|None=None,page:int=Query(default=1,ge=1),page_size:int=Query(default=20,ge=1,le=100))->ApiResponse[WarningListData]:
    return ApiResponse(data=warning_service.list_warnings(db,greenhouse_id=greenhouse_id,severity=severity,status=status,warning_type=warning_type,start_time=start_time,end_time=end_time,page=page,page_size=page_size))


@router.get("/{warning_id}",response_model=ApiResponse[WarningDetailData],summary="预警详情")
def get_warning(warning_id:int,db:Database)->ApiResponse[WarningDetailData]:return ApiResponse(data=warning_service.get_warning_detail(db,warning_id))


@router.post("/{warning_id}/acknowledge",response_model=ApiResponse[WarningEventData],summary="确认预警")
def acknowledge_warning(warning_id:int,request:WarningActionRequest,db:Database)->ApiResponse[WarningEventData]:return ApiResponse(data=warning_service.change_warning_status(db,warning_id,"acknowledged",request.operator,request.note or "已确认"))


@router.post("/{warning_id}/resolve",response_model=ApiResponse[WarningEventData],summary="解除预警")
def resolve_warning(warning_id:int,request:WarningActionRequest,db:Database)->ApiResponse[WarningEventData]:return ApiResponse(data=warning_service.change_warning_status(db,warning_id,"resolved",request.operator,request.note or "现场确认已恢复"))


@router.post("/{warning_id}/dismiss",response_model=ApiResponse[WarningEventData],summary="忽略预警")
def dismiss_warning(warning_id:int,request:WarningDismissRequest,db:Database)->ApiResponse[WarningEventData]:return ApiResponse(data=warning_service.change_warning_status(db,warning_id,"dismissed",request.operator,request.reason))
