from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from app.ml.data.audit import PROJECT_ROOT
from app.ml.v02.data import DEPLOY_FEATURES,DEPLOY_TARGETS,ForecastWindows,add_cycles
from app.ml.v02.training import apply_ensemble,load_residual_rnn,predict_residual_rnn,predict_residual_xgb


ARTIFACT_DIR=PROJECT_ROOT/"backend/app/ml/artifacts/environment_forecast_v0.2"


class PredictionInputError(ValueError):
    def __init__(self,status:str,message:str)->None:super().__init__(message);self.status=status


METHOD_LABELS={"seasonal_24":"前一天同小时统计基线","seasonal_residual_xgboost":"历史同期＋XGBoost残差修正","seasonal_residual_gru":"历史同期＋GRU残差修正","seasonal_residual_lstm":"历史同期＋LSTM残差修正","validation_weighted_ensemble":"滚动验证加权混合"}


def shanghai_naive_to_utc(value: Any) -> pd.Timestamp:
    """Convert the local feature-clock timestamp to an unambiguous API timestamp."""
    return pd.Timestamp(value).tz_localize("Asia/Shanghai").tz_convert("UTC")


class EnvironmentPredictorV02:
    def __init__(self,artifact_dir:Path=ARTIFACT_DIR)->None:
        self.artifact_dir=artifact_dir;self.status="not_trained";self.metadata:dict[str,Any]={};self.registry:dict[str,Any]={};self.xgb_models=[];self.rnns={};self._load()

    def _load(self)->None:
        registry_path=self.artifact_dir/"champion_registry.json";metadata_path=self.artifact_dir/"training_metadata.json"
        if not registry_path.exists() or not metadata_path.exists():return
        self.registry=json.loads(registry_path.read_text(encoding="utf-8"));self.metadata=json.loads(metadata_path.read_text(encoding="utf-8"));self.status=str(self.registry.get("forecast_service_status","not_trained"))
        model_path=self.artifact_dir/"deployment_compatible"/"residual_xgboost_final.joblib"
        if not model_path.exists():self.status="schema_mismatch";return
        self.xgb_models=joblib.load(model_path)["models"]
        for kind in ["gru","lstm"]:
            self.rnns[kind]=load_residual_rnn(self.artifact_dir/"deployment_compatible"/f"residual_{kind}_final.pt")

    def prepare_history(self,records:list[dict[str,Any]])->tuple[pd.DataFrame,str]:
        if not records:raise PredictionInputError("insufficient_data","没有环境历史数据")
        frame=pd.DataFrame(records);required={"recorded_at","temperature","air_humidity","source"}
        if not required.issubset(frame.columns):raise PredictionInputError("schema_mismatch",f"输入缺少字段：{sorted(required-set(frame.columns))}")
        frame["timestamp"]=pd.to_datetime(frame["recorded_at"],errors="coerce",utc=True).dt.tz_convert("Asia/Shanghai").dt.tz_localize(None);frame["air_temperature_c"]=pd.to_numeric(frame["temperature"],errors="coerce");frame["air_humidity_pct"]=pd.to_numeric(frame["air_humidity"],errors="coerce")
        frame=frame.dropna(subset=["timestamp"]).sort_values("timestamp").drop_duplicates("timestamp",keep="last");source=str(frame.source.iloc[-1]) if frame.source.nunique()==1 else "mixed"
        hourly=frame.set_index("timestamp")[["air_temperature_c","air_humidity_pct"]].resample("1h").mean().reset_index()
        if len(hourly)<24:raise PredictionInputError("insufficient_data",f"仅有{len(hourly)}个小时点，需要连续24个")
        hourly=hourly.tail(24).reset_index(drop=True)
        if hourly[["air_temperature_c","air_humidity_pct"]].isna().any().any():raise PredictionInputError("insufficient_data","最近24小时存在缺测或不连续小时")
        if not (hourly.timestamp.diff().dropna()==pd.Timedelta(hours=1)).all():raise PredictionInputError("insufficient_data","最近24小时不是连续小时序列")
        return add_cycles(hourly),source

    def _inference_window(self,history:pd.DataFrame)->ForecastWindows:
        end=history.timestamp.iloc[-1];future_times=pd.date_range(end+pd.Timedelta(hours=1),periods=6,freq="1h");hour=future_times.hour.to_numpy();day=future_times.dayofyear.to_numpy();cycles=np.column_stack([np.sin(2*np.pi*hour/24),np.cos(2*np.pi*hour/24),np.sin(2*np.pi*day/365.25),np.cos(2*np.pi*day/365.25)]).astype(np.float32)
        seasonal=history[DEPLOY_TARGETS].iloc[:6].to_numpy(np.float32)[None,:,:];dummy=np.zeros_like(seasonal)
        return ForecastWindows(history[DEPLOY_FEATURES].to_numpy(np.float32)[None,:,:],dummy,seasonal,np.array(["inference"]),np.array([end.to_datetime64()]),future_times.to_numpy(dtype="datetime64[ns]")[None,:],cycles[None,:,:],DEPLOY_FEATURES,DEPLOY_TARGETS)

    def _candidates(self,windows:ForecastWindows)->dict[str,np.ndarray]:
        result={"seasonal_24":windows.seasonal,"seasonal_residual_xgboost":predict_residual_xgb(self.xgb_models,windows)}
        for kind,(model,scalers) in self.rnns.items():result[f"seasonal_residual_{kind}"]=predict_residual_rnn(model,scalers,windows)
        ensemble=self.registry["ensembles"]["deployment_compatible"];weights=np.asarray(ensemble["weights"],np.float32);ml=np.empty_like(windows.y)
        for h in range(6):
            for ti,target in enumerate(DEPLOY_TARGETS):ml[:,h,ti]=result[ensemble["base_ml_methods"][target][f"h{h+1}"]][:,h,ti]
        result["validation_weighted_ensemble"]=apply_ensemble(windows.seasonal,ml,weights);return result

    def predict(self,records:list[dict[str,Any]],horizon_hours:int)->dict[str,Any]:
        if self.status!="ready":raise PredictionInputError(self.status,"V0.2预测注册表不可用")
        history,source=self.prepare_history(records);windows=self._inference_window(history);candidates=self._candidates(windows);quantiles=self.registry["prediction_interval_residual_quantiles"];points=[]
        for h in range(horizon_hours):
            values={};methods={};lower={};upper={}
            for ti,target in enumerate(DEPLOY_TARGETS):
                method=self.registry["targets"][target][f"h{h+1}"]["method"];value=float(candidates[method][0,h,ti]);values[target]=value;methods[target]=method;q=quantiles[target][f"h{h+1}"];lower[target]=value+float(q["lower_residual"]);upper[target]=value+float(q["upper_residual"])
            method_text="; ".join(f"{target}={methods[target]}" for target in DEPLOY_TARGETS)
            points.append({"forecast_time":shanghai_naive_to_utc(windows.target_times[0,h]),"horizon":h+1,"temperature_c":values["air_temperature_c"],"air_humidity_pct":values["air_humidity_pct"],"par_umol_m2_s":None,"lower_bounds":lower,"upper_bounds":upper,"forecast_method":method_text,"method_version":"v0.2","methods":methods,"units":{"temperature_c":"degree_Celsius","air_humidity_pct":"percent","par_umol_m2_s":"micromole_per_m2_second"}})
        used=sorted({method for point in points for method in point["methods"].values()});return {"history":history,"source":source,"input_end_time":shanghai_naive_to_utc(history.timestamp.iloc[-1]),"predictions":points,"forecast_method":" + ".join(used),"forecast_method_labels":[METHOD_LABELS[method] for method in used]}


@lru_cache(maxsize=1)
def get_environment_predictor_v02()->EnvironmentPredictorV02:return EnvironmentPredictorV02()
