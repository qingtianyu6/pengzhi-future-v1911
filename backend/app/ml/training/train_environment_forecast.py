from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[2] / ".mplconfig"))

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import torch
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from torch import nn
from torch.utils.data import DataLoader, TensorDataset
from xgboost import XGBRegressor

from app.ml.baselines.models import moving_average, persistence, seasonal_24
from app.ml.data.audit import PROJECT_ROOT
from app.ml.data.preprocessing import PROCESSED_DIR, SEQUENCE_FEATURES, TARGETS, TARGET_UNITS, process_agc2, process_agc4_external
from app.ml.evaluation.metrics import metric_rows
from app.ml.features.windows import WindowSet, assert_no_leakage, build_xgb_features, make_windows, split_group_time
from app.ml.models.recurrent import RecurrentForecaster


SEED = 20260822
HORIZON = 6
INPUT_HOURS = 24
THREADS = 4
ARTIFACT_DIR = PROJECT_ROOT / "backend" / "app" / "ml" / "artifacts" / "environment_forecast_v0.1"
PLOT_DIR = ARTIFACT_DIR / "plots"


def load_core_training_data() -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame, str]:
    """Load raw data when available, otherwise reuse the packaged processed snapshot."""
    agc2_raw = PROJECT_ROOT / "data" / "external" / "autonomous_greenhouse_challenge_2nd" / "extracted"
    agc4_raw = PROJECT_ROOT / "datasets" / "public_greenhouse" / "02_agc4_dwarf_tomato" / "extracted"
    agc2_processed = PROCESSED_DIR / "agc2_hourly.csv.gz"
    agc4_processed = PROCESSED_DIR / "agc4_external_hourly.csv.gz"
    stats_path = PROCESSED_DIR / "agc2_processing_stats.json"

    if list(agc2_raw.glob("*/GreenhouseClimate.csv")) and list(agc4_raw.rglob("*.csv")):
        hourly, processing_stats = process_agc2()
        external_hourly = process_agc4_external()
        return hourly, processing_stats, external_hourly, "raw_public_datasets"

    if not agc2_processed.is_file() or not agc4_processed.is_file():
        raise FileNotFoundError(
            "Neither the raw public datasets nor both packaged processed snapshots are available."
        )

    hourly = pd.read_csv(agc2_processed)
    external_hourly = pd.read_csv(agc4_processed)
    for frame in (hourly, external_hourly):
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="raise")
    processing_stats = json.loads(stats_path.read_text(encoding="utf-8")) if stats_path.is_file() else {}
    processing_stats = {
        **processing_stats,
        "training_input_mode": "packaged_processed_snapshot",
        "snapshot_files": [
            str(agc2_processed.relative_to(PROJECT_ROOT)),
            str(agc4_processed.relative_to(PROJECT_ROOT)),
        ],
    }
    return hourly, processing_stats, external_hourly, "packaged_processed_snapshot"


def seed_everything() -> None:
    random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
    torch.set_num_threads(THREADS)
    try: torch.set_num_interop_threads(1)
    except RuntimeError: pass


def scale_windows(train: WindowSet, validation: WindowSet, test: WindowSet) -> tuple[dict[str, WindowSet], dict[str, StandardScaler]]:
    feature_scaler = StandardScaler().fit(train.X.reshape(-1, train.X.shape[-1]))
    target_scaler = StandardScaler().fit(train.y.reshape(-1, train.y.shape[-1]))
    def transform(data: WindowSet) -> WindowSet:
        X = feature_scaler.transform(data.X.reshape(-1, data.X.shape[-1])).reshape(data.X.shape).astype(np.float32)
        y = target_scaler.transform(data.y.reshape(-1, data.y.shape[-1])).reshape(data.y.shape).astype(np.float32)
        return WindowSet(X, y, data.target_history, data.greenhouse_ids, data.input_end_times, data.target_times)
    return {"train": transform(train), "validation": transform(validation), "test": transform(test)}, {"feature": feature_scaler, "target": target_scaler}


def inverse_targets(values: np.ndarray, scaler: StandardScaler) -> np.ndarray:
    return scaler.inverse_transform(values.reshape(-1, values.shape[-1])).reshape(values.shape)


def train_xgboost(train: WindowSet, validation: WindowSet) -> tuple[list[XGBRegressor], list[str], dict[str, Any], float]:
    X_train, names = build_xgb_features(train); X_validation, _ = build_xgb_features(validation)
    y_train = train.y.reshape(len(train.y), -1); y_validation = validation.y.reshape(len(validation.y), -1)
    configs = [
        {"max_depth": 4, "learning_rate": 0.05, "n_estimators": 160, "min_child_weight": 3},
        {"max_depth": 6, "learning_rate": 0.04, "n_estimators": 200, "min_child_weight": 5},
    ]
    representatives = [0, 1, 2]
    search = []
    for config in configs:
        scores = []
        for output_index in representatives:
            model = XGBRegressor(objective="reg:squarederror", random_state=SEED, n_jobs=THREADS, subsample=0.85, colsample_bytree=0.85, reg_lambda=1.0, tree_method="hist", **config)
            model.fit(X_train, y_train[:, output_index], verbose=False)
            scale = max(float(np.std(y_validation[:, output_index])), 1e-6)
            scores.append(mean_absolute_error(y_validation[:, output_index], model.predict(X_validation)) / scale)
        search.append({"params": config, "representative_validation_normalized_mae": float(np.mean(scores))})
        print(f"XGBoost search {config}: normalized MAE={np.mean(scores):.4f}", flush=True)
    best = min(search, key=lambda item: item["representative_validation_normalized_mae"])["params"]
    models = []; started = time.perf_counter()
    model_dir = ARTIFACT_DIR / "xgboost_models"; model_dir.mkdir(parents=True, exist_ok=True)
    for output_index in range(y_train.shape[1]):
        model = XGBRegressor(objective="reg:squarederror", random_state=SEED, n_jobs=THREADS, subsample=0.85, colsample_bytree=0.85, reg_lambda=1.0, tree_method="hist", **best)
        model.fit(X_train, y_train[:, output_index], eval_set=[(X_validation, y_validation[:, output_index])], verbose=False)
        model.save_model(model_dir / f"output_{output_index:02d}.json")
        models.append(model)
    duration = time.perf_counter() - started
    return models, names, {"search": search, "best_params": best}, duration


def predict_xgboost(models: list[XGBRegressor], windows: WindowSet) -> np.ndarray:
    X, _ = build_xgb_features(windows)
    return np.column_stack([model.predict(X) for model in models]).reshape(-1, HORIZON, len(TARGETS)).astype(np.float32)


def train_recurrent(kind: str, scaled: dict[str, WindowSet], target_scaler: StandardScaler, max_epochs: int = 30, patience: int = 6) -> tuple[RecurrentForecaster, dict[str, Any], float]:
    model = RecurrentForecaster(len(SEQUENCE_FEATURES), 32, HORIZON, len(TARGETS), kind=kind, dropout=0.15)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.HuberLoss(delta=1.0)
    generator = torch.Generator().manual_seed(SEED)
    train_loader = DataLoader(TensorDataset(torch.from_numpy(scaled["train"].X), torch.from_numpy(scaled["train"].y)), batch_size=64, shuffle=True, generator=generator, num_workers=0)
    validation_x = torch.from_numpy(scaled["validation"].X); validation_y = torch.from_numpy(scaled["validation"].y)
    history = {"train_loss": [], "validation_loss": [], "epoch_seconds": []}; best_loss = float("inf"); best_state = None; stale = 0; started = time.perf_counter()
    checkpoint = ARTIFACT_DIR / f"{kind}_best.pt"
    for epoch in range(1, max_epochs + 1):
        epoch_started = time.perf_counter(); model.train(); total = 0.0; seen = 0
        for X_batch, y_batch in train_loader:
            optimizer.zero_grad(set_to_none=True); prediction = model(X_batch); loss = criterion(prediction, y_batch); loss.backward(); optimizer.step()
            total += float(loss.item()) * len(X_batch); seen += len(X_batch)
        train_loss = total / seen
        model.eval()
        with torch.no_grad():
            chunks = [model(validation_x[i:i + 1024]) for i in range(0, len(validation_x), 1024)]
            validation_loss = float(criterion(torch.cat(chunks), validation_y).item())
        elapsed = time.perf_counter() - epoch_started
        history["train_loss"].append(train_loss); history["validation_loss"].append(validation_loss); history["epoch_seconds"].append(elapsed)
        (ARTIFACT_DIR / f"{kind}_training_history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
        print(f"{kind.upper()} epoch {epoch:02d}: train={train_loss:.5f} validation={validation_loss:.5f} seconds={elapsed:.2f}", flush=True)
        state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        torch.save({"kind": kind, "state_dict": state, "input_size": len(SEQUENCE_FEATURES), "hidden_size": 32, "horizon": HORIZON, "target_count": len(TARGETS), "seed": SEED}, ARTIFACT_DIR / f"{kind}_last.pt")
        if validation_loss < best_loss - 1e-5:
            best_loss = validation_loss; best_state = state; stale = 0
            torch.save({"kind": kind, "state_dict": best_state, "input_size": len(SEQUENCE_FEATURES), "hidden_size": 32, "horizon": HORIZON, "target_count": len(TARGETS), "seed": SEED}, checkpoint)
        else:
            stale += 1
            if stale >= patience: print(f"{kind.upper()} early stopping at epoch {epoch}", flush=True); break
    if best_state is None: raise RuntimeError(f"{kind} did not produce a checkpoint")
    model.load_state_dict(best_state); model.eval(); duration = time.perf_counter() - started
    history.update({"best_validation_loss": best_loss, "epochs_trained": len(history["train_loss"]), "parameter_count": sum(p.numel() for p in model.parameters())})
    return model, history, duration


def predict_recurrent(model: RecurrentForecaster, data: WindowSet, target_scaler: StandardScaler) -> np.ndarray:
    model.eval(); predictions = []
    with torch.no_grad():
        X = torch.from_numpy(data.X)
        for start in range(0, len(X), 1024): predictions.append(model(X[start:start + 1024]).numpy())
    return inverse_targets(np.concatenate(predictions), target_scaler).astype(np.float32)


def inference_ms(function: Any) -> float:
    for _ in range(3): function()
    started = time.perf_counter()
    for _ in range(50): function()
    return (time.perf_counter() - started) * 1000 / 50


def group_and_condition_metrics(truth: np.ndarray, prediction: np.ndarray, windows: WindowSet, train_truth: np.ndarray) -> dict[str, Any]:
    group_rows = []
    for group in np.unique(windows.greenhouse_ids):
        mask = windows.greenhouse_ids == group
        for ti, target in enumerate(TARGETS): group_rows.append({"greenhouse_id": str(group), "target": target, "mae": float(np.mean(np.abs(truth[mask, :, ti] - prediction[mask, :, ti])))})
    hours = pd.to_datetime(windows.target_times.reshape(-1)).hour.to_numpy().reshape(windows.target_times.shape)
    day_mask = (hours >= 6) & (hours < 18)
    condition = {}
    for name, mask in {"day": day_mask, "night": ~day_mask}.items():
        condition[name] = {target: float(np.mean(np.abs(truth[:, :, ti][mask] - prediction[:, :, ti][mask]))) for ti, target in enumerate(TARGETS)}
    low = np.quantile(train_truth, 0.05, axis=(0, 1)); high = np.quantile(train_truth, 0.95, axis=(0, 1))
    extreme = ((truth < low) | (truth > high))
    condition["statistical_extreme"] = {target: float(np.mean(np.abs(truth[:, :, ti][extreme[:, :, ti]] - prediction[:, :, ti][extreme[:, :, ti]]))) for ti, target in enumerate(TARGETS)}
    condition["normal"] = {target: float(np.mean(np.abs(truth[:, :, ti][~extreme[:, :, ti]] - prediction[:, :, ti][~extreme[:, :, ti]]))) for ti, target in enumerate(TARGETS)}
    return {"greenhouse": group_rows, "conditions": condition, "extreme_definition": "outside training-set 5th/95th percentiles; statistical, not crop-risk thresholds"}


def save_plots(metrics_frame: pd.DataFrame, truth: np.ndarray, predictions: dict[str, np.ndarray], final_name: str, test: WindowSet, histories: dict[str, Any], feature_names: list[str], xgb_models: list[XGBRegressor], group_metrics: dict[str, Any]) -> list[str]:
    PLOT_DIR.mkdir(parents=True, exist_ok=True); sns.set_theme(style="whitegrid"); saved = []
    def finish(name: str) -> None:
        plt.tight_layout(); path = PLOT_DIR / name; plt.savefig(path, dpi=180, bbox_inches="tight"); plt.close(); saved.append(name)
    for kind in ["gru", "lstm"]:
        plt.figure(figsize=(8, 4.5)); h = histories[kind]; plt.plot(h["train_loss"], label="Train"); plt.plot(h["validation_loss"], label="Validation"); plt.xlabel("Epoch"); plt.ylabel("Huber loss (standardized)"); plt.title(f"{kind.upper()} training and validation loss"); plt.legend(); finish(f"01_{kind}_loss_curve.png")
    final = predictions[final_name]; n = min(240, len(truth))
    for ti, (target, unit) in enumerate(zip(TARGETS, TARGET_UNITS, strict=True)):
        plt.figure(figsize=(11, 4.8)); plt.plot(truth[:n, 0, ti], label="Observed", linewidth=1.2); plt.plot(final[:n, 0, ti], label=f"{final_name} h+1", linewidth=1.1); plt.xlabel("Ordered test sample"); plt.ylabel(f"{target} ({unit})"); plt.title(f"Observed versus forecast: {target}"); plt.legend(); finish(f"02_actual_vs_prediction_{target}.png")
    for horizon in [1, 3, 6]:
        errors = final[:, horizon - 1, :] - truth[:, horizon - 1, :]
        plt.figure(figsize=(9, 4.8)); sns.boxplot(pd.DataFrame(errors, columns=TARGETS), orient="h"); plt.xlabel("Forecast error (target native unit)"); plt.title(f"Forecast errors at h+{horizon}"); finish(f"03_error_h{horizon}.png")
    for metric in ["mae", "rmse", "r2"]:
        aggregate = metrics_frame.groupby("model", as_index=False)[metric].mean()
        plt.figure(figsize=(9, 4.8)); sns.barplot(data=aggregate, x="model", y=metric, hue="model", legend=False); plt.xticks(rotation=22); plt.ylabel(f"Mean {metric.upper()} (native units mixed)" if metric != "r2" else "Mean R²"); plt.title(f"Model {metric.upper()} comparison (descriptive aggregate)"); finish(f"04_model_{metric}_comparison.png")
    importance = np.mean(np.stack([model.feature_importances_ for model in xgb_models]), axis=0); top = np.argsort(importance)[-18:]
    plt.figure(figsize=(9, 6)); plt.barh(np.asarray(feature_names)[top], importance[top]); plt.xlabel("Mean gain-based importance"); plt.title("XGBoost feature importance"); finish("05_xgboost_feature_importance.png")
    plt.figure(figsize=(9, 4.8)); residual = (final - truth).reshape(-1, len(TARGETS)); sns.histplot(residual[:, 0], kde=True, label="temperature", stat="density"); sns.histplot(residual[:, 1], kde=True, label="humidity", stat="density", alpha=.45); plt.xlabel("Residual (native unit)"); plt.title("Residual distribution"); plt.legend(); finish("06_residual_distribution.png")
    group_frame = pd.DataFrame(group_metrics["greenhouse"])
    plt.figure(figsize=(10, 5)); sns.barplot(data=group_frame, x="greenhouse_id", y="mae", hue="target"); plt.ylabel("MAE (native unit)"); plt.title("Forecast MAE by greenhouse compartment"); plt.xticks(rotation=20); finish("07_greenhouse_performance.png")
    high_index = int(np.argmax(truth[:, 0, 0])); start = max(0, high_index - 36); end = min(len(truth), high_index + 36)
    plt.figure(figsize=(11, 4.8)); plt.plot(truth[start:end, 0, 0], label="Observed temperature"); plt.plot(final[start:end, 0, 0], label="Forecast h+1"); plt.xlabel("Ordered test sample around high-temperature observation"); plt.ylabel("Temperature (°C)"); plt.title("High-temperature case (not a crop-risk classification)"); plt.legend(); finish("08_typical_risk_period_case.png")
    return saved


def auxiliary_models() -> dict[str, Any]:
    output: dict[str, Any] = {}
    gets_path = PROJECT_ROOT / "datasets" / "public_greenhouse" / "03_gets_greenhouse_co2" / "raw" / "GreenhouseEnvironmentTimeSeries.txt"
    if not gets_path.is_file():
        return {
            "status": "not_trained",
            "reason": "Optional auxiliary public datasets are not included in this release package.",
        }
    gets = pd.read_csv(gets_path); gets["timestamp"] = pd.to_datetime(gets["date"], utc=True); gets["co2_ppm"] = pd.to_numeric(gets["co2_ppm"], errors="coerce")
    series = gets.set_index("timestamp")["co2_ppm"].resample("1h").mean().dropna().to_numpy(); X=[]; y=[]
    for i in range(24, len(series)-3): X.append(series[i-24:i]); y.append(series[i:i+3])
    X=np.asarray(X); y=np.asarray(y); a=int(.7*len(X)); b=int(.85*len(X)); models={}; pred={"persistence":np.repeat(X[b:,-1:],3,axis=1)}
    for name, model in {"ridge":Ridge(alpha=1.0), "xgboost":XGBRegressor(n_estimators=120,max_depth=4,learning_rate=.05,n_jobs=THREADS,random_state=SEED,tree_method="hist")}.items(): model.fit(X[:a],y[:a]); models[name]=model; pred[name]=model.predict(X[b:])
    output["gets_co2"]={name:[{"horizon":h+1,"mae":float(mean_absolute_error(y[b:,h],values[:,h])),"rmse":float(mean_squared_error(y[b:,h],values[:,h])**.5),"r2":float(r2_score(y[b:,h],values[:,h]))} for h in range(3)] for name,values in pred.items()}
    irr_path=PROJECT_ROOT/"datasets/public_greenhouse/04_agricultural_irrigation/extracted/Agricultural Irrigation Control Data/DailyAverageSensedData1.xlsx"; daily=pd.read_excel(irr_path); numeric=daily.select_dtypes(include="number")
    correlation = numeric.corr().abs().where(lambda x:np.triu(np.ones(x.shape),1).astype(bool)).stack().sort_values(ascending=False).head(10)
    output["agricultural_irrigation"]={"model_status":"not_trained","reason":"Raw long table has no timestamp; units are undefined; 53-row daily summary retained for correlation only.","daily_rows":len(daily),"strongest_absolute_correlations":[{"field_a":str(pair[0]),"field_b":str(pair[1]),"absolute_correlation":float(value)} for pair,value in correlation.items()]}
    lstm_path=PROJECT_ROOT/"datasets/public_greenhouse/05_lstm_predictive_irrigation/raw/Edge_IoT_Predictive_Irrigation_Dataset.xlsx"; irrigation=pd.read_excel(lstm_path); irrigation["Timestamp"]=pd.to_datetime(irrigation["Timestamp"]); soil=irrigation.set_index("Timestamp")["Soil_Moisture_pct"].resample("1h").mean().dropna().to_numpy(); X=[];y=[]
    for i in range(24,len(soil)-3):X.append(soil[i-24:i]);y.append(soil[i:i+3])
    X=np.asarray(X);y=np.asarray(y);a=int(.7*len(X));b=int(.85*len(X)); preds={"persistence":np.repeat(X[b:,-1:],3,axis=1)}
    for name,model in {"ridge":Ridge(alpha=1),"xgboost":XGBRegressor(n_estimators=100,max_depth=3,learning_rate=.05,n_jobs=THREADS,random_state=SEED,tree_method="hist")}.items():model.fit(X[:a],y[:a]);preds[name]=model.predict(X[b:])
    output["lstm_irrigation"]={"warning":"Pump_Status is historical operation and does not represent an optimal tomato or melon irrigation strategy.","soil_moisture_forecast":{name:[{"horizon":h+1,"mae":float(mean_absolute_error(y[b:,h],values[:,h])),"rmse":float(mean_squared_error(y[b:,h],values[:,h])**.5),"r2":float(r2_score(y[b:,h],values[:,h]))}for h in range(3)]for name,values in preds.items()}}
    return output


def write_checksums() -> None:
    files=[]
    for path in sorted(ARTIFACT_DIR.rglob("*")):
        if path.is_file() and path.name!="checksums.sha256": files.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(ARTIFACT_DIR).as_posix()}")
    (ARTIFACT_DIR/"checksums.sha256").write_text("\n".join(files)+"\n",encoding="utf-8")


def main() -> None:
    seed_everything(); ARTIFACT_DIR.mkdir(parents=True,exist_ok=True); PLOT_DIR.mkdir(parents=True,exist_ok=True)
    print("Stage 3-4: processing and leakage-safe windows",flush=True)
    hourly,processing_stats,external_hourly,training_input_mode=load_core_training_data(); splits=split_group_time(hourly)
    windows={name:make_windows(frame,INPUT_HOURS,HORIZON) for name,frame in splits.items()}
    for value in windows.values():assert_no_leakage(value)
    print("Window counts:", {k:len(v.X) for k,v in windows.items()},flush=True)
    scaled,scalers=scale_windows(windows["train"],windows["validation"],windows["test"]);joblib.dump(scalers,ARTIFACT_DIR/"scaler.joblib")
    np.savez_compressed(PROCESSED_DIR/"agc2_windows_split_summary.npz",train_input_end=windows["train"].input_end_times,validation_input_end=windows["validation"].input_end_times,test_input_end=windows["test"].input_end_times)
    print("Stage 5: baselines and XGBoost",flush=True)
    persistence_pred=persistence(windows["test"].target_history,HORIZON); predictions={"persistence":persistence_pred,"seasonal_24":seasonal_24(windows["test"].target_history,HORIZON),"moving_average_6":moving_average(windows["test"].target_history,HORIZON,6)}
    xgb_models,feature_names,xgb_search,xgb_time=train_xgboost(windows["train"],windows["validation"]);predictions["xgboost"]=predict_xgboost(xgb_models,windows["test"])
    print("Stage 6-7: GRU and LSTM",flush=True)
    gru,gru_history,gru_time=train_recurrent("gru",scaled,scalers["target"]);predictions["gru"]=predict_recurrent(gru,scaled["test"],scalers["target"])
    lstm,lstm_history,lstm_time=train_recurrent("lstm",scaled,scalers["target"]);predictions["lstm"]=predict_recurrent(lstm,scaled["test"],scalers["target"])
    rows=[]
    for name,prediction in predictions.items():rows.extend(metric_rows(name,windows["test"].y,prediction,persistence_pred if name!="persistence" else None))
    metrics_frame=pd.DataFrame(rows);formal=metrics_frame[metrics_frame.model.isin(["xgboost","gru","lstm"])].groupby("model")["relative_persistence_improvement_pct"].agg(["mean",lambda s:int((s>0).sum())]).rename(columns={"<lambda_0>":"wins"})
    final_name=str(formal.sort_values(["wins","mean"],ascending=False).index[0]); final_row=formal.loc[final_name]
    baseline_improvement = metrics_frame[metrics_frame.model.isin(["seasonal_24", "moving_average_6"])].groupby("model")["relative_persistence_improvement_pct"].mean()
    strongest_baseline_improvement = float(baseline_improvement.max())
    model_status="ready" if int(final_row["wins"])>=10 and float(final_row["mean"])>strongest_baseline_improvement else "under_evaluation"
    final_prediction=predictions[final_name]
    validation_predictions={"xgboost":predict_xgboost(xgb_models,windows["validation"]),"gru":predict_recurrent(gru,scaled["validation"],scalers["target"]),"lstm":predict_recurrent(lstm,scaled["validation"],scalers["target"])}
    validation_residual=windows["validation"].y-validation_predictions[final_name];quantiles={target:{f"h{h+1}":{"lower":float(np.quantile(validation_residual[:,h,ti],.05)),"upper":float(np.quantile(validation_residual[:,h,ti],.95))}for h in range(HORIZON)}for ti,target in enumerate(TARGETS)}
    group_metrics=group_and_condition_metrics(windows["test"].y,final_prediction,windows["test"],windows["train"].y)
    timing={"xgboost":inference_ms(lambda:predict_xgboost(xgb_models,WindowSet(windows['test'].X[:1],windows['test'].y[:1],windows['test'].target_history[:1],windows['test'].greenhouse_ids[:1],windows['test'].input_end_times[:1],windows['test'].target_times[:1]))),"gru":inference_ms(lambda:predict_recurrent(gru,WindowSet(scaled['test'].X[:1],scaled['test'].y[:1],scaled['test'].target_history[:1],scaled['test'].greenhouse_ids[:1],scaled['test'].input_end_times[:1],scaled['test'].target_times[:1]),scalers['target'])),"lstm":inference_ms(lambda:predict_recurrent(lstm,WindowSet(scaled['test'].X[:1],scaled['test'].y[:1],scaled['test'].target_history[:1],scaled['test'].greenhouse_ids[:1],scaled['test'].input_end_times[:1],scaled['test'].target_times[:1]),scalers['target']))}
    external=make_windows(external_hourly,INPUT_HOURS,HORIZON);assert_no_leakage(external)
    if final_name=="xgboost":external_prediction=predict_xgboost(xgb_models,external)
    else:
        ex_scaled=WindowSet(scalers["feature"].transform(external.X.reshape(-1,external.X.shape[-1])).reshape(external.X.shape).astype(np.float32),external.y,external.target_history,external.greenhouse_ids,external.input_end_times,external.target_times)
        external_prediction=predict_recurrent(gru if final_name=="gru" else lstm,ex_scaled,scalers["target"])
    external_metrics=metric_rows(f"{final_name}_external_agc4",external.y,external_prediction,persistence(external.target_history,HORIZON))
    bundle={"model_name":"environment-forecast-v0.1","model_version":"v0.1","model_type":final_name,"status":model_status,"input_window_hours":INPUT_HOURS,"forecast_horizon_hours":HORIZON,"features":SEQUENCE_FEATURES,"xgboost_feature_names":feature_names,"targets":TARGETS,"target_units":dict(zip(TARGETS,TARGET_UNITS,strict=True)),"prediction_interval_residual_quantiles":quantiles,"training_domain":"public_real_greenhouse_tomato"}
    if final_name=="xgboost":bundle["models"]=xgb_models;joblib.dump(bundle,ARTIFACT_DIR/"final_model.joblib")
    else:
        selected=gru if final_name=="gru" else lstm;torch.save({**bundle,"state_dict":selected.state_dict(),"input_size":len(SEQUENCE_FEATURES),"hidden_size":32,"target_count":len(TARGETS)},ARTIFACT_DIR/"final_model.pt")
    feature_schema={"input_window_hours":24,"sampling_interval":"1 hour","required_database_fields":["temperature","air_humidity"],"training_features":SEQUENCE_FEATURES,"targets":[{"name":n,"unit":u}for n,u in zip(TARGETS,TARGET_UNITS,strict=True)],"light_history_policy":"Database light is klx and is intentionally not used as AGC PAR input; no guessed conversion.","missing_policy":"No imputation at inference; require 24 contiguous complete hourly temperature/humidity points."}
    (ARTIFACT_DIR/"feature_schema.json").write_text(json.dumps(feature_schema,ensure_ascii=False,indent=2),encoding="utf-8")
    shutil.copy2(PROJECT_ROOT/"backend/app/ml/configs/dataset_registry.json",ARTIFACT_DIR/"dataset_registry_snapshot.json")
    config={"seed":SEED,"threads":THREADS,"device":"cpu","training_input_mode":training_input_mode,"input_hours":INPUT_HOURS,"horizon_hours":HORIZON,"split":[.7,.15,.15],"gru":{"hidden_size":32,"dropout":.15,"batch_size":64,"max_epochs":30,"patience":6},"lstm":{"hidden_size":32,"dropout":.15,"batch_size":64,"max_epochs":30,"patience":6},"xgboost":xgb_search}
    (ARTIFACT_DIR/"training_config.json").write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding="utf-8")
    auxiliary=auxiliary_models()
    metrics={"core":rows,"aggregate_formal_models":formal.reset_index().to_dict(orient="records"),"external_agc4":external_metrics,"group_and_condition":group_metrics,"auxiliary":auxiliary}
    (ARTIFACT_DIR/"metrics.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf-8");metrics_frame.to_csv(ARTIFACT_DIR/"model_comparison.csv",index=False)
    metadata={"model_name":"environment-forecast-v0.1","model_version":"v0.1","model_type":final_name,"model_status":model_status,"training_input_mode":training_input_mode,"training_device":"cpu","torch_version":torch.__version__,"xpu_available":bool(hasattr(torch,"xpu") and torch.xpu.is_available()),"cpu_threads_used":THREADS,"random_seed":SEED,"dataset_name":"Autonomous Greenhouse Challenge, Second Edition (2019)","dataset_version":"2","dataset_doi":"10.4121/uuid:88d22c60-21b3-4ea8-90db-20249a5be2a7","dataset_license":"CC0 1.0","crop":"cherry_tomato","training_domain":"public_real_greenhouse_tomato","input_window_hours":24,"forecast_horizon_hours":6,"sampling_interval":"1 hour","features":SEQUENCE_FEATURES,"targets":TARGETS,"train_time_range":[str(splits['train'].timestamp.min()),str(splits['train'].timestamp.max())],"validation_time_range":[str(splits['validation'].timestamp.min()),str(splits['validation'].timestamp.max())],"test_time_range":[str(splits['test'].timestamp.min()),str(splits['test'].timestamp.max())],"train_sample_count":len(windows['train'].X),"validation_sample_count":len(windows['validation'].X),"test_sample_count":len(windows['test'].X),"preprocessing_version":"environment-v0.1","created_at":datetime.now(UTC).isoformat(),"training_seconds":{"xgboost":xgb_time,"gru":gru_time,"lstm":lstm_time},"parameter_count":{"gru":gru_history['parameter_count'],"lstm":lstm_history['parameter_count']},"inference_ms":timing,"limitations":["Public greenhouse tomato dataset; performance should be evaluated against the target input distribution","No direct hardware control","Light forecast unit is PAR; platform sensor history is klx and is not converted","Risk rules for tomato are unavailable"]}
    (ARTIFACT_DIR/"training_metadata.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")
    plots=save_plots(metrics_frame,windows["test"].y,predictions,final_name,windows["test"],{"gru":gru_history,"lstm":lstm_history},feature_names,xgb_models,group_metrics)
    model_card=f"""# Environment Forecast V0.1 Model Card\n\n## Purpose\nForecast greenhouse air temperature, relative humidity and PAR for hours 1–6 from the previous 24 hourly observations. Status: **{model_status}**; selected model: **{final_name}**.\n\n## Data and licence\nTrained on Autonomous Greenhouse Challenge, Second Edition (2019), cherry tomato, Netherlands, DOI `10.4121/uuid:88d22c60-21b3-4ea8-90db-20249a5be2a7`, CC0 1.0. The fourth challenge dwarf-tomato data is reported separately as external validation.\n\n## Inputs and outputs\nInputs are hourly temperature, relative humidity and cyclical time features over 24 hours. Outputs are temperature (°C), humidity (%) and PAR (µmol/m²/s) at six horizons. Validation residual 5th/95th percentiles form empirical prediction intervals. All preprocessing statistics are fitted on training data only.\n\n## Evaluation\nTime split is 70%/15%/15% within each compartment. Full per-target/per-horizon metrics are in `metrics.json` and `model_comparison.csv`; no test data were used for parameter search. Selected formal model wins {int(final_row['wins'])}/18 target-horizon comparisons against persistence with mean relative MAE improvement {float(final_row['mean']):.2f}%.\n\n## Limitations and prohibited uses\nThis is public real tomato-greenhouse validation, not Shenxian melon field validation. It is not suitable for direct device control, safety-critical automation, non-hourly inputs, missing 24-hour histories, or interpreting PAR as klx. It cannot replace an agronomist. Tomato risk rules are unavailable, so the API returns `rules_unavailable`. Cross-crop use requires local calibration; Shenxian melon calibration still needs representative local sensor data, units, management actions and outcomes. Model version: v0.1.\n"""
    (ARTIFACT_DIR/"model_card.md").write_text(model_card,encoding="utf-8")
    summary={"status":model_status,"final_model":final_name,"plots":plots,"processing":processing_stats,"training_metadata":metadata}
    (ARTIFACT_DIR/"run_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");write_checksums()
    print(json.dumps({"model_status":model_status,"final_model":final_name,"wins_vs_persistence":int(final_row['wins']),"mean_improvement_pct":float(final_row['mean']),"test_samples":len(windows['test'].X),"external_samples":len(external.X)},ensure_ascii=False,indent=2),flush=True)


if __name__=="__main__":main()
