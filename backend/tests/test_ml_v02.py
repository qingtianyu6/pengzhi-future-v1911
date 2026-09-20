from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

from app.ml.data.audit import PROJECT_ROOT
from app.ml.inference.predictor_v02 import EnvironmentPredictorV02
from app.ml.v02.data import (
    DEPLOY_FEATURES,
    DEPLOY_TARGETS,
    V02_ARTIFACT_DIR,
    add_cycles,
    make_windows,
    validate_unit_contract,
)
from app.ml.v02.metrics import interval_statistics, metric_rows
from app.ml.v02.models import SeasonalResidualRNN
from app.ml.v02.run_v02 import select_champions
from app.ml.v02.training import apply_ensemble, fit_ensemble_weights
from app.ml.v02.validation import (
    assert_windows_no_leakage,
    expanding_rolling_folds,
    leave_one_greenhouse_out,
)


def sample_grouped_hourly(hours: int = 400) -> pd.DataFrame:
    frames = []
    for greenhouse, offset in [("g1", 0.0), ("g2", 1.0)]:
        timestamp = pd.date_range("2024-01-01", periods=hours, freq="1h")
        frames.append(pd.DataFrame({
            "timestamp": timestamp,
            "greenhouse_id": greenhouse,
            "air_temperature_c": 20 + offset + np.sin(np.arange(hours) / 24 * 2 * np.pi),
            "air_humidity_pct": 70 - offset + np.cos(np.arange(hours) / 24 * 2 * np.pi),
        }))
    return add_cycles(pd.concat(frames, ignore_index=True))


def test_v02_window_seasonal_index_and_labels_are_leak_free() -> None:
    windows = make_windows(sample_grouped_hourly(), DEPLOY_FEATURES, DEPLOY_TARGETS)
    assert_windows_no_leakage(windows)
    assert np.array_equal(windows.seasonal[:, 0], windows.X[:, 0, :2])
    assert np.array_equal(windows.seasonal[:, 5], windows.X[:, 5, :2])


def test_expanding_folds_are_ordered_and_training_expands() -> None:
    windows = make_windows(sample_grouped_hourly(), DEPLOY_FEATURES, DEPLOY_TARGETS)
    folds = expanding_rolling_folds(windows)
    assert len(folds) == 3
    assert [fold.train_mask.sum() for fold in folds] == sorted(fold.train_mask.sum() for fold in folds)
    for fold in folds:
        assert windows.target_times[fold.train_mask, -1].max() < windows.input_end_times[fold.validation_mask].min()


def test_leave_one_greenhouse_out_has_no_group_overlap() -> None:
    windows = make_windows(sample_grouped_hourly(), DEPLOY_FEATURES, DEPLOY_TARGETS)
    for held_out, train, validation in leave_one_greenhouse_out(windows):
        assert set(windows.greenhouse_ids[train]).isdisjoint(set(windows.greenhouse_ids[validation]))
        assert set(windows.greenhouse_ids[validation]) == {held_out}


def test_residual_label_is_actual_minus_seasonal() -> None:
    windows = make_windows(sample_grouped_hourly(), DEPLOY_FEATURES, DEPLOY_TARGETS)
    residual = windows.y - windows.seasonal
    assert np.allclose(windows.seasonal + residual, windows.y)


@pytest.mark.parametrize("kind", ["gru", "lstm"])
def test_recurrent_skip_connection_returns_seasonal_with_zero_residual(kind: str) -> None:
    model = SeasonalResidualRNN(6, 8, 6, 2, kind=kind, dropout=0)
    torch.nn.init.zeros_(model.residual_head.weight)
    torch.nn.init.zeros_(model.residual_head.bias)
    seasonal = torch.randn(3, 6, 2)
    assert torch.equal(model(torch.randn(3, 24, 6), seasonal), seasonal)


def test_ensemble_weights_are_validation_optimized_and_bounded() -> None:
    truth = np.array([[[0.0]], [[2.0]], [[4.0]]], dtype=np.float32)
    seasonal = np.array([[[1.0]], [[1.0]], [[1.0]]], dtype=np.float32)
    ml = truth.copy()
    weights = fit_ensemble_weights(truth, seasonal, ml)
    assert 0 <= weights.item() <= 1
    assert np.mean(np.abs(truth - apply_ensemble(seasonal, ml, weights))) <= np.mean(np.abs(truth - seasonal))


def test_champion_selection_prefers_simpler_method_within_one_percent() -> None:
    rows = []
    for fold in range(3):
        for method, mae in [("seasonal_24", 1.0), ("seasonal_residual_xgboost", 0.995)]:
            rows.append({"config": "deployment_compatible", "method": method, "fold": f"rolling_{fold}", "target": "air_temperature_c", "horizon": 1, "mae": mae, "rmse": mae, "stability": 0, "nmae": mae, "relative_seasonal_improvement_pct": 100 * (1 - mae)})
    frame = pd.DataFrame(rows)
    # Populate the remaining horizons so the registry contract is complete.
    frame = pd.concat([frame.assign(horizon=h) for h in range(1, 7)], ignore_index=True)
    selected = select_champions(frame, "deployment_compatible", ["air_temperature_c"])
    assert selected["air_temperature_c"]["h1"]["method"] == "seasonal_24"


def test_prediction_interval_statistics_cover_known_values() -> None:
    truth = np.zeros((4, 1, 1), dtype=np.float32)
    prediction = np.zeros_like(truth)
    lower = np.full_like(truth, -1)
    upper = np.full_like(truth, 1)
    times = pd.date_range("2024-01-01", periods=4, freq="6h").to_numpy()[:, None]
    rows = interval_statistics(truth, prediction, lower, upper, ["air_temperature_c"], times)
    assert rows[0]["coverage"] == 1.0
    assert {row["period"] for row in rows} == {"all", "day", "night"}


def test_metrics_use_positive_improvement_sign() -> None:
    truth = np.zeros((2, 1, 1), dtype=np.float32)
    prediction = np.full_like(truth, 0.5)
    seasonal = np.ones_like(truth)
    row = metric_rows("ml", "fold", truth, prediction, seasonal, ["target"], np.array([1]))[0]
    assert row["relative_seasonal_improvement_pct"] == pytest.approx(50)


def test_klx_is_rejected_for_par_model() -> None:
    with pytest.raises(ValueError, match="unit mismatch"):
        validate_unit_contract("kilolux", "micromole_per_m2_second")


def test_deployment_features_do_not_depend_on_par_and_par_unit_is_accepted() -> None:
    assert not any("par" in feature.lower() for feature in DEPLOY_FEATURES)
    validate_unit_contract("micromole_per_m2_second", "micromole_per_m2_second")


def test_registered_v02_predictor_is_ready_and_par_is_research_only() -> None:
    predictor = EnvironmentPredictorV02()
    assert predictor.status == "ready"
    assert predictor.metadata["model_status"] == "ready"
    assert predictor.registry["par_availability"].startswith("research_only")


def test_registered_predictor_is_deterministic_for_same_input() -> None:
    predictor = EnvironmentPredictorV02()
    start = pd.Timestamp("2026-08-20T00:00:00Z")
    records = [{"recorded_at": start + pd.Timedelta(hours=i), "temperature": 20 + i / 10, "air_humidity": 75 - i / 10, "source": "simulation"} for i in range(24)]
    first = predictor.predict(records, 2)
    second = predictor.predict(records, 2)
    assert first["predictions"] == second["predictions"]
    assert all(point["par_umol_m2_s"] is None for point in first["predictions"])


@pytest.mark.parametrize("version", ["v0.1", "v0.2"])
def test_artifact_checksums_match(version: str) -> None:
    root = PROJECT_ROOT / "backend" / "app" / "ml" / "artifacts" / f"environment_forecast_{version}"
    for line in (root / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        assert hashlib.sha256((root / Path(relative)).read_bytes()).hexdigest() == expected


def test_metadata_preserves_scope_and_external_benchmark_disclosure() -> None:
    metadata = json.loads((V02_ARTIFACT_DIR / "training_metadata.json").read_text(encoding="utf-8"))
    assert metadata["dataset_license"] == "CC0 1.0"
    assert metadata["crop"] == "cherry_tomato"
    assert metadata["ml_gate"]["wins_at_least_2pct"] > metadata["ml_gate"]["comparisons"] / 2
    assert any("not unseen" in item for item in metadata["limitations"])
