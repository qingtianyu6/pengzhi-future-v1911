from datetime import UTC, date, datetime, timedelta
import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.database import SessionLocal
from app.models import DecisionRecommendation, DiseaseRecognitionRecord, WarningEvent
from app.schemas.prediction import EnvironmentPredictionData


def create_context(client: TestClient, suffix: str = "A", crop_type: str = "tomato") -> tuple[int, int]:
    greenhouse = client.post("/api/greenhouses", json={
        "code": f"TASK-GH-{suffix}", "name": f"任务测试棚{suffix}", "location": "莘县",
        "area_mu": 2.5, "status": "active",
    }).json()["data"]
    batch = client.post(f"/api/greenhouses/{greenhouse['id']}/crop-batches", json={
        "batch_code": f"TASK-BATCH-{suffix}", "variety": "测试番茄",
        "crop_type": crop_type, "planted_at": (date.today() - timedelta(days=50)).isoformat(),
        "expected_harvest_at": (date.today() + timedelta(days=50)).isoformat(),
        "status": "growing",
    }).json()["data"]
    recorded_at = datetime.now(UTC).replace(microsecond=0)
    response = client.post("/api/sensors/batch", json={"items": [{
        "greenhouse_id": greenhouse["id"], "recorded_at": recorded_at.isoformat(),
        "temperature": 26, "air_humidity": 68, "soil_moisture": 62,
        "light_intensity": 35, "co2_concentration": 650,
        "source": "sensor", "quality_flag": "valid",
    }]})
    assert response.status_code == 200
    return greenhouse["id"], batch["id"]


def fake_prediction(greenhouse_id: int, _hours: int) -> EnvironmentPredictionData:
    return EnvironmentPredictionData(
        greenhouse_id=greenhouse_id, status="insufficient_data", forecast_service_status="ready",
        model_status="ready", ml_candidate_status="ready", model_name="test",
        model_version="v0.2", training_domain="public_real_greenhouse_tomato",
        validation_status="validated_on_public_dataset", input_data_source="sensor",
        history_hours=24, horizon_hours=6, predictions=[], rules_status="tomato_rule_active",
        generated_at=datetime.now(UTC), crop_type="tomato",
        crop_match_status="matched_public_tomato", cross_crop_warning=False,
        warnings=["测试窗口不足，不补随机结果"],
    )


@pytest.fixture
def task_context(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    greenhouse_id, batch_id = create_context(client)
    monkeypatch.setattr("app.services.task_service.predict_environment",
                        lambda _db, greenhouse_id, hours: fake_prediction(greenhouse_id, hours))
    monkeypatch.setattr("app.services.task_service.UPLOAD_DIR", tmp_path / "task-uploads")
    return greenhouse_id, batch_id


def manual_payload(greenhouse_id: int, batch_id: int) -> dict:
    return {
        "greenhouse_id": greenhouse_id, "crop_batch_id": batch_id,
        "title": "检查棚内通风", "description": "人工巡查通风口和叶面结露",
        "action_type": "ventilation_check", "priority": "medium", "created_by": "管理员",
    }


def create_manual(client: TestClient, greenhouse_id: int, batch_id: int) -> dict:
    response = client.post("/api/tasks", json=manual_payload(greenhouse_id, batch_id))
    assert response.status_code == 200, response.text
    return response.json()["data"]


def insert_warning(greenhouse_id: int, batch_id: int) -> tuple[int, int]:
    with SessionLocal() as db:
        now = datetime.now(UTC)
        warning = WarningEvent(
            greenhouse_id=greenhouse_id, crop_batch_id=batch_id, crop_type="tomato",
            crop_rule_version="tomato-rule-v0.1", crop_match_status="matched_public_tomato",
            cross_region_warning=True, expert_calibration_required=False,
            warning_code="test_high_humidity", warning_type="high_air_humidity",
            severity="warning", risk_score=72, certainty="expected", title="高湿预警",
            description="传感器数据触发的测试预警", evidence_json={"source": "sensor"},
            status="open", fingerprint=f"task-warning-{greenhouse_id}",
            rule_version="tomato-rule-v0.1", forecast_methods_json={},
            data_source="sensor", calibration_status="legacy_not_applicable",
            first_triggered_at=now, last_triggered_at=now,
        )
        db.add(warning); db.flush()
        recommendation = DecisionRecommendation(
            warning_event_id=warning.id, greenhouse_id=greenhouse_id, crop_batch_id=batch_id,
            crop_type="tomato", crop_rule_version="tomato-rule-v0.1",
            recommendation_code="test_humidity_control", priority="high",
            action_type="condensation_inspection", title="人工检查叶面结露",
            rationale="高湿风险需要现场核验", action_steps_json=["检查叶面", "记录结露"],
            safety_note="仅人工检查，不控制设备", status="pending_review",
            rule_version="tomato-decision-rule-v0.1", generated_at=now,
        )
        db.add(recommendation); db.commit()
        return warning.id, recommendation.id


def insert_disease(greenhouse_id: int, batch_id: int, *, recognition_status: str = "recognized",
                   review_status: str = "confirmed", crop_type: str = "tomato") -> int:
    with SessionLocal() as db:
        record = DiseaseRecognitionRecord(
            greenhouse_id=greenhouse_id, crop_batch_id=batch_id, crop_type=crop_type,
            image_path="uploads/disease/test.jpg", image_sha256=f"{'a' * 60}{batch_id:04d}",
            original_filename="leaf.jpg", predicted_class="early_blight",
            predicted_class_name="早疫病", confidence=0.91, top3_json=[],
            recognition_status=recognition_status, model_version="tomato-disease-v0.1",
            model_status="under_evaluation", local_calibration_status="not_calibrated",
            review_status=review_status,
            reviewed_class="early_blight" if review_status in {"confirmed", "corrected"} else None,
        )
        db.add(record); db.commit(); return record.id


def submit_assign_start(client: TestClient, task: dict) -> dict:
    task = client.post(f"/api/tasks/{task['id']}/submit", json={
        "version": task["version"], "operator": "管理员",
    }).json()["data"]
    task = client.post(f"/api/tasks/{task['id']}/assign", json={
        "version": task["version"], "operator": "管理员", "assignee_name": "巡棚员甲",
    }).json()["data"]
    response = client.post(f"/api/tasks/{task['id']}/start", json={
        "version": task["version"], "operator": "巡棚员甲",
    })
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_manual_create_and_invalid_context_and_forbidden_actions(client: TestClient, task_context) -> None:
    greenhouse_id, batch_id = task_context
    task = create_manual(client, greenhouse_id, batch_id)
    assert task["status"] == "draft" and task["version"] == 1
    assert task["evidence_snapshot_json"]["data_source"] == "sensor"
    invalid_greenhouse = manual_payload(9999, batch_id)
    assert client.post("/api/tasks", json=invalid_greenhouse).status_code == 404
    invalid_batch = manual_payload(greenhouse_id, 9999)
    assert client.post("/api/tasks", json=invalid_batch).status_code == 404
    forbidden = manual_payload(greenhouse_id, batch_id); forbidden["action_type"] = "device_control"
    assert client.post("/api/tasks", json=forbidden).status_code == 422


def test_state_machine_assignment_completion_feedback_and_snapshots(client: TestClient, task_context) -> None:
    greenhouse_id, batch_id = task_context
    task = submit_assign_start(client, create_manual(client, greenhouse_id, batch_id))
    assert task["status"] == "in_progress" and task["assignee_name"] == "巡棚员甲"
    completed = client.post(f"/api/tasks/{task['id']}/complete", json={
        "version": task["version"], "operator": "巡棚员甲",
        "executed_at": datetime.now(UTC).isoformat(), "result_type": "improved",
        "execution_note": "已完成现场通风条件检查", "observed_change": "叶面结露减少",
        "requires_follow_up": False,
    })
    assert completed.status_code == 200, completed.text
    data = completed.json()["data"]
    assert data["status"] == "completed" and data["result_snapshot_json"]["data_source"] == "sensor"
    detail = client.get(f"/api/tasks/{task['id']}").json()["data"]
    assert len(detail["feedbacks"]) == 1
    assert [item["event_type"] for item in detail["events"]] == [
        "created", "submitted", "assigned", "started", "feedback_added", "completed"
    ]
    assert "不代表" in detail["causality_notice"]


def test_illegal_transitions_version_conflict_and_required_fields(client: TestClient, task_context) -> None:
    greenhouse_id, batch_id = task_context
    task = create_manual(client, greenhouse_id, batch_id)
    assert client.post(f"/api/tasks/{task['id']}/start", json={
        "version": 1, "operator": "管理员",
    }).status_code == 409
    submitted = client.post(f"/api/tasks/{task['id']}/submit", json={
        "version": 1, "operator": "管理员",
    }).json()["data"]
    assert client.post(f"/api/tasks/{task['id']}/assign", json={
        "version": 1, "operator": "管理员", "assignee_name": "甲",
    }).status_code == 409
    started = client.post(f"/api/tasks/{task['id']}/start", json={
        "version": submitted["version"], "operator": "甲",
    }).json()["data"]
    assert client.post(f"/api/tasks/{task['id']}/complete", json={
        "version": started["version"], "operator": "甲",
    }).status_code == 422
    assert client.post(f"/api/tasks/{task['id']}/cancel", json={
        "version": started["version"], "operator": "甲",
    }).status_code == 422


def test_cancel_and_reopen_rules(client: TestClient, task_context) -> None:
    greenhouse_id, batch_id = task_context
    task = create_manual(client, greenhouse_id, batch_id)
    pending = client.post(f"/api/tasks/{task['id']}/submit", json={
        "version": 1, "operator": "管理员",
    }).json()["data"]
    cancelled = client.post(f"/api/tasks/{task['id']}/cancel", json={
        "version": pending["version"], "operator": "管理员", "reason": "现场计划调整",
    })
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["cancellation_reason"] == "现场计划调整"
    assert client.post(f"/api/tasks/{task['id']}/reopen", json={
        "version": cancelled.json()["data"]["version"], "operator": "管理员", "reason": "重新安排",
    }).status_code == 409


def test_warning_task_duplicate_and_no_auto_resolve(client: TestClient, task_context) -> None:
    greenhouse_id, batch_id = task_context
    warning_id, recommendation_id = insert_warning(greenhouse_id, batch_id)
    first = client.post(f"/api/tasks/from-warning/{warning_id}", json={"created_by": "管理员"})
    assert first.status_code == 200
    data = first.json()["data"]
    assert data["source_recommendation_id"] == recommendation_id and data["status"] == "draft"
    assert client.post(f"/api/tasks/from-warning/{warning_id}", json={
        "created_by": "管理员",
    }).status_code == 409
    task = submit_assign_start(client, data)
    result = client.post(f"/api/tasks/{task['id']}/complete", json={
        "version": task["version"], "operator": "巡棚员",
        "executed_at": datetime.now(UTC).isoformat(), "result_type": "resolved",
        "execution_note": "完成现场检查",
    })
    assert result.status_code == 200
    assert client.get(f"/api/warnings/{warning_id}").json()["data"]["status"] == "open"


def test_disease_review_rules_and_safe_action_whitelist(client: TestClient, task_context) -> None:
    greenhouse_id, batch_id = task_context
    confirmed_id = insert_disease(greenhouse_id, batch_id)
    created = client.post(f"/api/tasks/from-disease/{confirmed_id}", json={
        "created_by": "农技员", "action_type": "sample_collection",
    })
    assert created.status_code == 200
    assert created.json()["data"]["source_type"] == "disease_review"
    assert client.post(f"/api/tasks/from-disease/{confirmed_id}", json={
        "created_by": "农技员", "action_type": "automatic_spraying",
    }).status_code in {409, 422}

    unreviewed_id = insert_disease(greenhouse_id, batch_id, review_status="unreviewed")
    assert client.post(f"/api/tasks/from-disease/{unreviewed_id}", json={
        "created_by": "农技员",
    }).status_code == 422

    low_id = insert_disease(greenhouse_id, batch_id, recognition_status="low_confidence",
                            review_status="confirmed")
    assert client.post(f"/api/tasks/from-disease/{low_id}", json={
        "created_by": "农技员",
    }).status_code == 422


def test_muskmelon_disease_record_cannot_create_tomato_task(client: TestClient,
                                                            monkeypatch: pytest.MonkeyPatch,
                                                            tmp_path: Path) -> None:
    greenhouse_id, batch_id = create_context(client, "M", "muskmelon")
    monkeypatch.setattr("app.services.task_service.predict_environment",
                        lambda _db, greenhouse_id, hours: fake_prediction(greenhouse_id, hours))
    monkeypatch.setattr("app.services.task_service.UPLOAD_DIR", tmp_path / "task-uploads")
    record_id = insert_disease(greenhouse_id, batch_id, crop_type="muskmelon")
    assert client.post(f"/api/tasks/from-disease/{record_id}", json={
        "created_by": "农技员",
    }).status_code == 422


def test_feedback_attachment_security_and_append_only_event(client: TestClient, task_context,
                                                            tmp_path: Path) -> None:
    greenhouse_id, batch_id = task_context
    task = submit_assign_start(client, create_manual(client, greenhouse_id, batch_id))
    output = io.BytesIO(); Image.new("RGB", (80, 80), (40, 130, 60)).save(output, format="PNG")
    response = client.post(f"/api/tasks/{task['id']}/feedback", data={
        "version": task["version"], "operator": "巡棚员",
        "executed_at": datetime.now(UTC).isoformat(), "result_type": "unable_to_verify",
        "execution_note": "上传现场照片", "requires_follow_up": "true",
        "follow_up_note": "明日复查",
    }, files={"attachments": ("../../现场.png", output.getvalue(), "image/png")})
    assert response.status_code == 200, response.text
    path = response.json()["data"]["attachment_paths_json"][0]
    assert ".." not in path and path.endswith(".jpg")
    assert not (tmp_path / "现场.png").exists()
    events = client.get(f"/api/tasks/{task['id']}/events").json()["data"]
    assert events[-1]["event_type"] == "feedback_added"
    broken = client.post(f"/api/tasks/{task['id']}/feedback", data={
        "version": task["version"] + 1, "operator": "巡棚员",
        "executed_at": datetime.now(UTC).isoformat(), "result_type": "no_change",
        "execution_note": "损坏附件测试",
    }, files={"attachments": ("broken.jpg", b"broken", "image/jpeg")})
    assert broken.status_code == 422


def test_summary_pagination_filters_and_trace_order(client: TestClient, task_context) -> None:
    greenhouse_id, batch_id = task_context
    first = create_manual(client, greenhouse_id, batch_id)
    second_payload = manual_payload(greenhouse_id, batch_id)
    second_payload.update({"title": "传感器检查", "action_type": "sensor_inspection", "priority": "urgent"})
    second = client.post("/api/tasks", json=second_payload).json()["data"]
    client.post(f"/api/tasks/{second['id']}/submit", json={"version": 1, "operator": "管理员"})
    page = client.get("/api/tasks", params={
        "greenhouse_id": greenhouse_id, "status": "draft", "page": 1, "page_size": 1,
    }).json()["data"]
    assert page["total"] == 1 and page["items"][0]["id"] == first["id"]
    summary = client.get("/api/tasks/summary", params={"greenhouse_id": greenhouse_id}).json()["data"]
    assert summary["draft_total"] == 1 and summary["pending_total"] == 1
    assert summary["urgent_total"] == 1
    trace = client.get(f"/api/tasks/{first['id']}/trace").json()["data"]
    types = [node["type"] for node in trace["nodes"]]
    assert types == ["environment_record", "environment_prediction", "risk_assessment",
                     "warning_event", "decision_recommendation", "disease_review",
                     "farm_task", "execution_feedback"]
    assert trace["nodes"][3]["summary"] == "该环节暂无记录"
