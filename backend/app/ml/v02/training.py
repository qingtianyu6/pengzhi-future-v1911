from __future__ import annotations

import copy
import json
import random
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import torch
from sklearn.preprocessing import StandardScaler
from torch import nn
from torch.utils.data import DataLoader, TensorDataset
from xgboost import XGBRegressor

from app.ml.v02.data import ForecastWindows, xgb_matrix
from app.ml.v02.models import SeasonalResidualRNN


SEED=20260822


def seed_all()->None:
    random.seed(SEED);np.random.seed(SEED);torch.manual_seed(SEED);torch.set_num_threads(4)
    try:torch.set_num_interop_threads(1)
    except RuntimeError:pass


def train_residual_xgb(train:ForecastWindows,output_dir:Path|None=None,prefix:str="model")->tuple[list[XGBRegressor],list[str],float]:
    X,names=xgb_matrix(train); residual=(train.y-train.seasonal).reshape(len(train.y),-1);models=[];started=time.perf_counter()
    if output_dir:output_dir.mkdir(parents=True,exist_ok=True)
    for index in range(residual.shape[1]):
        model=XGBRegressor(n_estimators=140,max_depth=5,learning_rate=.045,min_child_weight=4,subsample=.85,colsample_bytree=.8,reg_lambda=1.2,objective="reg:squarederror",tree_method="hist",random_state=SEED,n_jobs=4)
        model.fit(X,residual[:,index],verbose=False);models.append(model)
        if output_dir:model.save_model(output_dir/f"{prefix}_{index:02d}.json")
    return models,names,time.perf_counter()-started


def predict_residual_xgb(models:list[XGBRegressor],windows:ForecastWindows,clip_nonnegative:bool=False)->np.ndarray:
    X,_=xgb_matrix(windows);residual=np.column_stack([model.predict(X) for model in models]).reshape(windows.y.shape);prediction=windows.seasonal+residual
    return np.maximum(prediction,0) if clip_nonnegative else prediction


def _scale_base(base:np.ndarray,scaler:StandardScaler)->np.ndarray:
    return scaler.transform(base.reshape(-1,base.shape[-1])).reshape(base.shape).astype(np.float32)


def train_residual_rnn(kind:str,train:ForecastWindows,validation:ForecastWindows,output_path:Path,max_epochs:int=18,patience:int=4)->tuple[SeasonalResidualRNN,dict[str,StandardScaler],dict[str,Any],float]:
    feature_scaler=StandardScaler().fit(train.X.reshape(-1,train.X.shape[-1]));target_scaler=StandardScaler().fit(train.y.reshape(-1,train.y.shape[-1]))
    X_train=feature_scaler.transform(train.X.reshape(-1,train.X.shape[-1])).reshape(train.X.shape).astype(np.float32);y_train=target_scaler.transform(train.y.reshape(-1,train.y.shape[-1])).reshape(train.y.shape).astype(np.float32);base_train=_scale_base(train.seasonal,target_scaler)
    X_val=feature_scaler.transform(validation.X.reshape(-1,validation.X.shape[-1])).reshape(validation.X.shape).astype(np.float32);y_val=target_scaler.transform(validation.y.reshape(-1,validation.y.shape[-1])).reshape(validation.y.shape).astype(np.float32);base_val=_scale_base(validation.seasonal,target_scaler)
    model=SeasonalResidualRNN(train.X.shape[-1],32,train.y.shape[1],train.y.shape[2],kind=kind,dropout=.15);optimizer=torch.optim.Adam(model.parameters(),lr=8e-4);criterion=nn.HuberLoss(delta=1.0)
    loader=DataLoader(TensorDataset(torch.from_numpy(X_train),torch.from_numpy(base_train),torch.from_numpy(y_train)),batch_size=128,shuffle=True,generator=torch.Generator().manual_seed(SEED),num_workers=0)
    best=float("inf");best_state=None;stale=0;history={"train_loss":[],"validation_loss":[],"epoch_seconds":[]};started=time.perf_counter();output_path.parent.mkdir(parents=True,exist_ok=True)
    for epoch in range(1,max_epochs+1):
        began=time.perf_counter();model.train();total=0.0;seen=0
        for X_batch,base_batch,y_batch in loader:
            optimizer.zero_grad(set_to_none=True);prediction=model(X_batch,base_batch);loss=criterion(prediction,y_batch);loss.backward();optimizer.step();total+=float(loss.item())*len(X_batch);seen+=len(X_batch)
        model.eval()
        with torch.no_grad():
            pieces=[model(torch.from_numpy(X_val[i:i+1024]),torch.from_numpy(base_val[i:i+1024])) for i in range(0,len(X_val),1024)];val_loss=float(criterion(torch.cat(pieces),torch.from_numpy(y_val)).item())
        train_loss=total/seen;history["train_loss"].append(train_loss);history["validation_loss"].append(val_loss);history["epoch_seconds"].append(time.perf_counter()-began)
        print(f"{output_path.stem} epoch={epoch:02d} train={train_loss:.5f} val={val_loss:.5f}",flush=True)
        if val_loss<best-1e-5:best=val_loss;best_state=copy.deepcopy(model.state_dict());stale=0
        else:
            stale+=1
            if stale>=patience:break
    if best_state is None:raise RuntimeError("no recurrent checkpoint")
    model.load_state_dict(best_state);model.eval();scalers={"feature":feature_scaler,"target":target_scaler};payload={"kind":kind,"state_dict":best_state,"input_size":train.X.shape[-1],"hidden_size":32,"horizon":train.y.shape[1],"target_count":train.y.shape[2],"features":train.feature_names,"targets":train.target_names,"explicit_skip_connection":True,"seed":SEED};torch.save(payload,output_path);joblib.dump(scalers,output_path.with_suffix(".scalers.joblib"));history.update({"best_validation_loss":best,"epochs":len(history["train_loss"]),"parameter_count":sum(p.numel() for p in model.parameters())});output_path.with_suffix(".history.json").write_text(json.dumps(history,indent=2),encoding="utf-8")
    return model,scalers,history,time.perf_counter()-started


def predict_residual_rnn(model:SeasonalResidualRNN,scalers:dict[str,StandardScaler],windows:ForecastWindows,clip_nonnegative:bool=False)->np.ndarray:
    X=scalers["feature"].transform(windows.X.reshape(-1,windows.X.shape[-1])).reshape(windows.X.shape).astype(np.float32);base=_scale_base(windows.seasonal,scalers["target"]);pieces=[];model.eval()
    with torch.no_grad():
        for index in range(0,len(X),1024):pieces.append(model(torch.from_numpy(X[index:index+1024]),torch.from_numpy(base[index:index+1024])).numpy())
    scaled=np.concatenate(pieces);prediction=scalers["target"].inverse_transform(scaled.reshape(-1,scaled.shape[-1])).reshape(scaled.shape)
    return np.maximum(prediction,0) if clip_nonnegative else prediction


def load_residual_rnn(path:Path)->tuple[SeasonalResidualRNN,dict[str,StandardScaler]]:
    payload=torch.load(path,map_location="cpu",weights_only=False);model=SeasonalResidualRNN(payload["input_size"],payload["hidden_size"],payload["horizon"],payload["target_count"],kind=payload["kind"],dropout=0);model.load_state_dict(payload["state_dict"]);model.eval();return model,joblib.load(path.with_suffix(".scalers.joblib"))


def fit_ensemble_weights(truth:np.ndarray,seasonal:np.ndarray,ml_prediction:np.ndarray)->np.ndarray:
    weights=np.zeros((truth.shape[1],truth.shape[2]),dtype=np.float32)
    for h in range(truth.shape[1]):
        for target in range(truth.shape[2]):
            candidates=np.linspace(0,1,21);errors=[np.mean(np.abs(truth[:,h,target]-(weight*ml_prediction[:,h,target]+(1-weight)*seasonal[:,h,target]))) for weight in candidates];weights[h,target]=float(candidates[int(np.argmin(errors))])
    return weights


def apply_ensemble(seasonal:np.ndarray,ml_prediction:np.ndarray,weights:np.ndarray)->np.ndarray:
    return seasonal*(1-weights[None,:,:])+ml_prediction*weights[None,:,:]
