"""Stateless model access for the browser-only guest workspace."""
from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta, timezone
from threading import Lock
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.services.ai_provider import LLMProviderError, get_llm_provider


router = APIRouter(prefix="/guest/ai", tags=["游客AI体验"])
_calls: dict[str, deque[datetime]] = defaultdict(deque)
_lock = Lock()
_greenhouses = {101: "游客体验番茄棚", 102: "游客体验甜瓜棚"}


class GuestTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)


class GuestChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=1000)
    greenhouse_id: int = 101
    history: list[GuestTurn] = Field(default_factory=list, max_length=8)
    tasks: list[str] = Field(default_factory=list, max_length=20)


class GuestTaskAction(BaseModel):
    greenhouse_id: Literal[101, 102]
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=1000)
    action_type: Literal["ventilation_check", "shading_check", "heating_check", "humidity_control",
                         "condensation_inspection", "irrigation_check", "sensor_inspection",
                         "manual_observation", "expert_review", "field_inspection", "sample_collection", "isolation_check"]
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    due_at: datetime | None = None


class GuestChatResponse(BaseModel):
    reply: str
    actions: list[GuestTaskAction]


_create_task_tool = {
    "type": "function",
    "function": {
        "name": "create_farm_task",
        "description": "仅在用户明确要求创建、添加或安排农事任务时使用。任务只存在于游客浏览器，不写服务器数据库，也不执行设备操作。",
        "parameters": GuestTaskAction.model_json_schema(),
    },
}


def _check_rate(client: str) -> None:
    now = datetime.now(UTC)
    with _lock:
        calls = _calls[client]
        while calls and now - calls[0] > timedelta(minutes=1):
            calls.popleft()
        if len(calls) >= 8:
            raise HTTPException(429, "请求过于频繁，请稍后再试")
        calls.append(now)


@router.get("/status")
def guest_status():
    from app.config import get_settings
    settings=get_settings()
    configured=bool(settings.ai_api_key and settings.ai_base_url and settings.ai_model)
    return {"configured":configured,"model":"guest-model","knowledge_items":0,
        "message":"游客AI已配置，任务仅在浏览器临时保存" if configured else "尚未配置外部AI服务，可继续体验其他模块"}


@router.post("/chat", response_model=GuestChatResponse)
async def guest_chat(payload: GuestChatRequest, request: Request) -> GuestChatResponse:
    client = request.client.host if request.client else "unknown"
    if client in {"127.0.0.1", "::1"}:
        client = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip() or client
    _check_rate(client)
    if payload.greenhouse_id not in _greenhouses:
        raise HTTPException(422, "请选择游客体验大棚")

    system = (
        "你是棚小智。面向游客提供真实的设施农业问答和任务创建能力。"
        "当前大棚：101=游客体验番茄棚，102=游客体验甜瓜棚。"
        f"当前中国时间：{datetime.now(timezone(timedelta(hours=8))).isoformat()}。"
        "只有用户明确要求新建/创建/添加/安排任务时才调用create_farm_task。"
        "可以根据提问选择目标大棚；若未指明则使用当前大棚。"
        "任务是人工执行的，不代表已经控制设备或完成现场操作。"
        "游客数据只存在于浏览器内存，刷新或关闭后丢失，不要声称已存档。"
        "没有现场真实数据，不得声称已读取真实传感器或完成病害确诊。"
        "回答要具体、简洁；不确定时明确说明。"
    )
    context = (
        f"当前选择大棚：{payload.greenhouse_id} {_greenhouses[payload.greenhouse_id]}。"
        f"当前游客任务标题：{json.dumps(payload.tasks, ensure_ascii=False)}。"
    )
    messages = [{"role": "system", "content": system + context}]
    messages.extend(turn.model_dump() for turn in payload.history)
    messages.append({"role": "user", "content": payload.content})
    intent = bool(re.search(r"(创建|新建|添加|安排).{0,40}(任务|待办)|(任务|待办).{0,40}(创建|新建|添加|安排)", payload.content))
    try:
        provider = get_llm_provider()
        result = await provider.chat(messages, [_create_task_tool])
        if intent and not result.get("tool_calls"):
            result = await provider.chat(messages, [_create_task_tool], tool_choice={
                "type": "function", "function": {"name": "create_farm_task"},
            })
    except LLMProviderError as exc:
        raise HTTPException(503, str(exc)) from exc

    actions: list[GuestTaskAction] = []
    for call in (result.get("tool_calls") or [])[:2]:
        if call.get("function", {}).get("name") != "create_farm_task":
            continue
        try:
            action = GuestTaskAction.model_validate_json(call["function"]["arguments"])
        except (KeyError, ValueError):
            continue
        if intent:
            actions.append(action)

    if actions:
        names = "、".join(action.title for action in actions)
        reply = f"已创建游客临时任务：{names}。可在农事任务页查看和继续操作；刷新或关闭页面后不会保留。"
    else:
        reply = str(result.get("content") or "暂时无法完成这项操作，请把任务名称、大棚和时间说得更具体一些。")
    return GuestChatResponse(reply=reply, actions=actions)
