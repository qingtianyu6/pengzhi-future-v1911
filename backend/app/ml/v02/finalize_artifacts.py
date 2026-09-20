"""Apply metadata-only V0.2 finalization without retraining any model."""

from __future__ import annotations

import json

import pandas as pd

from app.ml.v02.data import V02_ARTIFACT_DIR
from app.ml.v02.run_v02 import write_checksums


def main() -> None:
    registry_path = V02_ARTIFACT_DIR / "champion_registry.json"
    metadata_path = V02_ARTIFACT_DIR / "training_metadata.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    # The overall ML validation gate passed. Individual target/horizon champions
    # may still deliberately use the simpler seasonal baseline.
    expected = "ready" if registry["ml_candidate_status"] == "ready" else "baseline_ready"
    registry["model_status"] = expected
    metadata["model_status"] = expected
    metrics = pd.read_csv(V02_ARTIFACT_DIR / "rolling_cv_metrics.csv")
    ml = metrics[(metrics["config"] == "deployment_compatible") & metrics["method"].isin(["seasonal_residual_xgboost", "seasonal_residual_gru", "seasonal_residual_lstm"])]
    best = ml.loc[ml.groupby(["target", "horizon", "fold"])["mae"].idxmin()]
    seasonal = metrics[(metrics["config"] == "deployment_compatible") & (metrics["method"] == "seasonal_24")][["target", "horizon", "fold", "rmse"]].rename(columns={"rmse": "seasonal_rmse"})
    gate = best.merge(seasonal, on=["target", "horizon", "fold"], validate="one_to_one")
    metadata["ml_gate"]["rmse_within_5pct_of_seasonal"] = int((gate["rmse"] <= gate["seasonal_rmse"] * 1.05).sum())
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    write_checksums()


if __name__ == "__main__":
    main()
