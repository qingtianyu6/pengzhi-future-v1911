import { apiClient } from './client'
import type { ApiResponse } from '../types/api'
import type { DashboardSummary } from '../types/dashboard'

export async function getDashboardSummary(greenhouseId: number): Promise<DashboardSummary> {
  const response = await apiClient.get<ApiResponse<DashboardSummary>>('/dashboard/summary', {
    params: { greenhouse_id: greenhouseId },
  })
  return response.data.data
}
