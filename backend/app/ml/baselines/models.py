from __future__ import annotations

import numpy as np


def persistence(history: np.ndarray, horizon: int) -> np.ndarray:
    return np.repeat(history[:, -1:, :], horizon, axis=1)


def seasonal_24(history: np.ndarray, horizon: int) -> np.ndarray:
    if history.shape[1] < 24: raise ValueError("Seasonal baseline requires 24 history steps")
    return history[:, :horizon, :].copy()


def moving_average(history: np.ndarray, horizon: int, lookback: int = 6) -> np.ndarray:
    mean = history[:, -lookback:, :].mean(axis=1, keepdims=True)
    return np.repeat(mean, horizon, axis=1)
