import { apiClient } from './client'
import type { ApiResponse } from '../types/api'
import type { RiskLevel, WarningDetail, WarningEvaluation, WarningEvent, WarningList, WarningStatus, WarningSummary } from '../types/warning'

export interface WarningFilters {
  greenhouse_id?: number
  severity?: RiskLevel
  status?: WarningStatus
  warning_type?: string
  start_time?: string
  end_time?: string
  page?: number
  page_size?: number
}

export async function evaluateWarnings(greenhouseId: number): Promise<WarningEvaluation> {
  const response=await apiClient.post<ApiResponse<WarningEvaluation>>('/warnings/evaluate',{greenhouse_id:greenhouseId})
  return response.data.data
}
export async function getWarnings(filters:WarningFilters={}):Promise<WarningList>{const response=await apiClient.get<ApiResponse<WarningList>>('/warnings',{params:filters});return response.data.data}
export async function getWarningSummary():Promise<WarningSummary>{const response=await apiClient.get<ApiResponse<WarningSummary>>('/warnings/summary');return response.data.data}
export async function getWarning(id:number):Promise<WarningDetail>{const response=await apiClient.get<ApiResponse<WarningDetail>>(`/warnings/${id}`);return response.data.data}
export async function acknowledgeWarning(id:number,note:string):Promise<WarningEvent>{const response=await apiClient.post<ApiResponse<WarningEvent>>(`/warnings/${id}/acknowledge`,{operator:'管理员',note});return response.data.data}
export async function resolveWarning(id:number,note:string):Promise<WarningEvent>{const response=await apiClient.post<ApiResponse<WarningEvent>>(`/warnings/${id}/resolve`,{operator:'管理员',note});return response.data.data}
export async function dismissWarning(id:number,reason:string):Promise<WarningEvent>{const response=await apiClient.post<ApiResponse<WarningEvent>>(`/warnings/${id}/dismiss`,{operator:'管理员',reason});return response.data.data}
