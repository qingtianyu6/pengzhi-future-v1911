from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from app.ml.data.audit import PROJECT_ROOT, parse_excel_time


V02_ARTIFACT_DIR = PROJECT_ROOT / "backend" / "app" / "ml" / "artifacts" / "environment_forecast_v0.2"
V02_PROCESSED_DIR = PROJECT_ROOT / "backend" / "app" / "ml" / "data" / "processed" / "v0.2"
DEPLOY_FEATURES = ["air_temperature_c", "air_humidity_pct", "hour_sin", "hour_cos", "day_of_year_sin", "day_of_year_cos"]
DEPLOY_TARGETS = ["air_temperature_c", "air_humidity_pct"]
PAR_TARGETS = ["par_umol_m2_s"]
PAR_FEATURES = ["air_temperature_c", "air_humidity_pct", "par_umol_m2_s", "hour_sin", "hour_cos", "day_of_year_sin", "day_of_year_cos"]
RESEARCH_FEATURES = [
    "air_temperature_c", "air_humidity_pct", "par_umol_m2_s", "co2_ppm",
    "outside_temperature_c", "outside_humidity_pct", "wind_speed_m_s",
    "vent_lee_pct", "vent_wind_pct", "energy_screen_pct", "blackout_screen_pct",
    "lamp_state_pct", "irrigation_l_m2", "hour_sin", "hour_cos",
    "day_of_year_sin", "day_of_year_cos",
]
RESEARCH_TARGETS = ["air_temperature_c", "air_humidity_pct", "par_umol_m2_s"]


def add_cycles(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy(); hour = result["timestamp"].dt.hour + result["timestamp"].dt.minute / 60; day = result["timestamp"].dt.dayofyear
    result["hour_sin"] = np.sin(2 * np.pi * hour / 24); result["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    result["day_of_year_sin"] = np.sin(2 * np.pi * day / 365.25); result["day_of_year_cos"] = np.cos(2 * np.pi * day / 365.25)
    return result


def _numeric(raw: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(raw[column], errors="coerce")


def process_enriched_agc2(force: bool = False) -> pd.DataFrame:
    output = V02_PROCESSED_DIR / "agc2_enriched_hourly.csv.gz"
    if output.exists() and not force: return pd.read_csv(output, parse_dates=["timestamp"])
    root = PROJECT_ROOT / "data" / "external" / "autonomous_greenhouse_challenge_2nd" / "extracted"
    weather_raw = pd.read_csv(root / "Weather" / "Weather.csv", low_memory=False)
    weather = pd.DataFrame({"timestamp": parse_excel_time(weather_raw["%time"]), "outside_temperature_c": _numeric(weather_raw, "Tout"), "outside_humidity_pct": _numeric(weather_raw, "Rhout"), "wind_speed_m_s": _numeric(weather_raw, "Windsp")})
    weather.loc[~weather["outside_temperature_c"].between(-30, 60), "outside_temperature_c"] = np.nan
    weather.loc[~weather["outside_humidity_pct"].between(0, 100), "outside_humidity_pct"] = np.nan
    weather.loc[weather["wind_speed_m_s"] < 0, "wind_speed_m_s"] = np.nan
    weather_hourly = weather.dropna(subset=["timestamp"]).set_index("timestamp").resample("1h").mean().reset_index()
    frames = []; statistics = []
    for path in sorted(root.glob("*/GreenhouseClimate.csv")):
        raw = pd.read_csv(path, low_memory=False)
        frame = pd.DataFrame({
            "timestamp": parse_excel_time(raw["%time"]), "air_temperature_c": _numeric(raw, "Tair"), "air_humidity_pct": _numeric(raw, "Rhair"),
            "par_umol_m2_s": _numeric(raw, "Tot_PAR"), "co2_ppm": _numeric(raw, "CO2air"), "vent_lee_pct": _numeric(raw, "VentLee"),
            "vent_wind_pct": _numeric(raw, "Ventwind"), "energy_screen_pct": _numeric(raw, "EnScr"), "blackout_screen_pct": _numeric(raw, "BlackScr"),
            "lamp_state_pct": _numeric(raw, "AssimLight"), "cum_irrigation_l_m2_day": _numeric(raw, "Cum_irr"),
        })
        frame.loc[~frame["air_temperature_c"].between(0, 60), "air_temperature_c"] = np.nan; frame.loc[~frame["air_humidity_pct"].between(0, 100), "air_humidity_pct"] = np.nan
        frame.loc[frame["par_umol_m2_s"] < 0, "par_umol_m2_s"] = np.nan; frame.loc[~frame["co2_ppm"].between(0, 5000), "co2_ppm"] = np.nan
        for column in ["vent_lee_pct", "vent_wind_pct", "energy_screen_pct", "blackout_screen_pct", "lamp_state_pct"]: frame.loc[~frame[column].between(0, 100), column] = np.nan
        frame = frame.dropna(subset=["timestamp"]).sort_values("timestamp").drop_duplicates("timestamp", keep="last")
        day = frame["timestamp"].dt.date; increment = frame["cum_irrigation_l_m2_day"].groupby(day).diff().clip(lower=0); frame["irrigation_l_m2"] = increment
        means = ["air_temperature_c", "air_humidity_pct", "par_umol_m2_s", "co2_ppm", "vent_lee_pct", "vent_wind_pct", "energy_screen_pct", "blackout_screen_pct", "lamp_state_pct"]
        hourly = frame.set_index("timestamp")[means].resample("1h").mean()
        hourly["irrigation_l_m2"] = frame.set_index("timestamp")["irrigation_l_m2"].resample("1h").sum(min_count=1)
        hourly = hourly.reset_index().merge(weather_hourly, on="timestamp", how="left")
        hourly["greenhouse_id"] = path.parent.name; hourly["dataset_id"] = "agc2_2019"; hourly["source_dataset"] = "Autonomous Greenhouse Challenge, Second Edition (2019)"; hourly["crop"] = "cherry_tomato"; hourly["source_type"] = "public_real_dataset"
        hourly = add_cycles(hourly); frames.append(hourly)
        statistics.append({"greenhouse_id": path.parent.name, "raw_rows": len(raw), "hourly_rows": len(hourly)})
    result = pd.concat(frames, ignore_index=True).sort_values(["greenhouse_id", "timestamp"])
    V02_PROCESSED_DIR.mkdir(parents=True, exist_ok=True); result.to_csv(output, index=False, compression="gzip")
    (V02_PROCESSED_DIR / "agc2_enriched_processing.json").write_text(json.dumps({"output": str(output.relative_to(PROJECT_ROOT)).replace("\\", "/"), "raw_data_modified": False, "weather_semantics": "historical measured weather only; no future observations used", "heating_state": None, "heating_note": "AGC2 provides pipe temperatures, not an explicit heating state; excluded rather than guessed", "groups": statistics}, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


@dataclass
class ForecastWindows:
    X: np.ndarray
    y: np.ndarray
    seasonal: np.ndarray
    greenhouse_ids: np.ndarray
    input_end_times: np.ndarray
    target_times: np.ndarray
    future_cycles: np.ndarray
    feature_names: list[str]
    target_names: list[str]

    def subset(self, mask: np.ndarray) -> "ForecastWindows":
        return ForecastWindows(self.X[mask], self.y[mask], self.seasonal[mask], self.greenhouse_ids[mask], self.input_end_times[mask], self.target_times[mask], self.future_cycles[mask], self.feature_names, self.target_names)


def make_windows(frame: pd.DataFrame, features: list[str], targets: list[str], input_hours: int = 24, horizon: int = 6) -> ForecastWindows:
    Xs=[]; ys=[]; bases=[]; groups=[]; ends=[]; target_times=[]; cycles=[]
    for greenhouse_id, group in frame.sort_values("timestamp").groupby("greenhouse_id", sort=True):
        group=group.reset_index(drop=True); times=pd.to_datetime(group["timestamp"]); X=group[features].to_numpy(np.float32); y=group[targets].to_numpy(np.float32)
        for end in range(input_hours-1,len(group)-horizon):
            start=end-input_hours+1; final=end+horizon; span=times.iloc[start:final+1]
            if not (span.diff().dropna()==pd.Timedelta(hours=1)).all(): continue
            x=X[start:end+1]; future=y[end+1:final+1]; seasonal=y[start:start+horizon]
            if np.isnan(x).any() or np.isnan(future).any() or np.isnan(seasonal).any(): continue
            future_time=times.iloc[end+1:final+1]
            future_hour=future_time.dt.hour.to_numpy(); future_day=future_time.dt.dayofyear.to_numpy()
            future_cycle=np.column_stack([np.sin(2*np.pi*future_hour/24),np.cos(2*np.pi*future_hour/24),np.sin(2*np.pi*future_day/365.25),np.cos(2*np.pi*future_day/365.25)]).astype(np.float32)
            Xs.append(x);ys.append(future);bases.append(seasonal);groups.append(str(greenhouse_id));ends.append(times.iloc[end].to_datetime64());target_times.append(future_time.to_numpy(dtype="datetime64[ns]"));cycles.append(future_cycle)
    return ForecastWindows(np.asarray(Xs,np.float32),np.asarray(ys,np.float32),np.asarray(bases,np.float32),np.asarray(groups),np.asarray(ends),np.asarray(target_times),np.asarray(cycles,np.float32),features,targets)


def xgb_matrix(windows: ForecastWindows) -> tuple[np.ndarray, list[str]]:
    X=windows.X.reshape(len(windows.X),-1); seasonal=windows.seasonal.reshape(len(windows.X),-1); cycles=windows.future_cycles.reshape(len(windows.X),-1)
    names=[f"{feature}_lag_{lag}" for lag in range(24,0,-1) for feature in windows.feature_names]
    names += [f"seasonal_{target}_h{h}" for h in range(1,7) for target in windows.target_names]
    names += [f"future_{cycle}_h{h}" for h in range(1,7) for cycle in ["hour_sin","hour_cos","day_of_year_sin","day_of_year_cos"]]
    return np.column_stack([X,seasonal,cycles]).astype(np.float32),names


def validate_unit_contract(input_unit: str | None, expected_unit: str) -> None:
    if input_unit != expected_unit: raise ValueError(f"unit mismatch: expected {expected_unit}, received {input_unit}")
