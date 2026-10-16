import { apiClient } from './client'
import type { ApiResponse } from '../types/api'
import type {
  DecisionPlan,
  ExecuteDecisionResponse,
  GreenhouseProfile,
  GreenhouseRiskResponse,
  RiskEvent,
  SimulationData,
  TreatmentEvaluation,
} from '../types/v2Decision'

export async function getGreenhouseRisk(greenhouseId: number): Promise<GreenhouseRiskResponse> {
  const response = await apiClient.get<ApiResponse<GreenhouseRiskResponse>>(`/risk/greenhouse/${greenhouseId}`)
  return response.data.data
}

export async function recalculateRisk(greenhouseId: number, cropType?: string | null, growthStage?: string | null): Promise<RiskEvent> {
  const response = await apiClient.post<ApiResponse<RiskEvent>>('/risk/recalculate', {
    greenhouse_id: greenhouseId,
    crop_type: cropType,
    growth_stage: growthStage,
  })
  return response.data.data
}

export async function generateDecisionPlans(riskEventId: number): Promise<DecisionPlan[]> {
  const response = await apiClient.post<ApiResponse<DecisionPlan[]>>('/decision/generate', { risk_event_id: riskEventId })
  return response.data.data
}

export async function getDecisionPlans(eventId: number): Promise<DecisionPlan[]> {
  const response = await apiClient.get<ApiResponse<DecisionPlan[]>>("/decision", { params: { risk_event_id: eventId } })
  return response.data.data
}

export async function executeDecisionPlan(planId: number, operator = '系统演示员'): Promise<ExecuteDecisionResponse> {
  const response = await apiClient.post<ApiResponse<ExecuteDecisionResponse>>(`/decision/${planId}/execute`, { operator })
  return response.data.data
}

export async function runSimulation(payload: {
  greenhouse_id: number
  decision_plan_id?: number | null
  action_type: 'ventilation' | 'shading' | 'irrigation' | 'dehumidify'
  intensity: number
  duration_minutes: number
}): Promise<SimulationData> {
  const response = await apiClient.post<ApiResponse<SimulationData>>('/simulation/run', payload)
  return response.data.data
}

export async function getGreenhouseProfile(greenhouseId: number): Promise<GreenhouseProfile> {
  const response = await apiClient.get<ApiResponse<GreenhouseProfile>>(`/greenhouses/${greenhouseId}/profile`)
  return response.data.data
}

export async function getTaskEvaluation(taskId: number): Promise<TreatmentEvaluation | null> {
  const response = await apiClient.get<ApiResponse<TreatmentEvaluation | null>>(`/tasks/${taskId}/evaluation`)
  return response.data.data
}

export async function evaluateTask(taskId: number): Promise<TreatmentEvaluation> {
  const response = await apiClient.post<ApiResponse<TreatmentEvaluation>>(`/tasks/${taskId}/evaluate`, { operator: '系统演示员' })
  return response.data.data
}
