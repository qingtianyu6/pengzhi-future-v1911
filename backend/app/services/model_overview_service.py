from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import BACKEND_DIR


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def get_model_overview() -> dict[str, Any]:
    env_dir = BACKEND_DIR / "app" / "ml" / "artifacts" / "environment_forecast_v0.2"
    disease_dir = BACKEND_DIR / "app" / "artifacts" / "disease" / "v0.1"

    env_meta = _load_json(env_dir / "training_metadata.json")
    champions = _load_json(env_dir / "champion_registry.json")
    disease_internal = _load_json(disease_dir / "internal_metrics.json")
    disease_external = _load_json(disease_dir / "external_metrics.json")
    disease_classes = _load_json(disease_dir / "class_names.json")

    env_targets = champions.get("targets", {})
    temperature_h1 = env_targets.get("air_temperature_c", {}).get("h1", {})
    humidity_h1 = env_targets.get("air_humidity_pct", {}).get("h1", {})

    class_names = disease_classes.get("class_names", disease_classes)
    if isinstance(class_names, dict):
        class_count = len(class_names)
    elif isinstance(class_names, list):
        class_count = len(class_names)
    else:
        class_count = 0

    return {
        "environment": {
            "name": env_meta.get("model_name", "environment-forecast-v0.2"),
            "version": env_meta.get("model_version", "v0.2"),
            "status": env_meta.get("forecast_service_status", "under_evaluation"),
            "prediction_window_hours": 6,
            "algorithms": ["Seasonal-24", "GRU", "LSTM", "XGBoost", "Validation Weighted Ensemble"],
            "training_crop": env_meta.get("crop", "tomato"),
            "temperature_h1": {
                "mae": temperature_h1.get("rolling_validation_mae"),
                "rmse": temperature_h1.get("rolling_validation_rmse"),
                "improvement_pct": temperature_h1.get("mean_relative_seasonal_improvement_pct"),
                "method": temperature_h1.get("method"),
            },
            "humidity_h1": {
                "mae": humidity_h1.get("rolling_validation_mae"),
                "rmse": humidity_h1.get("rolling_validation_rmse"),
                "improvement_pct": humidity_h1.get("mean_relative_seasonal_improvement_pct"),
                "method": humidity_h1.get("method"),
            },
        },
        "disease": {
            "name": "tomato-disease-resnet18",
            "version": "v0.1",
            "status": "under_evaluation",
            "architecture": "ResNet18",
            "class_count": class_count,
            "confidence_threshold": disease_internal.get("confidence_threshold"),
            "internal_accuracy": disease_internal.get("accuracy"),
            "internal_macro_f1": disease_internal.get("macro_f1"),
            "accepted_accuracy": disease_internal.get("accepted_accuracy"),
            "external_accuracy": disease_external.get("accuracy"),
            "external_macro_f1": disease_external.get("macro_f1"),
        },
    }
