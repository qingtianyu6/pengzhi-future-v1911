from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ApiResponse, PaginatedData
from app.schemas.task import (AddFeedbackRequest, AssignTaskRequest, CancelTaskRequest,
                              CompleteTaskRequest, FarmTaskData, ManualTaskCreate,
                              ReopenTaskRequest, SourceTaskCreate, TaskDetailData, TaskEventData,
                              TaskFeedbackData, TaskSummaryData, TaskTraceData, VersionedAction)
from app.services import task_service


router = APIRouter(prefix="/tasks", tags=["农事任务与反馈"])
Database = Annotated[Session, Depends(get_db)]


@router.get("/summary", response_model=ApiResponse[TaskSummaryData], summary="任务摘要")
def get_task_summary(db: Database, greenhouse_id: int | None = Query(default=None, gt=0)):
    return ApiResponse(data=task_service.task_summary(db, greenhouse_id))


@router.get("", response_model=ApiResponse[PaginatedData[FarmTaskData]], summary="分页查询任务")
def get_tasks(
    db: Database, greenhouse_id: int | None = Query(default=None, gt=0),
    crop_batch_id: int | None = Query(default=None, gt=0),
    source_type: Literal["warning", "disease_review", "recommendation", "manual"] | None = None,
    status: Literal["draft", "pending", "in_progress", "completed", "cancelled"] | None = None,
    priority: Literal["low", "medium", "high", "urgent"] | None = None,
    assignee_name: str | None = Query(default=None, max_length=60),
    start_time: datetime | None = None, end_time: datetime | None = None,
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
):
    return ApiResponse(data=task_service.list_tasks(
        db, greenhouse_id=greenhouse_id, crop_batch_id=crop_batch_id, source_type=source_type,
        status=status, priority=priority, assignee_name=assignee_name, start_time=start_time,
        end_time=end_time, page=page, page_size=page_size,
    ))


@router.post("", response_model=ApiResponse[FarmTaskData], summary="手工创建任务草稿")
def create_task(payload: ManualTaskCreate, db: Database):
    return ApiResponse(message="任务草稿已创建，提交后进入待执行", data=task_service.create_manual_task(db, payload))


@router.post("/from-warning/{warning_id}", response_model=ApiResponse[FarmTaskData],
             summary="从活动预警人工生成任务草稿")
def create_task_from_warning(warning_id: int, payload: SourceTaskCreate, db: Database):
    return ApiResponse(message="预警任务草稿已创建，尚未执行", data=task_service.create_from_warning(db, warning_id, payload))


@router.post("/from-disease/{record_id}", response_model=ApiResponse[FarmTaskData],
             summary="从已审核病害记录人工生成任务草稿")
def create_task_from_disease(record_id: int, payload: SourceTaskCreate, db: Database):
    return ApiResponse(message="现场复核任务草稿已创建，尚未执行", data=task_service.create_from_disease(db, record_id, payload))


@router.get("/{task_id}", response_model=ApiResponse[TaskDetailData], summary="任务详情与完整证据")
def get_task(task_id: int, db: Database):
    return ApiResponse(data=task_service.get_task_detail(db, task_id))


@router.get("/{task_id}/events", response_model=ApiResponse[list[TaskEventData]], summary="追加式生命周期")
def get_task_events(task_id: int, db: Database):
    return ApiResponse(data=task_service.list_events(db, task_id))


@router.get("/{task_id}/trace", response_model=ApiResponse[TaskTraceData], summary="跨模块证据链")
def get_task_trace(task_id: int, db: Database):
    return ApiResponse(data=task_service.get_task_trace(db, task_id))


@router.post("/{task_id}/submit", response_model=ApiResponse[FarmTaskData], summary="人工确认并提交任务")
def submit_task(task_id: int, payload: VersionedAction, db: Database):
    return ApiResponse(message="任务已提交，等待执行", data=task_service.submit_task(db, task_id, payload))


@router.post("/{task_id}/assign", response_model=ApiResponse[FarmTaskData], summary="分配负责人")
def assign_task(task_id: int, payload: AssignTaskRequest, db: Database):
    return ApiResponse(message="负责人已更新", data=task_service.assign_task(db, task_id, payload))


@router.post("/{task_id}/start", response_model=ApiResponse[FarmTaskData], summary="开始执行")
def start_task(task_id: int, payload: VersionedAction, db: Database):
    return ApiResponse(message="任务已开始执行", data=task_service.start_task(db, task_id, payload))


@router.post("/{task_id}/feedback", response_model=ApiResponse[TaskFeedbackData], summary="添加执行反馈与安全附件")
async def add_task_feedback(
    task_id: int, db: Database,
    version: Annotated[int, Form(ge=1)], operator: Annotated[str, Form(min_length=1, max_length=60)],
    executed_at: Annotated[datetime, Form()],
    result_type: Annotated[Literal["resolved", "improved", "no_change", "worsened", "unable_to_verify"], Form()],
    execution_note: Annotated[str, Form(min_length=1, max_length=3000)],
    observed_change: Annotated[str | None, Form(max_length=2000)] = None,
    requires_follow_up: Annotated[bool, Form()] = False,
    follow_up_note: Annotated[str | None, Form(max_length=2000)] = None,
    attachments: Annotated[list[UploadFile] | None, File(description="可选 JPG/PNG/WEBP，每张最大10MB")] = None,
):
    uploads = []
    for item in attachments or []:
        content = await item.read(task_service.MAX_UPLOAD_BYTES + 1)
        await item.close()
        uploads.append((item.filename or "attachment", item.content_type, content))
    payload = AddFeedbackRequest(
        version=version, operator=operator, executed_at=executed_at, result_type=result_type,
        execution_note=execution_note, observed_change=observed_change,
        requires_follow_up=requires_follow_up, follow_up_note=follow_up_note,
    )
    return ApiResponse(message="执行反馈已追加", data=task_service.add_feedback(db, task_id, payload, uploads))


@router.post("/{task_id}/complete", response_model=ApiResponse[FarmTaskData], summary="完成任务并提交必填反馈")
def complete_task(task_id: int, payload: CompleteTaskRequest, db: Database):
    return ApiResponse(message="任务已完成；不会自动解除来源预警", data=task_service.complete_task(db, task_id, payload))


@router.post("/{task_id}/cancel", response_model=ApiResponse[FarmTaskData], summary="有理由地取消任务")
def cancel_task(task_id: int, payload: CancelTaskRequest, db: Database):
    return ApiResponse(message="任务已取消并保留历史", data=task_service.cancel_task(db, task_id, payload))


@router.post("/{task_id}/reopen", response_model=ApiResponse[FarmTaskData], summary="有理由地重新打开已完成任务")
def reopen_task(task_id: int, payload: ReopenTaskRequest, db: Database):
    return ApiResponse(message="任务已重新打开", data=task_service.reopen_task(db, task_id, payload))

