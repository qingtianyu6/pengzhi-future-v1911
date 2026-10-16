from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.greenhouse import utc_now


class ActionCandidate(Base):
    __tablename__ = "action_candidates"
    __table_args__ = (
        UniqueConstraint("warning_event_id", "action_code", name="uq_warning_action_candidate"),
        CheckConstraint("status IN ('available','selected','not_selected','cancelled')", name="ck_action_candidate_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    greenhouse_id: Mapped[int] = mapped_column(ForeignKey("greenhouses.id"), nullable=False, index=True)
    warning_event_id: Mapped[int] = mapped_column(ForeignKey("warning_events.id"), nullable=False, index=True)
    action_code: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    action_type: Mapped[str] = mapped_column(String(60), nullable=False)
    action_params_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    expected_response_minutes: Mapped[int | None] = mapped_column(Integer)
    energy_level: Mapped[str] = mapped_column(String(20), nullable=False)
    labor_level: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_note: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class Intervention(Base):
    __tablename__ = "interventions"
    __table_args__ = (
        Index("ix_intervention_greenhouse_status", "greenhouse_id", "status"),
        CheckConstraint("status IN ('selected','pending','in_progress','awaiting_observation','completed','cancelled')", name="ck_intervention_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    greenhouse_id: Mapped[int] = mapped_column(ForeignKey("greenhouses.id"), nullable=False)
    warning_event_id: Mapped[int] = mapped_column(ForeignKey("warning_events.id"), nullable=False)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("action_candidates.id"), nullable=False)
    recommendation_id: Mapped[int | None] = mapped_column(ForeignKey("decision_recommendations.id"))
    task_id: Mapped[int | None] = mapped_column(ForeignKey("farm_tasks.id"), unique=True)
    action_type: Mapped[str] = mapped_column(String(60), nullable=False)
    action_params_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    selection_reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="selected")
    selected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    before_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class OutcomeObservation(Base):
    __tablename__ = "outcome_observations"
    __table_args__ = (UniqueConstraint("intervention_id", "offset_minutes", name="uq_intervention_observation_offset"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    intervention_id: Mapped[int] = mapped_column(ForeignKey("interventions.id"), nullable=False, index=True)
    greenhouse_id: Mapped[int] = mapped_column(ForeignKey("greenhouses.id"), nullable=False)
    observation_type: Mapped[str] = mapped_column(String(20), nullable=False, default="follow_up")
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    target_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sample_delta_seconds: Mapped[int | None] = mapped_column(Integer)
    offset_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    sensor_record_id: Mapped[int | None] = mapped_column(ForeignKey("sensor_data.id"))
    temperature: Mapped[float | None] = mapped_column(Float)
    humidity: Mapped[float | None] = mapped_column(Float)
    soil_moisture: Mapped[float | None] = mapped_column(Float)
    co2: Mapped[float | None] = mapped_column(Float)
    risk_score: Mapped[float | None] = mapped_column(Float)
    manual_status: Mapped[str | None] = mapped_column(String(80))
    risk_resolved: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
