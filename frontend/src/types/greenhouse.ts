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
}

export interface GreenhouseInput {
  code: string
  name: string
  location: string
  area_mu: number
  status: GreenhouseStatus
  manager_name?: string
}
