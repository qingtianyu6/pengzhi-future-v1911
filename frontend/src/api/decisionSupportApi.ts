import { apiClient } from './client'
import type { ApiResponse } from '../types/api'

export type CostLevel = 'none' | 'low' | 'medium' | 'high'

export interface CandidateEvidence {
  candidate_id: number
  action_code: string
  applicability: 'suitable' | 'needs_site_check' | 'unknown'
  applicability_note: string
  historical_case_count: number
  measured_60min_count: number
  observed_risk_decrease_count: number
  manually_resolved_count: number
  median_temperature_change_c: number | null
  median_humidity_change_pct: number | null
  evidence_level: string
}

export interface DecisionSupport {
  status: 'ready' | 'insufficient_context'
  candidate_evidence: CandidateEvidence[]
  current_risk_score: number | null
  scenarios: {
    action_code: string
    title: string
    basis: 'historical_median' | 'rule_assumption' | 'recent_trend'
    supporting_cases: number
    points: {
      offset_minutes: 30 | 60
      temperature_c: number | null
      humidity_pct: number | null
      risk_score: number | null
      risk_lower: number | null
      risk_upper: number | null
    }[]
    note: string
  }[]
  outcome_model_status: 'insufficient_data' | 'observational_estimates'
  outcome_estimates: {
    action_code: string
    title: string
    measured_cases: number
    observed_risk_change_mean: number | null
    smoothed_risk_change: number | null
    observed_difference_vs_observe: number | null
    observed_resolution_rate: number | null
    energy_level: string
    labor_level: string
    within_cost_limit: boolean
    comparison_score: number | null
    note: string
  }[]
  explanation: string
}

export async function getDecisionSupport(warningId: number, maxEnergyLevel: CostLevel, maxLaborLevel: CostLevel) {
  const response = await apiClient.get<ApiResponse<DecisionSupport>>(`/warnings/${warningId}/decision-support`, {
    params: { max_energy_level: maxEnergyLevel, max_labor_level: maxLaborLevel },
  })
  return response.data.data
}
