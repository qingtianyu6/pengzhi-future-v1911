from __future__ import annotations

from typing import Any, Callable

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AIToolCall, CropBatch, FarmTask, Greenhouse, SensorData, WarningEvent
from app.services.knowledge_service import search_knowledge
from app.services.prediction_service import predict_environment
from app.services.sensor_service import VALID_BUSINESS_SOURCES


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_agriculture_knowledge",
            "description": "检索棚智未来本地农业知识库，返回公开技术资料整理后的知识要点和来源",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_environment",
            "description": "只读查询目标大棚最新环境数据、时间、质量和来源",
            "parameters": {"type": "object", "properties": {"greenhouse_id": {"type": "integer"}}, "required": ["greenhouse_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_future_prediction",
            "description": "只读查询目标大棚未来六小时环境预测及模型状态",
            "parameters": {"type": "object", "properties": {"greenhouse_id": {"type": "integer"}}, "required": ["greenhouse_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_warnings",
            "description": "只读查询目标大棚活动预警和证据来源",
            "parameters": {"type": "object", "properties": {"greenhouse_id": {"type": "integer"}}, "required": ["greenhouse_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_farm_tasks",
            "description": "只读查询目标大棚最近农事任务，不创建或修改任务",
            "parameters": {"type": "object", "properties": {"greenhouse_id": {"type": "integer"}}, "required": ["greenhouse_id"]},
        },
    },
]


SOURCE_LABELS = {
    "sensor": "传感器数据",
    "import": "导入数据",
    "mixed": "混合来源数据",
}


def greenhouse_context(db: Session, greenhouse_id: int | None) -> dict[str, Any]:
    if greenhouse_id is None:
        return {"mode": "general", "greenhouse": None, "active_batch": None}
    greenhouse = db.get(Greenhouse, greenhouse_id)
    if greenhouse is None:
        raise ValueError("大棚不存在")
    batch = db.scalar(
        select(CropBatch).where(
            CropBatch.greenhouse_id == greenhouse_id, CropBatch.status == "growing"
        ).limit(1)
    )
    return jsonable_encoder({
        "mode": "greenhouse",
        "greenhouse": {
            "id": greenhouse.id,
            "code": greenhouse.code,
            "name": greenhouse.name,
            "location": greenhouse.location,
            "status": greenhouse.status,
        },
        "active_batch": ({
            "id": batch.id,
            "batch_code": batch.batch_code,
            "crop_type": batch.crop_type,
            "variety": batch.variety,
            "growth_stage": batch.growth_stage,
        } if batch else None),
    })


def _environment(db: Session, greenhouse_id: int) -> dict[str, Any]:
    item = db.scalar(
        select(SensorData).where(
            SensorData.greenhouse_id == greenhouse_id,
            SensorData.source.in_(VALID_BUSINESS_SOURCES),
        ).order_by(SensorData.recorded_at.desc()).limit(1)
    )
    if item is None:
        return {"status": "insufficient_data", "message": "当前大棚暂无环境数据"}
    return jsonable_encoder({
        "status": "available",
        "recorded_at": item.recorded_at,
        "source": item.source,
        "source_label": SOURCE_LABELS.get(item.source, "未知来源"),
        "device_id": item.device_id,
        "quality_flag": item.quality_flag,
        "temperature_c": item.temperature,
        "air_humidity_pct": item.air_humidity,
        "soil_moisture_pct": item.soil_moisture,
        "light_intensity": item.light_intensity,
        "co2_ppm": item.co2_concentration,
    })


def _prediction(db: Session, greenhouse_id: int) -> dict[str, Any]:
    prediction = predict_environment(db, greenhouse_id, 6)
    return jsonable_encoder({
        "status": prediction.status,
        "generated_at": prediction.generated_at,
        "input_end_time": prediction.input_end_time,
        "input_data_source": prediction.input_data_source,
        "input_source_label": SOURCE_LABELS.get(prediction.input_data_source or "", "未提供"),
        "validation_status": prediction.validation_status,
        "model_status": prediction.model_status,
        "model_version": prediction.model_version,
        "warnings": prediction.warnings,
        "predictions": prediction.predictions,
    })


def _warnings(db: Session, greenhouse_id: int) -> dict[str, Any]:
    items = list(db.scalars(
        select(WarningEvent).where(
            WarningEvent.greenhouse_id == greenhouse_id,
            WarningEvent.status.in_(["open", "acknowledged"]),
        ).order_by(WarningEvent.risk_score.desc(), WarningEvent.last_triggered_at.desc()).limit(10)
    ))
    return jsonable_encoder({
        "status": "available" if items else "none",
        "items": [{
            "id": item.id,
            "title": item.title,
            "severity": item.severity,
            "risk_score": item.risk_score,
            "certainty": item.certainty,
            "description": item.description,
            "data_source": item.data_source,
            "source_label": SOURCE_LABELS.get(item.data_source or "", "未提供"),
            "last_triggered_at": item.last_triggered_at,
            "rule_version": item.rule_version,
            "status": item.status,
        } for item in items],
    })


def _tasks(db: Session, greenhouse_id: int) -> dict[str, Any]:
    items = list(db.scalars(
        select(FarmTask).where(FarmTask.greenhouse_id == greenhouse_id)
        .order_by(FarmTask.updated_at.desc()).limit(10)
    ))
    return jsonable_encoder({
        "status": "available" if items else "none",
        "items": [{
            "id": item.id,
            "task_code": item.task_code,
            "title": item.title,
            "status": item.status,
            "priority": item.priority,
            "source_type": item.source_type,
            "assignee_name": item.assignee_name,
            "due_at": item.due_at,
            "requires_manual_confirmation": item.requires_manual_confirmation,
            "updated_at": item.updated_at,
        } for item in items],
    })


GREENHOUSE_TOOLS: dict[str, Callable[[Session, int], dict[str, Any]]] = {
    "get_current_environment": _environment,
    "get_future_prediction": _prediction,
    "get_active_warnings": _warnings,
    "get_farm_tasks": _tasks,
}


def _tool_plan(question: str) -> list[str]:
    q = question.lower()
    if any(key in q for key in ("任务", "待办", "执行", "完成")):
        return ["get_current_environment", "get_farm_tasks"]
    if any(key in q for key in ("预测", "未来", "趋势", "小时")):
        return ["get_current_environment", "get_future_prediction", "get_active_warnings"]
    if any(key in q for key in ("风险", "预警", "异常", "危险", "为什么")):
        return ["get_current_environment", "get_future_prediction", "get_active_warnings"]
    return list(GREENHOUSE_TOOLS)


def _record_tool(
    db: Session,
    conversation_id: int,
    message_id: int,
    name: str,
    arguments: dict[str, Any],
    result: dict[str, Any],
    status: str = "completed",
    error_message: str | None = None,
) -> None:
    db.add(AIToolCall(
        conversation_id=conversation_id,
        message_id=message_id,
        tool_name=name,
        arguments_json=arguments,
        result_json=result,
        status=status,
        error_message=error_message,
    ))


def collect_tool_evidence(
    db: Session,
    conversation_id: int,
    message_id: int,
    greenhouse_id: int | None,
    question: str,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []

    knowledge_result = {"status": "available", "items": search_knowledge(question, limit=4)}
    _record_tool(
        db,
        conversation_id,
        message_id,
        "search_agriculture_knowledge",
        {"query": question},
        knowledge_result,
    )
    evidence.append({"tool": "search_agriculture_knowledge", "status": "completed", "result": knowledge_result})

    if greenhouse_id is not None:
        for name in _tool_plan(question):
            arguments = {"greenhouse_id": greenhouse_id}
            status = "completed"
            error_message = None
            try:
                result = GREENHOUSE_TOOLS[name](db, greenhouse_id)
            except Exception as exception:  # 单个只读工具失败不应拖垮整次对话
                status = "error"
                error_message = str(exception)[:500]
                result = {"status": "unavailable", "message": error_message}
            _record_tool(
                db,
                conversation_id,
                message_id,
                name,
                arguments,
                result,
                status,
                error_message,
            )
            evidence.append({"tool": name, "status": status, "result": result})

    db.commit()
    return evidence
