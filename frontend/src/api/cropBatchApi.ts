import { apiClient } from './client'
import type { ApiResponse } from '../types/api'
import type { CropBatch, CropBatchInput } from '../types/cropBatch'

export async function getCropBatches(greenhouseId: number): Promise<CropBatch[]> {
  const response = await apiClient.get<ApiResponse<CropBatch[]>>(`/greenhouses/${greenhouseId}/crop-batches`)
  return response.data.data
}

export async function createCropBatch(greenhouseId: number, payload: CropBatchInput): Promise<CropBatch> {
  const response = await apiClient.post<ApiResponse<CropBatch>>(`/greenhouses/${greenhouseId}/crop-batches`, payload)
  return response.data.data
}

export async function updateCropBatch(id: number, payload: Partial<CropBatchInput>): Promise<CropBatch> {
  const response = await apiClient.put<ApiResponse<CropBatch>>(`/crop-batches/${id}`, payload)
  return response.data.data
}
