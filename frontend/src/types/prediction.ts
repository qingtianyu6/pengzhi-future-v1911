export type PredictionStatus = 'ready' | 'not_trained' | 'insufficient_data' | 'schema_mismatch' | 'under_evaluation'
export type ModelStatus = 'baseline_ready' | 'ready' | 'under_evaluation' | 'not_trained' | 'schema_mismatch'

export interface PredictionHistoryPoint {
  timestamp: string
  temperature_c: number
  air_humidity_pct: number
}

export interface PredictionPoint {
  forecast_time: string
  horizon: number
  temperature_c: number | null
  air_humidity_pct: number | null
  par_umol_m2_s: number | null
  lower_bounds: Record<string, number>
  upper_bounds: Record<string, number>
  forecast_method: string
  method_version: string
  methods: Record<string, string>
  units: Record<string, string>
}

export interface EnvironmentPrediction {
  greenhouse_id: number
  status: PredictionStatus
  forecast_service_status: PredictionStatus
  forecast_method: string | null
  forecast_method_labels: string[]
  model_status: ModelStatus
  effective_model_status: 'hybrid_ready' | 'baseline_ready' | 'under_evaluation' | 'not_trained'
  ml_candidate_status: 'ready' | 'under_evaluation'
  forecast_strategy: 'per_target_per_horizon_hybrid'
  ml_output_count: number
  total_output_count: number
  crop: string | null
  crop_type: string
  crop_match_status: 'matched_public_tomato' | 'mismatched'
  model_name: string | null
  model_type: string | null
  model_version: string | null
  training_crop: string
  training_region: string
  training_domain: string
  validation_status: 'validated_on_public_dataset' | 'under_evaluation' | 'not_validated'
  calibration_status: string
  decision_scope: 'decision_support'
  cross_crop_warning: boolean
  cross_region_warning: boolean
  input_data_source: string | null
  input_end_time: string | null
  history_hours: number
  horizon_hours: number
  predictions: PredictionPoint[]
  history: PredictionHistoryPoint[]
  rules_status: 'tomato_rule_active' | 'rules_unavailable'
  warnings: string[]
  generated_at: string
}
