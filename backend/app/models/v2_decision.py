from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.greenhouse import utc_now


class GreenhouseProfile(Base):
    __tablename__ = "greenhouse_profiles"
    __table_args__ = (Index("uq_greenhouse_profiles_greenhouse", "greenhouse_id", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    greenhouse_id: Mapped[int] = mapped_column(ForeignKey("greenhouses.id"), nullable=False)
    heat_response: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cooling_response: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    humidity_response: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ventilation_response: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_sensitivity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    traits_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    greenhouse = relationship("Greenhouse")


class RiskEvent(Base):
    __tablename__ = "risk_events"
    __table_args__ = (
        Index("ix_risk_events_greenhouse_created", "greenhouse_id", "created_at"),
        Index("ix_risk_events_disease_type", "disease_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    greenhouse_id: Mapped[int] = mapped_column(ForeignKey("greenhouses.id"), nullable=False)
    crop_batch_id: Mapped[int | None] = mapped_column(ForeignKey("crop_batches.id"))
    risk_type: Mapped[str] = mapped_column(String(40), nullable=False, default="disease")
    disease_type: Mapped[str] = mapped_column(String(80), nullable=False)
    crop_type: Mapped[str] = mapped_column(String(40), nullable=False)
    growth_stage: Mapped[str | None] = mapped_column(String(40))
    current_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_24h: Mapped[float] = mapped_column(Float, nullable=False)
    risk_48h: Mapped[float] = mapped_column(Float, nullable=False)
    risk_72h: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    trend: Mapped[str] = mapped_column(String(30), nullable=False)
    factors_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    greenhouse = relationship("Greenhouse")
    crop_batch = relationship("CropBatch")


class DecisionPlan(Base):
    __tablename__ = "decision_plans"
    __table_args__ = (
        Index("ix_decision_plans_risk_event", "risk_event_id"),
        Index("ix_decision_plans_greenhouse_status", "greenhouse_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    risk_event_id: Mapped[int] = mapped_column(ForeignKey("risk_events.id"), nullable=False)
    greenhouse_id: Mapped[int] = mapped_column(ForeignKey("greenhouses.id"), nullable=False)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("farm_tasks.id"))
    plan_name: Mapped[str] = mapped_column(String(120), nullable=False)
    actions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    expected_result_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="candidate")
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    risk_event = relationship("RiskEvent")
    greenhouse = relationship("Greenhouse")
    task = relationship("FarmTask")


class TreatmentEvaluation(Base):
    __tablename__ = "treatment_evaluations"
    __table_args__ = (Index("ix_treatment_evaluations_task", "task_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("farm_tasks.id"), nullable=False)
    greenhouse_id: Mapped[int] = mapped_column(ForeignKey("greenhouses.id"), nullable=False)
    risk_event_id: Mapped[int | None] = mapped_column(ForeignKey("risk_events.id"))
    decision_plan_id: Mapped[int | None] = mapped_column(ForeignKey("decision_plans.id"))
    before_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    after_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    environment_change_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    risk_change: Mapped[float] = mapped_column(Float, nullable=False)
    effect_score: Mapped[float] = mapped_column(Float, nullable=False)
    effect_level: Mapped[str] = mapped_column(String(30), nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    task = relationship("FarmTask")
    greenhouse = relationship("Greenhouse")
    risk_event = relationship("RiskEvent")
    decision_plan = relationship("DecisionPlan")


class SimulationRecord(Base):
    __tablename__ = "simulation_records"
    __table_args__ = (Index("ix_simulation_records_greenhouse", "greenhouse_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    greenhouse_id: Mapped[int] = mapped_column(ForeignKey("greenhouses.id"), nullable=False)
    decision_plan_id: Mapped[int | None] = mapped_column(ForeignKey("decision_plans.id"))
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    greenhouse = relationship("Greenhouse")
    decision_plan = relationship("DecisionPlan")
