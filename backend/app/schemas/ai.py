from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


AIConversationMode = Literal["general", "greenhouse"]


class AIStatusData(BaseModel):
    configured: bool
    model: str | None
    message: str
    knowledge_items: int = 0


class AIConversationCreate(BaseModel):
    mode: AIConversationMode = "general"
    greenhouse_id: int | None = Field(default=None, gt=0)
    title: str | None = Field(default=None, min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_context(self) -> "AIConversationCreate":
        # 兼容旧客户端：只要传入 greenhouse_id，就按大棚对话处理。
        if self.greenhouse_id is not None:
            self.mode = "greenhouse"
        if self.mode == "greenhouse" and self.greenhouse_id is None:
            raise ValueError("大棚对话必须选择目标大棚")
        return self


class AIConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=80)


class AIConversationData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    greenhouse_id: int | None
    mode: AIConversationMode
    created_at: datetime
    updated_at: datetime


class AIMessageData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    status: str
    reply_to_id: int | None
    model_name: str | None
    created_at: datetime


class AIChatRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=4000)
    regenerate_message_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def exactly_one_action(self):
        if bool(self.content and self.content.strip()) == bool(self.regenerate_message_id):
            raise ValueError("请输入消息或指定需要重新生成的回复")
        if self.content is not None:
            self.content = self.content.strip()
        return self


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    limit: int = Field(default=4, ge=1, le=8)
