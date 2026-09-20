import type { CropBatch } from './cropBatch'
import type { Greenhouse } from './greenhouse'
import type { SensorReading, SensorSource } from './sensor'
import type { DashboardTaskSummary } from './task'

export interface MetricChanges {
  temperature: number | null
  air_humidity: number | null
  soil_moisture: number | null
  light_intensity: number | null
  co2_concentration: number | null
}

export interface RiskAssessment {
  data_status: 'sufficient' | 'insufficient'
  growth_stage: string | null
  component_scores: Record<string, number>
  overall_score: number | null
  level: string
  reasons: string[]
  rule_version: string
  crop_type: string
  rule_scope: string
  expert_calibration_required: boolean
  disclaimer: string
}

export interface DashboardSummary {
  greenhouse: Greenhouse
  active_batch: CropBatch | null
  latest_environment: SensorReading | null
  changes: MetricChanges | null
  risk: RiskAssessment
  today_abnormal_count: number
  trend_24h: SensorReading[]
  data_source: SensorSource | null
  data_source_label: string | null
  data_updated_at: string | null
  empty_state: boolean
  warning_summary: {
    highest_risk_level: string
    open_warning_count: number
    latest_warning_id: number | null
    latest_warning_title: string | null
    future_risk_timeline: Array<Record<string, unknown>>
    latest_recommendation_id: number | null
    latest_recommendation_title: string | null
    forecast_strategy: string
    validation_status: string
    cross_region_warning: boolean
  }
  task_summary: DashboardTaskSummary
}
