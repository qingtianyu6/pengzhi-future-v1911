from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = PACKAGE_DIR.parents[2]
PROJECT_DIR = BACKEND_DIR.parent
CLASS_CONFIG_PATH = PACKAGE_DIR / "class_names.json"

with CLASS_CONFIG_PATH.open("r", encoding="utf-8") as file:
    _CLASS_CONFIG = json.load(file)

CLASS_NAMES: tuple[str, ...] = tuple(item["key"] for item in _CLASS_CONFIG["classes"])
CLASS_NAME_ZH: dict[str, str] = {
    item["key"]: item["name_zh"] for item in _CLASS_CONFIG["classes"]
}
CLASS_INDEX: dict[str, int] = {name: index for index, name in enumerate(CLASS_NAMES)}
MODEL_VERSION = str(_CLASS_CONFIG["model_version"])
TARGET_CROP = str(_CLASS_CONFIG["target_crop"])
RANDOM_SEED = 20260823
INPUT_SIZE = 224
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
DATASET_ROOT = PROJECT_DIR / "datasets" / "disease_images"
PROCESSED_DIR = DATASET_ROOT / "processed"
ARTIFACT_DIR = BACKEND_DIR / "app" / "artifacts" / "disease" / "v0.1"
OUTPUT_DIR = PROJECT_DIR / "outputs" / "disease_training"


@dataclass(frozen=True)
class TrainingConfig:
    architecture: str = "mobilenet_v3_small"
    input_size: int = INPUT_SIZE
    batch_size: int = 32
    num_workers: int = 0
    seed: int = RANDOM_SEED
    head_learning_rate: float = 1e-3
    fine_tune_learning_rate: float = 1e-4
    weight_decay: float = 1e-4
    plantvillage_epochs: int = 1
    head_epochs: int = 8
    fine_tune_epochs: int = 5
    patience: int = 3
