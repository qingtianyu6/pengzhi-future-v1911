import type { AIChatPayload, AIConversation, AIConversationMode, AIMessage, AIStatus, AIStreamEvent, KnowledgeCatalogItem } from '../types/ai'
import { createTask, getTasks } from './taskApi'
import type { TaskPriority } from '../types/task'

const conversations: AIConversation[] = []
const messages = new Map<number, AIMessage[]>()
let nextId = 1

const now = () => new Date().toISOString()

export function guestAIStatus(): AIStatus {
  return { configured: false, model: 'guest-model', message: '真实模型问答，游客任务不会存档', knowledge_items: 0 }
}

export function guestKnowledgeCatalog(): KnowledgeCatalogItem[] {
  return []
}

export function guestAIConversations(): AIConversation[] {
  return [...conversations]
}

export function guestCreateConversation(mode: AIConversationMode, greenhouseId?: number): AIConversation {
  const item: AIConversation = {
    id: nextId++,
    title: mode === 'greenhouse' ? '大棚问答' : '新对话',
    greenhouse_id: greenhouseId ?? null,
    mode,
    created_at: now(),
    updated_at: now(),
  }
  conversations.unshift(item)
  messages.set(item.id, [])
  return item
}

export function guestRenameConversation(id: number, title: string): AIConversation {
  const item = conversations.find((conversation) => conversation.id === id)
  if (!item) throw new Error('对话不存在')
  item.title = title
  item.updated_at = now()
  return { ...item }
}

export function guestDeleteConversation(id: number): void {
  const index = conversations.findIndex((item) => item.id === id)
  if (index >= 0) conversations.splice(index, 1)
  messages.delete(id)
}

export function guestAIMessages(id: number): AIMessage[] {
  return [...(messages.get(id) ?? [])]
}

function apiBaseUrl(): string {
  return String(import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
}

type GuestAction = {
  greenhouse_id: number
  title: string
  description: string
  action_type: string
  priority: TaskPriority
  due_at?: string | null
}

type GuestChatResponse = { reply: string; actions: GuestAction[] }

async function chatWithGuestModel(
  content: string,
  greenhouseId: number,
  history: AIMessage[],
  taskTitles: string[],
  signal: AbortSignal,
): Promise<GuestChatResponse> {
  const response = await fetch(`${apiBaseUrl()}/guest/ai/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({
      content,
      greenhouse_id: greenhouseId,
      history: history.slice(-8).map((item) => ({ role: item.role, content: item.content })),
      tasks: taskTitles.slice(-20),
    }),
    signal,
  })
  if (!response.ok) {
    let detail = `请求失败（${response.status}）`
    try {
      const body = await response.json() as { detail?: string; message?: string }
      detail = body.detail || body.message || detail
    } catch { /* 使用状态码提示 */ }
    throw new Error(detail)
  }
  return await response.json() as GuestChatResponse
}

async function createGuestActions(actions: GuestAction[], greenhouseId: number): Promise<string[]> {
  const created: string[] = []
  for (const action of actions) {
    const targetGreenhouse = action.greenhouse_id === 102 ? 102 : action.greenhouse_id === 101 ? 101 : greenhouseId
    const task = await createTask({
      greenhouse_id: targetGreenhouse,
      crop_batch_id: targetGreenhouse === 102 ? 9002 : 9001,
      title: action.title,
      description: action.description,
      action_type: action.action_type,
      priority: action.priority,
      due_at: action.due_at || undefined,
      created_by: '游客棚小智',
    })
    created.push(`${task.title}（#${task.id}）`)
  }
  return created
}

export async function guestStreamAIChat(
  conversationId: number,
  payload: AIChatPayload,
  onEvent: (event: AIStreamEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const conversation = conversations.find((item) => item.id === conversationId)
  if (!conversation) throw new Error('对话不存在')
  if (signal.aborted) return
  const history = messages.get(conversationId) ?? []
  const previous = history.find((item) => item.id === payload.regenerate_message_id)
  const question = payload.content?.trim() || history.find((item) => item.id === previous?.reply_to_id)?.content || ''
  if (!question) throw new Error('请输入问题')

  let userMessage = history.find((item) => item.id === previous?.reply_to_id)
  if (!payload.regenerate_message_id) {
    userMessage = {
      id: nextId++, conversation_id: conversationId, role: 'user', content: question,
      status: 'completed', reply_to_id: null, model_name: null, created_at: now(),
    }
  }
  if (!userMessage) throw new Error('原问题不存在')

  const greenhouseId = conversation.greenhouse_id === 102 ? 102 : 101
  const taskTitles = (await getTasks({ greenhouse_id: greenhouseId, page: 1, page_size: 20 })).items.map((task) => task.title)
  const result = await chatWithGuestModel(question, greenhouseId, history.filter((item) => item.id !== userMessage?.id), taskTitles, signal)
  if (signal.aborted) return
  if (!payload.regenerate_message_id) history.push(userMessage)

  let reply = result.reply
  const pendingActions = payload.regenerate_message_id ? [] : (result.actions ?? []).slice(0, 2)
  if (payload.regenerate_message_id && result.actions?.length) {
    reply = '重新生成不会重复安排任务，请查看原消息中的待确认草稿或已有任务。'
  } else if (pendingActions.length) {
    reply += '\n\n已整理任务草稿，请核对下方内容并确认。当前尚未创建任务，也未执行设备操作。'
  }

  const assistantMessage: AIMessage = {
    id: nextId++, conversation_id: conversationId, role: 'assistant', content: reply,
    status: 'completed', reply_to_id: userMessage.id, model_name: 'guest-model', created_at: now(), pending_actions: pendingActions,
  }
  history.push(assistantMessage)
  messages.set(conversationId, history)
  if (conversation.title === '新对话' || conversation.title === '大棚问答') conversation.title = question.slice(0, 20)
  conversation.updated_at = now()
  onEvent({ event: 'meta', data: { user_message: userMessage, assistant_message: assistantMessage } })
  onEvent({ event: 'done', data: { message: assistantMessage } })
}

const pendingApprovals = new Set<number>()
export async function confirmGuestTasks(conversationId: number, messageId: number): Promise<void> {
  const item = messages.get(conversationId)?.find(message => message.id === messageId)
  if (!item?.pending_actions?.length || pendingApprovals.has(messageId)) return
  pendingApprovals.add(messageId)
  try {
    // Remove each action only after its write succeeds, so a retry cannot duplicate earlier tasks.
    while (item.pending_actions.length) {
      const action = item.pending_actions[0]
      const created = await createGuestActions([action], action.greenhouse_id)
      item.content += `\n已在游客会话创建：${created.join('、')}。刷新后不保留。`
      item.pending_actions.shift()
    }
  } finally { pendingApprovals.delete(messageId) }
}
export function rejectGuestTasks(conversationId: number, messageId: number): void {
  const item = messages.get(conversationId)?.find(message => message.id === messageId)
  if (!item || pendingApprovals.has(messageId)) return
  item.pending_actions = []; item.content += '\n用户已取消这些草稿，未创建任务。'
}
