import type { SensorReading } from '../../types/sensor'
import type { EnvironmentPrediction, PredictionPoint } from '../../types/prediction'

export const environmentMetrics = [
  { key: 'temperature', label: '空气温度', short: '温度', unit: '°C', digits: 1, forecast: 'temperature_c', bounds: 'air_temperature_c' },
  { key: 'air_humidity', label: '空气湿度', short: '空气湿度', unit: '%', digits: 0, forecast: 'air_humidity_pct', bounds: 'air_humidity_pct' },
  { key: 'soil_moisture', label: '土壤湿度', short: '土壤湿度', unit: '%', digits: 0 },
  { key: 'light_intensity', label: '光照强度', short: '光照', unit: 'klx', digits: 1 },
  { key: 'co2_concentration', label: 'CO₂浓度', short: 'CO₂', unit: 'ppm', digits: 0 },
] as const
export type MetricKey = typeof environmentMetrics[number]['key']
export type TimelineValue = [number, number | null]
const number = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)

export function buildTimeline(history: SensorReading[], prediction: EnvironmentPrediction | null, key: MetricKey, now: number, hours: number, horizon: number) {
  const metric = environmentMetrics.find(m => m.key === key)!
  const start = now - hours * 3600_000
  const end = now + horizon * 3600_000
  const unique = new Map(history.map(row => [Date.parse(row.recorded_at), row]))
  const rows = [...unique].filter(([t]) => Number.isFinite(t) && t >= start && t <= now).sort(([a], [b]) => a - b)
  const deltas = rows.slice(1).map(([t], i) => t - rows[i][0]).filter(d => d > 0).sort((a, b) => a - b)
  const cadence = deltas[Math.floor((deltas.length - 1) / 2)] || 3600_000
  const measured: TimelineValue[] = []
  rows.forEach(([t, row], i) => {
    if (i && t - rows[i - 1][0] > cadence * 2.5) measured.push([rows[i - 1][0] + 1, null])
    measured.push([t, number(row[key]) ? row[key] : null])
  })
  const forecast: TimelineValue[] = [], lower: TimelineValue[] = [], span: TimelineValue[] = []
  if ('forecast' in metric && prediction?.status === 'ready') {
    const forecastKey = metric.forecast as keyof PredictionPoint
    const points = prediction.predictions.filter(p => {
      const t = Date.parse(p.forecast_time)
      return t > now && t <= end && number(p[forecastKey])
    }).sort((a, b) => Date.parse(a.forecast_time) - Date.parse(b.forecast_time))
    const anchor = rows.find(([t]) => t === Date.parse(prediction.input_end_time || ''))
    if (points.length && anchor && now - anchor[0] <= cadence * 1.5 && number(anchor[1][key])) {
      forecast.push([anchor[0], anchor[1][key]])
      // A zero-width interval at an actual anchor does not invent an uncertainty estimate.
      lower.push([anchor[0], anchor[1][key]]); span.push([anchor[0], 0])
    }
    points.forEach(p => {
      const t = Date.parse(p.forecast_time)
      const previous = forecast.at(-1)?.[0]
      if (previous && t - previous > 1.5 * 3600_000) {
        forecast.push([previous + 1, null]); lower.push([previous + 1, null]); span.push([previous + 1, null])
      }
      forecast.push([t, p[forecastKey] as number])
      const lo = p.lower_bounds[metric.bounds], hi = p.upper_bounds[metric.bounds]
      const valid = number(lo) && number(hi) && hi >= lo
      lower.push([t, valid ? lo : null]); span.push([t, valid ? hi - lo : null])
    })
  }
  const intervalAvailable = span.some(([, v]) => number(v) && v > 0)
  return { metric, start, end, now, measured, forecast, lower: intervalAvailable ? lower : [], span: intervalAvailable ? span : [], intervalAvailable,
    predictionAvailable: forecast.some(([t, v]) => t > now && number(v)),
    latest: rows.at(-1), stale: !rows.length || now - rows.at(-1)![0] > 2 * 3600_000 }
}
