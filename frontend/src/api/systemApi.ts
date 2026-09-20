import { apiClient } from './client'
import type { ApiResponse, HealthData } from '../types/api'

export async function getHealth(): Promise<HealthData> {
  const response = await apiClient.get<ApiResponse<HealthData>>('/health')
  return response.data.data
}
