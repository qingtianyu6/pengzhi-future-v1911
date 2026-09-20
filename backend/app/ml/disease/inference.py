from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any

from PIL import Image
import torch

from app.ml.disease.config import (ARTIFACT_DIR, CLASS_NAMES, CLASS_NAME_ZH, INPUT_SIZE,
                                   MODEL_VERSION, TARGET_CROP)
from app.ml.disease.dataset import evaluation_transform
from app.ml.disease.model import load_checkpoint


class DiseasePredictor:
    def __init__(self, artifact_dir: Path = ARTIFACT_DIR):
        self.artifact_dir = artifact_dir
        self.model_path = artifact_dir / "model.pt"
        self.device = torch.device("cpu")
        self.model = None
        self.temperature = 1.0
        self.threshold = None
        self.model_status = "not_trained"
        self._load_metadata()

    def _read_json(self, filename: str, default: Any = None) -> Any:
        path = self.artifact_dir / filename
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

    def _load_metadata(self) -> None:
        internal = self._read_json("internal_metrics.json", {})
        self.internal_metrics = internal
        self.external_metrics = self._read_json("external_metrics.json", {})
        calibration = self._read_json("confidence_calibration.json", {})
        threshold = self._read_json("confidence_threshold.json", {})
        self.temperature = float(calibration.get("temperature", 1.0))
        self.threshold = threshold.get("selected_threshold")
        if self.model_path.exists():
            self.model_status = "ready" if internal.get("deployment_gate", {}).get("passed") else "under_evaluation"

    def ensure_loaded(self) -> bool:
        if self.model is not None:
            return True
        if not self.model_path.exists():
            self.model_status = "not_trained"
            return False
        try:
            self.model, checkpoint = load_checkpoint(self.model_path, self.device)
            if tuple(checkpoint["class_names"]) != CLASS_NAMES:
                raise ValueError("artifact class order differs from canonical class configuration")
            return True
        except (OSError, ValueError, KeyError, RuntimeError):
            self.model_status = "unavailable"
            self.model = None
            return False

    @torch.inference_mode()
    def predict(self, image: Image.Image) -> dict[str, Any]:
        if not self.ensure_loaded():
            return {"recognition_status": "model_unavailable", "top3_predictions": []}
        tensor = evaluation_transform(INPUT_SIZE)(image.convert("RGB")).unsqueeze(0)
        probabilities = torch.softmax(self.model(tensor) / self.temperature, dim=1)[0]
        values, indices = torch.topk(probabilities, k=3)
        top3 = [{"class_key": CLASS_NAMES[index], "class_name": CLASS_NAME_ZH[CLASS_NAMES[index]],
                 "confidence": float(value)} for value, index in zip(values.tolist(), indices.tolist())]
        confidence = top3[0]["confidence"]
        recognized = self.threshold is not None and confidence >= float(self.threshold)
        recognition_status = (
            "review_required" if recognized and self.model_status == "under_evaluation"
            else "recognized" if recognized else "low_confidence"
        )
        return {
            "recognition_status": recognition_status,
            "predicted_class": top3[0]["class_key"] if recognized else None,
            "predicted_class_name": top3[0]["class_name"] if recognized else None,
            "confidence": confidence, "top3_predictions": top3,
        }

    def status(self) -> dict[str, Any]:
        return {
            "service_status": "available" if self.model_path.exists() else "model_unavailable",
            "model_status": self.model_status, "model_version": MODEL_VERSION, "target_crop": TARGET_CROP,
            "supported_classes": [{"key": key, "name": CLASS_NAME_ZH[key]} for key in CLASS_NAMES],
            "input_size": INPUT_SIZE, "confidence_threshold": self.threshold,
            "internal_metrics_summary": {key: self.internal_metrics.get(key) for key in ("accuracy", "macro_f1")},
            "external_metrics_summary": {key: self.external_metrics.get(key) for key in ("accuracy", "macro_f1")},
            "local_calibration_status": "not_calibrated",
            "limitations": ["仅支持番茄六分类叶片辅助识别",
                            "不能替代农技人员或植物病理专家诊断", "不提供自动施药或设备控制"],
        }


@lru_cache(maxsize=1)
def get_disease_predictor() -> DiseasePredictor:
    return DiseasePredictor()


def reset_disease_predictor() -> None:
    get_disease_predictor.cache_clear()
