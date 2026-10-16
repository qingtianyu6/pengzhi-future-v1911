from __future__ import annotations

from typing import Any

from app.models import SensorData
from app.services.risk_engine.disease_rules import disease_rules
from app.services.risk_engine.environmental_features import EnvironmentalFeatures, build_features
from app.services.risk_engine.risk_explainer import readable_explanation, risk_level, risk_trend


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return round(max(lower, min(upper, value)), 2)


def _range_score(value: float | None, lower: float, upper: float, span: float) -> float:
    if value is None:
        return 0.0
    if lower <= value <= upper:
        return 100.0
    distance = lower - value if value < lower else value - upper
    return _clamp(100.0 - distance / span * 100.0)


class DiseaseRiskEngine:
    """Transparent first-version disease risk model; no random values are used."""

    def __init__(self, rules: dict[str, Any] | None = None) -> None:
        self.rules = rules or disease_rules()

    def _score(self, rule: dict[str, Any], features: EnvironmentalFeatures, growth_stage: str | None,
               history_factor: float, horizon_hours: int) -> tuple[float, list[dict[str, Any]]]:
        humidity_projection = (features.latest_humidity or features.avg_humidity_6h or 0) + features.humidity_trend_per_hour * min(horizon_hours, 24) * 0.35
        temp_projection = (features.latest_temperature or features.avg_temperature_12h or 0) + features.temperature_trend_per_hour * min(horizon_hours, 24) * 0.25
        temp_low, temp_high = rule["suitable_temperature"]
        humidity_low, humidity_high = rule["high_risk_humidity"]
        duration_target = max(1, int(rule["continuous_high_humidity_hours"]))
        stage_map = rule.get("stage_sensitivity", {})
        stage_factor = float(stage_map.get(growth_stage or "", 1.0))

        feature_scores = {
            "temperature": _range_score(temp_projection, temp_low, temp_high, 12),
            "humidity": _range_score(humidity_projection, humidity_low, humidity_high, 30),
            "high_humidity_duration": _clamp(features.high_humidity_hours / duration_target * 100),
            "diurnal_temp_diff": _clamp(features.diurnal_temp_diff / float(rule["diurnal_temp_diff_sensitive"]) * 100),
            "environment_trend": _clamp(max(0.0, features.humidity_trend_per_hour) * 22 + max(0.0, -features.temperature_trend_per_hour) * 8 + horizon_hours * 0.25),
            "growth_stage": _clamp((stage_factor - 0.65) / 0.7 * 100),
            "history": _clamp(history_factor * 100),
        }
        labels = {
            "temperature": "温度适宜",
            "humidity": "湿度适宜",
            "high_humidity_duration": "连续高湿",
            "diurnal_temp_diff": "昼夜温差",
            "environment_trend": "湿度趋势",
            "growth_stage": "生育期敏感",
            "history": "历史病害",
        }
        weights = rule["weights"]
        raw = sum(feature_scores[key] * float(weights[key]) for key in weights)
        score = _clamp(raw * stage_factor)
        contributions = [{
            "key": key,
            "label": labels[key],
            "feature_score": round(feature_scores[key], 2),
            "weight": weights[key],
            "value": round(feature_scores[key] * float(weights[key]) * stage_factor, 2),
        } for key in weights]
        contributions.sort(key=lambda item: item["value"], reverse=True)
        return score, contributions

    def evaluate_disease(self, disease_code: str, records: list[SensorData],
                         growth_stage: str | None = None, history_factor: float = 0.0) -> dict[str, Any]:
        if disease_code not in self.rules:
            raise KeyError(disease_code)
        rule = self.rules[disease_code]
        features = build_features(records)
        current, contributions = self._score(rule, features, growth_stage, history_factor, 0)
        risk_24h, _ = self._score(rule, features, growth_stage, history_factor, 24)
        risk_48h, _ = self._score(rule, features, growth_stage, history_factor, 48)
        risk_72h, _ = self._score(rule, features, growth_stage, history_factor, 72)
        if features.high_humidity_hours >= int(rule["continuous_high_humidity_hours"]) or features.humidity_trend_per_hour > 0:
            pressure = min(18.0, max(3.0, features.high_humidity_hours * 0.8 + max(0.0, features.humidity_trend_per_hour) * 4))
            risk_24h = max(risk_24h, _clamp(current + pressure * 0.35))
            risk_48h = max(risk_48h, _clamp(risk_24h + pressure * 0.35))
            risk_72h = max(risk_72h, _clamp(risk_48h + pressure * 0.3))
        return {
            "disease_type": disease_code,
            "disease_name": rule["name"],
            "current_score": current,
            "risk_24h": risk_24h,
            "risk_48h": risk_48h,
            "risk_72h": risk_72h,
            "risk_level": risk_level(max(current, risk_72h)),
            "trend": risk_trend(current, risk_72h),
            "factors": {
                "contributions": contributions,
                "score_kind": "rule_index",
                "calibration_status": "not_calibrated",
                "notice": "0～100规则风险指数，并非发病概率；需结合目标作物人工复核。",
                "features": features.__dict__,
                "rule": {
                    "suitable_temperature": rule["suitable_temperature"],
                    "high_risk_humidity": rule["high_risk_humidity"],
                    "continuous_high_humidity_hours": rule["continuous_high_humidity_hours"],
                },
            },
            "explanation": readable_explanation(rule["name"], risk_72h, contributions),
        }

    def evaluate_all(self, records: list[SensorData], growth_stage: str | None = None,
                     history_by_disease: dict[str, float] | None = None, *, crop_type: str = "muskmelon") -> list[dict[str, Any]]:
        if crop_type not in {"tomato", "muskmelon", "melon"}:
            return []
        # These are exploratory environmental-pressure rules, not crop-calibrated probabilities.
        history = history_by_disease or {}
        return [self.evaluate_disease(code, records, growth_stage, history.get(code, 0.0))
                for code in self.rules if crop_type != "tomato" or code in {"gray_mold", "powdery_mildew", "leaf_spot"}]
