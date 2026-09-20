from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import torch

from app.ml.data.audit import PROJECT_ROOT
from app.ml.data.preprocessing import SEQUENCE_FEATURES, TARGETS, add_cycles
from app.ml.models.recurrent import RecurrentForecaster


ARTIFACT_DIR = PROJECT_ROOT / "backend" / "app" / "ml" / "artifacts" / "environment_forecast_v0.1"


class PredictionInputError(ValueError):
    def __init__(self, status: str, message: str) -> None:
        super().__init__(message); self.status = status


class EnvironmentPredictor:
    def __init__(self, artifact_dir: Path = ARTIFACT_DIR) -> None:
        self.artifact_dir = artifact_dir; self.status = "not_trained"; self.metadata: dict[str, Any] = {}; self.bundle: dict[str, Any] = {}; self.scalers: dict[str, Any] = {}; self.model: RecurrentForecaster | None = None
        self._load()

    def _load(self) -> None:
        metadata_path = self.artifact_dir / "training_metadata.json"
        if not metadata_path.exists(): return
        import json
        self.metadata = json.loads(metadata_path.read_text(encoding="utf-8")); self.status = str(self.metadata.get("model_status", "under_evaluation"))
        schema_path = self.artifact_dir / "feature_schema.json"
        if not schema_path.exists(): self.status = "schema_mismatch"; return
        model_type = self.metadata.get("model_type")
        if model_type in {"gru", "lstm"}:
            model_path = self.artifact_dir / "final_model.pt"
            if not model_path.exists(): self.status = "not_trained"; return
            self.bundle = torch.load(model_path, map_location="cpu", weights_only=False)
            self.scalers = joblib.load(self.artifact_dir / "scaler.joblib")
            self.model = RecurrentForecaster(self.bundle["input_size"], self.bundle["hidden_size"], self.bundle["forecast_horizon_hours"], self.bundle["target_count"], kind=model_type, dropout=0.0)
            self.model.load_state_dict(self.bundle["state_dict"]); self.model.eval()
        else:
            model_path = self.artifact_dir / "final_model.joblib"
            if not model_path.exists(): self.status = "not_trained"; return
            self.bundle = joblib.load(model_path)

    def prepare_history(self, records: list[dict[str, Any]]) -> tuple[pd.DataFrame, str]:
        if not records: raise PredictionInputError("insufficient_data", "没有环境历史数据")
        frame = pd.DataFrame(records); required = {"recorded_at", "temperature", "air_humidity", "source"}
        if not required.issubset(frame.columns): raise PredictionInputError("schema_mismatch", f"输入缺少字段：{sorted(required-set(frame.columns))}")
        frame["timestamp"] = pd.to_datetime(frame["recorded_at"], errors="coerce", utc=True).dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)
        frame["air_temperature_c"] = pd.to_numeric(frame["temperature"], errors="coerce"); frame["air_humidity_pct"] = pd.to_numeric(frame["air_humidity"], errors="coerce")
        frame = frame.dropna(subset=["timestamp"]).sort_values("timestamp").drop_duplicates("timestamp", keep="last")
        source = str(frame["source"].iloc[-1]) if frame["source"].nunique() == 1 else "mixed"
        hourly = frame.set_index("timestamp")[["air_temperature_c", "air_humidity_pct"]].resample("1h").mean().reset_index()
        if len(hourly) < 24: raise PredictionInputError("insufficient_data", f"仅有{len(hourly)}个小时点，需要连续24个")
        hourly = hourly.tail(24).reset_index(drop=True)
        if hourly[["air_temperature_c", "air_humidity_pct"]].isna().any().any(): raise PredictionInputError("insufficient_data", "最近24小时存在缺测或不连续小时")
        if not (hourly["timestamp"].diff().dropna() == pd.Timedelta(hours=1)).all(): raise PredictionInputError("insufficient_data", "最近24小时不是连续小时序列")
        return add_cycles(hourly), source

    def predict(self, records: list[dict[str, Any]], horizon_hours: int) -> dict[str, Any]:
        if self.status != "ready": raise PredictionInputError(self.status, "模型尚未通过最强基线验证" if self.status == "under_evaluation" else "模型不可用")
        history, source = self.prepare_history(records)
        if list(self.bundle.get("features", [])) != SEQUENCE_FEATURES: raise PredictionInputError("schema_mismatch", "模型特征顺序与当前推理代码不一致")
        sequence = history[SEQUENCE_FEATURES].to_numpy(dtype=np.float32)
        if self.metadata["model_type"] in {"gru", "lstm"}:
            scaled = self.scalers["feature"].transform(sequence).astype(np.float32)
            assert self.model is not None
            with torch.no_grad(): predicted_scaled = self.model(torch.from_numpy(scaled[None, :, :])).numpy()[0]
            prediction = self.scalers["target"].inverse_transform(predicted_scaled)
        else:
            raise PredictionInputError("schema_mismatch", "当前推理器仅启用已选择的循环网络产物")
        quantiles = self.bundle["prediction_interval_residual_quantiles"]; end_time = history["timestamp"].iloc[-1]
        points = []
        for horizon in range(1, horizon_hours + 1):
            values = prediction[horizon - 1]; lower = {}; upper = {}
            for index, target in enumerate(TARGETS):
                lower[target] = float(values[index] + quantiles[target][f"h{horizon}"]["lower"]); upper[target] = float(values[index] + quantiles[target][f"h{horizon}"]["upper"])
            points.append({"forecast_time": end_time + pd.Timedelta(hours=horizon), "horizon": horizon, "temperature": float(values[0]), "air_humidity": float(values[1]), "light_intensity": float(values[2]), "lower_bounds": lower, "upper_bounds": upper})
        return {"history": history, "source": source, "input_end_time": end_time, "predictions": points}


@lru_cache(maxsize=1)
def get_environment_predictor() -> EnvironmentPredictor:
    return EnvironmentPredictor()
