from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer,
                        String, Text, text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.greenhouse import utc_now


class FarmTask(Base):
    __tablename__ = "farm_tasks"
    __table_args__ = (
        CheckConstraint("source_type IN ('warning','disease_review','recommendation','manual')",
                        name="ck_farm_task_source_type"),
        CheckConstraint("status IN ('draft','pending','in_progress','completed','cancelled')",
                        name="ck_farm_task_status"),
        CheckConstraint("priority IN ('low','medium','high','urgent')",
                        name="ck_farm_task_priority"),
        CheckConstraint("NOT (completed_at IS NOT NULL AND cancelled_at IS NOT NULL)",
                        name="ck_farm_task_terminal_time"),
        Index("ix_farm_task_greenhouse_status", "greenhouse_id", "status"),
        Index("ix_farm_task_crop_batch", "crop_batch_id"),
        Index("ix_farm_task_assignee", "assignee_name"),
        Index(
            "uq_farm_task_active_source_action", "source_type", "source_id", "action_type",
            unique=True,
            sqlite_where=text("source_id IS NOT NULL AND status IN ('draft','pending','in_progress')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    task_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    greenhouse_id: Mapped[int] = mapped_column(ForeignKey("greenhouses.id"), nullable=False)
    crop_batch_id: Mapped[int | None] = mapped_column(ForeignKey("crop_batches.id"))
    crop_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[int | None] = mapped_column(Integer, index=True)
    source_warning_id: Mapped[int | None] = mapped_column(ForeignKey("warning_events.id"))
    source_disease_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("disease_recognition_records.id")
    )
    source_recommendation_id: Mapped[int | None] = mapped_column(
        ForeignKey("decision_recommendations.id")
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    action_type: Mapped[str] = mapped_column(String(60), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    assignee_name: Mapped[str | None] = mapped_column(String(60))
    planned_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requires_manual_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    safety_note: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    result_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[str] = mapped_column(String(60), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)

    greenhouse = relationship("Greenhouse")
    crop_batch = relationship("CropBatch")
    source_warning = relationship("WarningEvent", foreign_keys=[source_warning_id])
    source_disease_record = relationship(
        "DiseaseRecognitionRecord", foreign_keys=[source_disease_record_id]
    )
    source_recommendation = relationship(
        "DecisionRecommendation", foreign_keys=[source_recommendation_id]
    )
    events = relationship("TaskEvent", back_populates="task", order_by="TaskEvent.id")
    feedbacks = relationship("TaskFeedback", back_populates="task", order_by="TaskFeedback.id")

