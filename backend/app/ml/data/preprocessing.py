from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.ml.data.audit import PROJECT_ROOT, parse_excel_time


ML_ROOT = PROJECT_ROOT / "backend" / "app" / "ml"
PROCESSED_DIR = ML_ROOT / "data" / "processed"
TARGETS = ["air_temperature_c", "air_humidity_pct", "light_intensity"]
TARGET_UNITS = ["degree_Celsius", "percent", "micromole_per_m2_second"]
SEQUENCE_FEATURES = [
    "air_temperature_c", "air_humidity_pct", "hour_sin", "hour_cos",
    "day_of_year_sin", "day_of_year_cos",
]


def add_cycles(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    hour = result["timestamp"].dt.hour + result["timestamp"].dt.minute / 60
    day = result["timestamp"].dt.dayofyear
    result["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    result["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    result["day_of_year_sin"] = np.sin(2 * np.pi * day / 365.25)
    result["day_of_year_cos"] = np.cos(2 * np.pi * day / 365.25)
    return result


def _clean_agc2_team(path: Path) -> tuple[pd.DataFrame, dict[str, int]]:
    raw = pd.read_csv(path, low_memory=False)
    frame = pd.DataFrame({
        "timestamp": parse_excel_time(raw["%time"]),
        "air_temperature_c": pd.to_numeric(raw["Tair"], errors="coerce"),
        "air_humidity_pct": pd.to_numeric(raw["Rhair"], errors="coerce"),
        "light_intensity": pd.to_numeric(raw["Tot_PAR"], errors="coerce"),
        "co2_ppm": pd.to_numeric(raw["CO2air"], errors="coerce"),
        "window_state": pd.to_numeric(raw["VentLee"], errors="coerce"),
        "ventilation_state": pd.to_numeric(raw["Ventwind"], errors="coerce"),
    })
    invalid = {
        "temperature": int((~frame["air_temperature_c"].between(0, 60)).sum()),
        "humidity": int((~frame["air_humidity_pct"].between(0, 100)).sum()),
        "light": int((frame["light_intensity"] < 0).sum() + frame["light_intensity"].isna().sum()),
        "co2": int((~frame["co2_ppm"].between(0, 5000)).sum()),
    }
    frame.loc[~frame["air_temperature_c"].between(0, 60), "air_temperature_c"] = np.nan
    frame.loc[~frame["air_humidity_pct"].between(0, 100), "air_humidity_pct"] = np.nan
    frame.loc[frame["light_intensity"] < 0, "light_intensity"] = np.nan
    frame.loc[~frame["co2_ppm"].between(0, 5000), "co2_ppm"] = np.nan
    frame = frame.dropna(subset=["timestamp"]).sort_values("timestamp").drop_duplicates("timestamp", keep="last")
    frame["greenhouse_id"] = path.parent.name
    frame["dataset_id"] = "agc2_2019"
    frame["source_dataset"] = "Autonomous Greenhouse Challenge, Second Edition (2019)"
    frame["crop"] = "cherry_tomato"
    frame["source_type"] = "public_real_dataset"
    return frame, invalid


def aggregate_hourly(frame: pd.DataFrame) -> pd.DataFrame:
    continuous = ["air_temperature_c", "air_humidity_pct", "light_intensity", "co2_ppm", "window_state", "ventilation_state"]
    aggregation: dict[str, object] = {column: "mean" for column in continuous}
    aggregation.update({
        "air_temperature_min_c": ("air_temperature_c", "min"),
        "air_temperature_max_c": ("air_temperature_c", "max"),
        "air_humidity_min_pct": ("air_humidity_pct", "min"),
        "air_humidity_max_pct": ("air_humidity_pct", "max"),
        "co2_max_ppm": ("co2_ppm", "max"),
        "observations": ("air_temperature_c", "size"),
    })
    indexed = frame.set_index("timestamp")
    named = {k: v for k, v in aggregation.items() if isinstance(v, tuple)}
    simple = {k: v for k, v in aggregation.items() if not isinstance(v, tuple)}
    hourly_simple = indexed[list(simple)].resample("1h").agg(simple)
    hourly_named = indexed.resample("1h").agg(**named)
    hourly = pd.concat([hourly_simple, hourly_named], axis=1).reset_index()
    for column in ["greenhouse_id", "dataset_id", "source_dataset", "crop", "source_type"]:
        hourly[column] = frame[column].iloc[0]
    hourly["light_unit"] = "micromole_per_m2_second"
    hourly["quality_flag"] = np.where(hourly["observations"] >= 6, "observed", "partial")
    return add_cycles(hourly)


def process_agc2() -> tuple[pd.DataFrame, dict[str, object]]:
    root = PROJECT_ROOT / "data" / "external" / "autonomous_greenhouse_challenge_2nd" / "extracted"
    frames = []; invalid_total = {"temperature": 0, "humidity": 0, "light": 0, "co2": 0}; raw_rows = 0
    groups: list[dict[str, object]] = []
    for path in sorted(root.glob("*/GreenhouseClimate.csv")):
        cleaned, invalid = _clean_agc2_team(path)
        raw_rows += len(pd.read_csv(path, usecols=["%time"]))
        for key in invalid_total: invalid_total[key] += invalid[key]
        hourly = aggregate_hourly(cleaned)
        groups.append({"greenhouse_id": path.parent.name, "raw_rows": len(cleaned), "hourly_rows": len(hourly), "start": hourly["timestamp"].min().isoformat(), "end": hourly["timestamp"].max().isoformat()})
        frames.append(hourly)
    result = pd.concat(frames, ignore_index=True).sort_values(["greenhouse_id", "timestamp"])
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    result.to_csv(PROCESSED_DIR / "agc2_hourly.csv.gz", index=False, compression="gzip")
    stats: dict[str, object] = {
        "dataset_id": "agc2_2019", "raw_rows": raw_rows, "hourly_rows": len(result),
        "invalid_values_set_to_missing": invalid_total, "interpolation": "none",
        "aggregation": "hourly mean; temperature/humidity min/max; CO2 max; no long-gap fill",
        "groups": groups, "output": "backend/app/ml/data/processed/agc2_hourly.csv.gz",
    }
    (PROCESSED_DIR / "agc2_processing_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return result, stats


def process_agc4_external() -> pd.DataFrame:
    base = PROJECT_ROOT / "datasets" / "public_greenhouse" / "02_agc4_dwarf_tomato" / "extracted" / "autonomous_greenhouse_challenge4_timeseries" / "timeseries"
    frames = []
    mapping = {"compartment/air_temperature": "air_temperature_c", "compartment/relative_humidity": "air_humidity_pct", "compartment/par": "light_intensity"}
    for path in sorted(base.glob("*.csv")):
        if path.stem in {"weather", "weather_forecast"}: continue
        raw = pd.read_csv(path, usecols=lambda c: c == "time" or c in mapping)
        frame = raw.rename(columns=mapping)
        frame["timestamp"] = pd.to_datetime(frame.pop("time"), errors="coerce", utc=True).dt.tz_convert("Europe/Amsterdam").dt.tz_localize(None)
        for column in TARGETS: frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame.loc[~frame["air_temperature_c"].between(0, 60), "air_temperature_c"] = np.nan
        frame.loc[~frame["air_humidity_pct"].between(0, 100), "air_humidity_pct"] = np.nan
        frame.loc[frame["light_intensity"] < 0, "light_intensity"] = np.nan
        frame = frame.dropna(subset=["timestamp"]).sort_values("timestamp").drop_duplicates("timestamp", keep="last").set_index("timestamp")[TARGETS].resample("1h").mean().reset_index()
        frame["greenhouse_id"] = path.stem; frame["dataset_id"] = "agc4_dwarf_tomato_2024"; frame["source_dataset"] = "4th Autonomous Greenhouse Challenge"; frame["crop"] = "dwarf_tomato"; frame["source_type"] = "public_real_dataset"; frame["light_unit"] = "micromole_per_m2_second"; frame["quality_flag"] = "observed"
        frames.append(add_cycles(frame))
    result = pd.concat(frames, ignore_index=True).sort_values(["greenhouse_id", "timestamp"])
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    result.to_csv(PROCESSED_DIR / "agc4_external_hourly.csv.gz", index=False, compression="gzip")
    return result


if __name__ == "__main__":
    data, stats = process_agc2(); external = process_agc4_external()
    print(json.dumps(stats, ensure_ascii=False, indent=2), flush=True)
    print(f"external_hourly_rows={len(external)}", flush=True)
