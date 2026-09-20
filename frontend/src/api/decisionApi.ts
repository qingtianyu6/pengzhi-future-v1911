import { apiClient } from './client'
import type { ApiResponse } from '../types/api'
import type { CurrentDecision, DecisionRecommendation } from '../types/decision'

export async function getCurrentDecisions(greenhouseId:number):Promise<CurrentDecision>{const response=await apiClient.get<ApiResponse<CurrentDecision>>('/decisions/current',{params:{greenhouse_id:greenhouseId}});return response.data.data}
export async function getDecision(id:number):Promise<DecisionRecommendation>{const response=await apiClient.get<ApiResponse<DecisionRecommendation>>(`/decisions/${id}`);return response.data.data}
export async function acceptDecision(id:number,note:string):Promise<DecisionRecommendation>{const response=await apiClient.post<ApiResponse<DecisionRecommendation>>(`/decisions/${id}/accept`,{operator:'管理员',note});return response.data.data}
export async function rejectDecision(id:number,note:string):Promise<DecisionRecommendation>{const response=await apiClient.post<ApiResponse<DecisionRecommendation>>(`/decisions/${id}/reject`,{operator:'管理员',note});return response.data.data}
