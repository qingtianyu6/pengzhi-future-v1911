from datetime import UTC, datetime, timedelta

from app.algorithms.warning_rules import assess_forecast_point, build_forecast_warning_candidates, clamp_score


def point(temperature: float | None = 26, humidity: float | None = 60, *, lower_temp: float = 24, upper_temp: float = 28, lower_humidity: float = 55, upper_humidity: float = 65, horizon: int = 1) -> dict[str, object]:
    return {"horizon": horizon, "forecast_time": datetime(2026, 8, 22, horizon, tzinfo=UTC), "temperature_c": temperature, "air_humidity_pct": humidity, "lower_bounds": {"air_temperature_c": lower_temp, "air_humidity_pct": lower_humidity}, "upper_bounds": {"air_temperature_c": upper_temp, "air_humidity_pct": upper_humidity}, "methods": {"air_temperature_c": "seasonal_24", "air_humidity_pct": "seasonal_residual_gru"}, "method_version": "v0.2"}


def assess(payload: dict[str, object]) -> dict[str, object]:
    return assess_forecast_point(payload, "开花坐果期", data_source="simulation")


def test_normal_forecast_does_not_trigger_warning() -> None:
    result = assess(point())
    assert result["triggered"] is False
    assert build_forecast_warning_candidates([result]) == []


def test_expected_when_point_prediction_crosses_threshold() -> None:
    result = assess(point(temperature=34))
    assert result["certainty"] == "expected"
    assert result["triggered"] is True


def test_possible_when_only_empirical_interval_crosses_threshold() -> None:
    result = assess(point(temperature=28, upper_temp=34))
    assert result["certainty"] == "possible"
    assert "可能" not in " ".join(result["trigger_reasons"])


def test_missing_temperature_uses_humidity_only_and_marks_partial() -> None:
    result = assess(point(temperature=None, humidity=80))
    assert result["partial_data"] is True
    assert result["risk_score"] is not None


def test_consecutive_two_hours_upgrade_risk() -> None:
    risks = [assess(point(temperature=34, horizon=h)) for h in [1, 2]]
    warning = next(item for item in build_forecast_warning_candidates(risks) if item["warning_type"] == "high_temperature")
    assert warning["evidence"]["continuous_hours"] == 2
    assert warning["risk_score"] >= 55


def test_adjacent_high_temperature_and_humidity_create_combination() -> None:
    risks = [assess(point(temperature=34, horizon=1)), assess(point(humidity=80, horizon=2))]
    types = {item["warning_type"] for item in build_forecast_warning_candidates(risks)}
    assert "temperature_humidity_combination" in types


def test_risk_score_is_always_clamped() -> None:
    assert clamp_score(-10) == 0
    assert clamp_score(180) == 100


def test_rules_unavailable_returns_insufficient() -> None:
    result = assess_forecast_point(point(), None, data_source="simulation")
    assert result["certainty"] == "insufficient"
    assert result["risk_score"] is None


def test_same_input_is_deterministic_except_evaluation_timestamp() -> None:
    first, second = assess(point(temperature=34)), assess(point(temperature=34))
    first.pop("evaluated_at"); second.pop("evaluated_at")
    assert first == second
