export type SensorSource = 'sensor' | 'import'
export type QualityFlag = 'valid' | 'suspect' | 'missing'

export interface SensorReading {
  id: number
  greenhouse_id: number
  recorded_at: string
  device_id?: string | null
  temperature: number | null
  air_humidity: number | null
  soil_moisture: number | null
  light_intensity: number | null
  co2_concentration: number | null
  source: SensorSource
  quality_flag: QualityFlag
}

export interface SensorHistory {
  items: SensorReading[]
  total: number
  page: number
  page_size: number
  start_time: string
  end_time: string
  source_note: string
}


export interface SensorIngestStatus {
  endpoint: string
  auth_required: boolean
  header_name: string
  accepted_metrics: string[]
  max_batch_size: number
}
