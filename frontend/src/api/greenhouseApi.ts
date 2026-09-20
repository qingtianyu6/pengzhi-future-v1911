import { apiClient } from './client'
import type { ApiResponse, PaginatedData } from '../types/api'
import type { Greenhouse, GreenhouseInput, GreenhouseStatus } from '../types/greenhouse'

export interface GreenhouseQuery {
  page?: number
  page_size?: number
  status?: GreenhouseStatus
  keyword?: string
}

export async function getGreenhouses(query: GreenhouseQuery = {}): Promise<PaginatedData<Greenhouse>> {
  const response = await apiClient.get<ApiResponse<PaginatedData<Greenhouse>>>('/greenhouses', { params: query })
  return response.data.data
}

export async function getGreenhouse(id: number): Promise<Greenhouse> {
  const response = await apiClient.get<ApiResponse<Greenhouse>>(`/greenhouses/${id}`)
  return response.data.data
}

export async function createGreenhouse(payload: GreenhouseInput): Promise<Greenhouse> {
  const response = await apiClient.post<ApiResponse<Greenhouse>>('/greenhouses', payload)
  return response.data.data
}

export async function updateGreenhouse(id: number, payload: Partial<GreenhouseInput>): Promise<Greenhouse> {
  const response = await apiClient.put<ApiResponse<Greenhouse>>(`/greenhouses/${id}`, payload)
  return response.data.data
}

export async function deleteGreenhouse(id: number): Promise<void> {
  await apiClient.delete<ApiResponse<null>>(`/greenhouses/${id}`)
}
