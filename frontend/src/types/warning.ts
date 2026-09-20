import type { DecisionRecommendation } from './decision'

export type RiskLevel = 'normal' | 'attention' | 'warning' | 'critical'
export type WarningStatus = 'open' | 'acknowledged' | 'resolved' | 'dismissed'
export type WarningCertainty = 'expected' | 'possible' | 'normal' | 'insufficient'

export interface ForecastRiskPoint {
  horizon: number
  forecast_time: string
  risk_score: number | null
  risk_level: RiskLevel
  risk_type: string
  triggered: boolean
  trigger_reasons: string[]
  evidence: Record<string, unknown>
  growth_stage: string | null
  rule_version: string
  evaluated_at: string
  data_source: string | null
  calibration_status: string
  certainty: WarningCertainty
  partial_data: boolean
}

export interface WarningEvent {
  id: number
  greenhouse_id: number
  crop_batch_id: number | null
  crop_type: string
  crop_rule_version: string
  crop_match_status: string
  cross_region_warning: boolean
  expert_calibration_required: boolean
  warning_code: string
  warning_type: string
  severity: RiskLevel
  risk_score: number
  certainty: WarningCertainty
  title: string
  description: string
  evidence_json: Record<string, unknown>
  forecast_start_at: string | null
  forecast_end_at: string | null
  status: WarningStatus
  fingerprint: string
  rule_version: string
  forecast_service_version: string | null
  forecast_methods_json: Record<string, unknown>
  data_source: string | null
  calibration_status: string
  first_triggered_at: string
  last_triggered_at: string
  acknowledged_at: string | null
  acknowledged_by: string | null
  acknowledgement_note: string | null
  resolved_at: string | null
  resolved_by: string | null
  resolution_note: string | null
  dismissed_at: string | null
  dismissed_reason: string | null
  created_at: string
  updated_at: string
}

export interface WarningDetail extends WarningEvent {
  greenhouse_name: string
  batch_code: string | null
  growth_stage: string | null
  recommendations: DecisionRecommendation[]
}

export interface WarningList {
  items: WarningEvent[]
  total: number
  page: number
  page_size: number
}

export interface WarningSummary {
  open_total: number
  attention_total: number
  warning_total: number
  critical_total: number
  acknowledged_total: number
  resolved_today: number
  latest_warning: WarningEvent | null
  greenhouse_distribution: Record<string, number>
}

export interface WarningEvaluation {
  greenhouse_id: number
  crop_batch_id: number | null
  crop_type: string
  crop_rule_version: string
  crop_match_status: string
  cross_region_warning: boolean
  expert_calibration_required: boolean
  growth_stage: string | null
  current_risk: Record<string, unknown>
  future_risks: ForecastRiskPoint[]
  forecast_status: string
  data_quality_issues: string[]
  created_count: number
  updated_count: number
  skipped_count: number
  warnings: WarningEvent[]
  recommendations: DecisionRecommendation[]
  data_source: string | null
  calibration_status: string
  decision_scope: string
  cross_crop_warning: boolean
  evaluated_at: string
}
