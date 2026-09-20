from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient

from app.algorithms.crop_rule_registry import get_operational_rule, get_rule_profile, thresholds_for
from app.algorithms.warning_rules import WarningCandidate
from app.schemas.sensor_data import SensorDataView
from app.services.growth_stage_service import calculate_growth_stage
from app.services.risk_service import assess_current_risk
from app.services.warning_service import _fingerprint


def _greenhouse(client: TestClient, code: str) -> int:
    response = client.post(
        "/api/greenhouses",
        json={"code": code, "name": f"{code}测试棚", "location": "测试区", "area_mu": 1.2},
    )
    assert response.status_code == 201
    return int(response.json()["data"]["id"])


def _batch(client: TestClient, greenhouse_id: int, crop_type: str, code: str) -> dict[str, object]:
    response = client.post(
        f"/api/greenhouses/{greenhouse_id}/crop-batches",
        json={
            "batch_code": code,
            "variety": "设施番茄" if crop_type == "tomato" else "设施甜瓜",
            "crop_type": crop_type,
            "planted_at": (date.today() - timedelta(days=50)).isoformat(),
            "status": "growing",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_crop_registry_activates_only_tomato() -> None:
    tomato = get_operational_rule("tomato")
    melon = get_rule_profile("muskmelon")
    assert tomato is not None and tomato.rule_version == "tomato-rule-v0.1"
    assert melon is not None and melon.rule_version == "melon-rule-v0.1"
    assert melon.rule_scope == "reference_profile"
    assert get_operational_rule("muskmelon") is None
    assert get_rule_profile("unknown") is None
    assert thresholds_for("unknown", "苗期", 12) is None


def test_tomato_growth_stage_and_threshold_are_not_melon_fallback() -> None:
    planted = date(2026, 1, 1)
    assert calculate_growth_stage(planted, planted + timedelta(days=50), "tomato") == "开花坐果期"
    assert calculate_growth_stage(planted, planted + timedelta(days=50), "muskmelon") == "开花坐果期"
    assert calculate_growth_stage(planted, planted + timedelta(days=50), "unknown") == "规则不可用"
    tomato_threshold = thresholds_for("tomato", "开花坐果期", 12)
    assert tomato_threshold is not None and tomato_threshold["temperature"] == (22, 28)
    assert thresholds_for("muskmelon", "开花坐果期", 12) is None

    reading = SensorDataView(
        id=1,
        greenhouse_id=1,
        recorded_at=datetime(2026, 8, 22, 4, tzinfo=UTC),
        temperature=29,
        air_humidity=60,
        soil_moisture=60,
        light_intensity=30,
        co2_concentration=600,
        source="sensor",
        quality_flag="valid",
    )
    result = assess_current_risk(reading, "开花坐果期", "tomato")
    assert result.rule_version == "tomato-rule-v0.1"
    assert result.component_scores["temperature"] > 0
    assert assess_current_risk(reading, "开花坐果期", "muskmelon").data_status == "insufficient"


def test_prediction_applicability_is_dynamic_by_crop(client: TestClient) -> None:
    tomato_id = _greenhouse(client, "TOMATO-PRED")
    _batch(client, tomato_id, "tomato", "TOMATO-PRED-BATCH")
    tomato = client.get("/api/predictions/environment", params={"greenhouse_id": tomato_id}).json()["data"]
    assert tomato["crop_match_status"] == "matched_public_tomato"
    assert tomato["cross_crop_warning"] is False
    assert tomato["cross_region_warning"] is True
    assert tomato["validation_status"] == "validated_on_public_dataset"
    assert tomato["effective_model_status"] == "hybrid_ready"

    melon_id = _greenhouse(client, "MELON-PRED")
    _batch(client, melon_id, "muskmelon", "MELON-PRED-BATCH")
    melon = client.get("/api/predictions/environment", params={"greenhouse_id": melon_id}).json()["data"]
    assert melon["crop_match_status"] == "mismatched"
    assert melon["cross_crop_warning"] is True


def test_crop_type_is_explicit_and_tomato_is_new_batch_default(client: TestClient) -> None:
    greenhouse_id = _greenhouse(client, "CROP-API")
    response = client.post(
        f"/api/greenhouses/{greenhouse_id}/crop-batches",
        json={"batch_code": "DEFAULT-TOMATO", "variety": "番茄品种", "planted_at": date.today().isoformat()},
    )
    assert response.status_code == 201
    assert response.json()["data"]["crop_type"] == "tomato"


def test_warning_fingerprint_separates_crop_and_rule() -> None:
    candidate: WarningCandidate = {
        "warning_code": "forecast_high_temperature",
        "warning_type": "high_temperature",
        "risk_score": 60,
        "severity": "warning",
        "certainty": "expected",
        "title": "测试",
        "description": "测试",
        "forecast_start_at": datetime(2026, 8, 22, 1, tzinfo=UTC),
        "forecast_end_at": datetime(2026, 8, 22, 2, tzinfo=UTC),
        "evidence": {},
    }
    tomato = _fingerprint(1, 1, "tomato", candidate, "tomato-rule-v0.1", None)
    melon = _fingerprint(1, 1, "muskmelon", candidate, "melon-rule-v0.1", None)
    assert tomato != melon

