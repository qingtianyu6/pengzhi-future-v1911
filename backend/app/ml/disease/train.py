from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import hashlib
import json
import logging
from pathlib import Path
import random
import shutil
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.metrics import f1_score
from torch import nn
from torch.utils.data import DataLoader

from app.ml.disease.calibration import fit_temperature, select_confidence_threshold
from app.ml.disease.config import (ARTIFACT_DIR, CLASS_CONFIG_PATH, CLASS_NAMES, CLASS_NAME_ZH,
                                   IMAGENET_MEAN, IMAGENET_STD, INPUT_SIZE, MODEL_VERSION, OUTPUT_DIR,
                                   PROCESSED_DIR, TARGET_CROP, TrainingConfig)
from app.ml.disease.dataset import (ManifestImageDataset, evaluation_transform, read_manifest,
                                    training_transform)
from app.ml.disease.evaluate import classification_metrics, collect_logits
from app.ml.disease.model import (build_model, freeze_backbone, load_checkpoint,
                                  unfreeze_last_backbone_block)


def select_device() -> torch.device:
    if hasattr(torch, "xpu") and torch.xpu.is_available():
        try:
            test = torch.ones(1, device="xpu") * 2
            if float(test.cpu()) == 2.0:
                return torch.device("xpu")
        except RuntimeError:
            pass
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def make_loader(rows: list[dict[str, str]], *, train: bool, config: TrainingConfig,
                batch_size: int | None = None) -> DataLoader:
    dataset = ManifestImageDataset(rows, training_transform() if train else evaluation_transform())
    generator = torch.Generator().manual_seed(config.seed)
    return DataLoader(dataset, batch_size=batch_size or config.batch_size, shuffle=train,
                      num_workers=config.num_workers, pin_memory=torch.cuda.is_available(), generator=generator)


def class_weights(rows: list[dict[str, str]], device: torch.device) -> torch.Tensor:
    counts = Counter(row["class_name"] for row in rows)
    total = sum(counts.values())
    return torch.tensor([total / (len(CLASS_NAMES) * max(counts[name], 1)) for name in CLASS_NAMES],
                        dtype=torch.float32, device=device)


def run_epochs(model: nn.Module, train_loader: DataLoader, validation_loader: DataLoader,
               device: torch.device, *, epochs: int, learning_rate: float, patience: int,
               weights: torch.Tensor, checkpoint_path: Path, history: list[dict[str, Any]], stage: str,
               architecture: str = "mobilenet_v3_small") -> float:
    optimizer = torch.optim.AdamW((parameter for parameter in model.parameters() if parameter.requires_grad),
                                  lr=learning_rate, weight_decay=1e-4)
    criterion = nn.CrossEntropyLoss(weight=weights)
    best_f1 = max((item["validation_macro_f1"] for item in history), default=-1.0)
    patience_left = patience
    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(images), labels)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item()) * len(labels)
        logits, labels = collect_logits(model, validation_loader, device)
        macro_f1 = float(f1_score(labels.numpy(), logits.argmax(dim=1).numpy(), average="macro", zero_division=0))
        item = {"stage": stage, "epoch": epoch, "train_loss": total_loss / len(train_loader.dataset),
                "validation_macro_f1": macro_f1}
        history.append(item)
        logging.info(json.dumps(item, ensure_ascii=False))
        if macro_f1 > best_f1 + 1e-6:
            best_f1, patience_left = macro_f1, patience
            torch.save({"state_dict": model.state_dict(), "class_names": list(CLASS_NAMES),
                        "architecture": architecture, "model_version": MODEL_VERSION,
                        "best_validation_macro_f1": best_f1}, checkpoint_path)
        else:
            patience_left -= 1
            if patience_left <= 0:
                break
    return best_f1


def plot_confusion(matrix: list[list[int]], title: str, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(8, 7))
    image = axis.imshow(matrix, cmap="Greens")
    axis.set_title(title)
    axis.set_xlabel("Predicted")
    axis.set_ylabel("True")
    axis.set_xticks(range(len(CLASS_NAMES)), CLASS_NAMES, rotation=45, ha="right")
    axis.set_yticks(range(len(CLASS_NAMES)), CLASS_NAMES)
    for row in range(len(matrix)):
        for column in range(len(matrix[row])):
            axis.text(column, row, str(matrix[row][column]), ha="center", va="center", fontsize=8)
    figure.colorbar(image, ax=axis)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def plot_history(history: list[dict[str, Any]], path: Path) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].plot([item["train_loss"] for item in history], marker="o")
    axes[0].set_title("Training loss")
    axes[1].plot([item["validation_macro_f1"] for item in history], marker="o")
    axes[1].set_title("Validation Macro-F1")
    for axis in axes:
        axis.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def finalize_existing_artifacts() -> dict[str, Any]:
    internal_metrics = json.loads((ARTIFACT_DIR / "internal_metrics.json").read_text(encoding="utf-8"))
    external_metrics = json.loads((ARTIFACT_DIR / "external_metrics.json").read_text(encoding="utf-8"))
    training_config = json.loads((ARTIFACT_DIR / "training_config.json").read_text(encoding="utf-8"))
    calibration = json.loads((ARTIFACT_DIR / "confidence_calibration.json").read_text(encoding="utf-8"))
    threshold = json.loads((ARTIFACT_DIR / "confidence_threshold.json").read_text(encoding="utf-8"))
    checkpoint = torch.load(ARTIFACT_DIR / "model.pt", map_location="cpu", weights_only=False)
    plot_confusion(internal_metrics["confusion_matrix"], "IMG-T02 internal test",
                   ARTIFACT_DIR / "confusion_matrix_internal.png")
    plot_confusion(external_metrics.get("confusion_matrix", [[0] * len(CLASS_NAMES) for _ in CLASS_NAMES]),
                   "IMG-T03 external test", ARTIFACT_DIR / "confusion_matrix_external.png")
    plot_history(training_config.get("history", []), ARTIFACT_DIR / "training_curves.png")
    status = "ready" if internal_metrics["deployment_gate"]["passed"] else "under_evaluation"
    architecture = checkpoint.get("architecture", "mobilenet_v3_small")
    card = f"""# Tomato disease model card

- target_crop={TARGET_CROP}
- model_version={MODEL_VERSION}
- architecture={architecture}
- model_status={status}
- local_calibration_status=not_calibrated
- decision_scope=auxiliary_identification_with_manual_review

The selected model uses ImageNet initialization. PlantVillage is controlled-background foundation data;
IMG-T02 is the real-scene fine-tuning, validation and internal-test source; IMG-T03 is an independent external test.
No local Shenxian annotated image was used. The model supports tomato only, not muskmelon.
Predictions are auxiliary and cannot replace agronomist or plant-pathologist diagnosis.
The system does not provide automatic pesticide dosing or equipment control.
"""
    (ARTIFACT_DIR / "model_card.md").write_text(card, encoding="utf-8")
    checksum_lines = []
    for path in sorted(item for item in ARTIFACT_DIR.iterdir() if item.is_file() and item.name != "sha256sums.txt"):
        checksum_lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    (ARTIFACT_DIR / "sha256sums.txt").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    result = {"model_status": status, "architecture": architecture,
              "best_validation_macro_f1": checkpoint.get("best_validation_macro_f1"),
              "internal_accuracy": internal_metrics["accuracy"], "internal_macro_f1": internal_metrics["macro_f1"],
              "external_accuracy": external_metrics.get("accuracy"), "external_macro_f1": external_metrics.get("macro_f1"),
              "confidence_threshold": threshold["selected_threshold"], "temperature": calibration["temperature"]}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "final_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def run_resnet_fallback() -> dict[str, Any]:
    config = TrainingConfig(architecture="resnet18")
    seed_everything(config.seed)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    device = select_device()
    train_rows = read_manifest(PROCESSED_DIR / "train_manifest.csv")
    pv_rows = [row for row in train_rows if row["stage"] == "plantvillage_pretrain"]
    field_rows = [row for row in train_rows if row["stage"] == "field_fine_tune"]
    validation_rows = read_manifest(PROCESSED_DIR / "validation_manifest.csv")
    internal_rows = read_manifest(PROCESSED_DIR / "internal_test_manifest.csv")
    external_rows = read_manifest(PROCESSED_DIR / "external_test_manifest.csv")
    mobile_checkpoint = torch.load(OUTPUT_DIR / "best_model.pt", map_location="cpu", weights_only=False)
    fallback_path = OUTPUT_DIR / "resnet18_best.pt"
    history: list[dict[str, Any]] = []
    model = build_model(pretrained=True, architecture="resnet18").to(device)
    freeze_backbone(model)
    run_epochs(model, make_loader(pv_rows, train=True, config=config),
               make_loader(validation_rows, train=False, config=config), device,
               epochs=config.plantvillage_epochs, learning_rate=config.head_learning_rate,
               patience=config.patience, weights=class_weights(field_rows, device),
               checkpoint_path=fallback_path, history=history, stage="resnet18_plantvillage_head",
               architecture="resnet18")
    model, _ = load_checkpoint(fallback_path, device)
    freeze_backbone(model)
    run_epochs(model, make_loader(field_rows, train=True, config=config),
               make_loader(validation_rows, train=False, config=config), device,
               epochs=config.head_epochs, learning_rate=config.head_learning_rate, patience=config.patience,
               weights=class_weights(field_rows, device), checkpoint_path=fallback_path,
               history=history, stage="resnet18_field_head", architecture="resnet18")
    model, _ = load_checkpoint(fallback_path, device)
    unfreeze_last_backbone_block(model)
    run_epochs(model, make_loader(field_rows, train=True, config=config),
               make_loader(validation_rows, train=False, config=config), device,
               epochs=config.fine_tune_epochs, learning_rate=config.fine_tune_learning_rate,
               patience=config.patience, weights=class_weights(field_rows, device), checkpoint_path=fallback_path,
               history=history, stage="resnet18_field_last_block", architecture="resnet18")
    model, fallback_checkpoint = load_checkpoint(fallback_path, device)
    mobile_score = float(mobile_checkpoint["best_validation_macro_f1"])
    fallback_score = float(fallback_checkpoint["best_validation_macro_f1"])
    existing_config = json.loads((ARTIFACT_DIR / "training_config.json").read_text(encoding="utf-8"))
    existing_config["resnet18_fallback"] = {"attempted": True, "validation_macro_f1": fallback_score,
                                             "mobile_validation_macro_f1": mobile_score,
                                             "selected": fallback_score > mobile_score, "history": history}
    if fallback_score <= mobile_score:
        (ARTIFACT_DIR / "training_config.json").write_text(json.dumps(existing_config, ensure_ascii=False, indent=2), encoding="utf-8")
        result = finalize_existing_artifacts()
        result["fallback_validation_macro_f1"] = fallback_score
        return result

    validation_logits, validation_labels = collect_logits(model, make_loader(validation_rows, train=False, config=config), device)
    temperature = fit_temperature(validation_logits, validation_labels)
    threshold_result = select_confidence_threshold(torch.softmax(validation_logits / temperature, dim=1).numpy(),
                                                   validation_labels.numpy())
    threshold = float(threshold_result["selected_threshold"])
    internal_logits, internal_labels = collect_logits(model, make_loader(internal_rows, train=False, config=config), device)
    internal_metrics = classification_metrics(internal_logits, internal_labels, temperature=temperature, threshold=threshold)
    recall_passed = all(item["recall"] >= 0.50 for item in internal_metrics["per_class"].values())
    internal_metrics["deployment_gate"] = {"passed": internal_metrics["macro_f1"] >= 0.75 and recall_passed,
        "macro_f1_requirement": 0.75, "per_class_recall_requirement": 0.50, "recall_passed": recall_passed}
    external_indices = [CLASS_NAMES.index(name) for name in ("healthy", "early_blight", "late_blight", "leaf_mold")]
    external_logits, external_labels = collect_logits(model, make_loader(external_rows, train=False, config=config), device)
    external_metrics = classification_metrics(external_logits, external_labels, temperature=temperature,
                                              threshold=threshold, metric_label_indices=external_indices)
    shutil.copy2(fallback_path, ARTIFACT_DIR / "model.pt")
    existing_config.update({"architecture": "resnet18", "selected_by": "validation_macro_f1",
                            "history": history, "device": str(device)})
    for filename, payload in (("training_config.json", existing_config),
                              ("confidence_calibration.json", {"method": "temperature_scaling", "temperature": temperature,
                                                               "fitted_on": "IMG-T02 validation logits only"}),
                              ("confidence_threshold.json", threshold_result),
                              ("internal_metrics.json", internal_metrics), ("external_metrics.json", external_metrics)):
        (ARTIFACT_DIR / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    result = finalize_existing_artifacts()
    result["fallback_validation_macro_f1"] = fallback_score
    return result


def smoke_rows(rows: list[dict[str, str]], maximum: int = 64) -> list[dict[str, str]]:
    selected = []
    for class_name in CLASS_NAMES:
        selected.extend([row for row in rows if row["class_name"] == class_name][:maximum])
    return selected


def run_training(*, smoke_only: bool = False) -> dict[str, Any]:
    config = TrainingConfig()
    seed_everything(config.seed)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=OUTPUT_DIR / "training.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", force=True)
    device = select_device()
    train_rows = read_manifest(PROCESSED_DIR / "train_manifest.csv")
    pv_rows = [row for row in train_rows if row["stage"] == "plantvillage_pretrain"]
    field_rows = [row for row in train_rows if row["stage"] == "field_fine_tune"]
    validation_rows = read_manifest(PROCESSED_DIR / "validation_manifest.csv")
    internal_rows = read_manifest(PROCESSED_DIR / "internal_test_manifest.csv")
    external_rows = read_manifest(PROCESSED_DIR / "external_test_manifest.csv")
    if not all((field_rows, validation_rows, internal_rows)):
        raise RuntimeError("IMG-T02 train/validation/internal manifests must be non-empty")

    checkpoint_path = OUTPUT_DIR / ("smoke_best.pt" if smoke_only else "best_model.pt")
    model = build_model(pretrained=True).to(device)
    history: list[dict[str, Any]] = []
    if smoke_only:
        # IMG-T02's deduplicated yellow-curl training split has fewer than 64 originals;
        # fill only the smoke-flow shortfall from the PlantVillage pretraining pool.
        rows = smoke_rows(field_rows + pv_rows)
        validation = smoke_rows(validation_rows, 16)
        freeze_backbone(model)
        run_epochs(model, make_loader(rows, train=True, config=config),
                   make_loader(validation, train=False, config=config), device, epochs=1,
                   learning_rate=config.head_learning_rate, patience=1, weights=class_weights(rows, device),
                   checkpoint_path=checkpoint_path, history=history, stage="smoke")
        loaded, checkpoint = load_checkpoint(checkpoint_path, device)
        sample = next(iter(make_loader(validation[:1], train=False, config=config)))[0].to(device)
        model.eval()
        with torch.inference_mode():
            before = model(sample).cpu()
            after = loaded(sample).cpu()
        result = {"status": "passed" if torch.allclose(before, after, atol=1e-6) else "failed",
                  "device": str(device), "samples": len(rows), "reload_output_equal": torch.allclose(before, after, atol=1e-6),
                  "checkpoint_classes": checkpoint["class_names"], "history": history}
        (OUTPUT_DIR / "smoke_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    if pv_rows:
        freeze_backbone(model)
        run_epochs(model, make_loader(pv_rows, train=True, config=config),
                   make_loader(validation_rows, train=False, config=config), device,
                   epochs=config.plantvillage_epochs, learning_rate=config.head_learning_rate,
                   patience=config.patience, weights=class_weights(field_rows, device),
                   checkpoint_path=checkpoint_path, history=history, stage="plantvillage_head")
        model, _ = load_checkpoint(checkpoint_path, device)
    freeze_backbone(model)
    run_epochs(model, make_loader(field_rows, train=True, config=config),
               make_loader(validation_rows, train=False, config=config), device,
               epochs=config.head_epochs, learning_rate=config.head_learning_rate, patience=config.patience,
               weights=class_weights(field_rows, device), checkpoint_path=checkpoint_path,
               history=history, stage="field_head")
    model, _ = load_checkpoint(checkpoint_path, device)
    unfreeze_last_backbone_block(model)
    run_epochs(model, make_loader(field_rows, train=True, config=config),
               make_loader(validation_rows, train=False, config=config), device,
               epochs=config.fine_tune_epochs, learning_rate=config.fine_tune_learning_rate,
               patience=config.patience, weights=class_weights(field_rows, device),
               checkpoint_path=checkpoint_path, history=history, stage="field_last_block")
    model, checkpoint = load_checkpoint(checkpoint_path, device)

    validation_logits, validation_labels = collect_logits(
        model, make_loader(validation_rows, train=False, config=config), device)
    temperature = fit_temperature(validation_logits, validation_labels)
    calibrated_validation = torch.softmax(validation_logits / temperature, dim=1).numpy()
    threshold_result = select_confidence_threshold(calibrated_validation, validation_labels.numpy())
    threshold = float(threshold_result["selected_threshold"])
    internal_logits, internal_labels = collect_logits(
        model, make_loader(internal_rows, train=False, config=config), device)
    internal_metrics = classification_metrics(internal_logits, internal_labels, temperature=temperature,
                                              threshold=threshold)
    recall_passed = all(item["recall"] >= 0.50 for item in internal_metrics["per_class"].values())
    gate_passed = internal_metrics["macro_f1"] >= 0.75 and recall_passed
    internal_metrics["deployment_gate"] = {
        "passed": gate_passed, "macro_f1_requirement": 0.75, "per_class_recall_requirement": 0.50,
        "recall_passed": recall_passed,
    }
    external_indices = [CLASS_NAMES.index(name) for name in ("healthy", "early_blight", "late_blight", "leaf_mold")]
    if external_rows:
        external_logits, external_labels = collect_logits(
            model, make_loader(external_rows, train=False, config=config), device)
        external_metrics = classification_metrics(external_logits, external_labels, temperature=temperature,
                                                  threshold=threshold, metric_label_indices=external_indices)
    else:
        external_metrics = {"status": "not_available", "sample_count": 0,
                            "reason": "IMG-T03 external manifest is empty"}

    shutil.copy2(checkpoint_path, ARTIFACT_DIR / "model.pt")
    shutil.copy2(CLASS_CONFIG_PATH, ARTIFACT_DIR / "class_names.json")
    preprocessing = {"input_size": INPUT_SIZE, "resize_shorter_side": 256, "center_crop": INPUT_SIZE,
                     "color_mode": "RGB", "mean": IMAGENET_MEAN, "std": IMAGENET_STD}
    training_config = {**asdict(config), "device": str(device), "pretrained_weights": "ImageNet1K_V1",
                       "train_augmentation": ["random_resized_crop", "horizontal_flip", "rotation_12deg",
                                              "mild_brightness_contrast_saturation_hue"],
                       "counts": {"plantvillage_pretrain": len(pv_rows), "field_train": len(field_rows),
                                  "validation": len(validation_rows), "internal_test": len(internal_rows),
                                  "external_test": len(external_rows)}, "history": history}
    calibration = {"method": "temperature_scaling", "temperature": temperature,
                   "fitted_on": "IMG-T02 validation logits only"}
    for filename, payload in (("preprocessing.json", preprocessing), ("training_config.json", training_config),
                              ("confidence_calibration.json", calibration),
                              ("confidence_threshold.json", threshold_result),
                              ("internal_metrics.json", internal_metrics), ("external_metrics.json", external_metrics)):
        (ARTIFACT_DIR / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    plot_confusion(internal_metrics["confusion_matrix"], "IMG-T02 internal test", ARTIFACT_DIR / "confusion_matrix_internal.png")
    if external_metrics.get("confusion_matrix"):
        plot_confusion(external_metrics["confusion_matrix"], "IMG-T03 external test", ARTIFACT_DIR / "confusion_matrix_external.png")
    else:
        plot_confusion([[0] * len(CLASS_NAMES) for _ in CLASS_NAMES], "IMG-T03 unavailable", ARTIFACT_DIR / "confusion_matrix_external.png")
    plot_history(history, ARTIFACT_DIR / "training_curves.png")
    status = "ready" if gate_passed else "under_evaluation"
    card = f"""# Tomato disease model card

- target_crop={TARGET_CROP}
- model_version={MODEL_VERSION}
- model_status={status}
- local_calibration_status=not_calibrated
- decision_scope=auxiliary_identification_with_manual_review

MobileNetV3-Small uses ImageNet initialization. PlantVillage is controlled-background foundation data;
IMG-T02 is the real-scene fine-tuning, validation and internal-test source; IMG-T03 is an independent external test.
No local Shenxian annotated image was used. The model supports tomato only, not muskmelon.
Predictions are auxiliary and cannot replace agronomist or plant-pathologist diagnosis.
The system does not provide automatic pesticide dosing or equipment control.
"""
    (ARTIFACT_DIR / "model_card.md").write_text(card, encoding="utf-8")
    checksum_lines = []
    for path in sorted(item for item in ARTIFACT_DIR.iterdir() if item.is_file() and item.name != "sha256sums.txt"):
        checksum_lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    (ARTIFACT_DIR / "sha256sums.txt").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    result = {"model_status": status, "device": str(device), "best_validation_macro_f1": checkpoint["best_validation_macro_f1"],
              "internal_accuracy": internal_metrics["accuracy"], "internal_macro_f1": internal_metrics["macro_f1"],
              "external_accuracy": external_metrics.get("accuracy"), "external_macro_f1": external_metrics.get("macro_f1"),
              "confidence_threshold": threshold, "temperature": temperature}
    (OUTPUT_DIR / "final_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
