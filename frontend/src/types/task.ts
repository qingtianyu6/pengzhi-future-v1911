import type { PaginatedData } from './api'

export type TaskSourceType = 'warning' | 'disease_review' | 'recommendation' | 'manual'
export type TaskStatus = 'draft' | 'pending' | 'in_progress' | 'completed' | 'cancelled'
export type TaskPriority = 'low' | 'medium' | 'high' | 'urgent'
export type FeedbackResult = 'resolved' | 'improved' | 'no_change' | 'worsened' | 'unable_to_verify'

export interface FarmTask {
  id: number; task_code: string; greenhouse_id: number; crop_batch_id: number | null
  crop_type: string; source_type: TaskSourceType; source_id: number | null
  source_warning_id: number | null; source_disease_record_id: number | null
  source_recommendation_id: number | null; title: string; description: string
  action_type: string; priority: TaskPriority; status: TaskStatus; assignee_name: string | null
  planned_start_at: string | null; due_at: string | null; requires_manual_confirmation: boolean
  safety_note: string; evidence_snapshot_json: Record<string, unknown>
  result_snapshot_json: Record<string, unknown> | null; version: number; created_by: string
  created_at: string; updated_at: string; started_at: string | null; completed_at: string | null
  cancelled_at: string | null; cancellation_reason: string | null
}

export interface TaskEvent {
  id: number; task_id: number; event_type: string; from_status: string | null
  to_status: string | null; operator: string; note: string | null
  payload_json: Record<string, unknown>; created_at: string
}

export interface TaskFeedback {
  id: number; task_id: number; operator: string; executed_at: string
  result_type: FeedbackResult; execution_note: string; observed_change: string | null
  attachment_paths_json: string[]; environment_snapshot_json: Record<string, unknown>
  requires_follow_up: boolean; follow_up_note: string | null; created_at: string; updated_at: string
}

export interface TaskDetail extends FarmTask {
  greenhouse: Record<string, unknown>; crop_batch: Record<string, unknown> | null
  source_warning: Record<string, unknown> | null
  source_disease_record: Record<string, unknown> | null
  source_recommendation: Record<string, unknown> | null
  events: TaskEvent[]; feedbacks: TaskFeedback[]; attachments: string[]; causality_notice: string
}

export interface TaskSummary {
  draft_total: number; pending_total: number; in_progress_total: number; completed_today: number
  overdue_total: number; urgent_total: number
}

export interface DashboardTaskSummary extends TaskSummary {
  recent_tasks: FarmTask[]
  source_distribution: Record<string, number>
}

export interface TaskTraceNode {
  type: string; id: number | string | null; title: string; status: string
  occurred_at: string | null; source: string | null; version: string | number | null; summary: string
}
export interface TaskTrace { task_id: number; nodes: TaskTraceNode[]; causality_notice: string }
export type TaskPage = PaginatedData<FarmTask>

export interface ManualTaskInput {
  greenhouse_id: number; crop_batch_id: number; title: string; description: string
  action_type: string; priority: TaskPriority; planned_start_at?: string; due_at?: string
  created_by: string; safety_note?: string
}
export interface VersionedActionInput { version: number; operator: string; note?: string }
export interface CompleteTaskInput extends VersionedActionInput {
  executed_at: string; result_type: FeedbackResult; execution_note: string
  observed_change?: string; requires_follow_up?: boolean; follow_up_note?: string
}
export interface AddFeedbackInput extends CompleteTaskInput { attachments?: File[] }
