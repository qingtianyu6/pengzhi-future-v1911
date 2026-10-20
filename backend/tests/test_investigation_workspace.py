"""The autonomous workspace reads real sources, without inventing observations."""
from test_final_product import create_context


def start(client, suffix="AUTO"):
    gid, _ = create_context(client, suffix)
    r = client.post("/api/investigate", json={"greenhouse_id": gid,
        "question": "东侧番茄叶片异常，请分析环境与叶背线索", "budget": 3})
    assert r.status_code == 201, r.text
    return r.json()["data"]


def test_refresh_scoped_context_and_version(client):
    original = start(client)
    response = client.post(f"/api/investigate/{original['id']}/refresh", json={"version": original["version"]})
    assert response.status_code == 200, response.text
    saved = response.json()["data"]
    p = saved["payload"]
    assert saved["version"] > original["version"]
    assert p["evidence"] == []  # Source reads are not human field observations.
    assert p["analysis"]["remaining"] == 3
    assert p["autonomy_runs"][-1]["state"] == "waiting_for_evidence"
    steps = p["autonomy_runs"][-1]["steps"]
    assert len(steps) == 5
    assert steps[0]["count"] == len(p["context"]["history"])
    assert steps[3]["count"] == len(p["context"]["knowledge"])
    assert client.post(f"/api/investigate/{saved['id']}/refresh", json={"version": original["version"]}).status_code == 409
    again = client.post(f"/api/investigate/{saved['id']}/refresh", json={"version": saved["version"]}).json()["data"]
    assert again["payload"]["history"] == p["history"]  # No invented judgment changes.
    assert len(again["payload"]["autonomy_runs"]) == 2


def test_refresh_after_evidence_preserves_revision_and_budget(client):
    r = start(client, "AUTOREVISE")
    response = client.post(f"/api/investigate/{r['id']}/evidence", json={"version": r["version"],
        "evidence": {"action": "back", "zone": "东侧", "features": {"webbing": True, "mold": False}}})
    assert response.status_code == 200, response.text
    r = response.json()["data"]
    leader = r["payload"]["analysis"]["candidates"][0]["id"]
    after = client.post(f"/api/investigate/{r['id']}/refresh", json={"version": r["version"]}).json()["data"]
    assert after["payload"]["analysis"]["candidates"][0]["id"] == leader == "mites"
    assert after["payload"]["analysis"]["remaining"] == 2
    assert len(after["payload"]["evidence"]) == 1
    assert not any(a["id"] == "back" for a in after["payload"]["analysis"]["rankings"])


def test_refresh_rejects_closed_and_other_organization(client):
    r = start(client, "AUTOACCESS")
    closed = client.post(f"/api/investigate/{r['id']}/finish", json={"version": r["version"], "note": "线索仍待农艺师人工核实"}).json()["data"]
    assert client.post(f"/api/investigate/{r['id']}/refresh", json={"version": closed["version"]}).status_code == 409
    other = client.post("/api/auth/register", json={"display_name": "另一组织", "phone": "13900000012",
        "organization": "隔离组织", "password": "Greenhouse2026"}).json()["data"]
    assert client.post(f"/api/investigate/{r['id']}/refresh", headers={"Authorization": "Bearer " + other["token"]},
        json={"version": closed["version"]}).status_code == 404
