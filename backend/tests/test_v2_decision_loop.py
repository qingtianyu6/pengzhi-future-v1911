from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.database import SessionLocal
from app.models import CropBatch, Greenhouse, SensorData
from app.services.risk_engine import DiseaseRiskEngine
from app.services.v2_decision_service import run_simulation
from app.schemas.v2_decision import SimulationRequest


def _seed_muskmelon_demo(client, crop_type="muskmelon") -> int:
    org_id = client.get("/api/auth/me").json()["data"]["organization_id"]
    with SessionLocal() as db:
        greenhouse = Greenhouse(
            organization_id=org_id,
            code="SX-MELON-01",
            name="1号香瓜棚",
            location="山东聊城莘县",
            area_mu=1.8,
            status="active",
            manager_name="测试员",
        )
        db.add(greenhouse)
        db.flush()
        db.add(CropBatch(
            greenhouse_id=greenhouse.id,
            batch_code="MELON-DEMO-2026",
            variety="莘县香瓜",
            crop_type=crop_type,
            planted_at=date(2026, 8, 10),
            growth_stage="开花坐果期",
            status="growing",
        ))
        base = datetime(2026, 9, 28, 0, 0, tzinfo=UTC).replace(tzinfo=None)
        for hour in range(24):
            db.add(SensorData(
                greenhouse_id=greenhouse.id,
                recorded_at=base + timedelta(hours=hour),
                device_id="demo-sensor-01",
                temperature=24.0 + (hour % 8) * 0.9,
                air_humidity=74.0 + min(hour, 12) * 1.1,
                soil_moisture=63.0,
                light_intensity=28.0 if 7 <= hour <= 17 else 2.0,
                co2_concentration=620.0,
                source="sensor",
                quality_flag="valid",
            ))
        db.commit()
        return greenhouse.id


def test_risk_engine_is_deterministic_without_randomness(client):
    greenhouse_id = _seed_muskmelon_demo(client)
    with SessionLocal() as db:
        records = db.query(SensorData).filter(SensorData.greenhouse_id == greenhouse_id).order_by(SensorData.recorded_at).all()
        first = DiseaseRiskEngine().evaluate_disease("gray_mold", records, "开花坐果期")
        second = DiseaseRiskEngine().evaluate_disease("gray_mold", records, "开花坐果期")
    assert first == second
    assert first["risk_72h"] >= first["current_score"]
    assert first["factors"]["contributions"][0]["value"] > 0


def test_v2_prediction_decision_execution_evaluation_profile_loop(client):
    # A measured risk comparison requires an enabled crop rule (tomato).
    greenhouse_id = _seed_muskmelon_demo(client, crop_type="tomato")

    risk_response = client.post("/api/risk/recalculate", json={
        "greenhouse_id": greenhouse_id,
        "crop_type": "tomato",
        "growth_stage": "开花坐果期",
    })
    assert risk_response.status_code == 200, risk_response.text
    risk_event = risk_response.json()["data"]
    assert risk_event["risk_72h"] > 30

    plans_response = client.post("/api/decision/generate", json={"risk_event_id": risk_event["id"]})
    assert plans_response.status_code == 200, plans_response.text
    plans = plans_response.json()["data"]
    assert len(plans) >= 3
    assert plans[0]["expected_result_json"]["risk_after"] < plans[0]["expected_result_json"]["risk_before"]

    simulation_response = client.post("/api/simulation/run", json={
        "greenhouse_id": greenhouse_id,
        "decision_plan_id": plans[0]["id"],
        "action_type": "ventilation",
        "intensity": 30,
        "duration_minutes": 30,
    })
    assert simulation_response.status_code == 200, simulation_response.text
    timeline = simulation_response.json()["data"]["timeline"]
    assert timeline[-1]["humidity"] < simulation_response.json()["data"]["baseline"]["humidity"]

    execute_response = client.post(f"/api/decision/{plans[0]['id']}/execute", json={"operator": "测试员"})
    assert execute_response.status_code == 200, execute_response.text
    task = execute_response.json()["data"]["task"]
    assert task["source_type"] == "recommendation"

    submit = client.post(f"/api/tasks/{task['id']}/submit", json={"version": task["version"], "operator": "测试员"})
    assert submit.status_code == 200, submit.text
    task = submit.json()["data"]
    start = client.post(f"/api/tasks/{task['id']}/start", json={"version": task["version"], "operator": "测试员"})
    assert start.status_code == 200, start.text
    task = start.json()["data"]

    with SessionLocal() as db:
        latest = db.query(SensorData).filter(SensorData.greenhouse_id == greenhouse_id).order_by(SensorData.recorded_at.desc()).first()
        db.add(SensorData(
            greenhouse_id=greenhouse_id,
            recorded_at=latest.recorded_at + timedelta(minutes=30),
            device_id="demo-sensor-01",
            temperature=(latest.temperature or 0) - 3.6,
            air_humidity=(latest.air_humidity or 0) - 9.0,
            soil_moisture=latest.soil_moisture,
            light_intensity=latest.light_intensity,
            co2_concentration=latest.co2_concentration,
            source="sensor",
            quality_flag="valid",
        ))
        db.commit()

    complete = client.post(f"/api/tasks/{task['id']}/complete", json={
        "version": task["version"],
        "operator": "测试员",
        "executed_at": "2026-09-28T12:40:00Z",
        "result_type": "improved",
        "execution_note": "按方案完成通风，湿度下降明显。",
        "observed_change": "湿度下降约9个百分点",
        "requires_follow_up": False,
    })
    assert complete.status_code == 200, complete.text

    evaluation = client.post(f"/api/tasks/{task['id']}/evaluate", json={"operator": "测试员"})
    assert evaluation.status_code == 200, evaluation.text
    evaluation_data = evaluation.json()["data"]
    assert evaluation_data["risk_change"] < 0
    assert evaluation_data["effect_level"] in {"有效", "效果有限"}

    profile = client.get(f"/api/greenhouses/{greenhouse_id}/profile")
    assert profile.status_code == 200, profile.text
    profile_data = profile.json()["data"]
    assert profile_data["sample_count"] >= 1
    assert profile_data["humidity_response"] > 0


def test_simulation_service_uses_profile_coefficients(client):
    greenhouse_id = _seed_muskmelon_demo(client)
    with SessionLocal() as db:
        result = run_simulation(db, SimulationRequest(
            greenhouse_id=greenhouse_id,
            action_type="ventilation",
            intensity=40,
            duration_minutes=30,
        ))
    assert result.timeline[-1]["temperature"] < result.baseline["temperature"]
    assert result.timeline[-1]["humidity"] < result.baseline["humidity"]
