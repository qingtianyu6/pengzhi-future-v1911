from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[4]
ML_ROOT = PROJECT_ROOT / "backend" / "app" / "ml"


def parse_excel_time(values: pd.Series) -> pd.Series:
    return pd.to_datetime(pd.to_numeric(values, errors="coerce"), unit="D", origin="1899-12-30")


def time_stats(values: pd.Series) -> dict[str, Any]:
    timestamps = pd.Series(pd.to_datetime(values, errors="coerce", utc=True)).dropna().sort_values()
    diffs = timestamps.diff().dropna()
    seconds = diffs.dt.total_seconds().round().astype(int)
    positive = seconds[seconds > 0]
    mode = int(positive.mode().iloc[0]) if not positive.empty else None
    stable = float((positive == mode).mean()) if mode is not None else None
    return {
        "time_range": [timestamps.min().isoformat(), timestamps.max().isoformat()] if len(timestamps) else [None, None],
        "sampling_interval": f"{mode} seconds" if mode is not None else None,
        "sampling_stability": stable,
        "duplicate_count": int(timestamps.duplicated().sum()),
    }


def file_rows(path: Path) -> dict[str, Any]:
    return {"path": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"), "format": path.suffix.lower(), "size_bytes": path.stat().st_size}


def numeric_ranges(frame: pd.DataFrame, columns: list[str]) -> dict[str, list[float | None]]:
    result: dict[str, list[float | None]] = {}
    for column in columns:
        if column not in frame:
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        result[column] = [float(values.min()) if values.notna().any() else None, float(values.max()) if values.notna().any() else None]
    return result


def load_agc2() -> dict[str, Any]:
    root = PROJECT_ROOT / "data" / "external" / "autonomous_greenhouse_challenge_2nd"
    extracted = root / "extracted"
    paths = sorted(extracted.glob("*/GreenhouseClimate.csv"))
    teams: list[dict[str, Any]] = []
    missing = 0
    cells = 0
    duplicates = 0
    all_times: list[pd.Timestamp] = []
    ranges: dict[str, list[float | None]] = {}
    row_total = 0
    columns: list[str] = []
    intervals: list[int] = []
    abnormal_temperature = 0
    abnormal_humidity = 0
    for path in paths:
        frame = pd.read_csv(path, low_memory=False)
        columns = list(frame.columns)
        times = parse_excel_time(frame["%time"])
        stats = time_stats(times)
        row_total += len(frame)
        numeric_payload = frame.drop(columns=["%time"]).apply(pd.to_numeric, errors="coerce")
        missing += int(numeric_payload.isna().sum().sum())
        cells += int(numeric_payload.size)
        duplicates += stats["duplicate_count"]
        all_times.extend(times.dropna().tolist())
        if stats["sampling_interval"]:
            intervals.append(int(stats["sampling_interval"].split()[0]))
        teams.append({"greenhouse_id": path.parent.name, "rows": len(frame), **stats})
        temperature = pd.to_numeric(frame["Tair"], errors="coerce")
        humidity = pd.to_numeric(frame["Rhair"], errors="coerce")
        abnormal_temperature += int(((temperature < -20) | (temperature > 60)).sum())
        abnormal_humidity += int(((humidity < 0) | (humidity > 100)).sum())
        for key, value in numeric_ranges(frame, ["Tair", "Rhair", "Tot_PAR", "CO2air", "VentLee", "Ventwind"]).items():
            if key not in ranges:
                ranges[key] = value
            else:
                ranges[key] = [min(ranges[key][0], value[0]), max(ranges[key][1], value[1])]  # type: ignore[arg-type]
    times_s = pd.Series(all_times).sort_values()
    raw_files = [file_rows(p) for p in sorted(extracted.rglob("*")) if p.is_file()]
    abnormal = {
        "temperature_outside_-20_60": abnormal_temperature,
        "humidity_outside_0_100": abnormal_humidity,
    }
    return {
        "dataset_id": "agc2_2019", "dataset_name": "Autonomous Greenhouse Challenge, Second Edition (2019)",
        "doi": "10.4121/uuid:88d22c60-21b3-4ea8-90db-20249a5be2a7", "version": "2", "license": "CC0 1.0",
        "crop": "cherry_tomato", "local_path": str(root.relative_to(PROJECT_ROOT)).replace("\\", "/"), "raw_files": raw_files,
        "extracted": True, "readable": True, "row_count": row_total, "column_count": len(columns), "columns": columns,
        "dtypes": {c: "numeric" for c in columns}, "time_column": "%time", "time_format": "Excel serial date", "timezone": "Europe/Amsterdam (location context; CSV is timezone-naive)",
        "sampling_interval": f"{Counter(intervals).most_common(1)[0][0]} seconds", "sampling_stability": min(x["sampling_stability"] for x in teams),
        "greenhouse_column": "parent directory/team", "greenhouses": [x["greenhouse_id"] for x in teams],
        "available_features": ["air_temperature_c", "air_humidity_pct", "light_intensity", "co2_ppm", "outside_temperature_c", "outside_humidity_pct", "wind_speed", "window_state", "ventilation_state", "irrigation_amount"],
        "available_targets": ["air_temperature_c", "air_humidity_pct", "light_intensity"],
        "unit_mapping": {"Tair": "degree_Celsius", "Rhair": "percent", "Tot_PAR": "micromole_per_m2_second", "CO2air": "ppm", "Tout": "degree_Celsius", "Rhout": "percent", "Windsp": "meter_per_second"},
        "missing_rate": missing / cells, "duplicate_count": duplicates, "time_range": [times_s.min().isoformat(), times_s.max().isoformat()],
        "numeric_ranges": ranges, "abnormal_counts": abnormal, "control_devices": ["vents", "HPS_lamps", "screens", "irrigation"], "outside_weather": True,
        "processed_exists_before_day04": False, "simulation_present": False, "source_type": "public_real_dataset", "usable_for_training": True,
        "limitations": ["Timestamps are Excel serial values without embedded timezone", "Tot_PAR is a computed rather than directly measured indoor PAR channel", "Different teams follow different control strategies"],
        "group_details": teams,
    }


def load_iran() -> dict[str, Any]:
    root = PROJECT_ROOT / "datasets" / "public_greenhouse" / "01_iran_greenhouse"
    path = root / "raw" / "greenhouse_dataset.csv"
    frame = pd.read_csv(path)
    stats = time_stats(frame["DateTime"])
    return {
        "dataset_id": "iran_shirvan_v2", "dataset_name": "Greenhouse_Shrivan_Iran_Dataset", "doi": "10.17632/ncrm9p4tc8.2", "version": "2", "license": "CC BY 4.0", "crop": None,
        "local_path": str(root.relative_to(PROJECT_ROOT)).replace("\\", "/"), "raw_files": [file_rows(path)], "extracted": True, "readable": True,
        "row_count": len(frame), "column_count": len(frame.columns), "columns": list(frame.columns), "dtypes": {k: str(v) for k, v in frame.dtypes.items()},
        "time_column": "DateTime", "time_format": "YYYY-MM-DD HH:MM:SS", "timezone": None, **stats,
        "greenhouse_column": None, "greenhouses": None,
        "available_features": ["inside_temperature", "inside_humidity", "light_lux", "outside_temperature", "outside_humidity", "wind_speed", "coded_device_states"],
        "available_targets": ["light_intensity"], "unit_mapping": {"MeanInsideTemp": None, "AVGHumidityInside": None, "L1": "lux", "OutsideTemp": None, "HumidityOutside": None, "WS1": None},
        "missing_rate": float(frame.isna().sum().sum() / frame.size), "numeric_ranges": numeric_ranges(frame, ["MeanInsideTemp", "AVGHumidityInside", "L1", "OutsideTemp", "HumidityOutside", "WS1"]),
        "abnormal_counts": {"humidity_outside_0_100": int(((frame["AVGHumidityInside"] < 0) | (frame["AVGHumidityInside"] > 100)).sum())},
        "control_devices": ["coded H/F/W columns; per-column codebook unavailable"], "outside_weather": True, "processed_exists_before_day04": False, "simulation_present": False, "source_type": "public_real_dataset",
        "usable_for_training": False, "limitations": ["Temperature, humidity and wind units are not explicit in supplied files", "Crop and timezone are not stated", "Device-state codebook is incomplete"],
    }


def load_agc4() -> dict[str, Any]:
    root = PROJECT_ROOT / "datasets" / "public_greenhouse" / "02_agc4_dwarf_tomato"
    base = root / "extracted" / "autonomous_greenhouse_challenge4_timeseries"
    paths = [p for p in sorted((base / "timeseries").glob("*.csv")) if p.stem not in {"weather", "weather_forecast"}]
    rows = 0; cells = 0; missing = 0; duplicate = 0; columns: set[str] = set(); details = []; all_times: list[pd.Timestamp] = []; ranges: dict[str, list[float | None]] = {}
    core = ["compartment/air_temperature", "compartment/relative_humidity", "compartment/par", "compartment/co2_concentration"]
    for path in paths:
        frame = pd.read_csv(path)
        stats = time_stats(frame["time"])
        rows += len(frame); cells += frame.size; missing += int(frame.isna().sum().sum()); duplicate += stats["duplicate_count"]; columns.update(frame.columns)
        all_times.extend(pd.to_datetime(frame["time"], errors="coerce", utc=True).dropna().tolist())
        details.append({"greenhouse_id": path.stem, "rows": len(frame), **stats})
        for key, value in numeric_ranges(frame, core).items():
            if key not in ranges: ranges[key] = value
            else: ranges[key] = [min(ranges[key][0], value[0]), max(ranges[key][1], value[1])]  # type: ignore[arg-type]
    times = pd.Series(all_times).sort_values()
    raw_files = [file_rows(p) for p in sorted(root.rglob("*")) if p.is_file()]
    return {
        "dataset_id": "agc4_dwarf_tomato_2024", "dataset_name": "4th Autonomous Greenhouse Challenge: Dwarf Tomato Timeseries and Images", "doi": "10.4121/fa102772-32db-4b30-bace-12f2016722ce", "version": "1", "license": "CC BY 4.0", "crop": "dwarf_tomato",
        "local_path": str(root.relative_to(PROJECT_ROOT)).replace("\\", "/"), "raw_files": raw_files, "extracted": True, "readable": True,
        "row_count": rows, "column_count": len(columns), "columns": sorted(columns), "dtypes": {"time": "datetime-like", "other": "numeric"},
        "time_column": "time", "time_format": "ISO-like local datetime", "timezone": "Europe/Amsterdam", "sampling_interval": "300 seconds", "sampling_stability": min(x["sampling_stability"] for x in details), "duplicate_count": duplicate,
        "time_range": [times.min().isoformat(), times.max().isoformat()], "greenhouse_column": "filename/team", "greenhouses": [p.stem for p in paths],
        "available_features": ["air_temperature_c", "air_humidity_pct", "light_intensity", "co2_ppm", "outside_weather", "window_state", "heating", "screens", "substrate"],
        "available_targets": ["air_temperature_c", "air_humidity_pct", "light_intensity"], "unit_mapping": {"compartment/air_temperature": "degree_Celsius", "compartment/relative_humidity": "percent", "compartment/par": "micromole_per_m2_second", "compartment/co2_concentration": "ppm"},
        "missing_rate": missing / cells, "numeric_ranges": ranges, "abnormal_counts": {}, "control_devices": ["windows", "heating", "lamps", "screens", "water_supply"], "outside_weather": True,
        "processed_exists_before_day04": False, "simulation_present": False, "source_type": "public_real_dataset", "usable_for_training": True,
        "limitations": ["Only about eleven weeks", "Many optional channels differ by team", "Images are intentionally excluded"], "group_details": details,
    }


def simple_dataset(dataset_id: str, root: Path, path: Path, name: str, doi: str | None, version: str | None, license_name: str, crop: str | None, time_column: str | None, time_values: pd.Series | None, frame: pd.DataFrame, units: dict[str, str | None], features: list[str], targets: list[str], usable: bool, limitations: list[str], control: list[str]) -> dict[str, Any]:
    stats = time_stats(time_values) if time_values is not None else {"time_range": [None, None], "sampling_interval": None, "sampling_stability": None, "duplicate_count": 0}
    return {"dataset_id": dataset_id, "dataset_name": name, "doi": doi, "version": version, "license": license_name, "crop": crop,
        "local_path": str(root.relative_to(PROJECT_ROOT)).replace("\\", "/"), "raw_files": [file_rows(path)], "extracted": True, "readable": True,
        "row_count": len(frame), "column_count": len(frame.columns), "columns": list(frame.columns), "dtypes": {k: str(v) for k, v in frame.dtypes.items()},
        "time_column": time_column, "time_format": "datetime" if time_column else None, "timezone": "UTC" if dataset_id == "gets_greenhouse_2025" else None, **stats,
        "greenhouse_column": None, "greenhouses": None, "available_features": features, "available_targets": targets, "unit_mapping": units,
        "missing_rate": float(frame.isna().sum().sum() / frame.size), "numeric_ranges": numeric_ranges(frame, [c for c in units if c in frame]), "abnormal_counts": {},
        "control_devices": control, "outside_weather": False, "processed_exists_before_day04": False, "simulation_present": False, "source_type": "public_real_dataset",
        "usable_for_training": usable, "limitations": limitations}


def load_remaining() -> list[dict[str, Any]]:
    gets_root = PROJECT_ROOT / "datasets" / "public_greenhouse" / "03_gets_greenhouse_co2"
    gets_path = gets_root / "raw" / "GreenhouseEnvironmentTimeSeries.txt"
    gets = pd.read_csv(gets_path)
    gets_record = simple_dataset("gets_greenhouse_2025", gets_root, gets_path, "GETS: Greenhouse Environment Time Series", None, None, "CC BY 4.0", None, "date", gets["date"], gets,
        {"co2_ppm": "ppm", "humidity_pct": "percent", "soil_temp_F": "degree_Fahrenheit"}, ["co2_ppm", "air_humidity_pct", "soil_temperature_c"], ["co2_ppm"], True,
        ["Only about 29 days", "Crop and location are not stated", "Soil temperature requires explicit Fahrenheit-to-Celsius conversion"], [])

    irr_root = PROJECT_ROOT / "datasets" / "public_greenhouse" / "04_agricultural_irrigation"
    irr_path = irr_root / "extracted" / "Agricultural Irrigation Control Data" / "All-Data-SensorParser.xlsx"
    irr = pd.read_excel(irr_path)
    irr_record = simple_dataset("agricultural_irrigation_v1", irr_root, irr_path, "Agricultural Irrigation Control Dataset", "10.17632/3w3pf3vnd4.1", "1", "CC BY 4.0", None, None, None, irr,
        {"TC": None, "HUM": None, "SOIL": None, "SOILTC": None, "PAR": None}, ["coded sensor values"], [], False,
        ["Raw long table has no timestamp", "Units are not defined in supplied workbook", "Daily summary has only 53 rows"], [])
    daily_path = irr_root / "extracted" / "Agricultural Irrigation Control Data" / "DailyAverageSensedData1.xlsx"
    daily = pd.read_excel(daily_path)
    irr_record["raw_files"].append(file_rows(daily_path)); irr_record["daily_summary_rows"] = len(daily); irr_record["daily_time_range"] = time_stats(daily["Date"])["time_range"]

    lstm_root = PROJECT_ROOT / "datasets" / "public_greenhouse" / "05_lstm_predictive_irrigation"
    lstm_path = lstm_root / "raw" / "Edge_IoT_Predictive_Irrigation_Dataset.xlsx"
    lstm = pd.read_excel(lstm_path)
    lstm_record = simple_dataset("lstm_irrigation_v1", lstm_root, lstm_path, "Environmental Sensor Dataset for LSTM-Based Predictive Irrigation in Smart Home Gardening Using Edge IoT", "10.17632/jtsyb593fy.1", "1", "CC BY 4.0", None, "Timestamp", lstm["Timestamp"], lstm,
        {"Temperature_C": "degree_Celsius", "Humidity_pct": "percent", "Soil_Moisture_pct": "percent", "Light_Intensity": None, "Pump_Status": "binary_0_1"},
        ["air_temperature_c", "air_humidity_pct", "soil_moisture", "pump_state"], ["soil_moisture"], True,
        ["Only 20 days and 960 observations", "Smart-home testbed, not a production greenhouse", "Light unit and crop are unknown", "Pump status is historical operation, not an optimal policy"], ["pump"])
    return [gets_record, irr_record, lstm_record]


def markdown_report(records: list[dict[str, Any]]) -> str:
    lines = ["# 第4天：六套公开温室数据只读审计", "", "> 审计时间：2026-08-22。原始文件未修改；未知信息保留为 `null`。这些公开数据不是莘县甜瓜基地实采数据。", "",
             "## 总览", "", "| 数据集 | 行数 | 列数 | 时间范围 | 主间隔 | 缺失率 | 重复时间 | 可用于训练 |", "|---|---:|---:|---|---|---:|---:|---|"]
    for r in records:
        tr = " — ".join(str(x) for x in r["time_range"])
        lines.append(f"| {r['dataset_name']} | {r['row_count']:,} | {r['column_count']} | {tr} | {r['sampling_interval']} | {r['missing_rate']:.4%} | {r['duplicate_count']:,} | {'是' if r['usable_for_training'] else '否'} |")
    lines += ["", "## 主数据集判定", "", "选择第二届自主温室挑战赛作为核心训练数据：它有约六个月、6个可区分团队/温室序列、5分钟规则采样，且官方 ReadMe 明确给出了温度、相对湿度、PAR 和 CO₂单位。第四届数据单位同样完整，但仅约十一周，因此作为跨数据集外部验证。伊朗数据周期长，但随附文件没有明确温湿度单位，按“不猜测单位”原则不进入核心比较。", ""]
    for i, r in enumerate(records, 1):
        lines += [f"## {i}. {r['dataset_name']}", "", f"- 标识：`{r['dataset_id']}`；DOI：`{r['doi']}`；版本：`{r['version']}`；许可：{r['license']}。",
                  f"- 本地位置：`{r['local_path']}`；已解压：{r['extracted']}；可读：{r['readable']}；来源：`{r['source_type']}`。",
                  f"- 作物：`{r['crop']}`；时间字段：`{r['time_column']}`；时间格式：{r['time_format']}；时区：`{r['timezone']}`。",
                  f"- 数据规模：{r['row_count']:,} 行、{r['column_count']} 列；采样稳定度：{r['sampling_stability']}；缺失率：{r['missing_rate']:.6%}；重复时间戳：{r['duplicate_count']}。",
                  f"- 可用特征：{', '.join(r['available_features']) or '无'}；可用目标：{', '.join(r['available_targets']) or '无'}。",
                  f"- 单位映射：`{json.dumps(r['unit_mapping'], ensure_ascii=False)}`。",
                  f"- 控制设备：{', '.join(r['control_devices']) or '无明确字段'}；室外天气：{r['outside_weather']}；模拟数据：{r['simulation_present']}；Day04前处理数据：{r['processed_exists_before_day04']}。",
                  f"- 数值范围：`{json.dumps(r.get('numeric_ranges', {}), ensure_ascii=False)}`。",
                  f"- 限制：{'；'.join(r['limitations'])}。", ""]
    lines += ["## 审计口径与异常规则", "", "- 缺失率按已读取主表的缺失单元格数/总单元格数计算；多温室数据按所有团队主气候表合计。", "- 重复时间戳在每个温室/团队内部计算，不把不同温室同一时刻误判为重复。", "- 采样稳定度是正时间差中等于众数间隔的比例。", "- 温度超出 -20–60 °C、相对湿度超出 0–100% 才计为核心物理范围异常；不会据此自动删除困难样本。", "- 原始 Agricultural Irrigation 长表无时间戳，明确判为不适合时序预测，不构造虚假顺序。", ""]
    return "\n".join(lines)


def run_audit() -> list[dict[str, Any]]:
    records = [load_agc2(), load_iran(), load_agc4(), *load_remaining()]
    config_dir = ML_ROOT / "configs"; config_dir.mkdir(parents=True, exist_ok=True)
    report_dir = ML_ROOT / "data" / "reports"; report_dir.mkdir(parents=True, exist_ok=True)
    docs_dir = PROJECT_ROOT / "docs"
    payload = {"generated_at": "2026-08-22", "raw_data_modified": False, "datasets": records}
    (config_dir / "dataset_registry.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    text = markdown_report(records)
    (docs_dir / "day04-data-audit.md").write_text(text, encoding="utf-8")
    (report_dir / "audit_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return records


if __name__ == "__main__":
    result = run_audit()
    for item in result:
        print(f"{item['dataset_id']}: rows={item['row_count']}, missing={item['missing_rate']:.4%}, usable={item['usable_for_training']}", flush=True)
