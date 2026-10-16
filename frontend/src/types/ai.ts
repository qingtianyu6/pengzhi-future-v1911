export interface AIStatus {
  configured: boolean
  model: string | null
  message: string
  knowledge_items: number
}

export type AIConversationMode = 'general' | 'greenhouse'

export interface AIConversation {
  id: number
  title: string
  greenhouse_id: number | null
  mode: AIConversationMode
  created_at: string
  updated_at: string
}

export interface AIMessage {
  id: number
  conversation_id: number
  pending_actions?: Array<{ greenhouse_id: number; title: string; description: string; action_type: string; priority: 'low' | 'medium' | 'high' | 'urgent'; due_at?: string | null }>
  role: 'user' | 'assistant'
  content: string
  status: 'streaming' | 'completed' | 'stopped' | 'error' | 'superseded'
  reply_to_id: number | null
  model_name: string | null
  created_at: string
}

export interface AIChatPayload {
  require_confirmation?: boolean
  content?: string
  regenerate_message_id?: number
}

export interface AIStreamEvent {
  event: 'meta' | 'tools' | 'delta' | 'done' | 'error' | 'run_started' | 'tool_started' | 'tool_finished' | 'approval_required' | 'recheck_scheduled' | 'run_resumed' | 'run_completed' | 'run_failed'
  data: Record<string, unknown>
}

export interface KnowledgeCatalogItem {
  id: string
  title: string
  topics: string[]
  crops: string[]
}
