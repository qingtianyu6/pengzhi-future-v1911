from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Literal, TypedDict

from app.algorithms.crop_rule_registry import get_operational_rule, get_rule_profile, thresholds_for


RiskLevel = Literal["normal", "attention", "warning", "critical"]
Certainty = Literal["expected", "possible", "normal", "insufficient"]

RISK_LEVEL_LABELS: dict[RiskLevel, str] = {
    "normal": "正常", "attention": "关注", "warning": "预警", "critical": "严重",
}
FORECAST_WEIGHTS = {"temperature": 0.55, "air_humidity": 0.45}
DEVIATION_SPANS = {"temperature": 10.0, "air_humidity": 25.0}


class WarningCandidate(TypedDict):
    warning_code: str
    warning_type: str
    risk_score: float
    severity: RiskLevel
    certainty: Certainty
    title: str
    description: str
    forecast_start_at: datetime | None
    forecast_end_at: datetime | None
    evidence: dict[str, Any]


def clamp_score(score: float) -> float:
    return round(max(0.0, min(100.0, score)), 2)


def risk_level(score: float) -> RiskLevel:
    if score < 30: return "normal"
    if score < 60: return "attention"
    if score < 80: return "warning"
    return "critical"


def metric_risk(value: float, suitable: tuple[float, float], span: float) -> float:
    lower, upper = suitable
    if lower <= value <= upper: return 0.0
    deviation = lower - value if value < lower else value - upper
    return clamp_score(deviation / span * 100)


def _metric_anomaly(
    metric: str,
    value: float | None,
    lower_bound: float | None,
    upper_bound: float | None,
    suitable: tuple[float, float],
) -> dict[str, Any] | None:
    if value is None: return None
    low, high = suitable
    direction: Literal["low", "high"] | None = "low" if value < low else "high" if value > high else None
    certainty: Certainty = "expected" if direction else "normal"
    evidence_value = value
    if direction is None and lower_bound is not None and lower_bound < low:
        direction, certainty, evidence_value = "low", "possible", lower_bound
    elif direction is None and upper_bound is not None and upper_bound > high:
        direction, certainty, evidence_value = "high", "possible", upper_bound
    if direction is None: return None
    score = metric_risk(evidence_value, suitable, DEVIATION_SPANS[metric])
    score = max(30.0, score)
    labels = {"temperature": "温度", "air_humidity": "空气湿度"}
    directions = {"low": "偏低", "high": "偏高"}
    return {
        "code": f"forecast_{direction}_{metric}",
        "type": f"{direction}_{metric}",
        "score": clamp_score(score),
        "certainty": certainty,
        "reason": f"{labels[metric]}{directions[direction]}：点预测 {value:.2f}，适宜范围 {low:g}～{high:g}",
    }


def assess_forecast_point(
    point: dict[str, Any], growth_stage: str | None, *, data_source: str | None,
    calibration_status: str = "legacy_not_applicable", crop_type: str = "tomato",
) -> dict[str, Any]:
    evaluated_at = datetime.now(UTC)
    profile=get_rule_profile(crop_type);operational=get_operational_rule(crop_type);rule_version=profile.rule_version if profile else "rules_unavailable"
    forecast_time=point.get("forecast_time");timestamp=datetime.fromisoformat(forecast_time) if isinstance(forecast_time,str) else forecast_time
    if timestamp is not None:
        aware=timestamp.replace(tzinfo=UTC) if timestamp.tzinfo is None else timestamp.astimezone(UTC);local_hour=aware.astimezone(timezone(timedelta(hours=8))).hour
    else:local_hour=12
    thresholds=thresholds_for(crop_type,growth_stage or "",local_hour) if operational else None
    if thresholds is None:
        return {"horizon": point.get("horizon"), "forecast_time": point.get("forecast_time"), "risk_score": None, "risk_level": "normal", "risk_type": "forecast_environment", "triggered": False, "trigger_reasons": ["生育期规则不可用"], "evidence": {}, "growth_stage": growth_stage, "rule_version": rule_version, "evaluated_at": evaluated_at, "data_source": data_source, "calibration_status": calibration_status, "certainty": "insufficient", "partial_data": True, "anomalies": []}
    values = {"temperature": point.get("temperature_c"), "air_humidity": point.get("air_humidity_pct")}
    bounds = point.get("lower_bounds", {}), point.get("upper_bounds", {})
    key_map = {"temperature": "air_temperature_c", "air_humidity": "air_humidity_pct"}
    anomalies = []
    scores: dict[str, float] = {}
    for metric, value in values.items():
        if value is None: continue
        key = key_map[metric]
        anomaly = _metric_anomaly(metric, float(value), bounds[0].get(key), bounds[1].get(key), thresholds[metric])  # type: ignore[literal-required]
        scores[metric] = float(anomaly["score"]) if anomaly else 0.0
        if anomaly: anomalies.append(anomaly)
    available_weight = sum(FORECAST_WEIGHTS[key] for key in scores)
    score = sum(scores[key] * FORECAST_WEIGHTS[key] for key in scores) / available_weight if available_weight else 0.0
    high_types = {item["type"] for item in anomalies}
    if {"high_temperature", "high_air_humidity"}.issubset(high_types):
        score = clamp_score(score + 20)
        anomalies.append({"code": "forecast_high_temperature_high_humidity", "type": "temperature_humidity_combination", "score": score, "certainty": "expected" if all(item["certainty"] == "expected" for item in anomalies) else "possible", "reason": "高温与高湿在同一预测时长共同出现"})
    certainty: Certainty = "expected" if any(item["certainty"] == "expected" for item in anomalies) else "possible" if anomalies else "normal"
    return {
        "horizon": point.get("horizon"), "forecast_time": point.get("forecast_time"), "risk_score": clamp_score(score), "risk_level": risk_level(score), "risk_type": "forecast_environment", "triggered": bool(anomalies), "trigger_reasons": [item["reason"] for item in anomalies],
        "evidence": {"values": values, "lower_bounds": bounds[0], "upper_bounds": bounds[1], "thresholds": {"temperature": thresholds["temperature"], "air_humidity": thresholds["air_humidity"]}, "methods": point.get("methods", {}), "method_version": point.get("method_version")},
        "growth_stage": growth_stage, "rule_version": rule_version, "evaluated_at": evaluated_at, "data_source": data_source, "calibration_status": calibration_status, "certainty": certainty, "partial_data": len(scores) < 2, "anomalies": anomalies,
    }


def build_forecast_warning_candidates(risks: list[dict[str, Any]]) -> list[WarningCandidate]:
    grouped: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for risk in risks:
        for anomaly in risk["anomalies"]:
            grouped[str(anomaly["type"])].append((risk, anomaly))
    candidates: list[WarningCandidate] = []
    titles = {"high_temperature": "未来高温预警", "low_temperature": "未来低温预警", "high_air_humidity": "未来高湿预警", "low_air_humidity": "未来低湿预警", "temperature_humidity_combination": "未来温湿度组合预警"}
    for warning_type, entries in grouped.items():
        entries.sort(key=lambda item: int(item[0]["horizon"]))
        horizons = [int(item[0]["horizon"]) for item in entries]
        longest = 1
        current = 1
        for before, after in zip(horizons, horizons[1:]):
            current = current + 1 if after == before + 1 else 1
            longest = max(longest, current)
        score = max(float(item[1]["score"]) for item in entries)
        if longest >= 2: score = clamp_score(score + 15)
        certainty: Certainty = "expected" if any(item[1]["certainty"] == "expected" for item in entries) else "possible"
        first, last = entries[0][0], entries[-1][0]
        reasons = [str(item[1]["reason"]) for item in entries]
        if longest >= 2: reasons.append(f"连续 {longest} 个预测时长触发同类异常，风险已升级")
        candidates.append({"warning_code": f"forecast_{warning_type}", "warning_type": warning_type, "risk_score": score, "severity": risk_level(score), "certainty": certainty, "title": titles.get(warning_type, "未来环境预警"), "description": "；".join(reasons), "forecast_start_at": first["forecast_time"], "forecast_end_at": last["forecast_time"], "evidence": {"forecast_risks": [item[0] for item in entries], "continuous_hours": longest, "trigger_reasons": reasons}})
    high_temp = grouped.get("high_temperature", [])
    high_humidity = grouped.get("high_air_humidity", [])
    if high_temp and high_humidity and not grouped.get("temperature_humidity_combination"):
        pairs = [(a, b) for a in high_temp for b in high_humidity if abs(int(a[0]["horizon"]) - int(b[0]["horizon"])) <= 1]
        if pairs:
            related = [item for pair in pairs for item in pair]
            score = clamp_score(max(float(item[1]["score"]) for item in related) + 20)
            times = sorted(item[0]["forecast_time"] for item in related)
            candidates.append({"warning_code": "forecast_temperature_humidity_combination", "warning_type": "temperature_humidity_combination", "risk_score": score, "severity": risk_level(score), "certainty": "expected" if any(item[1]["certainty"] == "expected" for item in related) else "possible", "title": "未来温湿度组合预警", "description": "高温和高湿在相同或相邻预测时长出现，组合风险已提高", "forecast_start_at": times[0], "forecast_end_at": times[-1], "evidence": {"forecast_risks": [item[0] for item in related], "continuous_hours": len(set(item[0]["horizon"] for item in related)), "trigger_reasons": ["高温和高湿在相同或相邻预测时长出现"]}})
    return candidates
