from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.greenhouse import utc_now


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("ai_conversations.id"), index=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("ai_messages.id"))
    greenhouse_id: Mapped[int | None] = mapped_column(ForeignKey("greenhouses.id"))
    goal: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="CREATED", index=True)
    context_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    step_count: Mapped[int] = mapped_column(default=0)
    result: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class AgentStep(Base):
    __tablename__ = "agent_steps"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    event: Mapped[str] = mapped_column(String(40))
    data_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AgentToolCall(Base):
    __tablename__ = "agent_tool_calls"
    __table_args__ = (Index("ix_agent_call_run_provider", "run_id", "call_id", unique=True),)
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    call_id: Mapped[str] = mapped_column(String(160))
    name: Mapped[str] = mapped_column(String(80))
    risk: Mapped[str] = mapped_column(String(24))
    arguments_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AgentApproval(Base):
    __tablename__ = "agent_approvals"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    tool_call_id: Mapped[int] = mapped_column(ForeignKey("agent_tool_calls.id"), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentRecheck(Base):
    __tablename__ = "agent_rechecks"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    greenhouse_id: Mapped[int] = mapped_column(ForeignKey("greenhouses.id"))
    task_id: Mapped[int | None] = mapped_column(ForeignKey("farm_tasks.id"))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    baseline_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    target_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evaluation_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
