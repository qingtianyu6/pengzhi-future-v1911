"""Re-evaluate the deployment gate from saved, real test metrics without retraining."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import torch

from app.ml.data.audit import PROJECT_ROOT


def main() -> None:
    root = PROJECT_ROOT / "backend" / "app" / "ml" / "artifacts" / "environment_forecast_v0.1"
    comparison = pd.read_csv(root / "model_comparison.csv")
    formal = comparison[comparison.model.isin(["xgboost", "gru", "lstm"])].groupby("model")["relative_persistence_improvement_pct"].agg(["mean", lambda values: int((values > 0).sum())])
    formal.columns = ["mean_improvement_pct", "wins_vs_persistence"]
    selected = str(formal.sort_values(["wins_vs_persistence", "mean_improvement_pct"], ascending=False).index[0])
    baseline = comparison[comparison.model.isin(["seasonal_24", "moving_average_6"])].groupby("model")["relative_persistence_improvement_pct"].mean()
    strongest_name = str(baseline.idxmax()); strongest = float(baseline.max()); selected_improvement = float(formal.loc[selected, "mean_improvement_pct"])
    status = "ready" if int(formal.loc[selected, "wins_vs_persistence"]) >= 10 and selected_improvement > strongest else "under_evaluation"
    gate = {"status": status, "selected_formal_model": selected, "selected_mean_improvement_vs_persistence_pct": selected_improvement, "selected_wins_vs_persistence": int(formal.loc[selected, "wins_vs_persistence"]), "strongest_baseline": strongest_name, "strongest_baseline_mean_improvement_vs_persistence_pct": strongest, "reason": "Formal model must beat persistence broadly and exceed the strongest deterministic baseline."}
    for filename in ["training_metadata.json", "run_summary.json", "metrics.json"]:
        path = root / filename; payload = json.loads(path.read_text(encoding="utf-8"))
        if filename == "training_metadata.json": payload["model_status"] = status; payload["validation_gate"] = gate
        elif filename == "run_summary.json": payload["status"] = status; payload["validation_gate"] = gate
        else: payload["validation_gate"] = gate
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    model_path = root / "final_model.pt"
    payload = torch.load(model_path, map_location="cpu", weights_only=False); payload["status"] = status; payload["validation_gate"] = gate; torch.save(payload, model_path)
    card_path = root / "model_card.md"; card = card_path.read_text(encoding="utf-8").replace("Status: **ready**", "Status: **under_evaluation**")
    card += f"\n## Validation gate\nThe selected GRU improves mean MAE over persistence by {selected_improvement:.2f}%, but the `{strongest_name}` baseline improves by {strongest:.2f}%. The model therefore remains `under_evaluation` and is not served as ready.\n"
    card_path.write_text(card, encoding="utf-8")
    checksums = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "checksums.sha256": checksums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root).as_posix()}")
    (root / "checksums.sha256").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    print(json.dumps(gate, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
