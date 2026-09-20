from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from datetime import UTC,datetime
from pathlib import Path
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS","4");os.environ.setdefault("MKL_NUM_THREADS","4");os.environ.setdefault("MPLCONFIGDIR",str(Path(__file__).resolve().parents[3]/".mplconfig"))
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import torch
from sklearn.metrics import mean_absolute_error

from app.ml.data.audit import PROJECT_ROOT
from app.ml.v02.data import DEPLOY_FEATURES,DEPLOY_TARGETS,PAR_FEATURES,PAR_TARGETS,RESEARCH_FEATURES,RESEARCH_TARGETS,V02_ARTIFACT_DIR,ForecastWindows,add_cycles,make_windows,process_enriched_agc2
from app.ml.v02.metrics import interval_statistics,metric_rows
from app.ml.v02.training import SEED,apply_ensemble,fit_ensemble_weights,predict_residual_rnn,predict_residual_xgb,seed_all,train_residual_rnn,train_residual_xgb
from app.ml.v02.validation import assert_windows_no_leakage,expanding_rolling_folds,leave_one_greenhouse_out


def subset(windows:ForecastWindows,mask:np.ndarray)->ForecastWindows:return windows.subset(mask)


def persistence_prediction(windows:ForecastWindows)->np.ndarray:
    indices=[windows.feature_names.index(target) for target in windows.target_names];last=windows.X[:,-1,indices]
    return np.repeat(last[:,None,:],6,axis=1)


def train_ranges(train:ForecastWindows)->np.ndarray:
    return np.quantile(train.y,.95,axis=(0,1))-np.quantile(train.y,.05,axis=(0,1))


def add_metrics(rows:list[dict[str,Any]],method:str,fold:str,config:str,train:ForecastWindows,validation:ForecastWindows,prediction:np.ndarray)->None:
    current=metric_rows(method,fold,validation.y,prediction,validation.seasonal,validation.target_names,train_ranges(train))
    for row in current:row["config"]=config
    rows.extend(current)


def run_fold(config:str,fold_number:int,train:ForecastWindows,validation:ForecastWindows,root:Path,clip:bool=False,deep:bool=True)->tuple[dict[str,np.ndarray],dict[str,Any]]:
    predictions={"seasonal_24":validation.seasonal.copy(),"persistence":persistence_prediction(validation)};metadata={}
    models,names,duration=train_residual_xgb(train,root/f"fold_{fold_number}","output");predictions["seasonal_residual_xgboost"]=predict_residual_xgb(models,validation,clip);metadata["xgboost_seconds"]=duration;metadata["xgboost_feature_count"]=len(names)
    if deep:
        for kind in ["gru","lstm"]:
            model,scalers,history,duration=train_residual_rnn(kind,train,validation,V02_ARTIFACT_DIR/f"residual_{kind}"/f"{config}_fold_{fold_number}.pt")
            predictions[f"seasonal_residual_{kind}"]=predict_residual_rnn(model,scalers,validation,clip);metadata[f"{kind}_seconds"]=duration;metadata[f"{kind}_history"]=history
    return predictions,metadata


def build_ensemble(store:list[dict[str,Any]],target_names:list[str])->tuple[np.ndarray,dict[str,dict[str,str]],list[np.ndarray]]:
    truth=np.concatenate([item["validation"].y for item in store]);seasonal=np.concatenate([item["validation"].seasonal for item in store]);methods=["seasonal_residual_xgboost","seasonal_residual_gru","seasonal_residual_lstm"]
    selected=np.empty((6,len(target_names)),dtype=object);combined=np.empty_like(truth)
    for h in range(6):
        for ti in range(len(target_names)):
            errors={method:float(np.mean(np.abs(truth[:,h,ti]-np.concatenate([item["predictions"][method][:,h,ti] for item in store])))) for method in methods}
            method=min(errors,key=errors.get);selected[h,ti]=method;combined[:,h,ti]=np.concatenate([item["predictions"][method][:,h,ti] for item in store])
    weights=fit_ensemble_weights(truth,seasonal,combined);fold_predictions=[];offset=0
    for item in store:
        count=len(item["validation"].y);ml=np.empty_like(item["validation"].y)
        for h in range(6):
            for ti in range(len(target_names)):ml[:,h,ti]=item["predictions"][selected[h,ti]][:,h,ti]
        fold_predictions.append(apply_ensemble(item["validation"].seasonal,ml,weights));offset+=count
    selection={target:{f"h{h+1}":str(selected[h,ti]) for h in range(6)} for ti,target in enumerate(target_names)}
    return weights,selection,fold_predictions


def select_champions(metrics:pd.DataFrame,config:str,target_names:list[str])->dict[str,dict[str,dict[str,Any]]]:
    candidates=["seasonal_24","seasonal_residual_xgboost","seasonal_residual_gru","seasonal_residual_lstm","validation_weighted_ensemble"];complexity={"seasonal_24":0,"seasonal_residual_xgboost":1,"seasonal_residual_gru":2,"seasonal_residual_lstm":3,"validation_weighted_ensemble":4};registry={}
    selected=metrics[(metrics.config==config)&metrics.method.isin(candidates)]
    for target in target_names:
        registry[target]={}
        for horizon in range(1,7):
            group=selected[(selected.target==target)&(selected.horizon==horizon)].groupby("method").agg(mae=("mae","mean"),rmse=("rmse","mean"),stability=("mae","std"),nmae=("nmae","mean"),relative=("relative_seasonal_improvement_pct","mean")).reset_index();best=float(group.mae.min());close=group[group.mae<=best*1.01].copy();close["complexity"]=close.method.map(complexity);winner=close.sort_values(["complexity","mae","rmse","stability"]).iloc[0]
            registry[target][f"h{horizon}"]={"method":str(winner.method),"rolling_validation_mae":float(winner.mae),"rolling_validation_rmse":float(winner.rmse),"rolling_validation_nmae":float(winner.nmae),"mean_relative_seasonal_improvement_pct":float(winner.relative),"selection_rule":"MAE primary; within 1% prefer simpler, then RMSE and fold stability"}
    return registry


def selected_prediction(validation:ForecastWindows,predictions:dict[str,np.ndarray],registry:dict[str,dict[str,dict[str,Any]]])->np.ndarray:
    result=np.empty_like(validation.y)
    for ti,target in enumerate(validation.target_names):
        for h in range(6):result[:,h,ti]=predictions[registry[target][f"h{h+1}"]["method"]][:,h,ti]
    return result


def residual_analysis(windows:ForecastWindows,early_train_mask:np.ndarray)->list[dict[str,Any]]:
    residual=windows.y-windows.seasonal;low=np.quantile(windows.y[early_train_mask],.05,axis=(0,1));high=np.quantile(windows.y[early_train_mask],.95,axis=(0,1));rows=[]
    hours=pd.to_datetime(windows.target_times.reshape(-1)).hour.to_numpy().reshape(windows.target_times.shape)
    for ti,target in enumerate(windows.target_names):
        for h in range(6):
            values=residual[:,h,ti];actual=windows.y[:,h,ti];extreme=(actual<low[ti])|(actual>high[ti])
            for group,mask in {"all":np.ones(len(values),bool),"day":(hours[:,h]>=6)&(hours[:,h]<18),"night":~((hours[:,h]>=6)&(hours[:,h]<18)),"statistical_extreme":extreme,"normal":~extreme}.items():
                rows.append({"target":target,"horizon":h+1,"group":group,"mean":float(values[mask].mean()),"std":float(values[mask].std()),"count":int(mask.sum())})
            for greenhouse in np.unique(windows.greenhouse_ids):
                mask=windows.greenhouse_ids==greenhouse;rows.append({"target":target,"horizon":h+1,"group":f"greenhouse:{greenhouse}","mean":float(values[mask].mean()),"std":float(values[mask].std()),"count":int(mask.sum())})
    return rows


def interval_payload(store:list[dict[str,Any]],registry:dict[str,dict[str,dict[str,Any]]],target_names:list[str])->tuple[dict[str,Any],pd.DataFrame]:
    truth=[];pred=[];times=[]
    for item in store:truth.append(item["validation"].y);pred.append(selected_prediction(item["validation"],item["predictions"],registry));times.append(item["validation"].target_times)
    truth_a=np.concatenate(truth);pred_a=np.concatenate(pred);times_a=np.concatenate(times);errors=truth_a-pred_a;quantiles={}
    lower=np.empty_like(pred_a);upper=np.empty_like(pred_a)
    for ti,target in enumerate(target_names):
        quantiles[target]={}
        for h in range(6):
            lo=float(np.quantile(errors[:,h,ti],.05));hi=float(np.quantile(errors[:,h,ti],.95));quantiles[target][f"h{h+1}"]={"lower_residual":lo,"upper_residual":hi};lower[:,h,ti]=pred_a[:,h,ti]+lo;upper[:,h,ti]=pred_a[:,h,ti]+hi
    return quantiles,pd.DataFrame(interval_statistics(truth_a,pred_a,lower,upper,target_names,times_a))


def final_candidate_predictions(windows:ForecastWindows,models:dict[str,Any],clip:bool=False)->dict[str,np.ndarray]:
    result={"seasonal_24":windows.seasonal,"persistence":persistence_prediction(windows)}
    result["seasonal_residual_xgboost"]=predict_residual_xgb(models["xgboost"],windows,clip)
    for kind in ["gru","lstm"]:result[f"seasonal_residual_{kind}"]=predict_residual_rnn(models[kind][0],models[kind][1],windows,clip)
    ml=np.empty_like(windows.y)
    for h in range(6):
        for ti,target in enumerate(windows.target_names):ml[:,h,ti]=result[models["ensemble_methods"][target][f"h{h+1}"]][:,h,ti]
    result["validation_weighted_ensemble"]=apply_ensemble(windows.seasonal,ml,models["ensemble_weights"])
    return result


def save_plots(metrics:pd.DataFrame,residuals:pd.DataFrame,intervals:pd.DataFrame,registry:dict[str,Any],logo:pd.DataFrame,external:pd.DataFrame)->list[str]:
    root=V02_ARTIFACT_DIR/"plots";root.mkdir(parents=True,exist_ok=True);sns.set_theme(style="whitegrid");saved=[]
    def finish(name:str)->None:plt.tight_layout();plt.savefig(root/name,dpi=180,bbox_inches="tight");plt.close();saved.append(name)
    all_res=residuals[residuals.group=="all"]
    plt.figure(figsize=(10,5));sns.lineplot(data=all_res,x="horizon",y="std",hue="target",marker="o");plt.title("Seasonal residual standard deviation by horizon");plt.ylabel("Residual std (native unit)");finish("01_seasonal_residual_std.png")
    deploy=metrics[(metrics.config=="deployment_compatible")&metrics.method.isin(["seasonal_24","seasonal_residual_xgboost","seasonal_residual_gru","seasonal_residual_lstm","validation_weighted_ensemble"])]
    plt.figure(figsize=(11,5));sns.barplot(data=deploy,x="horizon",y="nmae",hue="method");plt.title("Deployment-compatible rolling validation NMAE");finish("02_deployment_rolling_nmae.png")
    rich=metrics[(metrics.config=="research_rich")&metrics.method.isin(["seasonal_24","seasonal_residual_xgboost"])]
    plt.figure(figsize=(10,5));sns.barplot(data=rich,x="target",y="nmae",hue="method");plt.xticks(rotation=15);plt.title("Research-rich exogenous feature comparison");finish("03_research_rich_value.png")
    par=metrics[(metrics.config=="par_research")&metrics.method.isin(["seasonal_24","seasonal_residual_xgboost","seasonal_residual_gru","seasonal_residual_lstm","validation_weighted_ensemble"])]
    plt.figure(figsize=(10,5));sns.lineplot(data=par,x="horizon",y="mae",hue="method",marker="o");plt.title("PAR research rolling validation MAE");plt.ylabel("MAE (µmol/m²/s)");finish("04_par_methods.png")
    coverage=intervals[intervals.period=="all"]
    plt.figure(figsize=(10,5));sns.barplot(data=coverage,x="horizon",y="coverage",hue="target");plt.axhline(.9,color="black",linestyle="--",label="Nominal 90%");plt.ylim(0,1);plt.title("Rolling-validation prediction interval coverage");finish("05_interval_coverage.png")
    plt.figure(figsize=(10,5));sns.barplot(data=logo[logo.method=="seasonal_residual_xgboost"],x="greenhouse",y="nmae",hue="target");plt.xticks(rotation=20);plt.title("Leave-one-greenhouse-out residual XGBoost");finish("06_logo_nmae.png")
    plt.figure(figsize=(9,5));sns.barplot(data=external,x="target",y="nmae",hue="method");plt.xticks(rotation=15);plt.title("Repeated AGC4 external benchmark");finish("07_external_benchmark.png")
    champion_rows=[]
    for target,values in registry.items():
        for horizon,item in values.items():champion_rows.append({"target":target,"horizon":int(horizon[1:]),"method":item["method"]})
    champion=pd.DataFrame(champion_rows);pivot=champion.pivot(index="target",columns="horizon",values="method");codes={name:index for index,name in enumerate(sorted(champion.method.unique()))};matrix=pivot.map(codes.get)
    plt.figure(figsize=(10,3.6));sns.heatmap(matrix,annot=pivot,fmt="",cbar=False,cmap="YlGn",linewidths=.5);plt.title("Champion method by target and horizon");finish("08_champion_registry.png")
    return saved


def write_checksums()->None:
    rows=[]
    for path in sorted(V02_ARTIFACT_DIR.rglob("*")):
        if path.is_file() and path.name!="checksums.sha256":rows.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(V02_ARTIFACT_DIR).as_posix()}")
    (V02_ARTIFACT_DIR/"checksums.sha256").write_text("\n".join(rows)+"\n",encoding="utf-8")


def main()->None:
    seed_all();started=time.perf_counter();V02_ARTIFACT_DIR.mkdir(parents=True,exist_ok=True)
    for directory in ["deployment_compatible","research_rich","par_research","baselines","residual_xgboost","residual_gru","residual_lstm","ensembles","scalers","plots"]:(V02_ARTIFACT_DIR/directory).mkdir(exist_ok=True)
    print("V0.2 stage 2-3: enriched data, rolling folds and residual labels",flush=True)
    frame=process_enriched_agc2();deploy=make_windows(frame,DEPLOY_FEATURES,DEPLOY_TARGETS);par=make_windows(frame,PAR_FEATURES,PAR_TARGETS);rich=make_windows(frame,RESEARCH_FEATURES,RESEARCH_TARGETS)
    for windows in [deploy,par,rich]:assert_windows_no_leakage(windows)
    residual_rows=residual_analysis(rich,expanding_rolling_folds(rich)[0].train_mask);pd.DataFrame(residual_rows).to_csv(V02_ARTIFACT_DIR/"seasonal_residual_statistics.csv",index=False)
    all_metrics=[];stores={"deployment_compatible":[],"par_research":[],"research_rich":[]};training_log=[]
    print("V0.2 stage 4: deployment residual XGBoost/GRU/LSTM",flush=True)
    for config,windows,root,clip,deep in [("deployment_compatible",deploy,V02_ARTIFACT_DIR/"residual_xgboost"/"deployment",False,True),("par_research",par,V02_ARTIFACT_DIR/"par_research"/"residual_xgboost",True,True),("research_rich",rich,V02_ARTIFACT_DIR/"research_rich"/"residual_xgboost",False,False)]:
        for fold in expanding_rolling_folds(windows):
            train=subset(windows,fold.train_mask);validation=subset(windows,fold.validation_mask);predictions,metadata=run_fold(config,fold.fold,train,validation,root,clip,deep);training_log.append({"config":config,"fold":fold.fold,**metadata})
            for method,prediction in predictions.items():add_metrics(all_metrics,method,f"rolling_{fold.fold}",config,train,validation,prediction)
            stores[config].append({"fold":fold.fold,"train":train,"validation":validation,"predictions":predictions})
    print("V0.2 stage 6-7: validation-only ensembles and champions",flush=True)
    ensemble_payload={}
    for config,target_names in [("deployment_compatible",DEPLOY_TARGETS),("par_research",PAR_TARGETS)]:
        weights,methods,fold_predictions=build_ensemble(stores[config],target_names);ensemble_payload[config]={"weights":weights.tolist(),"base_ml_methods":methods}
        for item,prediction in zip(stores[config],fold_predictions,strict=True):item["predictions"]["validation_weighted_ensemble"]=prediction;add_metrics(all_metrics,"validation_weighted_ensemble",f"rolling_{item['fold']}",config,item["train"],item["validation"],prediction)
    metrics_frame=pd.DataFrame(all_metrics);deploy_registry=select_champions(metrics_frame,"deployment_compatible",DEPLOY_TARGETS);par_registry=select_champions(metrics_frame,"par_research",PAR_TARGETS);champions={**deploy_registry,**par_registry}
    deploy_quantiles,deploy_intervals=interval_payload(stores["deployment_compatible"],deploy_registry,DEPLOY_TARGETS);par_quantiles,par_intervals=interval_payload(stores["par_research"],par_registry,PAR_TARGETS);interval_frame=pd.concat([deploy_intervals.assign(config="deployment_compatible"),par_intervals.assign(config="par_research")],ignore_index=True)
    print("V0.2 stage 5: leave-one-greenhouse-out",flush=True)
    logo_rows=[]
    for greenhouse,train_mask,val_mask in leave_one_greenhouse_out(deploy):
        train=subset(deploy,train_mask);validation=subset(deploy,val_mask);models,_,_=train_residual_xgb(train);preds={"seasonal_24":validation.seasonal,"seasonal_residual_xgboost":predict_residual_xgb(models,validation)}
        for method,prediction in preds.items():
            current=metric_rows(method,f"logo_{greenhouse}",validation.y,prediction,validation.seasonal,validation.target_names,train_ranges(train))
            for row in current:row["greenhouse"]=greenhouse
            logo_rows.extend(current)
    logo_frame=pd.DataFrame(logo_rows)
    print("V0.2 stage 8: final 90% models and repeated external benchmark",flush=True)
    cutoff=np.unique(deploy.input_end_times)[int(len(np.unique(deploy.input_end_times))*.9)-1]
    final_models={}
    for config,windows,clip in [("deployment_compatible",deploy,False),("par_research",par,True)]:
        train_mask=windows.target_times[:,-1]<=cutoff;val_mask=windows.input_end_times>cutoff;train=subset(windows,train_mask);validation=subset(windows,val_mask)
        xgb,feature_names,xgb_seconds=train_residual_xgb(train,V02_ARTIFACT_DIR/("deployment_compatible" if config=="deployment_compatible" else "par_research")/"residual_xgboost_final","output")
        models={"xgboost":xgb,"feature_names":feature_names,"training_seconds":{"xgboost":xgb_seconds}}
        for kind in ["gru","lstm"]:
            model,scalers,history,duration=train_residual_rnn(kind,train,validation,V02_ARTIFACT_DIR/("deployment_compatible" if config=="deployment_compatible" else "par_research")/f"residual_{kind}_final.pt");models[kind]=(model,scalers);models["training_seconds"][kind]=duration
        models["ensemble_weights"]=np.asarray(ensemble_payload[config]["weights"],np.float32);models["ensemble_methods"]=ensemble_payload[config]["base_ml_methods"];final_models[config]=models
        joblib.dump({"models":xgb,"feature_names":feature_names,"features":windows.feature_names,"targets":windows.target_names},V02_ARTIFACT_DIR/("deployment_compatible" if config=="deployment_compatible" else "par_research")/"residual_xgboost_final.joblib")
    rich_train_mask=rich.target_times[:,-1]<=cutoff;rich_xgb,rich_names,rich_seconds=train_residual_xgb(subset(rich,rich_train_mask),V02_ARTIFACT_DIR/"research_rich"/"residual_xgboost_final","output");joblib.dump({"models":rich_xgb,"feature_names":rich_names,"features":RESEARCH_FEATURES,"targets":RESEARCH_TARGETS,"status":"research_only"},V02_ARTIFACT_DIR/"research_rich"/"residual_xgboost_final.joblib")
    external_path=PROJECT_ROOT/"backend/app/ml/data/processed/agc4_external_hourly.csv.gz"
    if not external_path.exists():raise FileNotFoundError("Preserved V0.1 AGC4 processed benchmark is missing")
    external_frame=pd.read_csv(external_path,parse_dates=["timestamp"]).rename(columns={"light_intensity":"par_umol_m2_s"});external_deploy=make_windows(external_frame,DEPLOY_FEATURES,DEPLOY_TARGETS);external_par=make_windows(external_frame,PAR_FEATURES,PAR_TARGETS);external_rows=[]
    for config,windows,registry in [("deployment_compatible",external_deploy,deploy_registry),("par_research",external_par,par_registry)]:
        predictions=final_candidate_predictions(windows,final_models[config],config=="par_research");predictions["champion_registry"]=selected_prediction(windows,predictions,registry)
        for method in ["seasonal_24","champion_registry"]:
            current=metric_rows(method,"repeated_external_agc4",windows.y,predictions[method],windows.seasonal,windows.target_names,train_ranges(subset(deploy if config=="deployment_compatible" else par,(deploy if config=="deployment_compatible" else par).target_times[:,-1]<=cutoff)))
            for row in current:row["config"]=config;row["benchmark_status"]="repeated_external_not_unseen"
            external_rows.extend(current)
    external_frame_metrics=pd.DataFrame(external_rows)
    # ML gate is deliberately strict and separate from forecast-service readiness.
    deploy_ml=metrics_frame[(metrics_frame.config=="deployment_compatible")&metrics_frame.method.isin(["seasonal_residual_xgboost","seasonal_residual_gru","seasonal_residual_lstm"])]
    best_ml=deploy_ml.groupby(["target","horizon","fold"]).apply(lambda group:group.loc[group.mae.idxmin()],include_groups=False).reset_index();ml_wins=int((best_ml.relative_seasonal_improvement_pct>=2).sum());ml_total=len(best_ml)
    seasonal_rmse=metrics_frame[(metrics_frame.config=="deployment_compatible")&(metrics_frame.method=="seasonal_24")][["target","horizon","fold","rmse"]].rename(columns={"rmse":"seasonal_rmse"});best_ml=best_ml.merge(seasonal_rmse,on=["target","horizon","fold"],validate="one_to_one");rmse_ok=float((best_ml.rmse<=best_ml.seasonal_rmse*1.05).mean())
    logo_degradation=logo_frame[logo_frame.method=="seasonal_residual_xgboost"].groupby("greenhouse").relative_seasonal_improvement_pct.mean();ml_status="ready" if ml_wins>ml_total/2 and rmse_ok>=.9 and float(logo_degradation.min())>-50 else "under_evaluation"
    champion_payload={"model_version":"v0.2","selection_source":"three expanding rolling-validation folds only","forecast_service_status":"ready","model_status":"ready" if ml_status=="ready" else "baseline_ready","ml_candidate_status":ml_status,"targets":champions,"ensembles":ensemble_payload,"prediction_interval_residual_quantiles":{**deploy_quantiles,**par_quantiles},"par_availability":"research_only; current SQLite klx is not accepted as PAR"}
    (V02_ARTIFACT_DIR/"champion_registry.json").write_text(json.dumps(champion_payload,ensure_ascii=False,indent=2),encoding="utf-8")
    unit_contract={"database":{"light_intensity":{"unit":"kilolux","purpose":"monitoring_and_rule_engine","accepted_by_par_model":False}},"forecast_outputs":{"temperature_c":"degree_Celsius","air_humidity_pct":"percent","par_umol_m2_s":"micromole_per_m2_second"},"deployment_inputs":{"temperature":"degree_Celsius","air_humidity":"percent","recorded_at":"ISO_8601"},"par_inference":{"required_input_unit":"micromole_per_m2_second","database_klx_conversion":None,"reason":"No spectrum-independent exact conversion; guessing is prohibited."}}
    (V02_ARTIFACT_DIR/"unit_contract.json").write_text(json.dumps(unit_contract,ensure_ascii=False,indent=2),encoding="utf-8")
    feature_schema={"deployment_compatible":{"features":DEPLOY_FEATURES,"targets":DEPLOY_TARGETS,"input_window_hours":24,"horizon_hours":6,"available_in_current_sqlite":True,"par_dependency":False},"research_rich":{"features":RESEARCH_FEATURES,"targets":RESEARCH_TARGETS,"status":"research_only","future_measured_weather_used":False},"par_research":{"features":PAR_FEATURES,"targets":PAR_TARGETS,"status":"research_only","required_light_unit":"micromole_per_m2_second"}}
    (V02_ARTIFACT_DIR/"feature_schema.json").write_text(json.dumps(feature_schema,ensure_ascii=False,indent=2),encoding="utf-8")
    config={"seed":SEED,"device":"cpu","threads":4,"input_hours":24,"horizon_hours":6,"rolling_folds":[{"train_fraction":.45,"validation_end_fraction":.60},{"train_fraction":.60,"validation_end_fraction":.75},{"train_fraction":.75,"validation_end_fraction":.90}],"selection":{"primary":"MAE","secondary":"RMSE","tertiary":"fold stability","simple_method_tolerance_pct":1},"prediction_interval":"rolling validation residual 5th/95th percentiles","xgboost":{"n_estimators":140,"max_depth":5,"learning_rate":.045},"recurrent":{"hidden_size":32,"dropout":.15,"max_epochs":18,"patience":4,"batch_size":128}}
    (V02_ARTIFACT_DIR/"training_config.json").write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding="utf-8")
    (V02_ARTIFACT_DIR/"baselines"/"seasonal_24.json").write_text(json.dumps({"formula":"prediction(t+h) = observation(t+h-24)","horizons":[1,2,3,4,5,6],"requires_contiguous_history_hours":24,"random":False},indent=2),encoding="utf-8")
    for source in (V02_ARTIFACT_DIR/"deployment_compatible").glob("*.scalers.joblib"):shutil.copy2(source,V02_ARTIFACT_DIR/"scalers"/source.name)
    metrics_frame.to_csv(V02_ARTIFACT_DIR/"rolling_cv_metrics.csv",index=False);logo_frame.to_csv(V02_ARTIFACT_DIR/"greenhouse_holdout_metrics.csv",index=False);external_frame_metrics.to_csv(V02_ARTIFACT_DIR/"external_metrics.csv",index=False);interval_frame.to_csv(V02_ARTIFACT_DIR/"prediction_interval_metrics.csv",index=False);metrics_frame.to_csv(V02_ARTIFACT_DIR/"model_comparison.csv",index=False)
    (V02_ARTIFACT_DIR/"ensembles"/"validation_weights.json").write_text(json.dumps(ensemble_payload,ensure_ascii=False,indent=2),encoding="utf-8");(V02_ARTIFACT_DIR/"training_log.json").write_text(json.dumps(training_log,ensure_ascii=False,indent=2),encoding="utf-8")
    plots=save_plots(metrics_frame,pd.DataFrame(residual_rows),interval_frame,champions,logo_frame,external_frame_metrics)
    metadata={"model_name":"environment-forecast-v0.2","model_version":"v0.2","forecast_service_status":"ready","model_status":champion_payload["model_status"],"ml_candidate_status":ml_status,"training_device":"cpu","random_seed":SEED,"dataset_name":"Autonomous Greenhouse Challenge, Second Edition (2019)","dataset_doi":"10.4121/uuid:88d22c60-21b3-4ea8-90db-20249a5be2a7","dataset_license":"CC0 1.0","crop":"cherry_tomato","region":"Bleiswijk, Netherlands","training_domain":"public_real_greenhouse_tomato","time_range":[str(frame.timestamp.min()),str(frame.timestamp.max())],"rolling_validation_folds":3,"greenhouse_holdouts":list(np.unique(deploy.greenhouse_ids)),"samples":{"deployment":len(deploy.X),"par":len(par.X),"research_rich":len(rich.X)},"ml_gate":{"wins_at_least_2pct":ml_wins,"comparisons":ml_total,"rmse_within_5pct_of_seasonal":int(round(rmse_ok*ml_total)),"logo_min_mean_improvement_pct":float(logo_degradation.min())},"created_at":datetime.now(UTC).isoformat(),"elapsed_seconds":time.perf_counter()-started,"limitations":["V0.1 test and AGC4 external results were previously viewed; external benchmark is repeated, not unseen","Public Dutch cherry-tomato domain, not Shenxian melon calibration","Current service provides temperature/humidity only; PAR is null because SQLite light is klx","No direct hardware control or tomato risk rule"]}
    (V02_ARTIFACT_DIR/"training_metadata.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")
    card=f"""# Environment Forecast V0.2 Model Card\n\n## Status\nForecast service: **ready**. Registered methods are selected per target and horizon from three rolling validation folds and may include the honest `seasonal_24` baseline. ML candidate: **{ml_status}**. A ready forecast service does not imply that deep learning passed validation.\n\n## Data\nAutonomous Greenhouse Challenge, Second Edition (2019), cherry tomato, Bleiswijk, Netherlands; DOI `10.4121/uuid:88d22c60-21b3-4ea8-90db-20249a5be2a7`; CC0 1.0. V0.1 artifacts and its `under_evaluation` conclusion are preserved. AGC4 is a repeated external benchmark, not a new unseen test.\n\n## Method\nThe seasonal baseline for horizon h is the observed value at target time minus 24 hours. Residual models learn `actual - seasonal`; recurrent models contain an explicit skip connection. Champions are selected by rolling-validation MAE, then RMSE/stability and simplicity within 1%. Prediction intervals are rolling-residual 5th/95th percentiles.\n\n## Product contract\nDeployment-compatible temperature/humidity uses only SQLite-available 24-hour temperature, humidity and time features. Research-rich historical weather and controls are `research_only`. PAR is trained and reported separately in µmol/m²/s; SQLite klx never enters that model and API PAR is null.\n\n## Limitations\nNot locally calibrated for Shenxian melon; statistical extremes are not crop risks; tomato rules are unavailable; no automatic hardware control; predictions do not replace agronomic judgment.\n"""
    (V02_ARTIFACT_DIR/"model_card.md").write_text(card,encoding="utf-8")
    shutil.copy2(PROJECT_ROOT/"backend/app/ml/configs/dataset_registry.json",V02_ARTIFACT_DIR/"dataset_registry_snapshot.json");write_checksums()
    print(json.dumps({"forecast_service_status":"ready","model_status":champion_payload["model_status"],"ml_candidate_status":ml_status,"champions":champions,"interval_mean_coverage":float(interval_frame[interval_frame.period=="all"].coverage.mean()),"plots":len(plots),"elapsed_seconds":metadata["elapsed_seconds"]},ensure_ascii=False,indent=2),flush=True)


if __name__=="__main__":main()
