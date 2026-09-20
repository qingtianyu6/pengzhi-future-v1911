from typing import Final, TypedDict


class StageThresholds(TypedDict):
    temperature: tuple[float, float]
    air_humidity: tuple[float, float]
    soil_moisture: tuple[float, float]
    light_intensity: tuple[float, float]
    co2_concentration: tuple[float, float]


GROWTH_STAGES: Final[tuple[str, ...]] = (
    "苗期",
    "伸蔓期",
    "开花坐果期",
    "果实膨大期",
    "成熟采收期",
)

STAGE_THRESHOLDS: Final[dict[str, StageThresholds]] = {
    "苗期": {
        "temperature": (20, 30), "air_humidity": (60, 80),
        "soil_moisture": (60, 75), "light_intensity": (12, 45),
        "co2_concentration": (400, 1000),
    },
    "伸蔓期": {
        "temperature": (22, 32), "air_humidity": (55, 75),
        "soil_moisture": (55, 72), "light_intensity": (18, 55),
        "co2_concentration": (400, 1100),
    },
    "开花坐果期": {
        "temperature": (22, 30), "air_humidity": (50, 70),
        "soil_moisture": (55, 70), "light_intensity": (20, 60),
        "co2_concentration": (450, 1200),
    },
    "果实膨大期": {
        "temperature": (24, 32), "air_humidity": (55, 75),
        "soil_moisture": (60, 78), "light_intensity": (22, 65),
        "co2_concentration": (450, 1200),
    },
    "成熟采收期": {
        "temperature": (22, 30), "air_humidity": (45, 65),
        "soil_moisture": (45, 62), "light_intensity": (20, 65),
        "co2_concentration": (400, 1100),
    },
}

RULE_VERSION: Final[str] = "melon-rule-v0.1"
RULE_SCOPE: Final[str] = "reference_profile"
