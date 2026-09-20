from __future__ import annotations

import numpy as np
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score


def metric_rows(method:str,fold:str,truth:np.ndarray,prediction:np.ndarray,seasonal:np.ndarray,target_names:list[str],train_ranges:np.ndarray)->list[dict[str,float|int|str]]:
    rows=[]
    for target_index,target in enumerate(target_names):
        scale=max(float(train_ranges[target_index]),1e-8)
        for h in range(truth.shape[1]):
            actual=truth[:,h,target_index];pred=prediction[:,h,target_index];base=seasonal[:,h,target_index]
            mae=float(mean_absolute_error(actual,pred));baseline_mae=float(mean_absolute_error(actual,base));rmse=float(mean_squared_error(actual,pred)**.5)
            rows.append({"method":method,"fold":fold,"target":target,"horizon":h+1,"mae":mae,"rmse":rmse,"r2":float(r2_score(actual,pred)),"nmae":mae/scale,"relative_seasonal_improvement_pct":((baseline_mae-mae)/baseline_mae*100) if baseline_mae>0 else 0.0})
    return rows


def interval_statistics(truth:np.ndarray,prediction:np.ndarray,lower:np.ndarray,upper:np.ndarray,target_names:list[str],target_times:np.ndarray)->list[dict[str,float|int|str]]:
    rows=[];hours=target_times.astype("datetime64[h]").astype(object)
    for ti,target in enumerate(target_names):
        for h in range(truth.shape[1]):
            covered=(truth[:,h,ti]>=lower[:,h,ti])&(truth[:,h,ti]<=upper[:,h,ti]);width=upper[:,h,ti]-lower[:,h,ti]
            rows.append({"target":target,"horizon":h+1,"period":"all","coverage":float(covered.mean()),"mean_width":float(width.mean())})
            hour_values=np.array([value.hour for value in hours[:,h]])
            for name,mask in {"day":(hour_values>=6)&(hour_values<18),"night":~((hour_values>=6)&(hour_values<18))}.items():
                rows.append({"target":target,"horizon":h+1,"period":name,"coverage":float(covered[mask].mean()),"mean_width":float(width[mask].mean())})
    return rows
