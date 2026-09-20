from datetime import UTC, timedelta, timezone

from app.algorithms.crop_rule_registry import get_operational_rule, get_rule_profile, thresholds_for
from app.schemas.dashboard import RiskAssessment
from app.schemas.sensor_data import SensorDataView


RISK_WEIGHTS = {
    "temperature": 0.30,
    "air_humidity": 0.25,
    "soil_moisture": 0.20,
    "light_intensity": 0.15,
    "co2_concentration": 0.05,
    "combination": 0.05,
}

DEVIATION_SPANS = {
    "temperature": 10.0,
    "air_humidity": 25.0,
    "soil_moisture": 20.0,
    "light_intensity": 30.0,
    "co2_concentration": 800.0,
}

METRIC_LABELS = {
    "temperature": "温度",
    "air_humidity": "空气湿度",
    "soil_moisture": "土壤湿度",
    "light_intensity": "光照",
    "co2_concentration": "CO₂",
}


def _metric_risk(value: float, suitable: tuple[float, float], span: float) -> float:
    lower, upper = suitable
    if lower <= value <= upper:
        return 0.0
    deviation = lower - value if value < lower else value - upper
    return round(min(100.0, deviation / span * 100), 2)


def _risk_level(score: float) -> str:
    if score < 30:
        return "正常"
    if score < 60:
        return "关注"
    if score < 80:
        return "预警"
    return "严重"


def assess_current_risk(
    reading: SensorDataView | None, growth_stage: str | None, crop_type: str = "tomato"
) -> RiskAssessment:
    profile=get_rule_profile(crop_type);operational=get_operational_rule(crop_type)
    rule_version=profile.rule_version if profile else "rules_unavailable"
    if reading is None or growth_stage is None or operational is None:
        return RiskAssessment(
            data_status="insufficient",
            growth_stage=growth_stage,
            component_scores={},
            overall_score=None,
            level="数据不足",
            reasons=["缺少最新环境数据、有效生育期，或当前作物没有启用的规则"],
            rule_version=rule_version,crop_type=crop_type,rule_scope=profile.rule_scope if profile else "rules_unavailable",expert_calibration_required=False,
        )

    values = {
        "temperature": reading.temperature,
        "air_humidity": reading.air_humidity,
        "soil_moisture": reading.soil_moisture,
        "light_intensity": reading.light_intensity,
        "co2_concentration": reading.co2_concentration,
    }
    missing = [METRIC_LABELS[key] for key, value in values.items() if value is None]
    if missing:
        return RiskAssessment(
            data_status="insufficient",
            growth_stage=growth_stage,
            component_scores={},
            overall_score=None,
            level="数据不足",
            reasons=[f"缺少必要指标：{'、'.join(missing)}"],
            rule_version=rule_version,crop_type=crop_type,rule_scope=operational.rule_scope,expert_calibration_required=operational.expert_calibration_required,
        )

    timestamp=reading.recorded_at
    aware=timestamp.replace(tzinfo=UTC) if timestamp.tzinfo is None else timestamp.astimezone(UTC)
    local_hour=aware.astimezone(timezone(timedelta(hours=8))).hour
    thresholds=thresholds_for(crop_type,growth_stage,local_hour)
    if thresholds is None:
        return RiskAssessment(data_status="insufficient",growth_stage=growth_stage,component_scores={},overall_score=None,level="数据不足",reasons=["当前作物或生育期没有可用规则"],rule_version=rule_version,crop_type=crop_type,rule_scope=operational.rule_scope,expert_calibration_required=False)
    scores: dict[str, float] = {}
    reasons: list[str] = []
    for key, nullable_value in values.items():
        value = float(nullable_value)  # 已在缺失检查中排除 None
        suitable = thresholds[key]  # type: ignore[literal-required]
        score = _metric_risk(value, suitable, DEVIATION_SPANS[key])
        scores[key] = score
        if score > 0:
            direction = "偏低" if value < suitable[0] else "偏高"
            reasons.append(
                f"{METRIC_LABELS[key]}{direction}（{value:g}，适宜 {suitable[0]:g}～{suitable[1]:g}）"
            )

    temperature = float(values["temperature"])
    humidity = float(values["air_humidity"])
    high_temp_high_humidity = (
        temperature > thresholds["temperature"][1]
        and humidity > thresholds["air_humidity"][1]
    )
    scores["combination"] = (
        round(min(100.0, max(scores["temperature"], scores["air_humidity"]) + 20), 2)
        if high_temp_high_humidity
        else 0.0
    )
    if high_temp_high_humidity:
        reasons.append("高温与高湿同时出现，触发组合风险加权")

    overall = round(
        min(100.0, sum(scores[key] * weight for key, weight in RISK_WEIGHTS.items())),
        2,
    )
    if not reasons:
        reasons.append(f"当前指标处于{growth_stage}规则的参考范围")
    return RiskAssessment(
        data_status="sufficient",
        growth_stage=growth_stage,
        component_scores=scores,
        overall_score=overall,
        level=_risk_level(overall),
        reasons=reasons,
        rule_version=rule_version,crop_type=crop_type,rule_scope=operational.rule_scope,expert_calibration_required=operational.expert_calibration_required,
    )
