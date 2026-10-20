from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Context(BaseModel):
    greenhouse_id: int = Field(gt=0)
    crop_batch_id: int | None = Field(default=None, gt=0)


class ObservationCreate(Context):
    observed_at: datetime | None = None
    study_id: int | None = Field(default=None, gt=0)
    phase: Literal["routine", "before", "after", "control"] = "routine"
    zone: str = Field(default="全棚", min_length=1, max_length=80)
    note: str = Field(min_length=1, max_length=3000)
    metrics: dict[Literal["plant_height_cm", "flower_count", "fruit_count", "harvest_kg", "leaf_wetness_pct"], float] = Field(default_factory=dict)


class ScenarioCreate(Context):
    duration_minutes: Literal[30, 60, 120] = 30
    intensity: int = Field(default=30, ge=0, le=100)


class StudyCreate(Context):
    question: str = Field(min_length=2, max_length=500)
    scenario_id: int | None = Field(default=None, gt=0)
    hypothesis: str = Field(default="", max_length=2000)


class PlanStep(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=2000)
    action_type: Literal["sensor_inspection", "ventilation_check", "humidity_control", "shading_check", "heating_check", "irrigation_check", "manual_observation", "field_inspection", "sample_collection", "expert_review", "condensation_inspection"]
    depends_on: list[int] = Field(default_factory=list, max_length=10)


class GoalCreate(Context):
    goal: str = Field(min_length=2, max_length=500)
    scenario_id: int | None = Field(default=None, gt=0)
    skill_id: int | None = Field(default=None, gt=0)
    study_id: int | None = Field(default=None, gt=0)
    use_ai: bool = False
    plan_steps: list[PlanStep] | None = Field(default=None, min_length=2, max_length=10)

    @model_validator(mode="after")
    def ordered_steps(self):
        for index, step in enumerate(self.plan_steps or []):
            if len(set(step.depends_on)) != len(step.depends_on) or any(i < 0 or i >= index for i in step.depends_on):
                raise ValueError("前置步骤必须指向更早的步骤，且不能重复")
        return self


class RecordAction(BaseModel):
    version: int = Field(ge=1)
    action: Literal["start", "complete", "archive", "derive_skill", "activate", "disable", "execute"]
    note: str = Field(default="", max_length=3000)


class RecordData(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    greenhouse_id: int
    crop_batch_id: int | None
    kind: str
    title: str
    status: str
    payload: dict
    version: int
    created_at: datetime
    updated_at: datetime
