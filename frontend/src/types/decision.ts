export type RecommendationStatus = 'pending_review' | 'accepted' | 'rejected' | 'superseded'
export type RecommendationPriority = 'low' | 'medium' | 'high' | 'urgent'

export interface TaskDraft {
  title: string
  greenhouse_id: number
  crop_batch_id: number | null
  crop_type: string
  crop_rule_version: string
  priority: RecommendationPriority
  action_type: string
  description: string
  suggested_execute_before: string | null
  source_warning_id: number
  source_recommendation_id: number
  requires_manual_confirmation: true
}

export interface DecisionRecommendation {
  id: number
  warning_event_id: number
  greenhouse_id: number
  crop_batch_id: number | null
  crop_type: string
  crop_rule_version: string
  recommendation_code: string
  priority: RecommendationPriority
  action_type: string
  title: string
  rationale: string
  action_steps_json: string[]
  execute_before: string | null
  safety_note: string
  status: RecommendationStatus
  rule_version: string
  generated_at: string
  reviewed_at: string | null
  review_note: string | null
  task_draft: TaskDraft | null
}

export interface CurrentDecision {
  greenhouse_id: number
  crop_batch_id: number | null
  crop_type: string
  crop_rule_version: string
  crop_match_status: string
  cross_crop_warning: boolean
  cross_region_warning: boolean
  validation_status: string
  decision_scope: string
  forecast_strategy: string
  growth_stage: string | null
  data_source: string | null
  calibration_status: string
  current_risk_level: string | null
  future_risk_timeline: Array<Record<string, unknown>>
  recommendations: DecisionRecommendation[]
  disclaimer: string
}
