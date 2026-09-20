from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.greenhouse import utc_now


class TaskFeedback(Base):
    __tablename__ = "task_feedbacks"
    __table_args__ = (
        CheckConstraint(
            "result_type IN ('resolved','improved','no_change','worsened','unable_to_verify')",
            name="ck_task_feedback_result_type",
        ),
        Index("ix_task_feedback_task_executed", "task_id", "executed_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("farm_tasks.id"), nullable=False)
    operator: Mapped[str] = mapped_column(String(60), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    result_type: Mapped[str] = mapped_column(String(30), nullable=False)
    execution_note: Mapped[str] = mapped_column(Text, nullable=False)
    observed_change: Mapped[str | None] = mapped_column(Text)
    attachment_paths_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    environment_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    requires_follow_up: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    follow_up_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    task = relationship("FarmTask", back_populates="feedbacks")

