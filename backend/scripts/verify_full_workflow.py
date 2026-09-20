"""Read-only verification for the final monitoring and disease workflows."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient
from sqlalchemy import select


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal, initialize_database  # noqa: E402
from app.main import app  # noqa: E402
from app.models import DiseaseRecognitionRecord, Greenhouse  # noqa: E402


VALID_SOURCES = {"sensor", "import"}


def api_data(client: TestClient, path: str, **kwargs):
    response = client.get(path, **kwargs)
    if response.status_code != 200:
        raise RuntimeError(f"{path} -> {response.status_code}: {response.text[-500:]}")
    return response.json()["data"]


def main() -> None:
    initialize_database()
    with SessionLocal() as db:
        greenhouse = db.scalar(select(Greenhouse).order_by(Greenhouse.id).limit(1))
        disease_record = db.scalar(
            select(DiseaseRecognitionRecord)
            .order_by(DiseaseRecognitionRecord.id.desc())
            .limit(1)
        )

    with TestClient(app) as client:
        health = api_data(client, "/api/health")
        disease_model = api_data(client, "/api/diseases/model-status")
        environment: dict[str, object] = {"status": "no_greenhouse"}
        if greenhouse is not None:
            params = {"greenhouse_id": greenhouse.id}
            dashboard = api_data(client, "/api/dashboard/summary", params=params)
            latest = api_data(client, "/api/sensors/latest", params=params)
            prediction = api_data(
                client,
                "/api/predictions/environment",
                params={**params, "horizon_hours": 6},
            )
            warnings = api_data(
                client, "/api/warnings", params={**params, "page_size": 50}
            )
            decisions = api_data(client, "/api/decisions/current", params=params)
            if latest is None:
                passed = (
                    dashboard["empty_state"] is True
                    and dashboard["latest_environment"] is None
                    and dashboard["risk"]["level"] == "数据不足"
                    and prediction["status"] == "insufficient_data"
                    and warnings["total"] == 0
                    and decisions["recommendations"] == []
                )
                environment_status = "empty_state_verified"
            else:
                passed = (
                    latest["source"] in VALID_SOURCES
                    and dashboard["data_source"] in VALID_SOURCES
                    and prediction["status"] in {"ready", "insufficient_data"}
                    and all(item["data_source"] in VALID_SOURCES for item in warnings["items"])
                )
                environment_status = "valid_business_data_verified"
            environment = {
                "status": environment_status,
                "passed": passed,
                "greenhouse_id": greenhouse.id,
                "data_source": latest["source"] if latest else None,
                "prediction_status": prediction["status"],
                "warning_total": warnings["total"],
                "recommendation_total": len(decisions["recommendations"]),
            }

        disease = {
            "passed": disease_model["model_status"] in {
                "ready", "under_evaluation", "not_trained"
            },
            "model_status": disease_model["model_status"],
            "validation_status": disease_model["validation_status"],
            "record_id": disease_record.id if disease_record else None,
        }
        if disease_record is not None:
            record = api_data(
                client, f"/api/diseases/records/{disease_record.id}"
            )
            disease["recognition_status"] = record["recognition_status"]
            disease["review_status"] = record["review_status"]

    report = {
        "health": health,
        "environment_workflow": environment,
        "disease_workflow": disease,
        "passed": bool(environment.get("passed", True)) and disease["passed"],
    }
    output_dir = PROJECT_ROOT / "outputs" / "full-workflow"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "verification-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
