from __future__ import annotations

import numpy as np
import torch
from torch import nn


def fit_temperature(logits: torch.Tensor, labels: torch.Tensor) -> float:
    logits = logits.detach().float().cpu()
    labels = labels.detach().long().cpu()
    log_temperature = nn.Parameter(torch.zeros(1))
    optimizer = torch.optim.LBFGS([log_temperature], lr=0.05, max_iter=80, line_search_fn="strong_wolfe")
    criterion = nn.CrossEntropyLoss()

    def closure() -> torch.Tensor:
        optimizer.zero_grad()
        temperature = log_temperature.exp().clamp(0.05, 20.0)
        loss = criterion(logits / temperature, labels)
        loss.backward()
        return loss

    optimizer.step(closure)
    return float(log_temperature.detach().exp().clamp(0.05, 20.0).item())


def expected_calibration_error(probabilities: np.ndarray, labels: np.ndarray, bins: int = 15) -> float:
    confidence = probabilities.max(axis=1)
    predicted = probabilities.argmax(axis=1)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for lower, upper in zip(edges[:-1], edges[1:]):
        selected = (confidence > lower) & (confidence <= upper)
        if selected.any():
            accuracy = (predicted[selected] == labels[selected]).mean()
            ece += selected.mean() * abs(float(accuracy) - float(confidence[selected].mean()))
    return float(ece)


def select_confidence_threshold(probabilities: np.ndarray, labels: np.ndarray) -> dict:
    confidence = probabilities.max(axis=1)
    predicted = probabilities.argmax(axis=1)
    candidates = []
    for threshold in np.round(np.arange(0.30, 0.951, 0.025), 3):
        accepted = confidence >= threshold
        coverage = float(accepted.mean())
        accuracy = float((predicted[accepted] == labels[accepted]).mean()) if accepted.any() else 0.0
        candidates.append({"threshold": float(threshold), "coverage": coverage,
                           "accepted_accuracy": accuracy, "accepted_count": int(accepted.sum())})
    target = [item for item in candidates if item["accepted_accuracy"] >= 0.90 and item["accepted_count"] > 0]
    if target:
        chosen = max(target, key=lambda item: (item["coverage"], -item["threshold"]))
        rule = "max_coverage_with_accepted_accuracy_at_least_0.90"
    else:
        fallback = [item for item in candidates if item["coverage"] >= 0.50]
        chosen = max(fallback, key=lambda item: (item["accepted_accuracy"], item["coverage"]))
        rule = "max_accepted_accuracy_with_coverage_at_least_0.50"
    return {"selected_threshold": chosen["threshold"], "selection_rule": rule,
            "selected": chosen, "candidates": candidates, "fitted_on": "validation_only"}
