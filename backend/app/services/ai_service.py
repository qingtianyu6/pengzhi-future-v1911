from __future__ import annotations

from collections.abc import AsyncIterator
import asyncio
import json
import logging
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AIConversation, AIMessage, AIToolCall, Greenhouse
from app.models.greenhouse import utc_now
from app.schemas.ai import (
    AIChatRequest,
    AIConversationCreate,
    AIConversationData,
    AIConversationUpdate,
    AIMessageData,
    AIStatusData,
)
from app.services.ai_provider import (
    LLMProviderError,
    ModelNotConfiguredError,
    get_llm_provider,
)
from app.services.ai_tools import TOOL_DEFINITIONS, collect_tool_evidence, greenhouse_context
from app.services.errors import ServiceError
from app.services.knowledge_service import load_knowledge


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """你是“棚小智”，棚智未来的设施农业生产决策智能体。
你有两种工作模式：
- 通用问答：依据本地农业知识库回答设施农业、番茄、甜瓜、数据接入和系统使用问题。
- 大棚对话：在知识库之外，结合当前大棚的环境数据、预测、预警和任务证据回答。

必须遵守：
1. 只依据本次提供的知识库检索结果和已审计工具证据回答，不得编造缺失数据。
2. 大棚数据不足或工具不可用时明确写出“数据不足”及缺少什么。
3. 关键判断尽量注明数据时间与来源，并区分现场传感器、文件导入和模型预测。
4. 病害模型输出只能称为“候选结果”或“辅助识别”，不得替代专业诊断。
5. 高风险生产建议必须提示管理人员或专业人员人工确认。
6. 不得声称已经控制设备、自动施药或执行了用户未确认的生产操作。
7. 不给出未经项目知识库支持的具体农药剂量；涉及植保用药时建议依据当地登记标签和专业农技人员意见。
8. 表达简洁、可执行、可追溯。若使用知识库，优先在结尾列出1至3个来源名称。
"""


def model_status() -> AIStatusData:
    settings = get_settings()
    external = bool(settings.ai_api_key and settings.ai_base_url and settings.ai_model)
    return AIStatusData(
        configured=True,
        model=settings.ai_model if external else "pengzhi-local-agent",
        message="外部模型服务已连接" if external else "本地农业智能体可用",
        knowledge_items=len(load_knowledge()),
    )


def _conversation_data(item: AIConversation) -> AIConversationData:
    return AIConversationData(
        id=item.id,
        title=item.title,
        greenhouse_id=item.greenhouse_id,
        mode="greenhouse" if item.greenhouse_id is not None else "general",
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _fmt(value: Any, suffix: str = "") -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.1f}{suffix}"
    return f"{value}{suffix}"


def _knowledge_reply(evidence: list[dict[str, Any]]) -> str:
    kb = next((item.get("result", {}) for item in evidence if item.get("tool") == "search_agriculture_knowledge"), {})
    items = kb.get("items", [])
    if not items:
        return "当前知识库没有检索到足够相关的资料。你可以换一种说法，或在大棚模式下让我结合现场数据分析。"
    top = items[0]
    lines = [str(top.get("summary") or "")]
    guidance = top.get("guidance", [])
    if guidance:
        lines.append("\n建议参考：")
        lines.extend(f"- {text}" for text in guidance[:4])
    sources: list[str] = []
    for item in items[:3]:
        for source in item.get("sources", [])[:1]:
            name = source.get("name")
            if name and name not in sources:
                sources.append(name)
    if sources:
        lines.append("\n知识来源：" + "；".join(sources))
    return "\n".join(line for line in lines if line)


def _local_evidence_reply(
    question: str, context: dict[str, Any], evidence: list[dict[str, Any]]
) -> str:
    by_tool = {item["tool"]: item.get("result", {}) for item in evidence}
    if context.get("mode") == "general":
        return _knowledge_reply(evidence)

    env = by_tool.get("get_current_environment", {})
    pred = by_tool.get("get_future_prediction", {})
    warning_data = by_tool.get("get_active_warnings", {})
    task_data = by_tool.get("get_farm_tasks", {})
    greenhouse = context.get("greenhouse") or {}
    batch = context.get("active_batch") or {}
    q = question.lower()

    if env.get("status") != "available":
        base = f"{greenhouse.get('name', '当前大棚')}暂无可用环境数据。先通过数据中心导入历史数据或接入传感器后，我可以继续分析趋势、风险和任务。"
    else:
        base = (
            f"{greenhouse.get('name', '当前大棚')}最新环境：温度 {_fmt(env.get('temperature_c'), '℃')}，"
            f"空气湿度 {_fmt(env.get('air_humidity_pct'), '%RH')}，土壤湿度 {_fmt(env.get('soil_moisture_pct'), '%')}，"
            f"光照 {_fmt(env.get('light_intensity'), ' klx')}，CO₂ {_fmt(env.get('co2_ppm'), ' ppm')}。"
        )

    if any(key in q for key in ("任务", "待办", "执行", "今天做", "完成")):
        items = task_data.get("items", [])
        if not items:
            return f"{base}\n\n当前没有农事任务。"
        lines = [
            f"- {item.get('title')}：{item.get('status')}，优先级 {item.get('priority')}"
            for item in items[:5]
        ]
        return f"{base}\n\n最近任务：\n" + "\n".join(lines)

    if any(key in q for key in ("风险", "预警", "异常", "危险", "为什么")):
        items = warning_data.get("items", [])
        if not items:
            knowledge = _knowledge_reply(evidence)
            return f"{base}\n\n当前没有活动预警。\n\n可参考知识库：\n{knowledge}"
        lines = [
            f"- {item.get('title')}：{item.get('severity')}，风险分 {_fmt(item.get('risk_score'))}。{item.get('description', '')}"
            for item in items[:5]
        ]
        return f"{base}\n\n当前活动预警：\n" + "\n".join(lines)

    if any(key in q for key in ("预测", "未来", "趋势", "小时")):
        points = pred.get("predictions", [])
        if pred.get("status") != "ready" or not points:
            return f"{base}\n\n当前预测数据不足，需要至少连续24小时的有效环境数据。"
        first = points[0]
        last = points[-1]
        return (
            f"{base}\n\n未来趋势：1小时后温度 {_fmt(first.get('temperature_c'), '℃')}、湿度 {_fmt(first.get('air_humidity_pct'), '%RH')}；"
            f"{last.get('horizon', 6)}小时后温度 {_fmt(last.get('temperature_c'), '℃')}、湿度 {_fmt(last.get('air_humidity_pct'), '%RH')}。"
        )

    if any(key in q for key in ("怎么", "如何", "管理", "建议", "番茄", "甜瓜", "病害", "通风", "湿度", "温度")):
        return f"{base}\n\n知识库参考：\n{_knowledge_reply(evidence)}"

    warnings = warning_data.get("items", [])
    tasks = task_data.get("items", [])
    summary = [base]
    if batch:
        summary.append(
            f"当前批次：{batch.get('variety') or batch.get('crop_type', '作物')}，生育阶段 {batch.get('growth_stage') or '未设置'}。"
        )
    if pred.get("status") == "ready" and pred.get("predictions"):
        point = pred["predictions"][0]
        summary.append(
            f"1小时预测：温度 {_fmt(point.get('temperature_c'), '℃')}，湿度 {_fmt(point.get('air_humidity_pct'), '%RH')}。"
        )
    summary.append(f"活动预警 {len(warnings)} 条，最近任务 {len(tasks)} 条。")
    summary.append("你可以继续问“当前风险”“未来6小时趋势”“有哪些任务”或“为什么建议通风”。")
    return "\n\n".join(summary)


def _conversation(db: Session, conversation_id: int) -> AIConversation:
    item = db.get(AIConversation, conversation_id)
    if item is None:
        raise ServiceError(404, "AI对话不存在")
    return item


def list_conversations(db: Session) -> list[AIConversationData]:
    items = list(db.scalars(select(AIConversation).order_by(AIConversation.updated_at.desc())))
    return [_conversation_data(item) for item in items]


def create_conversation(db: Session, payload: AIConversationCreate) -> AIConversationData:
    if payload.greenhouse_id is not None and db.get(Greenhouse, payload.greenhouse_id) is None:
        raise ServiceError(404, "大棚不存在")
    default_title = "大棚对话" if payload.greenhouse_id is not None else "通用问答"
    item = AIConversation(
        greenhouse_id=payload.greenhouse_id,
        title=(payload.title or default_title).strip(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _conversation_data(item)


def update_conversation(
    db: Session, conversation_id: int, payload: AIConversationUpdate
) -> AIConversationData:
    item = _conversation(db, conversation_id)
    item.title = payload.title.strip()
    item.updated_at = utc_now()
    db.commit()
    db.refresh(item)
    return _conversation_data(item)


def delete_conversation(db: Session, conversation_id: int) -> None:
    item = _conversation(db, conversation_id)
    message_ids = select(AIMessage.id).where(AIMessage.conversation_id == item.id)
    db.execute(delete(AIToolCall).where(AIToolCall.conversation_id == item.id))
    db.execute(delete(AIMessage).where(AIMessage.id.in_(message_ids)))
    db.delete(item)
    db.commit()


def list_messages(db: Session, conversation_id: int) -> list[AIMessageData]:
    _conversation(db, conversation_id)
    items = list(db.scalars(
        select(AIMessage).where(
            AIMessage.conversation_id == conversation_id,
            AIMessage.status != "superseded",
        ).order_by(AIMessage.id)
    ))
    return [AIMessageData.model_validate(item) for item in items]


def prepare_chat(
    db: Session, conversation_id: int, payload: AIChatRequest
) -> tuple[AIConversation, AIMessage, AIMessage]:
    conversation = _conversation(db, conversation_id)
    if payload.regenerate_message_id:
        previous = db.get(AIMessage, payload.regenerate_message_id)
        if (
            previous is None
            or previous.conversation_id != conversation_id
            or previous.role != "assistant"
            or previous.reply_to_id is None
        ):
            raise ServiceError(422, "只能重新生成当前对话中的AI回复")
        user_message = db.get(AIMessage, previous.reply_to_id)
        if user_message is None or user_message.role != "user":
            raise ServiceError(422, "未找到原始用户消息")
        previous.status = "superseded"
    else:
        user_message = AIMessage(
            conversation_id=conversation_id,
            role="user",
            content=payload.content or "",
            status="completed",
        )
        db.add(user_message)
        db.flush()
        if conversation.title in {"通用问答", "大棚对话", "新对话"}:
            conversation.title = (payload.content or "新对话")[:24]

    assistant = AIMessage(
        conversation_id=conversation_id,
        role="assistant",
        content="",
        status="streaming",
        reply_to_id=user_message.id,
        model_name=get_settings().ai_model or "pengzhi-local-agent",
    )
    conversation.updated_at = utc_now()
    db.add(assistant)
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant)
    return conversation, user_message, assistant


def _summarize_older(messages: list[AIMessage]) -> str:
    lines = []
    for item in messages:
        label = "用户" if item.role == "user" else "助手"
        compact = " ".join(item.content.split())[:240]
        if compact:
            lines.append(f"{label}：{compact}")
    return "\n".join(lines)[-4000:]


def _provider_messages(
    db: Session,
    conversation: AIConversation,
    tool_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    history = list(db.scalars(
        select(AIMessage).where(
            AIMessage.conversation_id == conversation.id,
            AIMessage.status.in_(["completed", "stopped"]),
        ).order_by(AIMessage.id)
    ))
    older, recent = history[:-10], history[-10:]
    if older:
        conversation.summary_text = _summarize_older(older)
        db.commit()

    context = greenhouse_context(db, conversation.greenhouse_id)
    context["readonly_tool_evidence"] = tool_evidence
    mode_text = "大棚对话" if conversation.greenhouse_id is not None else "通用问答"
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "system",
            "content": f"当前模式：{mode_text}\n已审计上下文和工具证据：\n"
            + json.dumps(context, ensure_ascii=False, separators=(",", ":")),
        },
    ]
    if conversation.summary_text:
        messages.append({
            "role": "system",
            "content": "较早对话摘要（仅作上下文，不替代当前工具证据）：\n"
            + conversation.summary_text,
        })
    messages.extend({"role": item.role, "content": item.content} for item in recent)
    return messages


async def stream_chat(
    db: Session,
    conversation: AIConversation,
    user_message: AIMessage,
    assistant: AIMessage,
) -> AsyncIterator[dict[str, Any]]:
    content_parts: list[str] = []
    completed = False
    try:
        yield {
            "event": "meta",
            "data": {
                "conversation_id": conversation.id,
                "mode": "greenhouse" if conversation.greenhouse_id is not None else "general",
                "user_message": AIMessageData.model_validate(user_message).model_dump(mode="json"),
                "assistant_message": AIMessageData.model_validate(assistant).model_dump(mode="json"),
            },
        }
        evidence = collect_tool_evidence(
            db,
            conversation.id,
            assistant.id,
            conversation.greenhouse_id,
            user_message.content,
        )
        yield {
            "event": "tools",
            "data": {"tools": [{"name": item["tool"], "status": item["status"]} for item in evidence]},
        }
        settings = get_settings()
        external = bool(settings.ai_api_key and settings.ai_base_url and settings.ai_model)
        if external:
            messages = _provider_messages(db, conversation, evidence)
            provider = get_llm_provider()
            async for delta in provider.chat_stream(messages, TOOL_DEFINITIONS):
                content_parts.append(delta)
                yield {"event": "delta", "data": {"content": delta}}
        else:
            context = greenhouse_context(db, conversation.greenhouse_id)
            reply = _local_evidence_reply(user_message.content, context, evidence)
            for start in range(0, len(reply), 24):
                delta = reply[start:start + 24]
                content_parts.append(delta)
                yield {"event": "delta", "data": {"content": delta}}
                await asyncio.sleep(0)

        assistant.content = "".join(content_parts).strip()
        assistant.status = "completed"
        conversation.updated_at = utc_now()
        db.commit()
        db.refresh(assistant)
        completed = True
        yield {
            "event": "done",
            "data": {"message": AIMessageData.model_validate(assistant).model_dump(mode="json")},
        }
    except asyncio.CancelledError:
        assistant.content = "".join(content_parts).strip()
        assistant.status = "stopped"
        conversation.updated_at = utc_now()
        db.commit()
        completed = True
        raise
    except ModelNotConfiguredError:
        assistant.content = "尚未配置模型服务"
        assistant.status = "error"
        conversation.updated_at = utc_now()
        db.commit()
        completed = True
        yield {"event": "error", "data": {"message": "尚未配置模型服务"}}
    except LLMProviderError:
        assistant.content = "模型服务暂时不可用，请稍后重试。"
        assistant.status = "error"
        conversation.updated_at = utc_now()
        db.commit()
        completed = True
        yield {"event": "error", "data": {"message": assistant.content}}
    except Exception:
        logger.exception("AI智能体流式处理失败")
        assistant.content = "棚小智处理请求时发生异常，请稍后重试。"
        assistant.status = "error"
        conversation.updated_at = utc_now()
        db.commit()
        completed = True
        yield {"event": "error", "data": {"message": assistant.content}}
    finally:
        if not completed and assistant.status == "streaming":
            assistant.content = "".join(content_parts).strip()
            assistant.status = "stopped"
            conversation.updated_at = utc_now()
            db.commit()
