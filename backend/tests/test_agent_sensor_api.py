from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.models import SensorData


def _greenhouse(client: TestClient, code: str = "SENSOR-GH-001") -> int:
    response = client.post("/api/greenhouses", json={
        "code": code,
        "name": "传感器接入棚",
        "location": "接口测试区",
        "area_mu": 2,
        "status": "active",
    })
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_sensor_ingest_api_accepts_device_payload(client: TestClient) -> None:
    greenhouse_id = _greenhouse(client)
    response = client.post("/api/v1/ingest/sensor-data", json={
        "items": [{
            "greenhouse_code": "SENSOR-GH-001",
            "device_id": "env-node-01",
            "recorded_at": "2026-08-30T20:00:00+08:00",
            "temperature": 27.2,
            "air_humidity": 71.5,
            "soil_moisture": 62,
            "light_intensity": 35.6,
            "co2_concentration": 650,
        }]
    })
    assert response.status_code == 200
    assert response.json()["data"]["success_count"] == 1

    with SessionLocal() as db:
        item = db.scalar(select(SensorData).where(SensorData.greenhouse_id == greenhouse_id))
        assert item is not None
        assert item.source == "sensor"
        assert item.device_id == "env-node-01"


def test_sensor_ingest_key_can_be_required(client: TestClient, monkeypatch) -> None:
    _greenhouse(client, "SENSOR-GH-KEY")
    monkeypatch.setattr(
        "app.api.sensor_ingest.get_settings",
        lambda: SimpleNamespace(sensor_ingest_key="secret-key"),
    )
    payload = {
        "items": [{
            "greenhouse_code": "SENSOR-GH-KEY",
            "device_id": "node-key",
            "recorded_at": "2026-08-30T20:00:00+08:00",
            "temperature": 25,
            "air_humidity": 70,
            "soil_moisture": 60,
            "light_intensity": 20,
            "co2_concentration": 600,
        }]
    }
    assert client.post("/api/v1/ingest/sensor-data", json=payload).status_code == 401
    assert client.post(
        "/api/v1/ingest/sensor-data",
        json=payload,
        headers={"X-Sensor-Key": "secret-key"},
    ).status_code == 200


def test_general_agent_uses_knowledge_without_greenhouse(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.ai_service.get_settings",
        lambda: SimpleNamespace(ai_api_key="", ai_base_url="", ai_model=""),
    )
    created = client.post("/api/v1/ai/conversations", json={"mode": "general"})
    assert created.status_code == 200
    data = created.json()["data"]
    assert data["mode"] == "general"
    assert data["greenhouse_id"] is None

    response = client.post(
        f"/api/v1/ai/conversations/{data['id']}/chat",
        json={"content": "番茄高湿时为什么容易发生叶霉病？"},
    )
    assert response.status_code == 200
    assert "知识来源" in response.text
    assert "叶霉病" in response.text
