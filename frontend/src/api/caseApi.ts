import { apiClient } from './client'
import type { ApiResponse } from '../types/api'
import type { OutcomeObservation } from './interventionApi'

export interface ProductionCase {
  id: number
  case_code: string
  warning_event_id: number
  warning_title: string
  context: {
    greenhouse_name: string
    crop_type: string
    growth_stage: string | null
    temperature_c: number | null
    air_humidity_pct: number | null
    risk_type: string
  }
  selected_action_code: string
  selected_action_title: string
  selection_reason: string
  execution: {
    task_status: string | null
    assignee_name: string | null
    started_at: string | null
    finished_at: string | null
    feedback_notes: string[]
  }
  observations: OutcomeObservation[]
  complete: boolean
  quality_flags: string[]
}

export interface SimilarCases {
  status: 'ready' | 'insufficient_context'
  total_eligible_cases: number
  matches: { case: ProductionCase; distance: number; feature_coverage: number }[]
  action_evidence: {
    action_code: string
    action_title: string
    case_count: number
    with_60min_measurement: number
    observed_risk_decrease_count: number
    manually_resolved_count: number
    median_temperature_change_c: number | null
    median_humidity_change_pct: number | null
    evidence_level: string
  }[]
  explanation: string
}

export async function getCases(greenhouseId: number) {
  const response = await apiClient.get<ApiResponse<{ items: ProductionCase[]; total: number }>>('/cases', {
    params: { greenhouse_id: greenhouseId, page_size: 5 },
  })
  return response.data.data
}

export async function getSimilarCases(warningId: number) {
  const response = await apiClient.get<ApiResponse<SimilarCases>>(`/warnings/${warningId}/similar-cases`)
  return response.data.data
}
