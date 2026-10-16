from __future__ import annotations
from dataclasses import dataclass
from datetime import timedelta
from statistics import median
from app.models import SensorData

@dataclass(frozen=True)
class EnvironmentalFeatures:
    latest_temperature: float | None
    latest_humidity: float | None
    latest_co2: float | None
    latest_light: float | None
    avg_humidity_6h: float | None
    avg_temperature_12h: float | None
    high_humidity_hours: float
    diurnal_temp_diff: float
    humidity_trend_per_hour: float
    temperature_trend_per_hour: float
    sample_count: int

def _avg(values):
    return round(sum(values)/len(values), 2) if values else None

def _slope(records, attr):
    valid=[r for r in records if getattr(r,attr) is not None]
    if len(valid)<2:return 0.0
    hours=(valid[-1].recorded_at-valid[0].recorded_at).total_seconds()/3600
    return round((getattr(valid[-1],attr)-getattr(valid[0],attr))/hours,2) if hours>0 else 0.0

def build_features(records: list[SensorData]) -> EnvironmentalFeatures:
    ordered=sorted(records,key=lambda r:r.recorded_at)
    latest=ordered[-1] if ordered else None
    end=latest.recorded_at if latest else None
    def window(hours):
        return [r for r in ordered if r.recorded_at>=end-timedelta(hours=hours)] if end else []
    last6,last12,last24=window(6),window(12),window(24)
    intervals=[(b.recorded_at-a.recorded_at).total_seconds()/3600 for a,b in zip(last24,last24[1:]) if b.recorded_at>a.recorded_at]
    typical=median(intervals) if intervals else 0
    duration=0.0
    # Measure the current continuous run; missing values or gaps break it.
    for a,b in reversed(list(zip(last24,last24[1:]))):
        gap=(b.recorded_at-a.recorded_at).total_seconds()/3600
        if a.air_humidity is None or b.air_humidity is None or min(a.air_humidity,b.air_humidity)<82 or gap>min(2.0,typical*1.75):break
        duration+=gap
    temps=[float(r.temperature) for r in last24 if r.temperature is not None]
    return EnvironmentalFeatures(
        latest_temperature=latest.temperature if latest else None,
        latest_humidity=latest.air_humidity if latest else None,
        latest_co2=latest.co2_concentration if latest else None,
        latest_light=latest.light_intensity if latest else None,
        avg_humidity_6h=_avg([r.air_humidity for r in last6 if r.air_humidity is not None]),
        avg_temperature_12h=_avg([r.temperature for r in last12 if r.temperature is not None]),
        high_humidity_hours=round(duration,2),
        diurnal_temp_diff=round(max(temps)-min(temps),2) if temps else 0,
        humidity_trend_per_hour=_slope(last6,'air_humidity'),
        temperature_trend_per_hour=_slope(last6,'temperature'),sample_count=len(ordered))
