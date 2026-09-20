import { apiClient } from './client'
import type { ApiResponse } from '../types/api'
import type { EnvironmentPrediction } from '../types/prediction'

export async function getEnvironmentPrediction(greenhouseId: number, horizonHours: number): Promise<EnvironmentPrediction> {
  const response = await apiClient.get<ApiResponse<EnvironmentPrediction>>('/predictions/environment', {
    params: { greenhouse_id: greenhouseId, horizon_hours: horizonHours },
  })
  return response.data.data
}
