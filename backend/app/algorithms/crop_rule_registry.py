from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.algorithms.growth_stage_rules import GROWTH_STAGES, RULE_VERSION
from app.algorithms.tomato_growth_stage_rules import (
    TOMATO_EXPERT_CALIBRATION_REQUIRED,
    TOMATO_GROWTH_STAGES,
    TOMATO_RULE_SCOPE,
    TOMATO_RULE_VERSION,
    TOMATO_STAGE_THRESHOLDS,
)


CropType = Literal["tomato", "muskmelon", "other", "unknown"]


@dataclass(frozen=True)
class CropRuleProfile:
    crop_type: CropType
    rule_version: str
    stages: tuple[str, ...]
    rule_scope: str
    expert_calibration_required: bool
    enabled_for_decision_support: bool


TOMATO_PROFILE = CropRuleProfile(
    crop_type="tomato",
    rule_version=TOMATO_RULE_VERSION,
    stages=TOMATO_GROWTH_STAGES,
    rule_scope=TOMATO_RULE_SCOPE,
    expert_calibration_required=TOMATO_EXPERT_CALIBRATION_REQUIRED,
    enabled_for_decision_support=True,
)

# 甜瓜生育期配置保留在注册表中，便于后续扩展；当前决策引擎只启用番茄规则。
MUSKMELON_PROFILE = CropRuleProfile(
    crop_type="muskmelon",
    rule_version=RULE_VERSION,
    stages=GROWTH_STAGES,
    rule_scope="reference_profile",
    expert_calibration_required=True,
    enabled_for_decision_support=False,
)


def get_rule_profile(crop_type: str) -> CropRuleProfile | None:
    if crop_type == "tomato":
        return TOMATO_PROFILE
    if crop_type == "muskmelon":
        return MUSKMELON_PROFILE
    return None


def get_operational_rule(crop_type: str) -> CropRuleProfile | None:
    profile = get_rule_profile(crop_type)
    if profile is None or not profile.enabled_for_decision_support:
        return None
    return profile


def thresholds_for(
    crop_type: str, growth_stage: str, local_hour: int
) -> dict[str, tuple[float, float]] | None:
    profile = get_operational_rule(crop_type)
    if profile is None or crop_type != "tomato":
        return None

    stage = TOMATO_STAGE_THRESHOLDS.get(growth_stage)
    if stage is None:
        return None
    return {
        "temperature": (
            stage["temperature_day"]
            if 6 <= local_hour < 18
            else stage["temperature_night"]
        ),
        "air_humidity": stage["air_humidity"],
        "soil_moisture": stage["soil_moisture"],
        "light_intensity": stage["light_intensity"],
        "co2_concentration": stage["co2_concentration"],
    }
