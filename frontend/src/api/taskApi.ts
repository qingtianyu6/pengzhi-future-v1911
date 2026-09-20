import { apiClient } from './client'
import type { ApiResponse } from '../types/api'
import type { AddFeedbackInput, CompleteTaskInput, FarmTask, ManualTaskInput, TaskDetail, TaskFeedback, TaskPage, TaskSummary, TaskTrace, VersionedActionInput } from '../types/task'

export interface TaskFilters {
  greenhouse_id?: number; crop_batch_id?: number; source_type?: string; status?: string
  priority?: string; assignee_name?: string; start_time?: string; end_time?: string
  page?: number; page_size?: number
}
export async function getTasks(filters: TaskFilters = {}): Promise<TaskPage> {
  const response = await apiClient.get<ApiResponse<TaskPage>>('/tasks', { params: filters })
  return response.data.data
}
export async function getTaskSummary(greenhouseId?: number): Promise<TaskSummary> {
  const response = await apiClient.get<ApiResponse<TaskSummary>>('/tasks/summary', { params: { greenhouse_id: greenhouseId } })
  return response.data.data
}
export async function getTask(taskId: number): Promise<TaskDetail> {
  const response = await apiClient.get<ApiResponse<TaskDetail>>(`/tasks/${taskId}`)
  return response.data.data
}
export async function getTaskTrace(taskId: number): Promise<TaskTrace> {
  const response = await apiClient.get<ApiResponse<TaskTrace>>(`/tasks/${taskId}/trace`)
  return response.data.data
}
export async function createTask(input: ManualTaskInput): Promise<FarmTask> {
  const response = await apiClient.post<ApiResponse<FarmTask>>('/tasks', input)
  return response.data.data
}
export async function createTaskFromWarning(warningId: number, createdBy: string): Promise<FarmTask> {
  const response = await apiClient.post<ApiResponse<FarmTask>>(`/tasks/from-warning/${warningId}`, { created_by: createdBy })
  return response.data.data
}
export async function createTaskFromDisease(recordId: number, createdBy: string): Promise<FarmTask> {
  const response = await apiClient.post<ApiResponse<FarmTask>>(`/tasks/from-disease/${recordId}`, { created_by: createdBy })
  return response.data.data
}
async function action(path: string, input: object): Promise<FarmTask> {
  const response = await apiClient.post<ApiResponse<FarmTask>>(path, input)
  return response.data.data
}
export const submitTask = (id: number, input: VersionedActionInput) => action(`/tasks/${id}/submit`, input)
export const assignTask = (id: number, input: VersionedActionInput & { assignee_name: string }) => action(`/tasks/${id}/assign`, input)
export const startTask = (id: number, input: VersionedActionInput) => action(`/tasks/${id}/start`, input)
export const completeTask = (id: number, input: CompleteTaskInput) => action(`/tasks/${id}/complete`, input)
export const cancelTask = (id: number, input: VersionedActionInput & { reason: string }) => action(`/tasks/${id}/cancel`, input)
export const reopenTask = (id: number, input: VersionedActionInput & { reason: string }) => action(`/tasks/${id}/reopen`, input)
export async function addTaskFeedback(id: number, input: AddFeedbackInput): Promise<TaskFeedback> {
  const data = new FormData()
  data.append('version', String(input.version)); data.append('operator', input.operator)
  data.append('executed_at', input.executed_at); data.append('result_type', input.result_type)
  data.append('execution_note', input.execution_note)
  if (input.observed_change) data.append('observed_change', input.observed_change)
  data.append('requires_follow_up', String(input.requires_follow_up ?? false))
  if (input.follow_up_note) data.append('follow_up_note', input.follow_up_note)
  input.attachments?.forEach((file) => data.append('attachments', file))
  const response = await apiClient.post<ApiResponse<TaskFeedback>>(`/tasks/${id}/feedback`, data, {
    headers: { 'Content-Type': 'multipart/form-data' }, timeout: 60_000,
  })
  return response.data.data
}
