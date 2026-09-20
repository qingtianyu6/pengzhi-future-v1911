from datetime import date, timedelta
import hashlib
import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.ml.disease.config import ARTIFACT_DIR, CLASS_NAMES
from app.ml.disease.inference import DiseasePredictor


def image_bytes(image_format: str = "JPEG", size: tuple[int, int] = (96, 96)) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, (38, 142, 72)).save(output, format=image_format)
    return output.getvalue()


def context(client: TestClient, crop_type: str = "tomato", suffix: str = "T") -> tuple[int, int]:
    greenhouse = client.post("/api/greenhouses", json={
        "code": f"GH-DISEASE-{suffix}", "name": "病害测试棚", "location": "莘县",
        "area_mu": 1.5, "status": "active",
    }).json()["data"]
    batch = client.post(f"/api/greenhouses/{greenhouse['id']}/crop-batches", json={
        "batch_code": f"DISEASE-{suffix}", "variety": "测试品种", "crop_type": crop_type,
        "planted_at": (date.today() - timedelta(days=40)).isoformat(),
        "expected_harvest_at": (date.today() + timedelta(days=60)).isoformat(), "status": "growing",
    }).json()["data"]
    return greenhouse["id"], batch["id"]


class FakePredictor:
    model_status = "ready"
    threshold = 0.6

    def __init__(self, status: str = "recognized"):
        self.result_status = status

    def predict(self, _image):
        if self.result_status == "model_unavailable":
            return {"recognition_status": "model_unavailable", "top3_predictions": []}
        top3 = [
            {"class_key": "healthy", "class_name": "健康叶片", "confidence": 0.82},
            {"class_key": "early_blight", "class_name": "早疫病", "confidence": 0.11},
            {"class_key": "late_blight", "class_name": "晚疫病", "confidence": 0.04},
        ]
        return {"recognition_status": self.result_status,
                "predicted_class": "healthy" if self.result_status == "recognized" else None,
                "predicted_class_name": "健康叶片" if self.result_status == "recognized" else None,
                "confidence": 0.82 if self.result_status == "recognized" else 0.42,
                "top3_predictions": top3}

    def status(self):
        return {"service_status": "available", "model_status": self.model_status,
                "model_version": "tomato-disease-v0.1", "target_crop": "tomato",
                "supported_classes": [{"key": item, "name": item} for item in CLASS_NAMES],
                "input_size": 224, "confidence_threshold": self.threshold,
                "internal_metrics_summary": {}, "external_metrics_summary": {},
                "local_calibration_status": "not_calibrated", "limitations": []}


@pytest.fixture
def disease_context(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    greenhouse_id, batch_id = context(client)
    monkeypatch.setattr("app.services.disease_service.UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr("app.services.disease_service.get_disease_predictor", lambda: FakePredictor())
    return greenhouse_id, batch_id


@pytest.mark.parametrize(("extension", "mime", "image_format"), [
    ("jpg", "image/jpeg", "JPEG"), ("png", "image/png", "PNG"), ("webp", "image/webp", "WEBP"),
])
def test_identify_supported_images_returns_top3_and_saves_record(
    client: TestClient, disease_context, extension: str, mime: str, image_format: str,
) -> None:
    greenhouse_id, batch_id = disease_context
    response = client.post("/api/diseases/identify", data={"greenhouse_id": greenhouse_id, "crop_batch_id": batch_id},
                           files={"image": (f"leaf.{extension}", image_bytes(image_format), mime)})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["recognition_status"] == "recognized"
    assert len(data["top3_predictions"]) == 3
    assert 0 <= data["confidence"] <= 1
    detail = client.get(f"/api/diseases/records/{data['record_id']}").json()["data"]
    assert detail["image_sha256"] == hashlib.sha256(image_bytes(image_format)).hexdigest()


@pytest.mark.parametrize(("filename", "content", "mime", "expected"), [
    ("note.txt", b"not an image", "text/plain", 415),
    ("broken.jpg", b"\xff\xd8broken", "image/jpeg", 422),
    ("empty.jpg", b"", "image/jpeg", 422),
])
def test_invalid_uploads_are_rejected(client: TestClient, disease_context, filename, content, mime, expected) -> None:
    greenhouse_id, batch_id = disease_context
    response = client.post("/api/diseases/identify", data={"greenhouse_id": greenhouse_id, "crop_batch_id": batch_id},
                           files={"image": (filename, content, mime)})
    assert response.status_code == expected


def test_oversize_upload_rejected(client: TestClient, disease_context) -> None:
    greenhouse_id, batch_id = disease_context
    response = client.post("/api/diseases/identify", data={"greenhouse_id": greenhouse_id, "crop_batch_id": batch_id},
                           files={"image": ("huge.jpg", b"x" * (10 * 1024 * 1024 + 1), "image/jpeg")})
    assert response.status_code == 413


def test_path_traversal_filename_never_becomes_disk_path(client: TestClient, disease_context, tmp_path: Path) -> None:
    greenhouse_id, batch_id = disease_context
    response = client.post("/api/diseases/identify", data={"greenhouse_id": greenhouse_id, "crop_batch_id": batch_id},
                           files={"image": ("../../escape.jpg", image_bytes(), "image/jpeg")})
    assert response.status_code == 200
    record = client.get(f"/api/diseases/records/{response.json()['data']['record_id']}").json()["data"]
    assert ".." not in record["image_path"]
    assert not (tmp_path / "escape.jpg").exists()


def test_duplicate_sha_is_detected(client: TestClient, disease_context) -> None:
    greenhouse_id, batch_id = disease_context
    kwargs = {"data": {"greenhouse_id": greenhouse_id, "crop_batch_id": batch_id},
              "files": {"image": ("same.jpg", image_bytes(), "image/jpeg")}}
    first = client.post("/api/diseases/identify", **kwargs)
    second = client.post("/api/diseases/identify", **kwargs)
    assert first.json()["data"]["duplicate_image"] is False
    assert second.json()["data"]["duplicate_image"] is True
    history = client.get("/api/diseases/records", params={"page": 1, "page_size": 1}).json()["data"]
    assert history["total"] == 2 and len(history["items"]) == 1


def test_low_confidence_has_no_definite_diagnosis(client: TestClient, disease_context,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    greenhouse_id, batch_id = disease_context
    monkeypatch.setattr("app.services.disease_service.get_disease_predictor", lambda: FakePredictor("low_confidence"))
    response = client.post("/api/diseases/identify", data={"greenhouse_id": greenhouse_id, "crop_batch_id": batch_id},
                           files={"image": ("leaf.jpg", image_bytes(), "image/jpeg")})
    data = response.json()["data"]
    assert data["recognition_status"] == "low_confidence"
    assert data["predicted_class"] is None and len(data["top3_predictions"]) == 3


def test_model_unavailable_is_traceable(client: TestClient, disease_context,
                                        monkeypatch: pytest.MonkeyPatch) -> None:
    greenhouse_id, batch_id = disease_context
    predictor = FakePredictor("model_unavailable"); predictor.model_status = "not_trained"
    monkeypatch.setattr("app.services.disease_service.get_disease_predictor", lambda: predictor)
    response = client.post("/api/diseases/identify", data={"greenhouse_id": greenhouse_id, "crop_batch_id": batch_id},
                           files={"image": ("leaf.jpg", image_bytes(), "image/jpeg")})
    assert response.json()["data"]["recognition_status"] == "model_unavailable"


def test_muskmelon_batch_rejected_before_model_call(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    greenhouse_id, batch_id = context(client, "muskmelon", "M")
    called = False
    def predictor():
        nonlocal called; called = True; return FakePredictor()
    monkeypatch.setattr("app.services.disease_service.get_disease_predictor", predictor)
    response = client.post("/api/diseases/identify", data={"greenhouse_id": greenhouse_id, "crop_batch_id": batch_id},
                           files={"image": ("leaf.jpg", image_bytes(), "image/jpeg")})
    assert response.status_code == 422 and called is False


def test_confirm_correct_and_reject_review(client: TestClient, disease_context) -> None:
    greenhouse_id, batch_id = disease_context
    def create_record() -> int:
        response = client.post("/api/diseases/identify", data={"greenhouse_id": greenhouse_id, "crop_batch_id": batch_id},
                               files={"image": ("leaf.jpg", image_bytes(), "image/jpeg")})
        return response.json()["data"]["record_id"]
    confirmed = client.post(f"/api/diseases/records/{create_record()}/review", json={"review_status": "confirmed"})
    corrected = client.post(f"/api/diseases/records/{create_record()}/review",
                            json={"review_status": "corrected", "reviewed_class": "late_blight", "review_note": "人工复核"})
    rejected = client.post(f"/api/diseases/records/{create_record()}/review", json={"review_status": "rejected"})
    assert confirmed.json()["data"]["reviewed_class"] == "healthy"
    assert corrected.json()["data"]["reviewed_class"] == "late_blight"
    assert rejected.json()["data"]["review_status"] == "rejected"


def test_model_status_and_canonical_class_order(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.disease_service.get_disease_predictor", lambda: FakePredictor())
    response = client.get("/api/diseases/model-status")
    assert response.status_code == 200
    assert tuple(item["key"] for item in response.json()["data"]["supported_classes"]) == CLASS_NAMES


def test_real_artifact_sha_and_load_when_available() -> None:
    if not (ARTIFACT_DIR / "model.pt").exists():
        pytest.skip("real artifact is produced by the disease-model training pipeline")
    lines = (ARTIFACT_DIR / "sha256sums.txt").read_text(encoding="utf-8").splitlines()
    expected = {line.split("  ", 1)[1]: line.split("  ", 1)[0] for line in lines}
    assert hashlib.sha256((ARTIFACT_DIR / "model.pt").read_bytes()).hexdigest() == expected["model.pt"]
    predictor = DiseasePredictor(ARTIFACT_DIR)
    assert predictor.ensure_loaded()
    result = predictor.predict(Image.new("RGB", (224, 224), (38, 142, 72)))
    assert result["recognition_status"] in {"review_required", "low_confidence"}
    if result["recognition_status"] == "review_required":
        assert predictor.model_status == "under_evaluation"
    assert len(result["top3_predictions"]) == 3
