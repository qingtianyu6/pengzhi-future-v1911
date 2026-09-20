from __future__ import annotations

from typing import Final, TypedDict


class TomatoStageThresholds(TypedDict):
    temperature_day: tuple[float, float]
    temperature_night: tuple[float, float]
    air_humidity: tuple[float, float]
    soil_moisture: tuple[float, float]
    light_intensity: tuple[float, float]
    co2_concentration: tuple[float, float]


TOMATO_RULE_VERSION: Final[str] = "tomato-rule-v0.1"
TOMATO_RULE_SCOPE: Final[str] = "decision_support"
TOMATO_EXPERT_CALIBRATION_REQUIRED: Final[bool] = False
TOMATO_THRESHOLD_BASIS: Final[str] = "公开设施番茄栽培资料的保守参考范围"
TOMATO_GROWTH_STAGES: Final[tuple[str, ...]] = ("苗期", "营养生长期", "开花坐果期", "果实膨大期", "成熟采收期")
TOMATO_STAGE_DAY_LIMITS: Final[tuple[int, ...]] = (20, 45, 75, 110)

TOMATO_STAGE_THRESHOLDS: Final[dict[str, TomatoStageThresholds]] = {
    "苗期": {"temperature_day": (20, 28), "temperature_night": (16, 20), "air_humidity": (60, 75), "soil_moisture": (60, 75), "light_intensity": (12, 45), "co2_concentration": (400, 1000)},
    "营养生长期": {"temperature_day": (22, 28), "temperature_night": (17, 21), "air_humidity": (60, 75), "soil_moisture": (58, 75), "light_intensity": (18, 55), "co2_concentration": (400, 1100)},
    "开花坐果期": {"temperature_day": (22, 28), "temperature_night": (17, 20), "air_humidity": (55, 70), "soil_moisture": (55, 70), "light_intensity": (20, 60), "co2_concentration": (450, 1200)},
    "果实膨大期": {"temperature_day": (22, 28), "temperature_night": (18, 21), "air_humidity": (55, 70), "soil_moisture": (60, 78), "light_intensity": (22, 65), "co2_concentration": (450, 1200)},
    "成熟采收期": {"temperature_day": (20, 27), "temperature_night": (16, 20), "air_humidity": (50, 65), "soil_moisture": (50, 68), "light_intensity": (20, 65), "co2_concentration": (400, 1100)},
}
