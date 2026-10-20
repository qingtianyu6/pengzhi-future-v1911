import { apiClient } from './client'
import { isGuestMode } from './guestMode'
import { guestAgronomist } from './agronomistGuest'
import type { ApiResponse } from '../types/api'
import type { GrowthArchive, ResearchContext, ResearchRecord, ResearchWorkspace } from '../types/agronomist'

async function request<T>(path: string, method: 'get' | 'post', data: object): Promise<T> {
  if (isGuestMode()) return guestAgronomist(path, method, data) as T
  const response = await apiClient.request<ApiResponse<T>>({ url: `/agronomist/${path}`, method,
    timeout: path === 'goals' ? 90000 : 15000,
    ...(method === 'get' ? { params: data } : { data }) })
  return response.data.data
}
export const getGrowthArchive = (context: ResearchContext) => request<GrowthArchive>('archive', 'get', context)
export const getResearchWorkspace = (context: ResearchContext) => request<ResearchWorkspace>('records', 'get', context)
export const addCropObservation = (data: ResearchContext & { note: string; zone: string; phase: string; observed_at?: string; study_id?: number; metrics: Record<string, number> }) => request<{ id: number }>('observations', 'post', data)
export const compareScenarios = (data: ResearchContext & { duration_minutes: number; intensity: number }) => request<ResearchRecord>('scenarios', 'post', data)
export const createResearchStudy = (data: ResearchContext & { question: string; hypothesis: string; scenario_id?: number }) => request<ResearchRecord>('studies', 'post', data)
export const createAgronomyGoal = (data: ResearchContext & { goal: string; scenario_id?: number; skill_id?: number; study_id?: number; use_ai?: boolean }) => request<ResearchRecord>('goals', 'post', data)
export const actOnResearchRecord = (id: number, version: number, action: string, note = '') => request<ResearchRecord>(`records/${id}/actions`, 'post', { version, action, note })
