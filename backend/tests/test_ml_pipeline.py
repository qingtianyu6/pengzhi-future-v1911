from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from app.ml.baselines.models import moving_average, persistence, seasonal_24
from app.ml.data.preprocessing import SEQUENCE_FEATURES, TARGETS, _clean_agc2_team, add_cycles, aggregate_hourly
from app.ml.features.windows import assert_no_leakage, make_windows, split_group_time
from app.ml.inference.predictor import ARTIFACT_DIR, EnvironmentPredictor, PredictionInputError
from app.ml.models.recurrent import RecurrentForecaster
from app.ml.training.train_environment_forecast import scale_windows


def sample_hourly(hours: int = 100) -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-01", periods=hours, freq="1h")
    frame = pd.DataFrame({
        "timestamp": timestamps, "greenhouse_id": "test", "air_temperature_c": np.linspace(18, 28, hours),
        "air_humidity_pct": np.linspace(80, 60, hours), "light_intensity": np.maximum(0, np.sin(np.arange(hours) / 24 * 2 * np.pi)) * 500,
    })
    return add_cycles(frame)


def test_agc2_adapter_reads_sorts_and_deduplicates(tmp_path: Path) -> None:
    team = tmp_path / "Team"; team.mkdir(); path = team / "GreenhouseClimate.csv"
    pd.DataFrame({"%time": [43831 + 10 / 24, 43831, 43831], "Tair": [21, 20, 22], "Rhair": [70, 71, 72], "Tot_PAR": [0, 10, 20], "CO2air": [500, 510, 520], "VentLee": [0, 1, 2], "Ventwind": [0, 1, 2]}).to_csv(path, index=False)
    frame, invalid = _clean_agc2_team(path)
    assert frame["timestamp"].is_monotonic_increasing
    assert len(frame) == 2
    assert invalid == {"temperature": 0, "humidity": 0, "light": 0, "co2": 0}


def test_hourly_aggregation_preserves_mean_min_max() -> None:
    raw = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=12, freq="5min"), "air_temperature_c": np.arange(12), "air_humidity_pct": np.arange(12) + 50,
        "light_intensity": np.arange(12) * 10, "co2_ppm": np.arange(12) + 500, "window_state": 0, "ventilation_state": 0,
        "greenhouse_id": "g", "dataset_id": "d", "source_dataset": "s", "crop": "tomato", "source_type": "public_real_dataset",
    })
    result = aggregate_hourly(raw)
    assert len(result) == 1
    assert result.iloc[0]["air_temperature_c"] == 5.5
    assert result.iloc[0]["air_temperature_min_c"] == 0
    assert result.iloc[0]["air_temperature_max_c"] == 11


def test_time_split_is_ordered() -> None:
    split = split_group_time(sample_hourly(100))
    assert split["train"].timestamp.max() < split["validation"].timestamp.min()
    assert split["validation"].timestamp.max() < split["test"].timestamp.min()
    assert [len(split[name]) for name in ["train", "validation", "test"]] == [70, 15, 15]


def test_windows_have_expected_shape_and_no_leakage() -> None:
    windows = make_windows(sample_hourly(100), 24, 6)
    assert windows.X.shape == (71, 24, len(SEQUENCE_FEATURES))
    assert windows.y.shape == (71, 6, len(TARGETS))
    assert_no_leakage(windows)
    assert np.all(windows.target_times[:, 0] > windows.input_end_times)


def test_windows_do_not_cross_a_missing_hour() -> None:
    frame = sample_hourly(100).drop(index=50).reset_index(drop=True)
    windows = make_windows(frame, 24, 6)
    assert not any(end < np.datetime64("2024-01-03T02") and target[-1] > np.datetime64("2024-01-03T02") for end, target in zip(windows.input_end_times, windows.target_times, strict=True))


def test_scaler_is_fitted_only_on_training_windows() -> None:
    parts = split_group_time(sample_hourly(300))
    windows = {name: make_windows(frame) for name, frame in parts.items()}
    _, scalers = scale_windows(windows["train"], windows["validation"], windows["test"])
    expected = windows["train"].X.reshape(-1, len(SEQUENCE_FEATURES)).mean(axis=0)
    assert np.allclose(scalers["feature"].mean_, expected, atol=1e-6)


def test_baselines_are_deterministic_and_correct() -> None:
    history = np.arange(2 * 24 * 3, dtype=np.float32).reshape(2, 24, 3)
    assert np.array_equal(persistence(history, 6)[:, 0], history[:, -1])
    assert np.array_equal(seasonal_24(history, 6), history[:, :6])
    assert np.allclose(moving_average(history, 6)[:, 0], history[:, -6:].mean(axis=1))
    assert np.array_equal(persistence(history, 6), persistence(history, 6))


def test_gru_and_lstm_output_shapes() -> None:
    inputs = torch.zeros(4, 24, len(SEQUENCE_FEATURES))
    for kind in ["gru", "lstm"]:
        model = RecurrentForecaster(len(SEQUENCE_FEATURES), 32, 6, len(TARGETS), kind=kind)
        assert model(inputs).shape == (4, 6, len(TARGETS))


def test_saved_model_loads_and_is_deterministic() -> None:
    payload = torch.load(ARTIFACT_DIR / "final_model.pt", map_location="cpu", weights_only=False)
    model = RecurrentForecaster(payload["input_size"], payload["hidden_size"], payload["forecast_horizon_hours"], payload["target_count"], kind=payload["model_type"], dropout=0)
    model.load_state_dict(payload["state_dict"]); model.eval(); inputs = torch.zeros(1, 24, len(SEQUENCE_FEATURES))
    with torch.no_grad(): first = model(inputs); second = model(inputs)
    assert torch.equal(first, second)


def test_predictor_reports_saved_gate() -> None:
    predictor = EnvironmentPredictor()
    assert predictor.status == "under_evaluation"
    assert predictor.model is not None


def test_missing_artifact_returns_not_trained(tmp_path: Path) -> None:
    assert EnvironmentPredictor(tmp_path).status == "not_trained"


def test_prepare_history_reports_insufficient_data() -> None:
    predictor = EnvironmentPredictor()
    records = [{"recorded_at": datetime.now(UTC), "temperature": 20, "air_humidity": 70, "source": "simulation"}]
    try: predictor.prepare_history(records)
    except PredictionInputError as error: assert error.status == "insufficient_data"
    else: raise AssertionError("Expected insufficient_data")


def test_prepare_history_reports_schema_mismatch() -> None:
    predictor = EnvironmentPredictor()
    try: predictor.prepare_history([{"recorded_at": datetime.now(UTC)}])
    except PredictionInputError as error: assert error.status == "schema_mismatch"
    else: raise AssertionError("Expected schema_mismatch")


def test_prepare_history_accepts_24_contiguous_hours() -> None:
    predictor = EnvironmentPredictor(); start = datetime(2026, 1, 1, tzinfo=UTC)
    records = [{"recorded_at": start + timedelta(hours=i), "temperature": 20 + i / 10, "air_humidity": 70 - i / 10, "source": "simulation"} for i in range(24)]
    frame, source = predictor.prepare_history(records)
    assert frame.shape[0] == 24
    assert source == "simulation"
    assert not frame[SEQUENCE_FEATURES].isna().any().any()
