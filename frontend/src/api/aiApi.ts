import { apiClient, getApiErrorMessage } from './client'
import { isGuestMode } from './guestMode'
import { guestAIConversations, guestAIMessages, guestAIStatus, guestCreateConversation, guestDeleteConversation, guestKnowledgeCatalog, guestRenameConversation, guestStreamAIChat } from './guestAI'
import type { ApiResponse } from '../types/api'
import type { AIChatPayload, AIConversation, AIConversationMode, AIMessage, AIStatus, AIStreamEvent, KnowledgeCatalogItem } from '../types/ai'

const aiBasePath = '/v1/ai'

export async function getAIStatus(): Promise<AIStatus> {
  if (isGuestMode()) {
    try { const result = await fetch(`${import.meta.env.VITE_API_BASE_URL || '/api'}/guest/ai/status`); if (!result.ok) throw new Error('status'); return await result.json() as AIStatus }
    catch { return { ...guestAIStatus(), configured: false, message: 'AI服务暂不可用' } }
  }
  const response = await apiClient.get<ApiResponse<AIStatus>>(`${aiBasePath}/status`)
  return response.data.data
}


export async function getKnowledgeCatalog(): Promise<KnowledgeCatalogItem[]> {
  if (isGuestMode()) return guestKnowledgeCatalog()
  const response = await apiClient.get<ApiResponse<KnowledgeCatalogItem[]>>(`${aiBasePath}/knowledge`)
  return response.data.data
}

export async function getAIConversations(): Promise<AIConversation[]> {
  if (isGuestMode()) return guestAIConversations()
  const response = await apiClient.get<ApiResponse<AIConversation[]>>(`${aiBasePath}/conversations`)
  return response.data.data
}

export async function createAIConversation(mode: AIConversationMode, greenhouseId?: number): Promise<AIConversation> {
  if (isGuestMode()) return guestCreateConversation(mode, greenhouseId)
  const response = await apiClient.post<ApiResponse<AIConversation>>(`${aiBasePath}/conversations`, { mode, greenhouse_id: greenhouseId ?? null })
  return response.data.data
}

export async function renameAIConversation(id: number, title: string): Promise<AIConversation> {
  if (isGuestMode()) return guestRenameConversation(id, title)
  const response = await apiClient.patch<ApiResponse<AIConversation>>(`${aiBasePath}/conversations/${id}`, { title })
  return response.data.data
}

export async function deleteAIConversation(id: number): Promise<void> {
  if (isGuestMode()) { guestDeleteConversation(id); return }
  await apiClient.delete(`${aiBasePath}/conversations/${id}`)
}

export async function getAIMessages(id: number): Promise<AIMessage[]> {
  if (isGuestMode()) return guestAIMessages(id)
  const response = await apiClient.get<ApiResponse<AIMessage[]>>(`${aiBasePath}/conversations/${id}/messages`)
  return response.data.data
}

export async function streamAIChat(
  conversationId: number,
  payload: AIChatPayload,
  onEvent: (event: AIStreamEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  if (isGuestMode()) return guestStreamAIChat(conversationId, payload, onEvent, signal)
  const baseURL = String(import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
  const response = await fetch(`${baseURL}${aiBasePath}/conversations/${conversationId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream',
      Authorization: `Bearer ${localStorage.getItem('pengzhi_auth_token') || ''}` },
    body: JSON.stringify(payload),
    signal,
  })
  if (!response.ok) {
    let message = `请求失败（${response.status}）`
    try {
      const body = await response.json() as { message?: string }
      message = body.message || message
    } catch { /* 非JSON错误响应使用状态提示 */ }
    throw new Error(message)
  }
  if (!response.body) throw new Error('浏览器未收到流式响应')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n')
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() || ''
    for (const block of blocks) {
      const lines = block.split('\n')
      const eventName = lines.find((line) => line.startsWith('event:'))?.slice(6).trim()
      const rawData = lines.filter((line) => line.startsWith('data:')).map((line) => line.slice(5).trim()).join('\n')
      if (!eventName || !rawData) continue
      onEvent({ event: eventName as AIStreamEvent['event'], data: JSON.parse(rawData) as Record<string, unknown> })
    }
    if (done) break
  }
}

export function getAIErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : getApiErrorMessage(error)
}
