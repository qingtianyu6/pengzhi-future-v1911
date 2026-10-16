import type { FarmTask } from './task'

export interface RiskContribution {
  key: string
  label: string
  feature_score: number
  weight: number
  value: number
}

export interface RiskItem {
  disease_type: string
  disease_name: string
  current_score: number
  risk_24h: number
  risk_48h: number
  risk_72h: number
  risk_level: string
  trend: string
  factors: {
    contributions: RiskContribution[]
    features: Record<string, number | string | null>
    rule: Record<string, unknown>
  }
  explanation: string
}

export interface RiskEvent {
  id: number
  greenhouse_id: number
  crop_batch_id: number | null
  risk_type: string
  disease_type: string
  crop_type: string
  growth_stage: string | null
  current_score: number
  risk_24h: number
  risk_48h: number
  risk_72h: number
  risk_level: string
  trend: string
  factors_json: RiskItem['factors']
  explanation: string
  status: string
  created_at: string
}

export interface GreenhouseRiskResponse {
  greenhouse_id: number
  crop_type: string
  growth_stage: string | null
  data_status: string
  current_environment: Record<string, unknown>
  risks: RiskItem[]
  top_event: RiskEvent | null
}

export interface DecisionPlan {
  id: number
  risk_event_id: number
  greenhouse_id: number
  task_id: number | null
  plan_name: string
  actions_json: Array<Record<string, unknown>>
  expected_result_json: Record<string, number | string>
  score: number
  status: string
  rationale: string
  created_at: string
}

export interface SimulationData {
  id: number | null
  greenhouse_id: number
  action_type: string
  intensity: number
  duration_minutes: number
  baseline: Record<string, number | string | null>
  timeline: Array<Record<string, number | string | null>>
  estimated_risk_after: number | null
  note: string
}

export interface TreatmentEvaluation {
  id: number
  task_id: number
  greenhouse_id: number
  risk_event_id: number | null
  decision_plan_id: number | null
  before_snapshot_json: Record<string, unknown>
  after_snapshot_json: Record<string, unknown>
  environment_change_json: Record<string, number>
  risk_change: number
  effect_score: number
  effect_level: string
  recommendation: string
  created_at: string
}

export interface GreenhouseProfile {
  id: number
  greenhouse_id: number
  heat_response: number
  cooling_response: number
  humidity_response: number
  ventilation_response: number
  risk_sensitivity: number
  sample_count: number
  traits_json: Record<string, string>
  updated_at: string
}

export interface ExecuteDecisionResponse {
  plan: DecisionPlan
  task: FarmTask
}
