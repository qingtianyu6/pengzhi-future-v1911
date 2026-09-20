from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from typing import Callable

from fastapi.testclient import TestClient
import pytest

from app.algorithms.warning_rules import assess_forecast_point
from app.schemas.prediction import EnvironmentPredictionData, PredictionPoint


def create_greenhouse(client: TestClient) -> int:
    response=client.post("/api/greenhouses",json={"code":"WARN-GH","name":"预警测试棚","location":"莘县","area_mu":2,"status":"active"})
    return int(response.json()["data"]["id"])


def create_batch(client: TestClient,greenhouse_id:int,crop_type:str="tomato")->None:
    response=client.post(f"/api/greenhouses/{greenhouse_id}/crop-batches",json={"batch_code":"WARN-BATCH","variety":"测试番茄" if crop_type=="tomato" else "测试甜瓜","crop_type":crop_type,"planted_at":(date.today()-timedelta(days=40)).isoformat(),"expected_harvest_at":(date.today()+timedelta(days=40)).isoformat(),"status":"growing"})
    assert response.status_code==201


def add_history(client:TestClient,greenhouse_id:int,*,temperature:float|None=None,humidity:float=60,quality_flag:str="valid")->datetime:
    end=datetime.now(UTC).replace(minute=0,second=0,microsecond=0)
    if temperature is None:
        local_hour=end.astimezone(timezone(timedelta(hours=8))).hour
        temperature=25 if 6<=local_hour<18 else 19
    items=[{"greenhouse_id":greenhouse_id,"recorded_at":(end-timedelta(hours=23-i)).isoformat(),"temperature":temperature,"air_humidity":humidity,"soil_moisture":62,"light_intensity":30,"co2_concentration":600,"source":"sensor","quality_flag":quality_flag} for i in range(24)]
    assert client.post("/api/sensors/batch",json={"items":items}).status_code==200
    return end


def prediction(greenhouse_id:int,values:list[tuple[float,float]],status:str="ready")->EnvironmentPredictionData:
    now=datetime(2026,8,22,0,tzinfo=UTC);points=[]
    if status=="ready":
        for index,(temperature,humidity) in enumerate(values,1):
            points.append(PredictionPoint(forecast_time=now+timedelta(hours=index),horizon=index,temperature_c=temperature,air_humidity_pct=humidity,par_umol_m2_s=None,lower_bounds={"air_temperature_c":temperature-2,"air_humidity_pct":humidity-5},upper_bounds={"air_temperature_c":temperature+2,"air_humidity_pct":humidity+5},forecast_method="air_temperature_c=seasonal_24; air_humidity_pct=seasonal_residual_gru",method_version="v0.2",methods={"air_temperature_c":"seasonal_24","air_humidity_pct":"seasonal_residual_gru"},units={"temperature_c":"degree_Celsius","air_humidity_pct":"percent","par_umol_m2_s":"micromole_per_m2_second"}))
    return EnvironmentPredictionData(greenhouse_id=greenhouse_id,status=status,forecast_service_status="ready",model_status="ready",ml_candidate_status="ready",model_name="test",model_version="v0.2",training_domain="public_real_greenhouse_tomato",validation_status="validated_on_public_dataset",input_data_source="sensor",history_hours=24,horizon_hours=6,predictions=points,rules_status="rules_unavailable",generated_at=now,crop_type="tomato",crop_match_status="matched_public_tomato",cross_crop_warning=False,cross_region_warning=True)


def install_forecast(monkeypatch:pytest.MonkeyPatch,values:Callable[[],list[tuple[float,float]]]|None=None,status:str="ready")->None:
    def fake(_db:object,greenhouse_id:int,growth_stage:str|None,*,crop_type:str="tomato",as_of:datetime|None=None):
        result=prediction(greenhouse_id,values() if values else [(26,65)]*6,status)
        risks=[assess_forecast_point(point.model_dump(),growth_stage,data_source="sensor",crop_type=crop_type) for point in result.predictions]
        return result,risks
    monkeypatch.setattr("app.services.warning_service.evaluate_future_risks",fake)


def setup_normal(client:TestClient,monkeypatch:pytest.MonkeyPatch)->int:
    greenhouse_id=create_greenhouse(client);create_batch(client,greenhouse_id);add_history(client,greenhouse_id);install_forecast(monkeypatch);return greenhouse_id


def test_normal_current_and_forecast_create_no_agricultural_warning(client:TestClient,monkeypatch:pytest.MonkeyPatch)->None:
    greenhouse_id=setup_normal(client,monkeypatch)
    data=client.post("/api/warnings/evaluate",json={"greenhouse_id":greenhouse_id}).json()["data"]
    assert data["warnings"]==[], data
    assert data["data_source"]=="sensor"
    assert data["validation_status"]=="validated_on_public_dataset"


@pytest.mark.parametrize(("temperature","humidity","warning_type"),[(36,60,"high_temperature"),(26,88,"high_air_humidity")])
def test_current_threshold_violation_creates_warning(client:TestClient,monkeypatch:pytest.MonkeyPatch,temperature:float,humidity:float,warning_type:str)->None:
    greenhouse_id=create_greenhouse(client);create_batch(client,greenhouse_id);add_history(client,greenhouse_id,temperature=temperature,humidity=humidity);install_forecast(monkeypatch)
    data=client.post("/api/warnings/evaluate",json={"greenhouse_id":greenhouse_id}).json()["data"]
    assert warning_type in {item["warning_type"] for item in data["warnings"]}


def test_future_expected_warning_and_seasonal_method_disclosure(client:TestClient,monkeypatch:pytest.MonkeyPatch)->None:
    greenhouse_id=create_greenhouse(client);create_batch(client,greenhouse_id);add_history(client,greenhouse_id);install_forecast(monkeypatch,lambda:[(36,65)]*2+[(26,65)]*4)
    data=client.post("/api/warnings/evaluate",json={"greenhouse_id":greenhouse_id}).json()["data"]
    warning=next(item for item in data["warnings"] if item["warning_type"]=="high_temperature")
    assert warning["certainty"]=="expected"
    assert warning["evidence_json"]["continuous_hours"]==2
    assert warning["forecast_methods_json"]["h1"]["air_temperature_c"]=="seasonal_24"


def test_duplicate_evaluation_updates_instead_of_creating(client:TestClient,monkeypatch:pytest.MonkeyPatch)->None:
    greenhouse_id=create_greenhouse(client);create_batch(client,greenhouse_id);add_history(client,greenhouse_id);install_forecast(monkeypatch,lambda:[(36,65)]*6)
    first=client.post("/api/warnings/evaluate",json={"greenhouse_id":greenhouse_id}).json()["data"]
    second=client.post("/api/warnings/evaluate",json={"greenhouse_id":greenhouse_id}).json()["data"]
    assert first["created_count"]==1
    assert second["created_count"]==0 and second["updated_count"]==1
    assert client.get("/api/warnings").json()["data"]["total"]==1


def test_risk_escalation_updates_existing_event(client:TestClient,monkeypatch:pytest.MonkeyPatch)->None:
    current={"temperature":32.0};greenhouse_id=create_greenhouse(client);create_batch(client,greenhouse_id);add_history(client,greenhouse_id);install_forecast(monkeypatch,lambda:[(current["temperature"],65)]*6)
    first=client.post("/api/warnings/evaluate",json={"greenhouse_id":greenhouse_id}).json()["data"]["warnings"][0]
    current["temperature"]=42
    second=client.post("/api/warnings/evaluate",json={"greenhouse_id":greenhouse_id}).json()["data"]["warnings"][0]
    assert second["id"]==first["id"] and second["risk_score"]>first["risk_score"]
    assert second["evidence_json"]["updates"]


def test_no_active_batch_returns_rules_unavailable_without_false_warning(client:TestClient,monkeypatch:pytest.MonkeyPatch)->None:
    greenhouse_id=create_greenhouse(client);add_history(client,greenhouse_id);install_forecast(monkeypatch)
    data=client.post("/api/warnings/evaluate",json={"greenhouse_id":greenhouse_id}).json()["data"]
    assert data["current_risk"]["data_status"]=="insufficient"
    assert data["warnings"] == []
    assert "没有活跃种植批次" in data["data_quality_issues"]


def test_forecast_unavailable_still_returns_current_warning(client:TestClient,monkeypatch:pytest.MonkeyPatch)->None:
    greenhouse_id=create_greenhouse(client);create_batch(client,greenhouse_id);add_history(client,greenhouse_id,temperature=38);install_forecast(monkeypatch,status="not_trained")
    data=client.post("/api/warnings/evaluate",json={"greenhouse_id":greenhouse_id}).json()["data"]
    assert data["forecast_status"]=="not_trained"
    assert any(item["warning_type"]=="high_temperature" for item in data["warnings"])


def test_warning_lifecycle_and_decision_review(client:TestClient,monkeypatch:pytest.MonkeyPatch)->None:
    greenhouse_id=create_greenhouse(client);create_batch(client,greenhouse_id);add_history(client,greenhouse_id);install_forecast(monkeypatch,lambda:[(36,65)]*6)
    evaluation=client.post("/api/warnings/evaluate",json={"greenhouse_id":greenhouse_id}).json()["data"];warning=evaluation["warnings"][0];recommendation=evaluation["recommendations"][0]
    assert recommendation["status"]=="pending_review" and recommendation["task_draft"]["requires_manual_confirmation"] is True
    assert "系统已控制" not in " ".join(recommendation["action_steps_json"])
    accepted=client.post(f"/api/decisions/{recommendation['id']}/accept",json={"operator":"管理员","note":"同意现场检查"})
    assert accepted.json()["data"]["status"]=="accepted"
    acknowledged=client.post(f"/api/warnings/{warning['id']}/acknowledge",json={"operator":"管理员","note":"已安排复核"})
    assert acknowledged.json()["data"]["status"]=="acknowledged"
    resolved=client.post(f"/api/warnings/{warning['id']}/resolve",json={"operator":"管理员","note":"环境恢复"})
    assert resolved.json()["data"]["status"]=="resolved"


def test_dismiss_requires_reason_and_404s_are_clear(client:TestClient,monkeypatch:pytest.MonkeyPatch)->None:
    greenhouse_id=setup_normal(client,monkeypatch)
    assert client.post("/api/warnings/999/dismiss",json={"operator":"管理员"}).status_code==422
    assert client.get("/api/warnings/999").status_code==404
    assert client.get("/api/decisions/999").status_code==404
    assert client.get("/api/warnings",params={"page":0}).status_code==422


def test_warning_summary_and_pagination(client:TestClient,monkeypatch:pytest.MonkeyPatch)->None:
    greenhouse_id=create_greenhouse(client);create_batch(client,greenhouse_id);add_history(client,greenhouse_id);install_forecast(monkeypatch,lambda:[(36,88)]*6)
    client.post("/api/warnings/evaluate",json={"greenhouse_id":greenhouse_id})
    page=client.get("/api/warnings",params={"page":1,"page_size":1}).json()["data"]
    summary=client.get("/api/warnings/summary").json()["data"]
    assert len(page["items"])==1 and page["total"]>=3
    assert summary["open_total"]==page["total"]
    assert summary["latest_warning"] is not None
