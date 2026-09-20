from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.ml.data.preprocessing import SEQUENCE_FEATURES, TARGETS


@dataclass
class WindowSet:
    X: np.ndarray
    y: np.ndarray
    target_history: np.ndarray
    greenhouse_ids: np.ndarray
    input_end_times: np.ndarray
    target_times: np.ndarray


def split_group_time(frame: pd.DataFrame, train_fraction: float = 0.70, validation_fraction: float = 0.15) -> dict[str, pd.DataFrame]:
    parts: dict[str, list[pd.DataFrame]] = {"train": [], "validation": [], "test": []}
    for _, group in frame.sort_values("timestamp").groupby("greenhouse_id", sort=True):
        n = len(group); train_end = int(n * train_fraction); validation_end = int(n * (train_fraction + validation_fraction))
        parts["train"].append(group.iloc[:train_end].copy())
        parts["validation"].append(group.iloc[train_end:validation_end].copy())
        parts["test"].append(group.iloc[validation_end:].copy())
    return {name: pd.concat(groups, ignore_index=True) for name, groups in parts.items()}


def make_windows(frame: pd.DataFrame, input_hours: int = 24, horizon_hours: int = 6) -> WindowSet:
    Xs = []; ys = []; histories = []; greenhouse_ids = []; input_ends = []; target_times = []
    for greenhouse_id, group in frame.sort_values("timestamp").groupby("greenhouse_id", sort=True):
        group = group.reset_index(drop=True)
        timestamps = pd.to_datetime(group["timestamp"])
        values_x = group[SEQUENCE_FEATURES].to_numpy(dtype=np.float32)
        values_y = group[TARGETS].to_numpy(dtype=np.float32)
        for end in range(input_hours - 1, len(group) - horizon_hours):
            start = end - input_hours + 1; target_end = end + horizon_hours
            window_times = timestamps.iloc[start:target_end + 1]
            if not (window_times.diff().dropna() == pd.Timedelta(hours=1)).all(): continue
            x = values_x[start:end + 1]; y = values_y[end + 1:target_end + 1]; history = values_y[start:end + 1]
            if np.isnan(x).any() or np.isnan(y).any() or np.isnan(history).any(): continue
            Xs.append(x); ys.append(y); histories.append(history); greenhouse_ids.append(str(greenhouse_id)); input_ends.append(timestamps.iloc[end].to_datetime64()); target_times.append(timestamps.iloc[end + 1:target_end + 1].to_numpy(dtype="datetime64[ns]"))
    return WindowSet(np.asarray(Xs, dtype=np.float32), np.asarray(ys, dtype=np.float32), np.asarray(histories, dtype=np.float32), np.asarray(greenhouse_ids), np.asarray(input_ends), np.asarray(target_times))


def build_xgb_features(windows: WindowSet) -> tuple[np.ndarray, list[str]]:
    result = []; names: list[str] = []
    lags = [1, 2, 3, 6, 12, 24]
    for sample_index in range(len(windows.X)):
        row = []
        # Deployment database stores light in klx while AGC uses PAR.  Light is
        # still a forecast target, but its history is deliberately excluded
        # from model inputs to avoid an invalid cross-unit conversion.
        for feature_index, target in enumerate(TARGETS[:2]):
            series = windows.target_history[sample_index, :, feature_index]
            row.extend(series[-lag] for lag in lags)
            row.extend([series[-3:].mean(), series[-6:].mean(), series[-12:].mean(), series.mean(), series[-3:].std(), series[-6:].std(), series[-6:].min(), series[-6:].max()])
        row.extend(windows.X[sample_index, -1, 2:].tolist())
        result.append(row)
    for target in TARGETS[:2]:
        names.extend([f"{target}_lag_{lag}" for lag in lags])
        names.extend([f"{target}_rolling_mean_3", f"{target}_rolling_mean_6", f"{target}_rolling_mean_12", f"{target}_rolling_mean_24", f"{target}_rolling_std_3", f"{target}_rolling_std_6", f"{target}_rolling_min_6", f"{target}_rolling_max_6"])
    names.extend(SEQUENCE_FEATURES[2:])
    return np.asarray(result, dtype=np.float32), names


def assert_no_leakage(windows: WindowSet) -> None:
    if len(windows.X) == 0: raise ValueError("No valid contiguous windows were created")
    if not np.all(windows.target_times[:, 0] > windows.input_end_times): raise AssertionError("Target timestamp leaks into input")
