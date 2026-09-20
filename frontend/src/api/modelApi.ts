import { apiClient } from './client'
import type { ApiResponse } from '../types/api'
import type { ModelOverview } from '../types/model'

export async function getModelOverview(): Promise<ModelOverview> {
  const response = await apiClient.get<ApiResponse<ModelOverview>>('/models/overview')
  return response.data.data
}
