from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.ml.v02.data import ForecastWindows


@dataclass(frozen=True)
class RollingFold:
    fold: int
    train_mask: np.ndarray
    validation_mask: np.ndarray
    train_end: np.datetime64
    validation_end: np.datetime64


def expanding_rolling_folds(windows: ForecastWindows) -> list[RollingFold]:
    times=np.unique(windows.input_end_times); proportions=[(.45,.60),(.60,.75),(.75,.90)]; folds=[]
    for index,(train_fraction,val_fraction) in enumerate(proportions,1):
        train_end=times[min(len(times)-1,int(len(times)*train_fraction)-1)]; val_end=times[min(len(times)-1,int(len(times)*val_fraction)-1)]
        train=(windows.target_times[:,-1]<=train_end); validation=(windows.input_end_times>train_end)&(windows.target_times[:,-1]<=val_end)
        if not train.any() or not validation.any(): raise ValueError(f"empty rolling fold {index}")
        if windows.target_times[train,-1].max()>=windows.input_end_times[validation].min(): raise AssertionError("rolling fold leakage")
        folds.append(RollingFold(index,train,validation,train_end,val_end))
    return folds


def leave_one_greenhouse_out(windows: ForecastWindows) -> list[tuple[str,np.ndarray,np.ndarray]]:
    result=[]
    for greenhouse in np.unique(windows.greenhouse_ids):
        validation=windows.greenhouse_ids==greenhouse; train=~validation
        if set(windows.greenhouse_ids[train])&set(windows.greenhouse_ids[validation]): raise AssertionError("greenhouse overlap")
        result.append((str(greenhouse),train,validation))
    return result


def assert_windows_no_leakage(windows: ForecastWindows) -> None:
    if len(windows.X)==0: raise ValueError("no windows")
    if not np.all(windows.target_times[:,0]>windows.input_end_times): raise AssertionError("future label in input")
    expected=windows.input_end_times[:,None]+np.arange(1,7).astype("timedelta64[h]")
    if not np.array_equal(windows.target_times.astype("datetime64[h]"),expected.astype("datetime64[h]")): raise AssertionError("incorrect future label order")
    if not np.array_equal(windows.seasonal[:,0],windows.X[:,0,:len(windows.target_names)]) and windows.feature_names[:len(windows.target_names)]==windows.target_names:
        raise AssertionError("seasonal h1 index is not t-23")
