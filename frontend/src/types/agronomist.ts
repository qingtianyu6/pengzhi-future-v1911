export interface Observation {
  id: number; study_id: number | null; observed_at: string; phase: string; zone: string; note: string; metrics: Record<string, number>
}
export interface EnvironmentPoint { id: number; recorded_at: string; temperature: number | null; air_humidity: number | null; soil_moisture: number | null }
export interface ScenarioCandidate {
  name: string; action: string; intensity: number
  timeline: { minute: number; temperature: number; humidity: number }[]
  end: { minute: number; temperature: number; humidity: number }
}
export interface Comparison { zone: string; metric: string; before: number; after: number; delta: number; before_n: number; after_n: number }
export interface ResearchRecord {
  id: number; greenhouse_id: number; crop_batch_id: number | null
  kind: 'scenario' | 'study' | 'skill' | 'goal'; title: string; status: string; version: number; created_at: string; updated_at: string
  payload: {
    baseline?: { sensor_record_id: number; recorded_at: string; temperature: number; humidity: number }
    duration_minutes?: number; candidates?: ScenarioCandidate[]; method?: string; note?: string
    question?: string; hypothesis?: string; alternatives?: string[]; protocol?: string[]
    conclusion?: { comparisons: Comparison[]; interpretation: string; note?: string } | null
    source_study_id?: number; steps?: { title: string; action_type: string; description: string; depends_on: number[] }[] | string[]
    applicability?: string; validation?: string; goal?: string; task_ids?: number[]; planner?: string
    links?: Record<string, ResearchRecord>; source_snapshot?: ResearchRecord
  }
}
export interface GrowthArchive {
  greenhouse: { id: number; name: string; code: string }
  batch: { id: number; batch_code: string; variety: string; growth_stage: string; planted_at: string; status: string; growth_day: number } | null
  batches: { id: number; batch_code: string; status: string }[]
  latest: EnvironmentPoint | null; fresh: boolean; history: EnvironmentPoint[]
  metrics: Record<string, { mean: number; min: number; max: number } | null>
  sample_count: number; gaps: string[]; observations: Observation[]
  timeline: { id: string; at: string; type: string; title: string; detail: string; source_id: number }[]
  task_counts: Record<string, number>; open_warnings: number; window_note: string
}
export interface ResearchWorkspace { records: ResearchRecord[]; tasks: { id: number; title: string; status: string }[] }
export interface ResearchContext { greenhouse_id: number; crop_batch_id?: number }
