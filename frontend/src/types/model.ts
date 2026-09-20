export interface ModelMetric {
  mae: number | null
  rmse: number | null
  improvement_pct: number | null
  method: string | null
}

export interface ModelOverview {
  environment: {
    name: string
    version: string
    status: string
    prediction_window_hours: number
    algorithms: string[]
    training_crop: string
    temperature_h1: ModelMetric
    humidity_h1: ModelMetric
  }
  disease: {
    name: string
    version: string
    status: string
    architecture: string
    class_count: number
    confidence_threshold: number | null
    internal_accuracy: number | null
    internal_macro_f1: number | null
    accepted_accuracy: number | null
    external_accuracy: number | null
    external_macro_f1: number | null
  }
}
