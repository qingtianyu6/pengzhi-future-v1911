from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
import json
from threading import Lock
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import AIConversation, AIMessage
from app.schemas.ai import (
    AIChatRequest,
    AIConversationCreate,
    AIConversationData,
    AIConversationUpdate,
    AIMessageData,
    AIStatusData,
    KnowledgeSearchRequest,
)
from app.schemas.common import ApiResponse
from app.services import ai_service
from app.services.errors import ServiceError
from app.services.knowledge_service import knowledge_catalog, search_knowledge


router = APIRouter(prefix="/v1/ai", tags=["AI农业助手"])
Database = Annotated[Session, Depends(get_db)]


class _RateLimiter:
    def __init__(self, limit: int = 12, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window = timedelta(seconds=window_seconds)
        self.calls: dict[str, deque[datetime]] = defaultdict(deque)
        self.lock = Lock()

    def check(self, key: str) -> None:
        now = datetime.now(UTC)
        with self.lock:
            calls = self.calls[key]
            while calls and now - calls[0] > self.window:
                calls.popleft()
            if len(calls) >= self.limit:
                raise ServiceError(429, "请求过于频繁，请稍后再试")
            calls.append(now)


rate_limiter = _RateLimiter()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"




@router.get("/knowledge", response_model=ApiResponse[list[dict]], summary="获取农业知识库目录")
def get_knowledge_catalog() -> ApiResponse[list[dict]]:
    return ApiResponse(data=knowledge_catalog())


@router.post("/knowledge/search", response_model=ApiResponse[list[dict]], summary="检索农业知识库")
def search_ai_knowledge(payload: KnowledgeSearchRequest) -> ApiResponse[list[dict]]:
    return ApiResponse(data=search_knowledge(payload.query, payload.limit))


@router.get("/status", response_model=ApiResponse[AIStatusData], summary="查询模型配置状态")
def get_ai_status() -> ApiResponse[AIStatusData]:
    return ApiResponse(data=ai_service.model_status())


@router.get(
    "/conversations",
    response_model=ApiResponse[list[AIConversationData]],
    summary="获取AI历史对话",
)
def get_conversations(db: Database) -> ApiResponse[list[AIConversationData]]:
    return ApiResponse(data=ai_service.list_conversations(db))


@router.post(
    "/conversations",
    response_model=ApiResponse[AIConversationData],
    summary="新建AI对话",
)
def create_conversation(
    payload: AIConversationCreate, db: Database
) -> ApiResponse[AIConversationData]:
    return ApiResponse(message="AI对话已创建", data=ai_service.create_conversation(db, payload))


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ApiResponse[AIConversationData],
    summary="重命名AI对话",
)
def update_conversation(
    conversation_id: int, payload: AIConversationUpdate, db: Database
) -> ApiResponse[AIConversationData]:
    return ApiResponse(
        message="AI对话已重命名",
        data=ai_service.update_conversation(db, conversation_id, payload),
    )


@router.delete(
    "/conversations/{conversation_id}",
    response_model=ApiResponse[None],
    summary="删除AI对话",
)
def delete_conversation(conversation_id: int, db: Database) -> ApiResponse[None]:
    ai_service.delete_conversation(db, conversation_id)
    return ApiResponse(message="AI对话已删除", data=None)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ApiResponse[list[AIMessageData]],
    summary="获取完整对话消息",
)
def get_messages(
    conversation_id: int, db: Database
) -> ApiResponse[list[AIMessageData]]:
    return ApiResponse(data=ai_service.list_messages(db, conversation_id))


@router.post(
    "/conversations/{conversation_id}/chat",
    summary="SSE流式生成AI回复",
    response_class=StreamingResponse,
)
async def chat(
    conversation_id: int, payload: AIChatRequest, request: Request, db: Database
) -> StreamingResponse:
    client_key = request.client.host if request.client else "unknown"
    rate_limiter.check(client_key)
    conversation, user_message, assistant = ai_service.prepare_chat(
        db, conversation_id, payload
    )
    conversation_key = conversation.id
    user_message_key = user_message.id
    assistant_key = assistant.id

    async def events() -> AsyncIterator[str]:
        # 流式响应可能晚于请求依赖会话的生命周期，使用专属会话保证对象不脱管。
        with SessionLocal() as stream_db:
            stream_conversation = stream_db.get(AIConversation, conversation_key)
            stream_user = stream_db.get(AIMessage, user_message_key)
            stream_assistant = stream_db.get(AIMessage, assistant_key)
            if stream_conversation is None or stream_user is None or stream_assistant is None:
                yield _sse("error", {"message": "AI对话状态已失效，请刷新后重试"})
                return
            async for item in ai_service.stream_chat(
                stream_db, stream_conversation, stream_user, stream_assistant
            ):
                if await request.is_disconnected():
                    break
                yield _sse(item["event"], item["data"])

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
