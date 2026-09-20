"""Final-product data boundaries, cascade deletion, and artifact integrity."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from fastapi.testclient import TestClient
import numpy as np
import pandas as pd
import pytest
from sqlalchemy import func, select

from app.config import BACKEND_DIR
from app.database import SessionLocal
from app.models import (
    CropBatch,
    DecisionRecommendation,
    DiseaseRecognitionRecord,
    FarmTask,
    Greenhouse,
    SensorData,
    TaskEvent,
    TaskFeedback,
    WarningEvent,
)


def create_context(client: TestClient, suffix: str) -> tuple[int, int]:
    greenhouse = client.post("/api/greenhouses", json={
        "code": f"FINAL-{suffix}", "name": f"正式测试棚{suffix}", "location": "临时测试库",
        "area_mu": 1.2, "status": "active", "manager_name": "测试员",
    })
    assert greenhouse.status_code == 201
    greenhouse_id = int(greenhouse.json()["data"]["id"])
    batch = client.post(f"/api/greenhouses/{greenhouse_id}/crop-batches", json={
        "batch_code": f"FINAL-BATCH-{suffix}", "variety": "测试番茄", "crop_type": "tomato",
        "planted_at": (date.today() - timedelta(days=45)).isoformat(),
        "expected_harvest_at": (date.today() + timedelta(days=50)).isoformat(),
        "status": "growing",
    })
    assert batch.status_code == 201
    return greenhouse_id, int(batch.json()["data"]["id"])


def readings(greenhouse_id: int, source: str, count: int = 24) -> list[dict[str, object]]:
    end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    return [{
        "greenhouse_id": greenhouse_id,
        "recorded_at": (end - timedelta(hours=count - 1 - index)).isoformat(),
        "temperature": 24.0 + index / 20,
        "air_humidity": 68.0 - index / 20,
        "soil_moisture": 61.0,
        "light_intensity": 28.0,
        "co2_concentration": 650.0,
        "source": source,
        "quality_flag": "valid",
    } for index in range(count)]


def test_simulation_source_is_not_accepted_by_final_api(client: TestClient) -> None:
    greenhouse_id, _ = create_context(client, "SOURCE-BOUNDARY")
    inserted = client.post("/api/sensors/batch", json={
        "items": readings(greenhouse_id, "simulation")
    })
    assert inserted.status_code == 422

    dashboard = client.get(
        "/api/dashboard/summary", params={"greenhouse_id": greenhouse_id}
    ).json()["data"]
    assert dashboard["empty_state"] is True
    assert dashboard["latest_environment"] is None
    assert dashboard["trend_24h"] == []
    assert dashboard["risk"]["level"] == "数据不足"



@pytest.mark.parametrize("source", ["sensor", "import"])
def test_sensor_and_import_history_can_drive_prediction(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    greenhouse_id, _ = create_context(client, source.upper())
    assert client.post("/api/sensors/batch", json={
        "items": readings(greenhouse_id, source)
    }).status_code == 200

    class ReadyPredictor:
        status = "ready"
        metadata = {
            "model_name": "test-model", "model_version": "v0.2", "model_status": "ready",
            "ml_candidate_status": "ready", "training_domain": "public_real_greenhouse_tomato",
        }

        def predict(self, records: list[dict[str, object]], horizon_hours: int) -> dict[str, object]:
            assert len(records) >= 24
            assert {item["source"] for item in records} == {source}
            history = pd.DataFrame({
                "timestamp": pd.date_range("2026-01-01", periods=24, freq="1h"),
                "air_temperature_c": np.arange(24) + 20,
                "air_humidity_pct": np.arange(24) + 50,
            })
            points = [{
                "forecast_time": (history.timestamp.iloc[-1] + pd.Timedelta(hours=hour))
                    .tz_localize("Asia/Shanghai").tz_convert("UTC"),
                "horizon": hour, "temperature_c": 25.0, "air_humidity_pct": 70.0,
                "par_umol_m2_s": None, "lower_bounds": {}, "upper_bounds": {},
                "forecast_method": "seasonal_24", "method_version": "v0.2",
                "methods": {"air_temperature_c": "seasonal_24", "air_humidity_pct": "seasonal_24"},
                "units": {"temperature_c": "degree_Celsius", "air_humidity_pct": "percent"},
            } for hour in range(1, horizon_hours + 1)]
            return {
                "history": history, "source": source,
                "input_end_time": history.timestamp.iloc[-1].tz_localize("Asia/Shanghai").tz_convert("UTC"),
                "forecast_method": "seasonal_24",
                "forecast_method_labels": ["前一天同小时统计基线"], "predictions": points,
            }

    monkeypatch.setattr(
        "app.services.prediction_service.get_environment_predictor_v02",
        lambda: ReadyPredictor(),
    )
    prediction = client.get(
        "/api/predictions/environment",
        params={"greenhouse_id": greenhouse_id, "horizon_hours": 6},
    ).json()["data"]
    assert prediction["status"] == "ready"
    assert prediction["input_data_source"] == source
    assert prediction["validation_status"] == "validated_on_public_dataset"
    assert len(prediction["predictions"]) == 6


def test_delete_greenhouse_removes_all_related_records(client: TestClient) -> None:
    greenhouse_id, batch_id = create_context(client, "DELETE")
    assert client.post("/api/sensors/batch", json={
        "items": readings(greenhouse_id, "sensor", 1)
    }).status_code == 200
    now = datetime.now(UTC)
    with SessionLocal() as db:
        warning = WarningEvent(
            greenhouse_id=greenhouse_id, crop_batch_id=batch_id, crop_type="tomato",
            crop_rule_version="tomato-rule-v0.1", crop_match_status="matched_public_tomato",
            cross_region_warning=True, expert_calibration_required=False,
            warning_code="delete-test", warning_type="high_temperature", severity="warning",
            risk_score=70, certainty="expected", title="删除链路测试", description="测试",
            evidence_json={}, status="open", fingerprint=f"delete-{greenhouse_id}",
            rule_version="tomato-rule-v0.1", forecast_methods_json={}, data_source="sensor",
            calibration_status="legacy_not_applicable", first_triggered_at=now,
            last_triggered_at=now,
        )
        db.add(warning)
        db.flush()
        recommendation = DecisionRecommendation(
            warning_event_id=warning.id, greenhouse_id=greenhouse_id,
            crop_batch_id=batch_id, crop_type="tomato", crop_rule_version="tomato-rule-v0.1",
            recommendation_code="delete-test", priority="high", action_type="field_inspection",
            title="现场检查", rationale="测试", action_steps_json=["检查"],
            safety_note="人工确认", status="pending_review",
            rule_version="tomato-decision-rule-v0.1", generated_at=now,
        )
        disease = DiseaseRecognitionRecord(
            greenhouse_id=greenhouse_id, crop_batch_id=batch_id, crop_type="tomato",
            image_path="uploads/disease/delete-test.jpg", image_sha256="d" * 64,
            original_filename="leaf.jpg", predicted_class="healthy",
            predicted_class_name="健康", confidence=0.9, top3_json=[],
            recognition_status="recognized", model_version="tomato-disease-v0.1",
            model_status="under_evaluation", local_calibration_status="not_calibrated",
            review_status="confirmed", reviewed_class="healthy",
        )
        db.add_all([recommendation, disease])
        db.flush()
        task = FarmTask(
            task_code=f"DELETE-{greenhouse_id}", greenhouse_id=greenhouse_id,
            crop_batch_id=batch_id, crop_type="tomato", source_type="warning",
            source_id=warning.id, source_warning_id=warning.id,
            source_disease_record_id=disease.id, source_recommendation_id=recommendation.id,
            title="删除任务", description="测试关联删除", action_type="field_inspection",
            priority="high", status="in_progress", requires_manual_confirmation=True,
            safety_note="人工确认", evidence_snapshot_json={}, version=1, created_by="测试员",
        )
        db.add(task)
        db.flush()
        db.add(TaskEvent(
            task_id=task.id, event_type="created", operator="测试员", payload_json={}
        ))
        db.add(TaskFeedback(
            task_id=task.id, operator="测试员", executed_at=now, result_type="unable_to_verify",
            execution_note="测试", attachment_paths_json=[], environment_snapshot_json={},
            requires_follow_up=False,
        ))
        db.commit()

    response = client.delete(f"/api/greenhouses/{greenhouse_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "大棚删除成功"
    assert client.get(f"/api/greenhouses/{greenhouse_id}").status_code == 404

    with SessionLocal() as db:
        for model in (
            TaskFeedback, TaskEvent, FarmTask, DecisionRecommendation,
            DiseaseRecognitionRecord, WarningEvent, SensorData, CropBatch, Greenhouse,
        ):
            assert db.scalar(select(func.count()).select_from(model)) == 0


def _verify_checksum_manifest(directory: Path, manifest_name: str) -> None:
    manifest = directory / manifest_name
    assert manifest.is_file()
    for line in manifest.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        expected, relative_name = line.split(maxsplit=1)
        artifact = directory / relative_name.strip()
        assert artifact.is_file(), relative_name
        assert sha256(artifact.read_bytes()).hexdigest() == expected, relative_name


def test_model_artifact_checksums_are_unchanged() -> None:
    _verify_checksum_manifest(
        BACKEND_DIR / "app/ml/artifacts/environment_forecast_v0.1", "checksums.sha256"
    )
    _verify_checksum_manifest(
        BACKEND_DIR / "app/ml/artifacts/environment_forecast_v0.2", "checksums.sha256"
    )
    _verify_checksum_manifest(
        BACKEND_DIR / "app/artifacts/disease/v0.1", "sha256sums.txt"
    )


def test_health_and_model_status_expose_final_contract(client: TestClient) -> None:
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["data"]["version"] == "1.2.0"
    model = client.get("/api/diseases/model-status").json()["data"]
    assert model["model_status"] == "under_evaluation"
    assert model["validation_status"] == "under_evaluation"
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/greenhouses/{greenhouse_id}" in paths
    assert "delete" in paths["/api/greenhouses/{greenhouse_id}"]


def test_csv_import_creates_import_source_records(client: TestClient) -> None:
    greenhouse_id, _ = create_context(client, "FILE-IMPORT")
    csv = (
        "recorded_at,temperature,air_humidity,soil_moisture,light_intensity,co2_concentration\n"
        "2026-08-29 08:00:00,26.5,72,61,24.8,680\n"
        "2026-08-29 09:00:00,27.1,70,60,31.2,665\n"
    )
    response = client.post(
        "/api/sensors/import-file",
        data={"greenhouse_id": str(greenhouse_id)},
        files={"file": ("environment.csv", csv.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["data"]["success_count"] == 2

    history = client.get("/api/sensors/history", params={
        "greenhouse_id": greenhouse_id,
        "start_time": "2026-08-29T07:00:00Z",
        "end_time": "2026-08-29T10:00:00Z",
    }).json()["data"]
    assert history["total"] == 2
    assert {item["source"] for item in history["items"]} == {"import"}


def test_import_preview_reports_quality_before_writing(client: TestClient) -> None:
    csv = (
        "time,temp,humidity,soil_moisture,light,co2\n"
        "2026-08-29 08:00:00,26.5,72,61,24.8,680\n"
        "2026-08-29 09:00:00,27.1,70,60,31.2,665\n"
        "2026-08-29 10:00:00,27.4,69,60,35.0,650\n"
    )
    response = client.post(
        "/api/sensors/import-preview",
        files={"file": ("environment.csv", csv.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_rows"] == 3
    assert data["import_ready"] is True
    assert data["quality_score"] >= 90
    assert data["interval_minutes"] == 60.0
    assert "空气温度" in data["available_metrics"]


def test_import_preview_blocks_invalid_range(client: TestClient) -> None:
    csv = (
        "recorded_at,temperature,air_humidity\n"
        "2026-08-29 08:00:00,126.5,72\n"
    )
    preview = client.post(
        "/api/sensors/import-preview",
        files={"file": ("bad.csv", csv.encode("utf-8"), "text/csv")},
    ).json()["data"]
    assert preview["import_ready"] is False
    assert preview["out_of_range_rows"] == 1


def test_model_overview_uses_registered_artifacts(client: TestClient) -> None:
    response = client.get("/api/models/overview")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["environment"]["version"] == "v0.2"
    assert data["environment"]["status"] == "ready"
    assert data["environment"]["temperature_h1"]["mae"] > 0
    assert data["disease"]["architecture"] == "ResNet18"
    assert data["disease"]["status"] == "under_evaluation"
