from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient
from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal, initialize_database
from app.main import app
from app.ml.disease.inference import reset_disease_predictor
from app.models.crop_batch import CropBatch
from app.models.greenhouse import Greenhouse


def first_manifest_sample() -> dict[str, str]:
    path = PROJECT_DIR / "datasets" / "disease_images" / "processed" / "internal_test_manifest.csv"
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return next(csv.DictReader(file))


def main() -> int:
    initialize_database()
    reset_disease_predictor()
    with SessionLocal() as db:
        tomato_batch = db.scalar(select(CropBatch).where(
            CropBatch.crop_type == "tomato", CropBatch.status == "growing").order_by(CropBatch.id))
        muskmelon_batch = db.scalar(select(CropBatch).where(
            CropBatch.crop_type == "muskmelon").order_by(CropBatch.id))
        if tomato_batch is None:
            raise RuntimeError("database has no growing tomato batch; create one before verification")
        tomato_greenhouse = db.get(Greenhouse, tomato_batch.greenhouse_id)
        muskmelon_greenhouse_id = muskmelon_batch.greenhouse_id if muskmelon_batch else None
        tomato_context = (tomato_greenhouse.id, tomato_batch.id)

    sample = first_manifest_sample()
    sample_path = PROJECT_DIR / sample["path"]
    mime = "image/png" if sample_path.suffix.lower() == ".png" else "image/jpeg"
    report: dict = {"sample_path": sample["path"], "true_class": sample["class_name"]}
    with TestClient(app) as client:
        model_status = client.get("/api/diseases/model-status")
        report["model_status"] = model_status.json()["data"]
        with sample_path.open("rb") as image:
            response = client.post("/api/diseases/identify", data={
                "greenhouse_id": tomato_context[0], "crop_batch_id": tomato_context[1],
            }, files={"image": (sample_path.name, image, mime)})
        response.raise_for_status()
        identification = response.json()["data"]
        if identification["recognition_status"] == "model_unavailable":
            raise RuntimeError("real model was unavailable during integration")
        report["identification"] = identification
        review_payload = ({"review_status": "confirmed", "review_note": "病害识别工作流人工确认"}
                          if identification["recognition_status"] == "recognized" and
                          identification["predicted_class"] == sample["class_name"]
                          else {"review_status": "corrected", "reviewed_class": sample["class_name"],
                                "review_note": "病害识别工作流按数据集标签人工修正"})
        review = client.post(f"/api/diseases/records/{identification['record_id']}/review", json=review_payload)
        review.raise_for_status()
        report["review"] = review.json()["data"]
        history = client.get("/api/diseases/records", params={"greenhouse_id": tomato_context[0], "page_size": 5})
        report["history_contains_record"] = any(
            item["id"] == identification["record_id"] for item in history.json()["data"]["items"])
        invalid = client.post("/api/diseases/identify", data={
            "greenhouse_id": tomato_context[0], "crop_batch_id": tomato_context[1],
        }, files={"image": ("invalid.jpg", b"not-an-image", "image/jpeg")})
        report["invalid_image_http_status"] = invalid.status_code
        if muskmelon_batch and muskmelon_greenhouse_id:
            unsupported = client.post("/api/diseases/identify", data={
                "greenhouse_id": muskmelon_greenhouse_id, "crop_batch_id": muskmelon_batch.id,
            }, files={"image": (sample_path.name, sample_path.read_bytes(), mime)})
            report["muskmelon_http_status"] = unsupported.status_code
            report["muskmelon_message"] = unsupported.json()["message"]
    report["passed"] = (report["history_contains_record"] and report["invalid_image_http_status"] == 422 and
                        report.get("muskmelon_http_status", 422) == 422)
    output = PROJECT_DIR / "outputs" / "disease-workflow" / "integration_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
