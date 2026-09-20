from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.schemas.sensor_data import (
    EnvironmentImportPreview,
    ImportPreviewSample,
    SensorBatchRequest,
    SensorDataInput,
)
from app.services.errors import ServiceError
from app.services.sensor_service import batch_insert

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_IMPORT_ROWS = 5000

COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "recorded_at": (
        "recorded_at", "timestamp", "datetime", "date_time", "time",
        "采集时间", "记录时间", "时间",
    ),
    "temperature": (
        "temperature", "temp", "air_temperature", "air_temperature_c",
        "空气温度", "温度",
    ),
    "air_humidity": (
        "air_humidity", "humidity", "relative_humidity", "air_humidity_pct",
        "空气湿度", "湿度",
    ),
    "soil_moisture": (
        "soil_moisture", "soil_humidity", "substrate_moisture",
        "土壤湿度", "基质湿度",
    ),
    "light_intensity": (
        "light_intensity", "light", "illuminance", "light_klx",
        "光照强度", "光照",
    ),
    "co2_concentration": (
        "co2_concentration", "co2", "co2_ppm", "carbon_dioxide",
        "co₂浓度", "co2浓度", "二氧化碳浓度",
    ),
}

METRIC_RANGES: dict[str, tuple[float, float]] = {
    "temperature": (-20.0, 60.0),
    "air_humidity": (0.0, 100.0),
    "soil_moisture": (0.0, 100.0),
    "light_intensity": (0.0, 150.0),
    "co2_concentration": (200.0, 5000.0),
}

METRIC_LABELS = {
    "temperature": "空气温度",
    "air_humidity": "空气湿度",
    "soil_moisture": "土壤湿度",
    "light_intensity": "光照强度",
    "co2_concentration": "CO₂浓度",
}


def _read_table(filename: str, content: bytes) -> pd.DataFrame:
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".csv":
            # Excel 导出的 CSV 常带 BOM，utf-8-sig 可以一并兼容。
            return pd.read_csv(BytesIO(content), encoding="utf-8-sig")
        if suffix in {".xlsx", ".xlsm"}:
            return pd.read_excel(BytesIO(content), engine="openpyxl")
    except Exception as exc:
        raise ServiceError(422, "数据文件读取失败，请检查文件格式和内容") from exc
    raise ServiceError(422, "仅支持 CSV、XLSX 或 XLSM 文件")


def _find_columns(frame: pd.DataFrame) -> dict[str, str]:
    normalized = {str(column).strip().lower(): str(column) for column in frame.columns}
    result: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            original = normalized.get(alias.strip().lower())
            if original is not None:
                result[canonical] = original
                break
    return result


def _read_upload(upload: UploadFile, content: bytes) -> tuple[str, pd.DataFrame, dict[str, str]]:
    filename = upload.filename or "environment-data"
    if not content:
        raise ServiceError(422, "上传文件为空")
    if len(content) > MAX_FILE_SIZE:
        raise ServiceError(413, "单个数据文件不能超过 10 MB")

    frame = _read_table(filename, content)
    if frame.empty:
        raise ServiceError(422, "数据文件没有可读取的记录")
    if len(frame) > MAX_IMPORT_ROWS:
        raise ServiceError(422, f"单次最多处理 {MAX_IMPORT_ROWS} 条记录")

    columns = _find_columns(frame)
    if "recorded_at" not in columns:
        raise ServiceError(422, "缺少时间列，请使用 recorded_at、timestamp、time 或“采集时间”")
    if not any(name in columns for name in METRIC_RANGES):
        raise ServiceError(422, "至少需要一个环境指标列")
    return filename, frame, columns


def _safe_number(value: object) -> float | None:
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _quality_level(score: int) -> str:
    if score >= 90:
        return "优秀"
    if score >= 75:
        return "良好"
    if score >= 60:
        return "需关注"
    return "较差"


def _build_preview(filename: str, frame: pd.DataFrame, columns: dict[str, str]) -> EnvironmentImportPreview:
    timestamps = pd.to_datetime(frame[columns["recorded_at"]], errors="coerce")
    invalid_time_rows = int(timestamps.isna().sum())
    valid_times = timestamps.dropna().sort_values()
    duplicate_time_rows = int(valid_times.duplicated().sum())

    unique_times = valid_times.drop_duplicates()
    interval_minutes: float | None = None
    continuity_rate = 100.0 if len(unique_times) <= 1 else 0.0
    if len(unique_times) >= 2:
        deltas = unique_times.diff().dropna().dt.total_seconds().div(60)
        positive = deltas[deltas > 0]
        if not positive.empty:
            interval_minutes = round(float(positive.median()), 2)
            duration = (unique_times.iloc[-1] - unique_times.iloc[0]).total_seconds() / 60
            expected = max(1, int(round(duration / interval_minutes)) + 1)
            continuity_rate = min(100.0, round(len(unique_times) / expected * 100, 1))

    metric_columns = [name for name in METRIC_RANGES if name in columns]
    total_metric_cells = len(frame) * len(metric_columns)
    present_cells = 0
    valid_range_cells = 0
    invalid_metric_rows: set[int] = set()

    normalized_metric_values: dict[str, pd.Series] = {}
    for name in metric_columns:
        series = pd.to_numeric(frame[columns[name]], errors="coerce")
        normalized_metric_values[name] = series
        present_cells += int(series.notna().sum())
        lower, upper = METRIC_RANGES[name]
        bad_mask = series.notna() & ~series.between(lower, upper)
        invalid_metric_rows.update(int(index) for index in frame.index[bad_mask])
        valid_range_cells += int((series.notna() & series.between(lower, upper)).sum())

    completeness_rate = 100.0 if total_metric_cells == 0 else round(present_cells / total_metric_cells * 100, 1)
    valid_range_rate = 100.0 if present_cells == 0 else round(valid_range_cells / present_cells * 100, 1)
    time_validity_rate = round((len(frame) - invalid_time_rows) / len(frame) * 100, 1)

    raw_score = (
        completeness_rate * 0.35
        + continuity_rate * 0.30
        + valid_range_rate * 0.25
        + time_validity_rate * 0.10
    )
    quality_score = max(0, min(100, int(round(raw_score))))

    issues: list[str] = []
    if invalid_time_rows:
        issues.append(f"有 {invalid_time_rows} 行时间无法识别")
    if duplicate_time_rows:
        issues.append(f"有 {duplicate_time_rows} 行时间重复，导入时会自动跳过重复时间点")
    if invalid_metric_rows:
        issues.append(f"有 {len(invalid_metric_rows)} 行指标超出允许范围")
    if completeness_rate < 95:
        issues.append(f"环境指标完整率为 {completeness_rate:.1f}%")
    if continuity_rate < 90 and len(unique_times) >= 2:
        issues.append(f"时间序列连续率为 {continuity_rate:.1f}%")
    if not issues:
        issues.append("未发现影响导入的明显数据问题")

    samples: list[ImportPreviewSample] = []
    for offset, (_, row) in enumerate(frame.head(5).iterrows()):
        parsed_time = timestamps.iloc[offset]
        sample_values = {
            name: _safe_number(row[columns[name]]) if name in columns else None
            for name in METRIC_RANGES
        }
        samples.append(ImportPreviewSample(
            recorded_at=None if pd.isna(parsed_time) else parsed_time.to_pydatetime(),
            **sample_values,
        ))

    return EnvironmentImportPreview(
        filename=filename,
        total_rows=len(frame),
        recognized_columns=columns,
        available_metrics=[METRIC_LABELS[name] for name in metric_columns],
        time_start=None if unique_times.empty else unique_times.iloc[0].to_pydatetime(),
        time_end=None if unique_times.empty else unique_times.iloc[-1].to_pydatetime(),
        interval_minutes=interval_minutes,
        duplicate_time_rows=duplicate_time_rows,
        invalid_time_rows=invalid_time_rows,
        out_of_range_rows=len(invalid_metric_rows),
        completeness_rate=completeness_rate,
        continuity_rate=continuity_rate,
        valid_range_rate=valid_range_rate,
        quality_score=quality_score,
        quality_level=_quality_level(quality_score),
        import_ready=invalid_time_rows == 0 and len(invalid_metric_rows) == 0 and quality_score >= 60,
        issues=issues,
        sample_rows=samples,
    )


async def preview_environment_file(upload: UploadFile) -> EnvironmentImportPreview:
    content = await upload.read(MAX_FILE_SIZE + 1)
    filename, frame, columns = _read_upload(upload, content)
    return _build_preview(filename, frame, columns)


async def import_environment_file(
    db: Session,
    greenhouse_id: int,
    upload: UploadFile,
) -> dict[str, object]:
    content = await upload.read(MAX_FILE_SIZE + 1)
    filename, frame, columns = _read_upload(upload, content)
    preview = _build_preview(filename, frame, columns)
    if not preview.import_ready:
        raise ServiceError(422, "数据质量检查未通过，请修正时间、指标范围或数据连续性后再导入")

    timestamps = pd.to_datetime(frame[columns["recorded_at"]], errors="raise")
    items: list[SensorDataInput] = []
    for offset, (_, row) in enumerate(frame.iterrows(), start=2):
        values = {
            name: _safe_number(row[columns[name]]) if name in columns else None
            for name in METRIC_RANGES
        }
        try:
            items.append(SensorDataInput(
                greenhouse_id=greenhouse_id,
                recorded_at=timestamps.iloc[offset - 2].to_pydatetime(),
                source="import",
                quality_flag="valid",
                **values,
            ))
        except ValueError as exc:
            raise ServiceError(422, f"第 {offset} 行数据超出允许范围：{exc}") from exc

    result = batch_insert(db, SensorBatchRequest(items=items))
    return {
        **result.model_dump(),
        "filename": filename,
        "recognized_columns": columns,
        "total_rows": len(frame),
        "quality_score": preview.quality_score,
        "quality_level": preview.quality_level,
    }
