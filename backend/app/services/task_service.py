from __future__ import annotations

from datetime import UTC, datetime, timezone
import io
from pathlib import Path
import uuid
import warnings
from typing import Any

from fastapi.encoders import jsonable_encoder
from PIL import Image, UnidentifiedImageError
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import BACKEND_DIR
from app.models import (CropBatch, DecisionRecommendation, DiseaseRecognitionRecord, FarmTask,
                        Greenhouse, SensorData, TaskEvent, TaskFeedback, WarningEvent)
from app.schemas.common import PaginatedData
from app.schemas.task import (AddFeedbackRequest, AssignTaskRequest, CancelTaskRequest,
                              CompleteTaskRequest, FarmTaskData, ManualTaskCreate,
                              ReopenTaskRequest, SourceTaskCreate, TaskDetailData, TaskEventData,
                              TaskFeedbackData, TaskSummaryData, TaskTraceData, TaskTraceNode,
                              VersionedAction)
from app.services.errors import ServiceError
from app.services.prediction_service import predict_environment
from app.services.risk_service import assess_current_risk
from app.services.sensor_service import to_sensor_view


SAFE_ACTION_TYPES = {
    "ventilation_check", "shading_check", "heating_check", "humidity_control",
    "condensation_inspection", "irrigation_check", "sensor_inspection", "manual_observation",
    "expert_review", "field_inspection", "sample_collection", "isolation_check",
}
DISEASE_ACTION_TYPES = {
    "field_inspection", "sample_collection", "expert_review", "manual_observation",
    "isolation_check",
}
FORBIDDEN_ACTION_TOKENS = {
    "automatic_spraying", "pesticide_dosage", "device_control", "自动施药", "农药剂量",
    "设备控制",
}
ACTIVE_STATUSES = {"draft", "pending", "in_progress"}
UPLOAD_DIR = BACKEND_DIR / "uploads" / "tasks"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 50_000_000
ALLOWED_EXTENSIONS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
DEFAULT_SAFETY_NOTE = (
    "任务必须由人员现场确认并执行；系统不自动施药、不提供农药剂量，也不控制设备。"
)
CAUSALITY_NOTICE = "前后变化只用于记录，不代表任务操作与环境改善存在已验证因果关系。"


def _now() -> datetime:
    return datetime.now(UTC)


def _naive_utc(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


def _safe_action(action_type: str, *, disease: bool = False) -> str:
    normalized = action_type.strip()
    allowed = DISEASE_ACTION_TYPES if disease else SAFE_ACTION_TYPES
    if normalized not in allowed or any(token in normalized for token in FORBIDDEN_ACTION_TOKENS):
        raise ServiceError(422, "任务动作不在人工安全操作白名单内")
    return normalized


def _context(db: Session, greenhouse_id: int, crop_batch_id: int | None) -> tuple[Greenhouse, CropBatch]:
    greenhouse = db.get(Greenhouse, greenhouse_id)
    if greenhouse is None:
        raise ServiceError(404, "大棚不存在")
    batch = db.get(CropBatch, crop_batch_id) if crop_batch_id else db.scalar(
        select(CropBatch).where(CropBatch.greenhouse_id == greenhouse_id,
                                CropBatch.status == "growing")
    )
    if batch is None or batch.greenhouse_id != greenhouse_id:
        raise ServiceError(404, "该大棚下不存在有效种植批次")
    return greenhouse, batch


def _snapshot(db: Session, greenhouse: Greenhouse, batch: CropBatch, *,
              warning: WarningEvent | None = None,
              disease: DiseaseRecognitionRecord | None = None) -> dict[str, Any]:
    latest = db.scalar(
        select(SensorData).where(SensorData.greenhouse_id == greenhouse.id)
        .order_by(SensorData.recorded_at.desc()).limit(1)
    )
    latest_view = to_sensor_view(latest) if latest else None
    current_risk = assess_current_risk(latest_view, batch.growth_stage, batch.crop_type)
    prediction = predict_environment(db, greenhouse.id, 6)
    model_or_rule_version = (
        warning.rule_version if warning else disease.model_version if disease else current_risk.rule_version
    )
    return jsonable_encoder({
        "snapshot_status": "complete" if latest else "insufficient_data",
        "latest_sensor_data": latest_view,
        "current_risk": current_risk,
        "forecast_summary": {
            "status": prediction.status,
            "forecast_service_status": prediction.forecast_service_status,
            "model_status": prediction.model_status,
            "model_version": prediction.model_version,
            "predictions": prediction.predictions,
            "warnings": prediction.warnings,
        },
        "warning_evidence": warning.evidence_json if warning else None,
        "disease_review": ({
            "record_id": disease.id,
            "recognition_status": ("review_required" if disease.recognition_status == "recognized"
                                   and disease.model_status == "under_evaluation"
                                   else disease.recognition_status),
            "review_status": disease.review_status,
            "reviewed_class": disease.reviewed_class,
            "model_status": disease.model_status,
        } if disease else None),
        "model_or_rule_version": model_or_rule_version,
        "data_source": latest.source if latest else None,
        "recorded_at": latest_view.recorded_at if latest_view else None,
        "captured_at": _now(),
        "causality_notice": CAUSALITY_NOTICE,
    })


def _task_code() -> str:
    return f"TASK-{_now():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def _event(db: Session, task: FarmTask, event_type: str, operator: str, *,
           from_status: str | None = None, to_status: str | None = None,
           note: str | None = None, payload: dict[str, Any] | None = None) -> TaskEvent:
    record = TaskEvent(task_id=task.id, event_type=event_type, from_status=from_status,
                       to_status=to_status, operator=operator, note=note,
                       payload_json=jsonable_encoder(payload or {}))
    db.add(record)
    return record


def _ensure_not_duplicate(db: Session, source_type: str, source_id: int | None,
                          action_type: str) -> None:
    if source_id is None:
        return
    existing = db.scalar(select(FarmTask.id).where(
        FarmTask.source_type == source_type, FarmTask.source_id == source_id,
        FarmTask.action_type == action_type, FarmTask.status.in_(ACTIVE_STATUSES),
    ).limit(1))
    if existing is not None:
        raise ServiceError(409, f"同一来源和动作已有活动任务：{existing}")


def _create(db: Session, *, greenhouse: Greenhouse, batch: CropBatch, source_type: str,
            source_id: int | None, source_warning_id: int | None,
            source_disease_record_id: int | None, source_recommendation_id: int | None,
            title: str, description: str, action_type: str, priority: str,
            planned_start_at: datetime | None, due_at: datetime | None, created_by: str,
            safety_note: str, warning: WarningEvent | None = None,
            disease: DiseaseRecognitionRecord | None = None) -> FarmTaskData:
    _ensure_not_duplicate(db, source_type, source_id, action_type)
    task = FarmTask(
        task_code=_task_code(), greenhouse_id=greenhouse.id, crop_batch_id=batch.id,
        crop_type=batch.crop_type, source_type=source_type, source_id=source_id,
        source_warning_id=source_warning_id,
        source_disease_record_id=source_disease_record_id,
        source_recommendation_id=source_recommendation_id,
        title=title, description=description, action_type=action_type, priority=priority,
        status="draft", planned_start_at=planned_start_at, due_at=due_at,
        requires_manual_confirmation=True, safety_note=safety_note,
        evidence_snapshot_json=_snapshot(db, greenhouse, batch, warning=warning, disease=disease),
        version=1, created_by=created_by,
    )
    db.add(task)
    db.flush()
    _event(db, task, "created", created_by, to_status="draft", note="任务草稿已创建",
           payload={"source_type": source_type, "source_id": source_id,
                    "requires_manual_confirmation": True})
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ServiceError(409, "同一来源和动作已有活动任务") from exc
    db.refresh(task)
    return FarmTaskData.model_validate(task)


def create_manual_task(db: Session, payload: ManualTaskCreate) -> FarmTaskData:
    greenhouse, batch = _context(db, payload.greenhouse_id, payload.crop_batch_id)
    action = _safe_action(payload.action_type)
    return _create(
        db, greenhouse=greenhouse, batch=batch, source_type="manual", source_id=None,
        source_warning_id=None, source_disease_record_id=None, source_recommendation_id=None,
        title=payload.title, description=payload.description, action_type=action,
        priority=payload.priority, planned_start_at=payload.planned_start_at,
        due_at=payload.due_at, created_by=payload.created_by,
        safety_note=payload.safety_note or DEFAULT_SAFETY_NOTE,
    )


def create_from_warning(db: Session, warning_id: int, payload: SourceTaskCreate) -> FarmTaskData:
    warning = db.get(WarningEvent, warning_id)
    if warning is None:
        raise ServiceError(404, "预警不存在")
    if warning.status not in {"open", "acknowledged"}:
        raise ServiceError(422, "只有待处理或已确认预警可以生成任务草稿")
    recommendation = db.scalar(
        select(DecisionRecommendation).where(
            DecisionRecommendation.warning_event_id == warning.id,
            DecisionRecommendation.status.in_(["pending_review", "accepted"]),
        ).order_by(DecisionRecommendation.id).limit(1)
    )
    if recommendation is None:
        raise ServiceError(422, "预警尚无结构化建议，不能生成任务")
    greenhouse, batch = _context(db, warning.greenhouse_id, warning.crop_batch_id)
    action = _safe_action(payload.action_type or recommendation.action_type)
    return _create(
        db, greenhouse=greenhouse, batch=batch, source_type="warning", source_id=warning.id,
        source_warning_id=warning.id, source_disease_record_id=None,
        source_recommendation_id=recommendation.id,
        title=payload.title or recommendation.title,
        description=payload.description or "；".join(recommendation.action_steps_json),
        action_type=action, priority=payload.priority or recommendation.priority,
        planned_start_at=payload.planned_start_at, due_at=payload.due_at or recommendation.execute_before,
        created_by=payload.created_by, safety_note=recommendation.safety_note,
        warning=warning,
    )


def create_from_disease(db: Session, record_id: int, payload: SourceTaskCreate) -> FarmTaskData:
    record = db.get(DiseaseRecognitionRecord, record_id)
    if record is None:
        raise ServiceError(404, "病害识别记录不存在")
    if record.crop_type != "tomato":
        raise ServiceError(422, "非番茄病害记录不能使用番茄候选结果创建任务")
    if record.review_status not in {"confirmed", "corrected"}:
        raise ServiceError(422, "只有人工确认或修正后的病害记录可以生成任务")
    if record.review_status == "confirmed" and record.recognition_status != "recognized":
        raise ServiceError(422, "低置信度记录不能直接确认后生成任务")
    action = _safe_action(payload.action_type or "field_inspection", disease=True)
    greenhouse, batch = _context(db, record.greenhouse_id, record.crop_batch_id)
    reviewed_label = record.reviewed_class or record.predicted_class or "未确定类别"
    return _create(
        db, greenhouse=greenhouse, batch=batch, source_type="disease_review", source_id=record.id,
        source_warning_id=None, source_disease_record_id=record.id,
        source_recommendation_id=None,
        title=payload.title or f"番茄叶片候选结果现场复核：{reviewed_label}",
        description=payload.description or "现场观察叶片、记录症状；必要时取样并联系农技专家。",
        action_type=action, priority=payload.priority or "high",
        planned_start_at=payload.planned_start_at, due_at=payload.due_at,
        created_by=payload.created_by, safety_note=DEFAULT_SAFETY_NOTE,
        disease=record,
    )


def list_tasks(db: Session, *, greenhouse_id: int | None, crop_batch_id: int | None,
               source_type: str | None, status: str | None, priority: str | None,
               assignee_name: str | None, start_time: datetime | None, end_time: datetime | None,
               page: int, page_size: int) -> PaginatedData[FarmTaskData]:
    filters = []
    if greenhouse_id is not None:
        filters.append(FarmTask.greenhouse_id == greenhouse_id)
    if crop_batch_id is not None:
        filters.append(FarmTask.crop_batch_id == crop_batch_id)
    if source_type:
        filters.append(FarmTask.source_type == source_type)
    if status:
        filters.append(FarmTask.status == status)
    if priority:
        filters.append(FarmTask.priority == priority)
    if assignee_name:
        filters.append(FarmTask.assignee_name.contains(assignee_name))
    if start_time:
        filters.append(FarmTask.created_at >= _naive_utc(start_time))
    if end_time:
        filters.append(FarmTask.created_at <= _naive_utc(end_time))
    total = int(db.scalar(select(func.count()).select_from(FarmTask).where(*filters)) or 0)
    records = list(db.scalars(
        select(FarmTask).where(*filters).order_by(FarmTask.created_at.desc(), FarmTask.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ))
    return PaginatedData(items=[FarmTaskData.model_validate(item) for item in records],
                         total=total, page=page, page_size=page_size)


def task_summary(db: Session, greenhouse_id: int | None = None) -> TaskSummaryData:
    filters = [FarmTask.greenhouse_id == greenhouse_id] if greenhouse_id else []
    now = _now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None)

    def count(*extra: Any) -> int:
        return int(db.scalar(select(func.count()).select_from(FarmTask).where(*filters, *extra)) or 0)

    return TaskSummaryData(
        draft_total=count(FarmTask.status == "draft"),
        pending_total=count(FarmTask.status == "pending"),
        in_progress_total=count(FarmTask.status == "in_progress"),
        completed_today=count(FarmTask.status == "completed", FarmTask.completed_at >= today),
        overdue_total=count(FarmTask.status.in_(["pending", "in_progress"]),
                            FarmTask.due_at.is_not(None), FarmTask.due_at < now.replace(tzinfo=None)),
        urgent_total=count(FarmTask.status.in_(ACTIVE_STATUSES), FarmTask.priority == "urgent"),
    )


def _load_task(db: Session, task_id: int, *, relationships: bool = False) -> FarmTask:
    query = select(FarmTask).where(FarmTask.id == task_id)
    if relationships:
        query = query.options(
            selectinload(FarmTask.events), selectinload(FarmTask.feedbacks),
            selectinload(FarmTask.greenhouse), selectinload(FarmTask.crop_batch),
            selectinload(FarmTask.source_warning), selectinload(FarmTask.source_disease_record),
            selectinload(FarmTask.source_recommendation),
        )
    task = db.scalar(query)
    if task is None:
        raise ServiceError(404, "农事任务不存在")
    return task


def _source_warning_data(item: WarningEvent | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return jsonable_encoder({"id": item.id, "title": item.title, "status": item.status,
                             "severity": item.severity, "risk_score": item.risk_score,
                             "rule_version": item.rule_version, "evidence": item.evidence_json,
                             "data_source": item.data_source, "created_at": item.created_at})


def _source_disease_data(item: DiseaseRecognitionRecord | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return jsonable_encoder({"id": item.id, "recognition_status": (
        "review_required" if item.recognition_status == "recognized"
        and item.model_status == "under_evaluation" else item.recognition_status),
        "predicted_class": item.predicted_class, "confidence": item.confidence,
        "review_status": item.review_status, "reviewed_class": item.reviewed_class,
        "review_note": item.review_note, "model_version": item.model_version,
        "model_status": item.model_status, "image_path": item.image_path,
        "created_at": item.created_at})


def _source_recommendation_data(item: DecisionRecommendation | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return jsonable_encoder({"id": item.id, "title": item.title, "status": item.status,
                             "action_type": item.action_type, "steps": item.action_steps_json,
                             "rationale": item.rationale, "safety_note": item.safety_note,
                             "rule_version": item.rule_version, "generated_at": item.generated_at})


def get_task_detail(db: Session, task_id: int) -> TaskDetailData:
    task = _load_task(db, task_id, relationships=True)
    base = FarmTaskData.model_validate(task).model_dump()
    attachments = [path for feedback in task.feedbacks for path in feedback.attachment_paths_json]
    return TaskDetailData(
        **base,
        greenhouse=jsonable_encoder({"id": task.greenhouse.id, "code": task.greenhouse.code,
                                     "name": task.greenhouse.name, "location": task.greenhouse.location}),
        crop_batch=jsonable_encoder({"id": task.crop_batch.id, "batch_code": task.crop_batch.batch_code,
                                    "crop_type": task.crop_batch.crop_type,
                                    "growth_stage": task.crop_batch.growth_stage}) if task.crop_batch else None,
        source_warning=_source_warning_data(task.source_warning),
        source_disease_record=_source_disease_data(task.source_disease_record),
        source_recommendation=_source_recommendation_data(task.source_recommendation),
        events=[TaskEventData.model_validate(item) for item in task.events],
        feedbacks=[TaskFeedbackData.model_validate(item) for item in task.feedbacks],
        attachments=attachments,
    )


def _check_version(task: FarmTask, version: int) -> None:
    if task.version != version:
        raise ServiceError(409, f"任务已被其他操作更新，当前版本为 {task.version}")


def _transition(db: Session, task_id: int, payload: VersionedAction, *, expected: set[str],
                target: str, event_type: str) -> FarmTaskData:
    task = _load_task(db, task_id)
    _check_version(task, payload.version)
    if task.status not in expected:
        raise ServiceError(409, f"不允许从 {task.status} 迁移到 {target}")
    previous = task.status
    task.status = target
    task.version += 1
    if target == "in_progress":
        task.started_at = _now()
    _event(db, task, event_type, payload.operator, from_status=previous, to_status=target,
           note=payload.note)
    db.commit()
    db.refresh(task)
    return FarmTaskData.model_validate(task)


def submit_task(db: Session, task_id: int, payload: VersionedAction) -> FarmTaskData:
    return _transition(db, task_id, payload, expected={"draft"}, target="pending",
                       event_type="submitted")


def assign_task(db: Session, task_id: int, payload: AssignTaskRequest) -> FarmTaskData:
    task = _load_task(db, task_id)
    _check_version(task, payload.version)
    if task.status not in {"pending", "in_progress"}:
        raise ServiceError(409, "只有待执行或执行中的任务可以分配")
    previous_assignee = task.assignee_name
    task.assignee_name = payload.assignee_name
    task.version += 1
    _event(db, task, "assigned", payload.operator, from_status=task.status,
           to_status=task.status, note=payload.note,
           payload={"previous_assignee": previous_assignee,
                    "assignee_name": payload.assignee_name})
    db.commit()
    db.refresh(task)
    return FarmTaskData.model_validate(task)


def start_task(db: Session, task_id: int, payload: VersionedAction) -> FarmTaskData:
    return _transition(db, task_id, payload, expected={"pending"}, target="in_progress",
                       event_type="started")


def _decode_attachment(filename: str, content_type: str | None, content: bytes) -> Image.Image:
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise ServiceError(413 if content else 422, "反馈附件为空或超过10MB")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS or content_type not in ALLOWED_MIME:
        raise ServiceError(415, "反馈附件仅支持 JPG、JPEG、PNG 和 WEBP")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as probe:
                probe.verify()
            image = Image.open(io.BytesIO(content)); image.load()
            if image.width * image.height > MAX_PIXELS:
                raise ServiceError(413, "反馈附件像素过大")
            if image.format != ALLOWED_EXTENSIONS[suffix]:
                raise ServiceError(415, "反馈附件扩展名与真实格式不一致")
            return image.convert("RGB")
    except ServiceError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise ServiceError(422, "反馈附件损坏或无法安全解码") from exc


def _save_attachments(task: FarmTask,
                      attachments: list[tuple[str, str | None, bytes]]) -> list[str]:
    decoded = [(filename, _decode_attachment(filename, content_type, content))
               for filename, content_type, content in attachments]
    if not decoded:
        return []
    target = UPLOAD_DIR / task.task_code
    target.mkdir(parents=True, exist_ok=True)
    paths = []
    for _filename, image in decoded:
        path = target / f"{uuid.uuid4().hex}.jpg"
        image.save(path, format="JPEG", quality=92, optimize=True, exif=b"")
        paths.append(f"uploads/tasks/{task.task_code}/{path.name}")
    return paths


def _feedback(db: Session, task: FarmTask, payload: AddFeedbackRequest | CompleteTaskRequest,
              attachments: list[tuple[str, str | None, bytes]]) -> TaskFeedback:
    paths = _save_attachments(task, attachments)
    snapshot = _snapshot(db, task.greenhouse, task.crop_batch,
                         warning=task.source_warning, disease=task.source_disease_record)
    record = TaskFeedback(
        task_id=task.id, operator=payload.operator, executed_at=payload.executed_at,
        result_type=payload.result_type, execution_note=payload.execution_note,
        observed_change=payload.observed_change, attachment_paths_json=paths,
        environment_snapshot_json=snapshot, requires_follow_up=payload.requires_follow_up,
        follow_up_note=payload.follow_up_note,
    )
    db.add(record)
    db.flush()
    return record


def add_feedback(db: Session, task_id: int, payload: AddFeedbackRequest,
                 attachments: list[tuple[str, str | None, bytes]] | None = None) -> TaskFeedbackData:
    task = _load_task(db, task_id, relationships=True)
    _check_version(task, payload.version)
    if task.status != "in_progress":
        raise ServiceError(409, "只有执行中的任务可以添加反馈")
    feedback = _feedback(db, task, payload, attachments or [])
    task.version += 1
    _event(db, task, "feedback_added", payload.operator, from_status=task.status,
           to_status=task.status, note=payload.execution_note,
           payload={"feedback_id": feedback.id, "result_type": payload.result_type,
                    "attachment_count": len(feedback.attachment_paths_json)})
    db.commit()
    db.refresh(feedback)
    return TaskFeedbackData.model_validate(feedback)


def complete_task(db: Session, task_id: int, payload: CompleteTaskRequest) -> FarmTaskData:
    task = _load_task(db, task_id, relationships=True)
    _check_version(task, payload.version)
    if task.status != "in_progress":
        raise ServiceError(409, "只有执行中的任务可以完成")
    feedback = _feedback(db, task, payload, [])
    previous = task.status
    task.status = "completed"
    task.completed_at = _now()
    task.result_snapshot_json = feedback.environment_snapshot_json
    task.version += 1
    _event(db, task, "feedback_added", payload.operator, from_status=previous, to_status=previous,
           note=payload.execution_note,
           payload={"feedback_id": feedback.id, "result_type": payload.result_type})
    _event(db, task, "completed", payload.operator, from_status=previous, to_status="completed",
           note="任务已完成人工反馈；预警状态未自动修改",
           payload={"feedback_id": feedback.id, "warning_auto_resolved": False})
    db.commit()
    db.refresh(task)
    return FarmTaskData.model_validate(task)


def cancel_task(db: Session, task_id: int, payload: CancelTaskRequest) -> FarmTaskData:
    task = _load_task(db, task_id)
    _check_version(task, payload.version)
    if task.status not in {"pending", "in_progress"}:
        raise ServiceError(409, "只有待执行或执行中的任务可以取消")
    previous = task.status
    task.status = "cancelled"
    task.cancelled_at = _now()
    task.cancellation_reason = payload.reason
    task.version += 1
    _event(db, task, "cancelled", payload.operator, from_status=previous, to_status="cancelled",
           note=payload.reason)
    db.commit(); db.refresh(task)
    return FarmTaskData.model_validate(task)


def reopen_task(db: Session, task_id: int, payload: ReopenTaskRequest) -> FarmTaskData:
    task = _load_task(db, task_id)
    _check_version(task, payload.version)
    if task.status != "completed":
        raise ServiceError(409, "只有已完成任务可以重新打开")
    task.status = "pending"
    task.completed_at = None
    task.version += 1
    _event(db, task, "reopened", payload.operator, from_status="completed", to_status="pending",
           note=payload.reason, payload={"previous_result_snapshot": task.result_snapshot_json})
    db.commit(); db.refresh(task)
    return FarmTaskData.model_validate(task)


def list_events(db: Session, task_id: int) -> list[TaskEventData]:
    _load_task(db, task_id)
    records = list(db.scalars(select(TaskEvent).where(TaskEvent.task_id == task_id)
                             .order_by(TaskEvent.id)))
    return [TaskEventData.model_validate(item) for item in records]


def _trace_node(node_type: str, payload: dict[str, Any] | None, *, title: str,
                status: str = "available", source: str | None = None,
                version: str | int | None = None, summary: str | None = None) -> TaskTraceNode:
    if not payload:
        return TaskTraceNode(type=node_type, id=None, title=title, status="missing",
                             occurred_at=None, source=None, version=None,
                             summary="该环节暂无记录")
    return TaskTraceNode(
        type=node_type, id=payload.get("id"), title=title, status=status,
        occurred_at=payload.get("occurred_at") or payload.get("created_at")
        or payload.get("recorded_at"), source=source or payload.get("source"),
        version=version, summary=summary or payload.get("summary") or title,
    )


def get_task_trace(db: Session, task_id: int) -> TaskTraceData:
    task = _load_task(db, task_id, relationships=True)
    snapshot = task.evidence_snapshot_json or {}
    sensor = snapshot.get("latest_sensor_data")
    forecast = snapshot.get("forecast_summary")
    risk = snapshot.get("current_risk")
    warning = _source_warning_data(task.source_warning)
    recommendation = _source_recommendation_data(task.source_recommendation)
    disease = _source_disease_data(task.source_disease_record)
    nodes = [
        _trace_node("environment_record", sensor, title="环境记录",
                    status=(sensor or {}).get("quality_flag", "available") if sensor else "missing",
                    source=(sensor or {}).get("source"),
                    summary=(f"温度 {(sensor or {}).get('temperature')}℃，湿度 "
                             f"{(sensor or {}).get('air_humidity')}%RH") if sensor else None),
        _trace_node("environment_prediction", {"id": None, "created_at": snapshot.get("captured_at")}
                    if forecast and forecast.get("status") else None, title="环境预测",
                    status=(forecast or {}).get("status", "missing"),
                    version=(forecast or {}).get("model_version"),
                    summary=f"预测状态：{(forecast or {}).get('status')}" if forecast else None),
        _trace_node("risk_assessment", {"id": None, "created_at": snapshot.get("captured_at")}
                    if risk else None, title="风险评估",
                    status=(risk or {}).get("level", "missing"),
                    version=(risk or {}).get("rule_version"),
                    summary=f"综合风险：{(risk or {}).get('level')}" if risk else None),
        _trace_node("warning_event", warning, title="预警事件",
                    status=(warning or {}).get("status", "missing"),
                    source=(warning or {}).get("data_source"),
                    version=(warning or {}).get("rule_version"),
                    summary=(warning or {}).get("title")),
        _trace_node("decision_recommendation", recommendation, title="决策建议",
                    status=(recommendation or {}).get("status", "missing"),
                    version=(recommendation or {}).get("rule_version"),
                    summary=(recommendation or {}).get("title")),
        _trace_node("disease_review", disease, title="病害人工复核",
                    status=(disease or {}).get("review_status", "missing"),
                    version=(disease or {}).get("model_version"),
                    summary=(f"人工复核类别：{(disease or {}).get('reviewed_class')}"
                             if disease else None)),
        TaskTraceNode(type="farm_task", id=task.id, title=task.title, status=task.status,
                      occurred_at=task.created_at, source=task.source_type, version=task.version,
                      summary=f"{task.task_code} · {task.action_type}"),
    ]
    if task.feedbacks:
        nodes.extend(TaskTraceNode(
            type="execution_feedback", id=item.id, title="执行反馈", status=item.result_type,
            occurred_at=item.executed_at, source="manual", version=None,
            summary=item.execution_note,
        ) for item in task.feedbacks)
    else:
        nodes.append(_trace_node("execution_feedback", None, title="执行反馈"))
    return TaskTraceData(task_id=task.id, nodes=nodes)

