from datetime import UTC, datetime, timedelta
from sqlalchemy import select
from app.database import SessionLocal, initialize_database
from app.models import SensorData, User
from app.models.greenhouse_device import GreenhouseDevice


def create(client, code="MANAGEMENT-01"):
    result = client.post("/api/greenhouses", json={"code": code, "name": "管理测试棚", "location": "测试区", "area_mu": 2})
    assert result.status_code == 201
    return result.json()["data"]["id"]


def bind(client, gid, device="NODE-01"):
    return client.post(f"/api/greenhouses/{gid}/devices", json={"device_id": device, "name": "温湿度传感器", "kind": "environment"})


def report(gid, age, device="NODE-01", source="sensor"):
    with SessionLocal() as db:
        db.add(SensorData(greenhouse_id=gid, device_id=device, recorded_at=datetime.now(UTC)-timedelta(hours=age), temperature=25, source=source, quality_flag="valid"))
        db.commit()


def test_binding_is_idempotent_and_not_a_sensor_reading(client):
    gid=create(client)
    assert bind(client,gid).status_code == 200
    assert bind(client,gid).status_code == 200
    devices=client.get(f"/api/greenhouses/{gid}/devices").json()["data"]
    assert len(devices)==1 and not devices[0]["online"] and devices[0]["last_seen"] is None
    summary=client.get("/api/greenhouses/management-summary").json()["data"]
    assert (summary["total"],summary["connected"],summary["device_count"],summary["online_devices"])==(1,0,1,0)
    with SessionLocal() as db:
        assert db.scalar(select(SensorData.id)) is None


def test_online_uses_latest_device_report_not_registration_or_import(client):
    gid=create(client)
    bind(client,gid)
    report(gid,3)
    report(gid,.1,"NODE-02")
    report(gid,.2,"FILE-ONLY",source="import")
    rows=client.get(f"/api/greenhouses/{gid}/devices").json()["data"]
    assert len(rows)==2
    assert {r["device_id"]:r["online"] for r in rows}=={"NODE-01":False,"NODE-02":True}
    summary=client.get("/api/greenhouses/management-summary").json()["data"]
    assert summary["online_devices"]==1 and summary["connected"]==1
    row=client.get(f"/api/greenhouses/{gid}").json()["data"]
    assert row["device_count"]==2 and row["online_device_count"]==1


def test_unbinding_retains_history_and_greenhouse_delete_cleans_binding(client):
    gid=create(client)
    bind(client,gid); report(gid,.1)
    assert client.delete(f"/api/greenhouses/{gid}/devices/NODE-01").status_code==200
    rows=client.get(f"/api/greenhouses/{gid}/devices").json()["data"]
    assert len(rows)==1 and rows[0]["registered"] is False
    bind(client,gid,"NODE-02")
    assert client.delete(f"/api/greenhouses/{gid}").status_code==200
    with SessionLocal() as db:
        assert db.scalar(select(GreenhouseDevice.id)) is None


def test_device_access_and_aggregates_are_organization_scoped(client):
    gid=create(client); bind(client,gid); report(gid,.1)
    second=client.post("/api/auth/register",json={"display_name":"另一用户","phone":"13900000001","organization":"另一个组织","password":"Greenhouse2026"}).json()["data"]
    client.headers.update({"Authorization":f"Bearer {second['token']}"})
    assert client.get(f"/api/greenhouses/{gid}/devices").status_code==404
    assert bind(client,gid).status_code==404
    assert client.delete(f"/api/greenhouses/{gid}/devices/NODE-01").status_code==404
    summary=client.get("/api/greenhouses/management-summary").json()["data"]
    assert summary["total"]==summary["connected"]==summary["device_count"]==summary["online_devices"]==0


def test_observer_cannot_bind_and_invalid_device_rejected(client):
    gid=create(client)
    assert bind(client,gid,"invalid/device").status_code==422
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.phone=="13900000000")); user.role="observer"; db.commit()
    assert client.get(f"/api/greenhouses/{gid}/devices").status_code==200
    assert bind(client,gid).status_code==403


def test_summary_global_counts_are_independent_of_list_pagination_and_upgrade_is_repeatable(client):
    for i in range(5): create(client,f"MANAGEMENT-{i}")
    assert len(client.get("/api/greenhouses?page_size=4").json()["data"]["items"])==4
    assert client.get("/api/greenhouses/management-summary").json()["data"]["total"]==5
    initialize_database(); initialize_database()
    assert client.get("/api/greenhouses/management-summary").json()["data"]["total"]==5
