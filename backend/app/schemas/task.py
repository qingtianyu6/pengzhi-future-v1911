from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


TaskSourceType = Literal["warning", "disease_review", "recommendation", "manual"]
TaskStatus = Literal["draft", "pending", "in_progress", "completed", "cancelled"]
TaskPriority = Literal["low", "medium", "high", "urgent"]
FeedbackResult = Literal["resolved", "improved", "no_change", "worsened", "unable_to_verify"]


class ManualTaskCreate(BaseModel):
    greenhouse_id: int = Field(gt=0)
    crop_batch_id: int | None = Field(default=None, gt=0)
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=3000)
    action_type: str = Field(min_length=1, max_length=60)
    priority: TaskPriority = "medium"
    planned_start_at: datetime | None = None
    due_at: datetime | None = None
    created_by: str = Field(min_length=1, max_length=60)
    safety_note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def dates_in_order(self):
        if self.planned_start_at and self.due_at and self.planned_start_at > self.due_at:
            raise ValueError("计划开始时间不能晚于截止时间")
        return self


class SourceTaskCreate(BaseModel):
    created_by: str = Field(min_length=1, max_length=60)
    action_type: str | None = Field(default=None, min_length=1, max_length=60)
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, min_length=1, max_length=3000)
    priority: TaskPriority | None = None
    planned_start_at: datetime | None = None
    due_at: datetime | None = None

    @model_validator(mode="after")
    def dates_in_order(self):
        if self.planned_start_at and self.due_at and self.planned_start_at > self.due_at:
            raise ValueError("计划开始时间不能晚于截止时间")
        return self


class VersionedAction(BaseModel):
    version: int = Field(ge=1)
    operator: str = Field(min_length=1, max_length=60)
    note: str | None = Field(default=None, max_length=1000)


class AssignTaskRequest(VersionedAction):
    assignee_name: str = Field(min_length=1, max_length=60)


class CancelTaskRequest(VersionedAction):
    reason: str = Field(min_length=1, max_length=1000)


class ReopenTaskRequest(VersionedAction):
    reason: str = Field(min_length=1, max_length=1000)


class FeedbackPayload(BaseModel):
    operator: str = Field(min_length=1, max_length=60)
    executed_at: datetime
    result_type: FeedbackResult
    execution_note: str = Field(min_length=1, max_length=3000)
    observed_change: str | None = Field(default=None, max_length=2000)
    requires_follow_up: bool = False
    follow_up_note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def follow_up_has_note(self):
        if self.requires_follow_up and not self.follow_up_note:
            raise ValueError("需要后续跟进时必须填写说明")
        return self


class AddFeedbackRequest(FeedbackPayload):
    version: int = Field(ge=1)


class CompleteTaskRequest(FeedbackPayload):
    version: int = Field(ge=1)


class TaskEventData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    event_type: str
    from_status: str | None
    to_status: str | None
    operator: str
    note: str | None
    payload_json: dict[str, Any]
    created_at: datetime


class TaskFeedbackData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    operator: str
    executed_at: datetime
    result_type: FeedbackResult
    execution_note: str
    observed_change: str | None
    attachment_paths_json: list[str]
    environment_snapshot_json: dict[str, Any]
    requires_follow_up: bool
    follow_up_note: str | None
    created_at: datetime
    updated_at: datetime


class FarmTaskData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_code: str
    greenhouse_id: int
    crop_batch_id: int | None
    crop_type: str
    source_type: TaskSourceType
    source_id: int | None
    source_warning_id: int | None
    source_disease_record_id: int | None
    source_recommendation_id: int | None
    title: str
    description: str
    action_type: str
    priority: TaskPriority
    status: TaskStatus
    assignee_name: str | None
    planned_start_at: datetime | None
    due_at: datetime | None
    requires_manual_confirmation: bool
    safety_note: str
    evidence_snapshot_json: dict[str, Any]
    result_snapshot_json: dict[str, Any] | None
    version: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    cancellation_reason: str | None


class TaskDetailData(FarmTaskData):
    greenhouse: dict[str, Any]
    crop_batch: dict[str, Any] | None
    source_warning: dict[str, Any] | None
    source_disease_record: dict[str, Any] | None
    source_recommendation: dict[str, Any] | None
    events: list[TaskEventData]
    feedbacks: list[TaskFeedbackData]
    attachments: list[str]
    causality_notice: str = "前后变化只用于记录，不代表任务操作与环境改善存在已验证因果关系。"


class TaskSummaryData(BaseModel):
    draft_total: int
    pending_total: int
    in_progress_total: int
    completed_today: int
    overdue_total: int
    urgent_total: int


class TaskTraceNode(BaseModel):
    type: str
    id: int | str | None
    title: str
    status: str
    occurred_at: datetime | None
    source: str | None
    version: str | int | None
    summary: str


class TaskTraceData(BaseModel):
    task_id: int
    nodes: list[TaskTraceNode]
    causality_notice: str = "前后变化只用于记录，不代表任务操作与环境改善存在已验证因果关系。"

