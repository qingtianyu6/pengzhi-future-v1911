import type { CropBatch } from './cropBatch'

export type GreenhouseStatus = 'active' | 'paused' | 'closed'

export interface Greenhouse {
  id: number
  code: string
  name: string
  location: string
  area_mu: string
  status: GreenhouseStatus
  manager_name: string | null
  created_at: string
  updated_at: string
  active_batch: CropBatch | null
  last_recorded_at?: string | null
  data_status?: string
  device_count?: number
  online_device_count?: number
}

export interface GreenhouseManagementSummary {
  total: number; connected: number; device_count: number; online_devices: number; online_window_minutes: number
}
export interface GreenhouseDevice {
  greenhouse_id: number; device_id: string; name: string; kind: string; registered: boolean
  last_seen: string | null; online: boolean
}
export interface DeviceBinding { device_id: string; name: string; kind: string }

export interface GreenhouseInput {
  code: string
  name: string
  location: string
  area_mu: number
  status: GreenhouseStatus
  manager_name?: string
}
