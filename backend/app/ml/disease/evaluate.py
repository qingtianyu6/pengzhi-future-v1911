from __future__ import annotations

import numpy as np
import torch
from sklearn.metrics import (accuracy_score, confusion_matrix, precision_recall_fscore_support)
from torch.utils.data import DataLoader

from app.ml.disease.calibration import expected_calibration_error
from app.ml.disease.config import CLASS_NAMES


@torch.no_grad()
def collect_logits(model: torch.nn.Module, loader: DataLoader, device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    model.eval()
    logits, labels = [], []
    for images, target in loader:
        logits.append(model(images.to(device)).cpu())
        labels.append(target.cpu())
    return torch.cat(logits), torch.cat(labels)


def classification_metrics(logits: torch.Tensor, labels: torch.Tensor, *, temperature: float = 1.0,
                           threshold: float = 0.0, metric_label_indices: list[int] | None = None) -> dict:
    raw_probabilities = torch.softmax(logits, dim=1).numpy()
    probabilities = torch.softmax(logits / temperature, dim=1).numpy()
    true = labels.numpy()
    predicted = probabilities.argmax(axis=1)
    metric_labels = metric_label_indices or list(range(len(CLASS_NAMES)))
    precision, recall, f1, support = precision_recall_fscore_support(
        true, predicted, labels=metric_labels, average=None, zero_division=0
    )
    macro_precision, macro_recall, macro_f1, _ = precision_recall_fscore_support(
        true, predicted, labels=metric_labels, average="macro", zero_division=0
    )
    accepted = probabilities.max(axis=1) >= threshold
    per_class = {
        CLASS_NAMES[index]: {"precision": float(precision[position]), "recall": float(recall[position]),
                             "f1": float(f1[position]), "support": int(support[position])}
        for position, index in enumerate(metric_labels)
    }
    return {
        "accuracy": float(accuracy_score(true, predicted)), "macro_precision": float(macro_precision),
        "macro_recall": float(macro_recall), "macro_f1": float(macro_f1), "per_class": per_class,
        "confusion_matrix": confusion_matrix(true, predicted, labels=list(range(len(CLASS_NAMES)))).tolist(),
        "ece_before": expected_calibration_error(raw_probabilities, true),
        "ece_after": expected_calibration_error(probabilities, true),
        "confidence": {"mean": float(probabilities.max(axis=1).mean()),
                       "median": float(np.median(probabilities.max(axis=1))),
                       "min": float(probabilities.max(axis=1).min()),
                       "max": float(probabilities.max(axis=1).max())},
        "confidence_threshold": threshold, "acceptance_coverage": float(accepted.mean()),
        "low_confidence_ratio": float((~accepted).mean()),
        "accepted_accuracy": float((predicted[accepted] == true[accepted]).mean()) if accepted.any() else 0.0,
        "sample_count": int(len(true)),
    }
