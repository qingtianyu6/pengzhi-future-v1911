import { apiClient } from './client'
import type { ApiResponse } from '../types/api'
import type { DiseaseIdentification, DiseaseModelStatus, DiseaseRecord, DiseaseRecordPage, DiseaseReviewInput } from '../types/disease'

export async function getDiseaseModelStatus(): Promise<DiseaseModelStatus> {
  const response = await apiClient.get<ApiResponse<DiseaseModelStatus>>('/diseases/model-status')
  return response.data.data
}
export async function identifyDisease(greenhouseId: number, cropBatchId: number, image: File): Promise<DiseaseIdentification> {
  const data = new FormData(); data.append('greenhouse_id', String(greenhouseId)); data.append('crop_batch_id', String(cropBatchId)); data.append('image', image)
  const response = await apiClient.post<ApiResponse<DiseaseIdentification>>('/diseases/identify', data, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 60_000 })
  return response.data.data
}
export async function getDiseaseRecords(page = 1, pageSize = 10, greenhouseId?: number): Promise<DiseaseRecordPage> {
  const response = await apiClient.get<ApiResponse<DiseaseRecordPage>>('/diseases/records', { params: { page, page_size: pageSize, greenhouse_id: greenhouseId } })
  return response.data.data
}
export async function reviewDiseaseRecord(recordId: number, input: DiseaseReviewInput): Promise<DiseaseRecord> {
  const response = await apiClient.post<ApiResponse<DiseaseRecord>>(`/diseases/records/${recordId}/review`, input)
  return response.data.data
}
