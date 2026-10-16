from datetime import UTC, date, datetime, timedelta

from app.database import SessionLocal
from app.models import FarmTask, Intervention, SensorData, WarningEvent


def _register(client, phone, name):
    response = client.post("/api/auth/register", json={
        "display_name": name, "phone": phone, "organization": name,
        "password": "Greenhouse2026",
    })
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def test_organization_isolation_and_login_requirement(client):
    first = client.post("/api/greenhouses", json={
        "code": "TENANT-A", "name": "甲棚", "location": "测试地", "area_mu": 1.0,
    })
    assert first.status_code == 201, first.text
    greenhouse_id = first.json()["data"]["id"]
    other = _register(client, "13800000002", "乙管理员")
    assert client.get("/api/greenhouses", headers=other).json()["data"]["total"] == 0
    assert client.get(f"/api/greenhouses/{greenhouse_id}", headers=other).status_code == 404
    assert client.get("/api/greenhouses", headers={"Authorization": ""}).status_code == 401
    assert client.post("/api/tasks", headers=other, json={
        "greenhouse_id": greenhouse_id, "title": "越权任务", "description": "test",
        "action_type": "manual_observation", "created_by": "乙管理员",
    }).status_code in {403, 404}


def test_observer_can_read_but_cannot_write(client):
    created = client.post("/api/auth/members", json={
        "display_name": "观察人员", "phone": "13800000003",
        "password": "Greenhouse2026", "role": "observer",
    })
    assert created.status_code == 200, created.text
    login = client.post("/api/auth/login", json={
        "phone": "13800000003", "password": "Greenhouse2026",
    })
    headers = {"Authorization": f"Bearer {login.json()['data']['token']}"}
    assert client.get("/api/greenhouses", headers=headers).status_code == 200
    assert client.post("/api/greenhouses", headers=headers, json={
        "code": "NO-WRITE", "name": "不可创建", "location": "测试地", "area_mu": 1.0,
    }).status_code == 403
    assert client.get("/api/auth/members", headers=headers).status_code == 403


def test_tomato_heat_humidity_choice_and_follow_up(client):
    greenhouse = client.post("/api/greenhouses", json={
        "code": "V20-TOMATO", "name": "番茄试验棚", "location": "测试地", "area_mu": 1.0,
    })
    assert greenhouse.status_code == 201, greenhouse.text
    greenhouse_id = greenhouse.json()["data"]["id"]
    batch = client.post(f"/api/greenhouses/{greenhouse_id}/crop-batches", json={
        "batch_code": "V20-BATCH", "variety": "番茄", "crop_type": "tomato",
        "planted_at": (date.today() - timedelta(days=55)).isoformat(),
        "growth_stage": "开花坐果期", "status": "growing",
    })
    assert batch.status_code == 201, batch.text
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    readings = [{
        "greenhouse_id": greenhouse_id, "recorded_at": (now - timedelta(hours=23 - i)).isoformat(),
        "temperature": 35.0 if i == 23 else 27.0,
        "air_humidity": 90.0 if i == 23 else 70.0,
        "soil_moisture": 60.0, "light_intensity": 30.0,
        "co2_concentration": 700.0, "source": "sensor", "quality_flag": "valid",
    } for i in range(24)]
    inserted = client.post("/api/sensors/batch", json={"items": readings})
    assert inserted.status_code == 200, inserted.text
    evaluation = client.post("/api/warnings/evaluate", json={"greenhouse_id": greenhouse_id})
    assert evaluation.status_code == 200, evaluation.text
    combo = next(item for item in evaluation.json()["data"]["warnings"]
                 if item["warning_type"] == "temperature_humidity_combination")
    candidates = client.get(f"/api/warnings/{combo['id']}/candidates")
    assert candidates.status_code == 200, candidates.text
    assert len(candidates.json()["data"]) == 4
    assert client.post(f"/api/tasks/from-warning/{combo['id']}",
                       json={"created_by": "测试管理员"}).status_code == 409
    selected = client.post(f"/api/candidates/{candidates.json()['data'][0]['id']}/select",
                           json={"reason": "现场顶窗可用"})
    assert selected.status_code == 200, selected.text
    item = selected.json()["data"]
    assert item["task_id"] and item["before_snapshot_json"]["temperature"] == 35.0
    task_id = item["task_id"]
    assert client.post(f"/api/candidates/{candidates.json()['data'][1]['id']}/select",
                       json={"reason": "改选方案"}).status_code == 409
    task = client.get(f"/api/tasks/{task_id}").json()["data"]
    submitted = client.post(f"/api/tasks/{task_id}/submit", json={
        "version": task["version"], "operator": "测试管理员"})
    assert submitted.status_code == 200, submitted.text
    started = client.post(f"/api/tasks/{task_id}/start", json={
        "version": submitted.json()["data"]["version"], "operator": "测试管理员"})
    assert started.status_code == 200, started.text
    with SessionLocal() as db:
        task_record = db.get(FarmTask, task_id)
        intervention = db.get(Intervention, item["id"])
        earlier = datetime.now(UTC) - timedelta(minutes=65)
        task_record.started_at = earlier
        intervention.started_at = earlier
        for minutes_ago, temperature, humidity in ((35, 29.0, 71.0), (34, 31.0, 80.0),
                                                   (29, 32.0, 82.0), (4, 30.0, 76.0)):
            db.add(SensorData(greenhouse_id=greenhouse_id,
                              recorded_at=(datetime.now(UTC) - timedelta(minutes=minutes_ago)).replace(tzinfo=None),
                              temperature=temperature, air_humidity=humidity, soil_moisture=60.0,
                              light_intensity=30.0, co2_concentration=700.0,
                              source="sensor", quality_flag="suspect" if minutes_ago == 35 else "valid"))
        db.commit()
    assert client.post(f"/api/warnings/{combo['id']}/resolve", json={
        "operator": "测试管理员", "note": "提前解除"}).status_code == 409
    for offset in (30, 60):
        recorded = client.post(f"/api/interventions/{item['id']}/observations", json={
            "offset_minutes": offset, "manual_status": "结露减轻",
            "risk_resolved": offset == 60, "notes": "现场复查",
        })
        assert recorded.status_code == 200, recorded.text
    final = client.get(f"/api/interventions/{item['id']}").json()["data"]
    assert len(final["observations"]) == 2
    assert final["observations"][0]["temperature"] == 31.0
    assert final["observations"][1]["temperature"] == 30.0
    assert final["observations"][0]["sample_delta_seconds"] is not None
    assert final["status"] == "in_progress"
    task = client.get(f"/api/tasks/{task_id}").json()["data"]
    completed = client.post(f"/api/tasks/{task_id}/complete", json={
        "version": task["version"], "operator": "测试管理员",
        "executed_at": datetime.now(UTC).isoformat(), "result_type": "improved",
        "execution_note": "调整顶窗后检查通风，现场确认环境改善",
    })
    assert completed.status_code == 200, completed.text
    case = client.get(f"/api/cases/{item['id']}")
    assert case.status_code == 200, case.text
    memory = case.json()["data"]
    assert memory["complete"] is True
    assert memory["selection_reason"] == "现场顶窗可用"
    assert len(memory["candidates"]) == 4
    assert len(memory["observations"]) == 2
    assert memory["execution"]["feedback_notes"]
    assert client.post(f"/api/warnings/{combo['id']}/resolve", json={
        "operator": "测试管理员", "note": "60 分钟复测后人工确认"}).status_code == 200
    with SessionLocal() as db:
        source = db.get(WarningEvent, combo["id"])
        columns = {column.name: getattr(source, column.name) for column in WarningEvent.__table__.columns
                   if column.name not in {"id", "fingerprint"}}
        query_warning = WarningEvent(**columns, fingerprint="similar-case-query-warning")
        db.add(query_warning)
        db.commit()
        query_id = query_warning.id
    similar = client.get(f"/api/warnings/{query_id}/similar-cases")
    assert similar.status_code == 200, similar.text
    result = similar.json()["data"]
    assert result["total_eligible_cases"] == 1
    assert result["matches"][0]["case"]["id"] == item["id"]
    assert result["action_evidence"][0]["case_count"] == 1
    assert result["action_evidence"][0]["with_60min_measurement"] == 1
    other = _register(client, "13800000009", "隔离验证管理员")
    assert client.get(f"/api/cases/{item['id']}", headers=other).status_code == 404
    assert client.get("/api/cases", headers=other).json()["data"]["total"] == 0
    assert client.get(f"/api/warnings/{query_id}/similar-cases", headers=other).status_code == 404
