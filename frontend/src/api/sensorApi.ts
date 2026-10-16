import { apiClient } from './client'
import type { ApiResponse } from '../types/api'
import type { SensorHistory, SensorIngestStatus, SensorReading } from '../types/sensor'

export async function getLatestSensor(greenhouseId: number): Promise<SensorReading | null> {
  const response = await apiClient.get<ApiResponse<SensorReading | null>>('/sensors/latest', {
    params: { greenhouse_id: greenhouseId },
  })
  return response.data.data
}

export interface HistoryQuery {
  greenhouse_id: number
  start_time: string
  end_time: string
  page?: number
  page_size?: number
}

export async function getSensorHistory(query: HistoryQuery): Promise<SensorHistory> {
  const response = await apiClient.get<ApiResponse<SensorHistory>>('/sensors/history', { params: query })
  const first = response.data.data
  if (first.total <= first.items.length || (query.page ?? 1) !== 1) return first
  const remaining = Math.ceil(first.total / (query.page_size ?? 100))
  const pages = await Promise.all(Array.from({ length: remaining - 1 }, (_, index) =>
    apiClient.get<ApiResponse<SensorHistory>>('/sensors/history', { params: { ...query, page: index + 2 } })))
  const complete = [...first.items, ...pages.flatMap(r => r.data.data.items)]
  // Keep the full time coverage while limiting the number of points rendered.
  if (complete.length <= 1000) return { ...first, items: complete }
  const size = Math.ceil(complete.length / 1000)
  const items = []
  const metrics = ['temperature', 'air_humidity', 'soil_moisture', 'light_intensity', 'co2_concentration'] as const
  for (let i = 0; i < complete.length; i += size) {
    const bucket = complete.slice(i, i + size), item = { ...bucket[bucket.length - 1] }
    for (const key of metrics) { const values = bucket.map(r => r[key]).filter((v): v is number => v !== null); item[key] = values.length ? values.reduce((a,b)=>a+b,0)/values.length : null }
    if (bucket.some(r => r.quality_flag !== 'valid')) item.quality_flag = 'suspect'
    items.push(item)
  }
  return { ...first, items, source_note: `完整覆盖${complete.length}条原始记录，按时间聚合显示${items.length}个点` }
}


export interface ImportPreviewSample {
  recorded_at: string | null
  temperature: number | null
  air_humidity: number | null
  soil_moisture: number | null
  light_intensity: number | null
  co2_concentration: number | null
}

export interface EnvironmentImportPreview {
  filename: string
  total_rows: number
  recognized_columns: Record<string, string>
  available_metrics: string[]
  time_start: string | null
  time_end: string | null
  interval_minutes: number | null
  duplicate_time_rows: number
  invalid_time_rows: number
  out_of_range_rows: number
  completeness_rate: number
  continuity_rate: number
  valid_range_rate: number
  quality_score: number
  quality_level: string
  import_ready: boolean
  issues: string[]
  sample_rows: ImportPreviewSample[]
}

export async function previewSensorFile(file: File): Promise<EnvironmentImportPreview> {
  const data = new FormData()
  data.append('file', file)
  const response = await apiClient.post<ApiResponse<EnvironmentImportPreview>>('/sensors/import-preview', data, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000,
  })
  return response.data.data
}

export interface SensorFileImportResult {
  success_count: number
  skipped_count: number
  failed_count: number
  message: string
  filename: string
  total_rows: number
  recognized_columns: Record<string, string>
  quality_score: number
  quality_level: string
}

export async function importSensorFile(greenhouseId: number, file: File): Promise<SensorFileImportResult> {
  const data = new FormData()
  data.append('greenhouse_id', String(greenhouseId))
  data.append('file', file)
  const response = await apiClient.post<ApiResponse<SensorFileImportResult>>('/sensors/import-file', data, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000,
  })
  return response.data.data
}


export async function getSensorIngestStatus(): Promise<SensorIngestStatus> {
  const response = await apiClient.get<ApiResponse<SensorIngestStatus>>('/v1/ingest/status')
  return response.data.data
}
