from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.greenhouse import utc_now


class DecisionRecommendation(Base):
    __tablename__ = "decision_recommendations"
    __table_args__ = (
        CheckConstraint("priority IN ('low','medium','high','urgent')", name="ck_recommendation_priority"),
        CheckConstraint("status IN ('pending_review','accepted','rejected','superseded')", name="ck_recommendation_status"),
        UniqueConstraint("warning_event_id", "recommendation_code", name="uq_warning_recommendation_code"),
        Index("ix_recommendation_greenhouse", "greenhouse_id"),
        Index("ix_recommendation_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    warning_event_id: Mapped[int] = mapped_column(ForeignKey("warning_events.id"), nullable=False)
    greenhouse_id: Mapped[int] = mapped_column(ForeignKey("greenhouses.id"), nullable=False)
    crop_batch_id: Mapped[int | None] = mapped_column(ForeignKey("crop_batches.id"))
    crop_type: Mapped[str] = mapped_column(String(20),nullable=False,default="unknown",server_default="unknown")
    crop_rule_version: Mapped[str] = mapped_column(String(40),nullable=False,default="rules_unavailable",server_default="rules_unavailable")
    recommendation_code: Mapped[str] = mapped_column(String(80), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    action_steps_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    execute_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safety_note: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending_review")
    rule_version: Mapped[str] = mapped_column(String(40), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    warning_event = relationship("WarningEvent", back_populates="recommendations")
