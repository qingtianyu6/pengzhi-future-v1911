import { apiClient } from './client'
import type { ApiResponse } from '../types/api'

export interface ActionCandidate {
  id: number
  warning_event_id: number
  action_code: string
  title: string
  description: string
  action_type: string
  expected_response_minutes: number | null
  energy_level: string
  labor_level: string
  evidence_note: string
  status: string
}

export interface OutcomeObservation {
  id: number
  offset_minutes: number
  observed_at: string
  sensor_record_id: number | null
  temperature: number | null
  humidity: number | null
  risk_score: number | null
  manual_status: string | null
  risk_resolved: boolean | null
  notes: string | null
}

export interface Intervention {
  id: number
  warning_event_id: number
  candidate_id: number
  task_id: number | null
  action_type: string
  selection_reason: string
  status: string
  selected_at: string
  started_at: string | null
  finished_at: string | null
  before_snapshot_json: Record<string, unknown>
  observations: OutcomeObservation[]
  causality_notice: string
}

export async function getCandidates(warningId: number) {
  const response = await apiClient.get<ApiResponse<ActionCandidate[]>>(`/warnings/${warningId}/candidates`)
  return response.data.data
}

export async function getInterventions(greenhouseId: number) {
  const response = await apiClient.get<ApiResponse<Intervention[]>>('/interventions', { params: { greenhouse_id: greenhouseId } })
  return response.data.data
}

export async function selectCandidate(id: number, reason: string) {
  const response = await apiClient.post<ApiResponse<Intervention>>(`/candidates/${id}/select`, { reason })
  return response.data.data
}

export async function recordObservation(id: number, offsetMinutes: 30 | 60, manualStatus: string, riskResolved: boolean | null, notes: string) {
  const response = await apiClient.post<ApiResponse<Intervention>>(`/interventions/${id}/observations`, {
    offset_minutes: offsetMinutes,
    manual_status: manualStatus || null,
    risk_resolved: riskResolved,
    notes: notes || null,
  })
  return response.data.data
}
