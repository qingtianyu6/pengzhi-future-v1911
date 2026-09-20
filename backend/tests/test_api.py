from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
import pandas as pd
import pytest

from app.schemas.dashboard import RiskAssessment
from app.schemas.sensor_data import SensorDataView
from app.services.growth_stage_service import calculate_growth_stage
from app.services.risk_service import assess_current_risk


def create_greenhouse(client: TestClient, code: str = "GH-001") -> dict[str, object]:
    response = client.post(
        "/api/greenhouses",
        json={
            "code": code,
            "name": "测试番茄棚",
            "location": "山东省聊城市莘县",
            "area_mu": 2.5,
            "status": "active",
            "manager_name": "测试员",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def create_batch(client: TestClient, greenhouse_id: int, code: str = "BATCH-001") -> dict[str, object]:
    response = client.post(
        f"/api/greenhouses/{greenhouse_id}/crop-batches",
        json={
            "batch_code": code,
            "variety": "测试番茄",
            "crop_type": "tomato",
            "planted_at": (date.today() - timedelta(days=40)).isoformat(),
            "expected_harvest_at": (date.today() + timedelta(days=45)).isoformat(),
            "status": "growing",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def sensor_payload(greenhouse_id: int, recorded_at: datetime, temperature: float = 28.0) -> dict[str, object]:
    return {
        "greenhouse_id": greenhouse_id,
        "recorded_at": recorded_at.isoformat(),
        "temperature": temperature,
        "air_humidity": 65,
        "soil_moisture": 60,
        "light_intensity": 30,
        "co2_concentration": 600,
        "source": "sensor",
        "quality_flag": "valid",
    }


def test_health_check(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["data"]["database"] == "connected"


def test_create_greenhouse_success(client: TestClient) -> None:
    data = create_greenhouse(client)
    assert data["code"] == "GH-001"
    assert data["active_batch"] is None


def test_duplicate_greenhouse_code_returns_409(client: TestClient) -> None:
    create_greenhouse(client)
    response = client.post(
        "/api/greenhouses",
        json={"code": "GH-001", "name": "重复", "location": "莘县", "area_mu": 1},
    )
    assert response.status_code == 409


def test_invalid_greenhouse_area_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/greenhouses",
        json={"code": "GH-X", "name": "面积非法", "location": "莘县", "area_mu": 0},
    )
    assert response.status_code == 422


def test_create_crop_batch_and_growth_fields(client: TestClient) -> None:
    greenhouse = create_greenhouse(client)
    batch = create_batch(client, int(greenhouse["id"]))
    assert batch["crop_type"] == "tomato"
    assert batch["growth_stage"] == "营养生长期"
    assert batch["growth_day"] == 40
    assert batch["stage_updated_at"]


def test_invalid_greenhouse_cannot_create_batch(client: TestClient) -> None:
    response = client.post(
        "/api/greenhouses/999/crop-batches",
        json={
            "batch_code": "NO-GH",
            "variety": "测试甜瓜",
            "planted_at": date.today().isoformat(),
            "expected_harvest_at": (date.today() + timedelta(days=80)).isoformat(),
        },
    )
    assert response.status_code == 404


def test_growth_stage_boundaries() -> None:
    planted = date(2026, 1, 1)
    assert calculate_growth_stage(planted, planted + timedelta(days=20), "tomato") == "苗期"
    assert calculate_growth_stage(planted, planted + timedelta(days=21), "tomato") == "营养生长期"
    assert calculate_growth_stage(planted, planted + timedelta(days=46), "tomato") == "开花坐果期"
    assert calculate_growth_stage(planted, planted + timedelta(days=76), "tomato") == "果实膨大期"
    assert calculate_growth_stage(planted, planted + timedelta(days=111), "tomato") == "成熟采收期"
    assert calculate_growth_stage(planted, planted + timedelta(days=16), "muskmelon") == "伸蔓期"


def test_one_greenhouse_cannot_have_two_growing_batches(client: TestClient) -> None:
    greenhouse = create_greenhouse(client)
    greenhouse_id = int(greenhouse["id"])
    create_batch(client, greenhouse_id)
    response = client.post(
        f"/api/greenhouses/{greenhouse_id}/crop-batches",
        json={
            "batch_code": "BATCH-002",
            "variety": "另一个批次",
            "planted_at": date.today().isoformat(),
            "expected_harvest_at": (date.today() + timedelta(days=80)).isoformat(),
        },
    )
    assert response.status_code == 409


def test_latest_environment_data(client: TestClient) -> None:
    greenhouse_id = int(create_greenhouse(client)["id"])
    create_batch(client, greenhouse_id)
    now = datetime.now(UTC).replace(microsecond=0)
    response = client.post(
        "/api/sensors/batch",
        json={"items": [sensor_payload(greenhouse_id, now - timedelta(hours=1)), sensor_payload(greenhouse_id, now, 31)]},
    )
    assert response.status_code == 200
    latest = client.get("/api/sensors/latest", params={"greenhouse_id": greenhouse_id})
    assert latest.json()["data"]["temperature"] == 31


def test_history_is_sorted_ascending(client: TestClient) -> None:
    greenhouse_id = int(create_greenhouse(client)["id"])
    now = datetime.now(UTC).replace(microsecond=0)
    client.post(
        "/api/sensors/batch",
        json={"items": [sensor_payload(greenhouse_id, now), sensor_payload(greenhouse_id, now - timedelta(hours=2))]},
    )
    response = client.get(
        "/api/sensors/history",
        params={
            "greenhouse_id": greenhouse_id,
            "start_time": (now - timedelta(days=1)).isoformat(),
            "end_time": (now + timedelta(hours=1)).isoformat(),
        },
    )
    times = [item["recorded_at"] for item in response.json()["data"]["items"]]
    assert times == sorted(times)


def test_invalid_history_range_returns_422(client: TestClient) -> None:
    greenhouse_id = int(create_greenhouse(client)["id"])
    now = datetime.now(UTC)
    response = client.get(
        "/api/sensors/history",
        params={"greenhouse_id": greenhouse_id, "start_time": now.isoformat(), "end_time": now.isoformat()},
    )
    assert response.status_code == 422


def test_duplicate_environment_data_is_skipped(client: TestClient) -> None:
    greenhouse_id = int(create_greenhouse(client)["id"])
    item = sensor_payload(greenhouse_id, datetime.now(UTC).replace(microsecond=0))
    first = client.post("/api/sensors/batch", json={"items": [item]})
    second = client.post("/api/sensors/batch", json={"items": [item, item]})
    assert first.json()["data"]["success_count"] == 1
    assert second.json()["data"]["success_count"] == 0
    assert second.json()["data"]["skipped_count"] == 2


def test_dashboard_summary(client: TestClient) -> None:
    greenhouse_id = int(create_greenhouse(client)["id"])
    create_batch(client, greenhouse_id)
    now = datetime.now(UTC).replace(microsecond=0)
    client.post("/api/sensors/batch", json={"items": [sensor_payload(greenhouse_id, now)]})
    response = client.get("/api/dashboard/summary", params={"greenhouse_id": greenhouse_id})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["empty_state"] is False
    assert data["risk"]["rule_version"] == "tomato-rule-v0.1"
    assert data["data_source_label"] == "传感器数据"


def test_risk_level_calculation() -> None:
    reading = SensorDataView(
        id=1, greenhouse_id=1, recorded_at=datetime.now(UTC), temperature=60,
        air_humidity=100, soil_moisture=0, light_intensity=150,
        co2_concentration=5000, source="sensor", quality_flag="suspect",
    )
    result: RiskAssessment = assess_current_risk(reading, "开花坐果期")
    assert result.overall_score is not None and result.overall_score >= 80
    assert result.level == "严重"
    assert any("组合风险" in reason for reason in result.reasons)


def test_prediction_contract_reports_validation_gate(client: TestClient) -> None:
    greenhouse_id = int(create_greenhouse(client)["id"])
    create_batch(client, greenhouse_id)
    response = client.post(
        "/api/predictions/environment",
        json={"greenhouse_id": greenhouse_id, "forecast_hours": 6},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "insufficient_data"
    assert data["forecast_service_status"] == "ready"
    assert data["model_status"] == "ready"
    assert data["ml_candidate_status"] == "ready"
    assert data["model_version"] == "v0.2"
    assert data["predictions"] == []
    assert data["validation_status"] == "validated_on_public_dataset"


def test_prediction_api_success_uses_service_result(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    greenhouse_id = int(create_greenhouse(client)["id"])
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    client.post("/api/sensors/batch", json={"items": [sensor_payload(greenhouse_id, now - timedelta(hours=23 - i)) for i in range(24)]})

    class ReadyPredictor:
        status = "ready"
        metadata = {"model_name": "test-model", "model_type": "registry", "model_version": "v0.2", "model_status": "baseline_ready", "ml_candidate_status": "under_evaluation", "training_domain": "public_real_greenhouse_tomato"}

        def predict(self, records: list[dict[str, object]], horizon_hours: int) -> dict[str, object]:
            history = pd.DataFrame({"timestamp": pd.date_range("2026-01-01", periods=24, freq="1h"), "air_temperature_c": np.arange(24) + 20, "air_humidity_pct": np.arange(24) + 50})
            return {"history": history, "source": "sensor", "input_end_time": history.timestamp.iloc[-1].tz_localize("Asia/Shanghai").tz_convert("UTC"), "forecast_method": "seasonal_24", "forecast_method_labels": ["前一天同小时统计基线"], "predictions": [{"forecast_time": (history.timestamp.iloc[-1] + pd.Timedelta(hours=h)).tz_localize("Asia/Shanghai").tz_convert("UTC"), "horizon": h, "temperature_c": 25.0, "air_humidity_pct": 70.0, "par_umol_m2_s": None, "lower_bounds": {"air_temperature_c": 24.0}, "upper_bounds": {"air_temperature_c": 26.0}, "forecast_method": "seasonal_24", "method_version": "v0.2", "methods": {"air_temperature_c": "seasonal_24", "air_humidity_pct": "seasonal_24"}, "units": {"temperature_c": "degree_Celsius", "air_humidity_pct": "percent", "par_umol_m2_s": "micromole_per_m2_second"}} for h in range(1, horizon_hours + 1)]}

    import numpy as np
    monkeypatch.setattr("app.services.prediction_service.get_environment_predictor_v02", lambda: ReadyPredictor())
    response = client.get("/api/predictions/environment", params={"greenhouse_id": greenhouse_id, "horizon_hours": 3})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "ready"
    assert data["model_status"] == "baseline_ready"
    assert data["ml_candidate_status"] == "under_evaluation"
    assert len(data["predictions"]) == 3
    assert data["predictions"][0]["temperature_c"] == 25.0
    assert data["predictions"][0]["par_umol_m2_s"] is None
    assert data["predictions"][0]["units"]["temperature_c"] == "degree_Celsius"
    assert data["forecast_method_labels"] == ["前一天同小时统计基线"]
    assert data["input_data_source"] == "sensor"


@pytest.mark.parametrize("expected_status", ["insufficient_data", "schema_mismatch"])
def test_prediction_api_propagates_input_status(client: TestClient, monkeypatch: pytest.MonkeyPatch, expected_status: str) -> None:
    greenhouse_id = int(create_greenhouse(client, code=f"GH-{expected_status}")["id"])
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    client.post("/api/sensors/batch", json={"items": [sensor_payload(greenhouse_id, now)]})

    class InvalidInputPredictor:
        status = "ready"
        metadata = {"model_name": "test", "model_type": "registry", "model_version": "v0.2", "model_status": "ready", "ml_candidate_status": "ready", "training_domain": "public_real_greenhouse_tomato"}

        def predict(self, records: list[dict[str, object]], horizon_hours: int) -> dict[str, object]:
            from app.ml.inference.predictor_v02 import PredictionInputError
            raise PredictionInputError(expected_status, "test input status")

    monkeypatch.setattr("app.services.prediction_service.get_environment_predictor_v02", lambda: InvalidInputPredictor())
    response = client.get("/api/predictions/environment", params={"greenhouse_id": greenhouse_id, "horizon_hours": 6})
    assert response.status_code == 200
    assert response.json()["data"]["status"] == expected_status
    assert response.json()["data"]["predictions"] == []


def test_prediction_api_rejects_non_contiguous_real_history(client: TestClient) -> None:
    greenhouse_id = int(create_greenhouse(client, code="GH-GAP")["id"])
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    items = [sensor_payload(greenhouse_id, now - timedelta(hours=24 - i)) for i in range(25) if i != 12]
    assert client.post("/api/sensors/batch", json={"items": items}).status_code == 200
    response = client.get("/api/predictions/environment", params={"greenhouse_id": greenhouse_id, "horizon_hours": 6})
    data = response.json()["data"]
    assert data["status"] == "insufficient_data"
    assert data["forecast_service_status"] == "ready"
    assert data["predictions"] == []
