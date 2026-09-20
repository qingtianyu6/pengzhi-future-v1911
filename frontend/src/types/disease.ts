import type { PaginatedData } from './api'

export type RecognitionStatus = 'recognized' | 'review_required' | 'low_confidence' | 'model_unavailable'
export type ReviewStatus = 'unreviewed' | 'confirmed' | 'corrected' | 'rejected'
export interface SupportedDiseaseClass { key: string; name: string }
export interface TopPrediction { class_key: string; class_name: string; confidence: number }
export interface DiseaseModelStatus {
  service_status: string; model_status: string; model_version: string; target_crop: 'tomato'
  supported_classes: SupportedDiseaseClass[]; input_size: number; confidence_threshold: number | null
  internal_metrics_summary: { accuracy?: number | null; macro_f1?: number | null }
  external_metrics_summary: { accuracy?: number | null; macro_f1?: number | null }
  validation_status: 'validated_on_public_dataset' | 'under_evaluation' | 'not_validated'; limitations: string[]
}
export interface DiseaseIdentification {
  record_id: number; recognition_status: RecognitionStatus; predicted_class: string | null
  predicted_class_name: string | null; confidence: number | null; top3_predictions: TopPrediction[]
  model_version: string; target_crop: 'tomato'
  validation_status: 'validated_on_public_dataset' | 'under_evaluation' | 'not_validated'
  limitations: string[]; safety_notice: string; duplicate_image: boolean
}
export interface DiseaseRecord {
  id: number; greenhouse_id: number; crop_batch_id: number; crop_type: string; image_path: string
  image_sha256: string; original_filename: string; predicted_class: string | null
  predicted_class_name: string | null; confidence: number | null; top3_predictions: TopPrediction[]
  recognition_status: RecognitionStatus; model_version: string; model_status: string
  validation_status: string; review_status: ReviewStatus; reviewed_class: string | null
  review_note: string | null; created_at: string; updated_at: string
}
export type DiseaseRecordPage = PaginatedData<DiseaseRecord>
export interface DiseaseReviewInput {
  review_status: Exclude<ReviewStatus, 'unreviewed'>; reviewed_class?: string; review_note?: string
}
