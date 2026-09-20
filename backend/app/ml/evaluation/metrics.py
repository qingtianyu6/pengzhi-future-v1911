from __future__ import annotations

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from app.ml.data.preprocessing import TARGETS


def metric_rows(model: str, truth: np.ndarray, prediction: np.ndarray, persistence_prediction: np.ndarray | None = None) -> list[dict[str, float | int | str | None]]:
    rows = []
    for target_index, target in enumerate(TARGETS):
        for horizon_index in range(truth.shape[1]):
            actual = truth[:, horizon_index, target_index]; predicted = prediction[:, horizon_index, target_index]
            mae = float(mean_absolute_error(actual, predicted)); rmse = float(mean_squared_error(actual, predicted) ** 0.5); r2 = float(r2_score(actual, predicted))
            baseline_mae = float(mean_absolute_error(actual, persistence_prediction[:, horizon_index, target_index])) if persistence_prediction is not None else None
            improvement = ((baseline_mae - mae) / baseline_mae * 100) if baseline_mae and baseline_mae > 0 else None
            rows.append({"model": model, "target": target, "horizon": horizon_index + 1, "mae": mae, "rmse": rmse, "r2": r2, "relative_persistence_improvement_pct": improvement})
    return rows
