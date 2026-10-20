from app.services import investigation_service as s
from app.database import SessionLocal
from app.models.agronomist import AgronomyRecord
from sqlalchemy import select, func
from test_final_product import create_context

def test_active_observation_and_dynamic_revision():
    initial = s.demo(s.Demo(budget=3))
    a = initial["payload"]["analysis"]
    assert len(a["candidates"]) == 6 and a["next"]["target"]
    assert a["candidates"][0]["id"] == "microclimate"
    changed = s.demo(s.Demo(budget=3, evidence=[
        s.Evidence(action="local", zone="东侧", humidity=45, note="异常区实测"),
        s.Evidence(action="back", zone="东侧", features={"webbing": True, "mold": False}, note="可见细蛛网，未见霉层")]))
    b = changed["payload"]["analysis"]
    assert b["candidates"][0]["id"] == "mites"
    assert b["next"]["id"] != a["next"]["id"]
    assert all(x["id"] not in {"local", "back"} for x in b["rankings"])
    assert len(changed["payload"]["history"]) == 3
    assert next(c for c in b["candidates"] if c["id"] == "microclimate")["conflict"]

def test_budget_and_spatial_rules():
    for budget in (1, 2, 3, 0):
        result = s.demo(s.Demo(budget=budget))["payload"]["analysis"]
        assert 0<len(result["plan"]) <= (budget or 10)
        assert all(a["score"]>0 and a["can_execute"] for a in result["plan"])
        assert result["next"]["score"] == result["rankings"][0]["score"]
    result = s.demo(s.Demo(budget=1, evidence=[s.Evidence(action="back", zone="东侧", features={"webbing": True})]))
    assert result["payload"]["analysis"]["next"] is None
    assert result["status"] == "budget_exhausted"
    from app.services.errors import ServiceError
    import pytest
    with pytest.raises(ServiceError):
        s.demo(s.Demo(budget=1, evidence=[s.Evidence(action="back", zone="东侧", features={"webbing": True}),
            s.Evidence(action="front", zone="东侧", features={"stippling": True})]))
    with pytest.raises(ServiceError):
        s.demo(s.Demo(evidence=[s.Evidence(action="normal", zone="东侧", humidity=60)]))

def test_persistence_version_permissions_and_guest_isolation(client, monkeypatch):
    gid, _ = create_context(client, "INVESTIGATE")
    response = client.post("/api/investigate", json={"greenhouse_id": gid, "question": "东侧番茄叶片异常，中央湿度正常", "budget": 3})
    assert response.status_code == 201, response.text
    r = response.json()["data"]
    assert r["payload"]["context"]["source"].startswith("正式账号")
    updated = client.post(f"/api/investigate/{r['id']}/evidence", json={"version": r["version"],
        "evidence": {"action": "back", "zone": "东侧", "features": {"webbing": True, "mold": False}}})
    assert updated.status_code == 200, updated.text
    saved = updated.json()["data"]
    assert saved["version"] > r["version"] and len(saved["payload"]["history"]) == 2
    assert client.post(f"/api/investigate/{r['id']}/evidence", json={"version": r["version"],
        "evidence": {"action": "front", "zone": "东侧", "features": {"stippling": True}}}).status_code == 409
    assert client.get(f"/api/investigate?greenhouse_id={gid}").json()["data"][0]["id"] == r["id"]
    assert client.get(f"/api/agronomist/records?greenhouse_id={gid}").status_code == 200
    from app.services import ai_provider
    class Unavailable:
        async def chat(self, *args):
            raise ai_provider.LLMProviderError("测试模型不可用")
    monkeypatch.setattr(ai_provider, "get_llm_provider", lambda: Unavailable())
    explanation = client.post(f"/api/investigate/{r['id']}/explain").json()["data"]
    assert explanation["mode"] == "rules_only" and "不可用" in explanation["text"]
    other = client.post("/api/auth/register", json={"display_name":"其他组织", "phone":"13900000012","organization":"隔离", "password":"Greenhouse2026"}).json()["data"]
    assert client.get(f"/api/investigate/{r['id']}", headers={"Authorization":"Bearer "+other["token"]}).status_code == 404
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(AgronomyRecord))
    for features in ({"webbing": True}, {"mold": True}):
        result = client.post("/api/investigate-demo/analyze", json={"evidence":[{"action":"back","zone":"东侧","features":features}]})
        assert result.status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(AgronomyRecord)) == before
    finish = client.post(f"/api/investigate/{r['id']}/finish", json={"version":saved["version"],"note":"需农艺师复核叶背观察"})
    assert finish.status_code == 200 and finish.json()["data"]["status"] == "completed"
    assert client.post(f"/api/investigate/{r['id']}/evidence",json={"version":finish.json()["data"]["version"],"evidence":{"action":"front","zone":"东侧","features":{"stippling":True}}}).status_code == 409

def test_measurement_pair_requires_different_locations_and_comparable_time():
    from datetime import UTC, datetime, timedelta
    t = datetime.now(UTC)
    paired = s.demo(s.Demo(evidence=[s.Evidence(action="local",zone="东侧",humidity=95,observed_at=t),
        s.Evidence(action="normal",zone="中央",humidity=60,observed_at=t)]))
    assert paired["payload"]["analysis"]["facts"]["humidity_gap"] is True
    distant = s.demo(s.Demo(evidence=[s.Evidence(action="local",zone="东侧",humidity=95,observed_at=t-timedelta(hours=3)),
        s.Evidence(action="normal",zone="中央",humidity=60,observed_at=t)]))
    assert "humidity_gap" not in distant["payload"]["analysis"]["facts"]
