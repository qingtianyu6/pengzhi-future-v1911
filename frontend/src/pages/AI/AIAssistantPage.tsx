import { useEffect, useMemo, useRef, useState } from 'react'
import {
  CheckCircleFilled,
  CloudServerOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  RedoOutlined,
  SendOutlined,
  StopOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { Alert, Button, Empty, Input, Modal, Segmented, Select, Space, Spin, Tag, Tooltip, message } from 'antd'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  createAIConversation,
  deleteAIConversation,
  getAIConversations,
  getAIErrorMessage,
  getAIMessages,
  getAIStatus,
  renameAIConversation,
  streamAIChat,
} from '../../api/aiApi'
import { getGreenhouses } from '../../api/greenhouseApi'
import { AgriculturalAgentMascot, type MascotState } from '../../components/AgriculturalAgentMascot'
import { useAssistantVoice } from '../../hooks/useAssistantVoice'
import { confirmGuestTasks, rejectGuestTasks } from '../../api/guestAI'
import { canManage } from '../../utils/permissions'
import { label } from '../../utils/labels'
import { useNavigate } from 'react-router-dom'
import type { AIChatPayload, AIConversation, AIConversationMode, AIMessage as AIMessageType, AIStatus } from '../../types/ai'
import type { Greenhouse } from '../../types/greenhouse'
import { apiClient } from '../../api/client'
import { isGuestMode } from '../../api/guestMode'
import { identifyDisease } from '../../api/diseaseApi'
import AgentRunCard from './AgentRunCard'
import './AIAssistantPage.css'

const { TextArea } = Input

const generalPrompts = ['番茄高湿时应该关注什么？', '甜瓜开花坐果期如何管理温湿度？', '传感器数据怎么接入系统？']
const greenhousePrompts = ['现在最需要关注什么？', '未来6小时环境趋势怎么样？', '为什么出现这个风险？', '有哪些任务还没有完成？']

function upsertMessage(items: AIMessageType[], item: AIMessageType): AIMessageType[] {
  const index = items.findIndex((messageItem) => messageItem.id === item.id)
  if (index < 0) return [...items, item]
  const next = [...items]
  next[index] = item
  return next
}

interface AssistantProps {
  embedded?: boolean
  workspaceId?: number
  expanded?: boolean
  voiceRequest?: number
  onActivity?: (state: MascotState) => void
}

export default function AIAssistantPage({ embedded = false, workspaceId, expanded = false, voiceRequest = 0, onActivity }: AssistantProps) {
  const [status, setStatus] = useState<AIStatus | null>(null)
  const [greenhouses, setGreenhouses] = useState<Greenhouse[]>([])
  const [newMode, setNewMode] = useState<AIConversationMode>(workspaceId ? 'greenhouse' : 'general')
  const [selectedGreenhouseId, setSelectedGreenhouseId] = useState<number>()
  const [conversations, setConversations] = useState<AIConversation[]>([])
  const [activeId, setActiveId] = useState<number | null>(null)
  const [messages, setMessages] = useState<AIMessageType[]>([])
  const [input, setInput] = useState('')
  const [boot, setBoot] = useState(0)
  const [loading, setLoading] = useState(true)
  const [messagesLoading, setMessagesLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [runStatus, setRunStatus] = useState('')
  const [finished, setFinished] = useState(false)
  const [approvalBusy, setApprovalBusy] = useState(false)
  const mounted = useRef(false)
  const sending = useRef(false)
  const createPromise = useRef<Promise<AIConversation> | null>(null)
  const lastVoiceRequest = useRef(0)
  const fileRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()
  const voice = useAssistantVoice(value => setInput(current => ((current ? current + ' ' : '') + value).slice(0, isGuestMode() ? 1000 : 4000)))
  const [activeTools, setActiveTools] = useState<string[]>([])
  const [runId, setRunId] = useState<number>()
  const [trace, setTrace] = useState<Array<{ tool: string; status: string; callId: number }>>([])
  const [renaming, setRenaming] = useState<AIConversation | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const abortRef = useRef<AbortController | null>(null)
  const messageEndRef = useRef<HTMLDivElement>(null)
  const [messageApi, messageContext] = message.useMessage()
  const [modalApi, modalContext] = Modal.useModal()

  const activeConversation = conversations.find((item) => item.id === activeId)
  const activeGreenhouse = greenhouses.find((item) => item.id === (activeConversation?.greenhouse_id ?? (newMode === 'greenhouse' ? workspaceId ?? selectedGreenhouseId : undefined)))
  const quickPrompts = (activeConversation?.mode ?? newMode) === 'greenhouse' ? greenhousePrompts : generalPrompts

  const loadConversations = async () => {
    const data = await getAIConversations()
    setConversations(data)
    return data
  }

  useEffect(() => {
    mounted.current = true
    setLoading(true)
    let active = true
    void Promise.all([
      getAIStatus(), getGreenhouses({ page: 1, page_size: 100, status: 'active' }), getAIConversations(),
    ]).then(([aiStatus, greenhouseData, conversationData]) => {
      if (!active) return
      setStatus(aiStatus); setGreenhouses(greenhouseData.items); setConversations(conversationData)
      const target = workspaceId ?? (Number(new URLSearchParams(window.location.search).get('greenhouse_id')) || undefined)
      setSelectedGreenhouseId(target && greenhouseData.items.some(item => item.id === target) ? target : undefined)
      const previous = conversationData.find(item => target ? item.mode === 'greenhouse' && item.greenhouse_id === target : item.mode === 'general')
      setActiveId(previous?.id ?? null)
    }).catch(cause => { if (active) setError(getAIErrorMessage(cause)) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false; mounted.current = false; abortRef.current?.abort() }
  }, [workspaceId, boot])

  const { startListening } = voice
  useEffect(() => {
    if (!loading && voiceRequest > lastVoiceRequest.current) {
      lastVoiceRequest.current = voiceRequest
      startListening()
    }
  }, [loading, voiceRequest, startListening])
  useEffect(() => {
    onActivity?.(generating || uploading ? 'thinking' : voice.listening ? 'listening' : voice.speaking ? 'speaking' : error ? 'unavailable' : runStatus === 'WAITING_APPROVAL' ? 'reminder' : finished ? 'complete' : 'idle')
  }, [generating, uploading, voice.listening, voice.speaking, error, finished, runStatus, onActivity])
  useEffect(() => {
    if (!finished) return
    const timer = window.setTimeout(() => setFinished(false), 2400)
    return () => window.clearTimeout(timer)
  }, [finished])

  useEffect(() => {
    if (!activeId) {
      setMessages([])
      return
    }
    let active = true
    setMessagesLoading(true)
    setActiveTools([])
    setTrace([])
    setRunStatus('')
    setRunId(undefined)
    if (!isGuestMode()) {
      void apiClient.get('/agent/runs', { params: { conversation_id: activeId } })
        .then(response => { if (active) setRunId(response.data.data[0]?.id) })
        .catch(() => { /* 历史消息仍可正常加载 */ })
    }
    void getAIMessages(activeId).then(items => { if (active && !abortRef.current) setMessages(items) })
      .catch((cause) => { if (active) setError(getAIErrorMessage(cause)) })
      .finally(() => { if (active) setMessagesLoading(false) })
    return () => { active = false }
  }, [activeId, messageApi])

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: generating ? 'auto' : 'smooth' })
  }, [generating, messages])

  const createConversation = async () => {
    if (newMode === 'greenhouse' && !selectedGreenhouseId) {
      messageApi.warning('大棚问答需要先选择目标大棚')
      return
    }
    try {
      const item = await createAIConversation(newMode, newMode === 'greenhouse' ? selectedGreenhouseId : undefined)
      setConversations((current) => [item, ...current])
      setActiveId(item.id)
      setMessages([])
    } catch (error) {
      messageApi.error(getAIErrorMessage(error))
    }
  }

  const removeConversation = (item: AIConversation) => {
    modalApi.confirm({
      title: '删除这条对话？',
      content: '该对话的历史消息和工具证据会一并删除。',
      okText: '删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        await deleteAIConversation(item.id)
        const remaining = conversations.filter((conversation) => conversation.id !== item.id)
        setConversations(remaining)
        if (activeId === item.id) setActiveId(remaining[0]?.id ?? null)
      },
    })
  }

  const saveRename = async () => {
    if (!renaming || !renameValue.trim()) return
    try {
      const item = await renameAIConversation(renaming.id, renameValue.trim())
      setConversations((current) => current.map((conversation) => conversation.id === item.id ? item : conversation))
      setRenaming(null)
    } catch (error) {
      messageApi.error(getAIErrorMessage(error))
    }
  }

  const runChat = async (payload: AIChatPayload, conversationId = activeId) => {
    if (!conversationId || abortRef.current) return
    voice.stopListening(true); voice.stopSpeaking(); setError(''); setFinished(false)
    setGenerating(true)
    setActiveTools([])
    const controller = new AbortController()
    abortRef.current = controller
    try {
      setTrace([])
      await streamAIChat(conversationId, { ...payload, require_confirmation: true }, (event) => {
        if (controller.signal.aborted || !mounted.current) return
        if (event.data.run_id) setRunId(Number(event.data.run_id))
        if (event.event === 'tool_started' || event.event === 'tool_finished') {
          const callId = Number(event.data.call_id)
          const entry = { tool: String(event.data.tool), status: String(event.data.status || 'running'), callId }
          setTrace(current => [...current.filter(item => item.callId !== callId), entry])
        }
        if (event.event === 'run_failed') setError(String(event.data.content || '运行失败'))
        if (event.event === 'meta') {
          const userMessage = event.data.user_message as AIMessageType | undefined
          const assistantMessage = event.data.assistant_message as AIMessageType | undefined
          setMessages((current) => {
            let next = current
            if (userMessage) next = upsertMessage(next, userMessage)
            if (assistantMessage) next = upsertMessage(next, assistantMessage)
            return next
          })
          setInput('')
        }
        if (event.event === 'tools') {
          const tools = Array.isArray(event.data.tools) ? event.data.tools as Array<{ name?: string }> : []
          setActiveTools(tools.map((item) => item.name || '').filter(Boolean))
        }
        if (event.event === 'delta') {
          const content = String(event.data.content || '')
          setMessages((current) => {
            const index = [...current].reverse().findIndex((item) => item.role === 'assistant' && item.status === 'streaming')
            if (index < 0) return current
            const actualIndex = current.length - 1 - index
            const next = [...current]
            next[actualIndex] = { ...next[actualIndex], content: next[actualIndex].content + content }
            return next
          })
        }
        if (event.event === 'done') {
          const item = event.data.message as AIMessageType | undefined
          if (item) setMessages((current) => upsertMessage(current, item))
        }
        if (event.event === 'error') {
          setError(String(event.data.message || '棚小智暂时无法回答'))
        }
      }, controller.signal)
    } catch (error) {
      if (!controller.signal.aborted && mounted.current) setError(getAIErrorMessage(error))
    } finally {
      abortRef.current = null
      if (mounted.current) {
        setGenerating(false)
        try {
          const items = await getAIMessages(conversationId)
          if (mounted.current) {
            setMessages(items)
            if (!controller.signal.aborted && items.at(-1)?.status === 'completed') setFinished(true)
            await loadConversations()
          }
        } catch { /* Keep the already received stream if history refresh fails. */ }
      }
    }
  }

  const ensureConversation = async (): Promise<number> => {
    if (activeId) return activeId
    const id = workspaceId ?? selectedGreenhouseId
    if (newMode === 'greenhouse' && !id) throw new Error('请先选择当前大棚，或切换到通用问答。')
    if (!createPromise.current) createPromise.current = createAIConversation(newMode, newMode === 'greenhouse' ? id : undefined)
    try {
      const item = await createPromise.current
      if (!mounted.current) throw new Error('对话已关闭')
      setConversations(current => [item, ...current.filter(value => value.id !== item.id)])
      setActiveId(item.id)
      return item.id
    } finally { createPromise.current = null }
  }
  const stopGeneration = async () => {
    abortRef.current?.abort()
    if (runId && !isGuestMode()) {
      try { await apiClient.post(`/agent/runs/${runId}/cancel`, {}); if (mounted.current) setRunStatus('CANCELLED') }
      catch { if (mounted.current) setError('已停止接收回答，但服务端状态尚未确认，请在本轮处理记录中重试停止。') }
    }
  }
  const send = async (content = input.trim()) => {
    if (!content || generating || sending.current || !status?.configured) return
    sending.current = true
    try { const id = await ensureConversation(); if (mounted.current) await runChat({ content }, id) }
    catch (cause) { if (mounted.current) setError(getAIErrorMessage(cause)) }
    finally { sending.current = false }
  }
  const openTaskDraft = () => {
    const id = (activeConversation?.mode ?? newMode) === 'greenhouse' ? activeConversation?.greenhouse_id ?? workspaceId : workspaceId
    if (!id) { messageApi.warning('请先选择当前大棚'); return }
    const params = new URLSearchParams({ greenhouse_id: String(id), create: '1', tab: 'tasks', title: '棚小智 · 现场复核任务',
      description: lastAssistant?.content.slice(0, 2400) || '请结合本棚环境、风险与现场情况进行人工检查，填写检查要求后保存。', action_type: 'field_inspection', priority: 'medium' })
    window.dispatchEvent(new Event('pengzhi:close-assistant'))
    navigate(`/platform/production?${params}`)
  }
  const uploadLeaf = async (file: File) => {
    if (!canManage()) { setError('当前账号只能查看识别记录，不能上传创建新记录。'); return }
    if ((activeConversation?.mode ?? newMode) !== 'greenhouse') { setError('请先在历史 / 模式中切换到本棚问答，再上传叶片。'); return }
    const id = (activeConversation?.mode ?? newMode) === 'greenhouse' ? activeConversation?.greenhouse_id ?? workspaceId : workspaceId
    const greenhouse = greenhouses.find(item => item.id === id)
    if (!greenhouse) { setError('请先选择本棚问答，再上传叶片。'); return }
    if (greenhouse.active_batch?.crop_type !== 'tomato') { setError('当前识别模型仅支持番茄叶片，请选择有番茄批次的大棚。'); return }
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024) { setError('请选择不超过 10MB 的 JPG、PNG 或 WebP 图片。'); return }
    setUploading(true); setError('')
    try {
      const diagnosis = await identifyDisease(greenhouse.id, greenhouse.active_batch.id, file)
      if (!mounted.current) return
      messageApi.success('识别结果已保存，需要人工复核')
      if (status?.configured) {
        const conversationId = await ensureConversation()
        if (mounted.current) await runChat({ content: `番茄叶片辅助识别记录ID：${diagnosis.record_id}。请读取真实识别记录，说明候选与复核要求，不得将候选分数当确诊或总体准确率。` }, conversationId)
      } else setError('图片已识别并保存，请到病害检测查看记录；AI 问答服务尚不可用。')
    } catch (cause) { if (mounted.current) setError(getAIErrorMessage(cause)) }
    finally { if (mounted.current) setUploading(false) }
  }
  const decideGuest = async (messageId: number, accepted: boolean) => {
    if (!activeId || approvalBusy) return
    setApprovalBusy(true)
    try {
      if (accepted) await confirmGuestTasks(activeId, messageId)
      else rejectGuestTasks(activeId, messageId)
      setMessages(await getAIMessages(activeId)); setFinished(accepted)
      window.dispatchEvent(new Event('pengzhi:tasks-changed'))
    } catch (cause) { setError(getAIErrorMessage(cause)) }
    finally { setApprovalBusy(false) }
  }

  const lastAssistant = useMemo(
    () => [...messages].reverse().find((item) => item.role === 'assistant' && item.status !== 'streaming'),
    [messages],
  )

  if (loading) return <div className="page-loading"><Spin /></div>

  return <div className={`agent-page${embedded ? ' assistant-embedded' : ''}${expanded ? ' is-expanded' : ''}${historyOpen ? ' show-history' : ''}`}>
    {messageContext}{modalContext}
    <aside className="agent-sidebar">
      {embedded && !expanded && <Button className="assistant-history-back" onClick={() => setHistoryOpen(false)}>返回当前对话</Button>}
      <div className="agent-brand-card">
        <AgriculturalAgentMascot />
        <div><strong>棚小智 · 农业助手</strong><span>为大棚种植提供问答服务</span></div>
      </div>

      <div className="agent-new-chat">
        <span className="agent-section-label">新建对话</span>
        <Segmented
          block
          value={newMode}
          disabled={generating || uploading}
          onChange={(value) => { setNewMode(value as AIConversationMode); setActiveId(null); setMessages([]) }}
          options={[
            { label: '通用问答', value: 'general' },
            { label: '大棚问答', value: 'greenhouse' },
          ]}
        />
        {newMode === 'greenhouse' && <Select
          className="agent-greenhouse-select"
          placeholder="选择一个大棚"
          value={selectedGreenhouseId}
          onChange={setSelectedGreenhouseId}
          disabled={embedded && Boolean(workspaceId)}
          options={greenhouses.map((item) => ({ value: item.id, label: `${item.name} · ${item.code}` }))}
        />}
        <Button type="primary" block icon={<PlusOutlined />} onClick={() => void createConversation()}>
          {newMode === 'general' ? '开始通用问答' : '开始大棚问答'}
        </Button>
      </div>

      <div className="agent-history-head"><span className="agent-section-label">历史对话</span><Tag>{conversations.length}</Tag></div>
      <div className="agent-conversation-list">
        {conversations.filter(item => !embedded || item.mode === 'general' || item.greenhouse_id === workspaceId).map((item) => <div
          key={item.id}
          className={`agent-conversation${activeId === item.id ? ' active' : ''}`}
          onClick={() => { if (!generating) { voice.stopListening(true); voice.stopSpeaking(); setActiveId(item.id); setNewMode(item.mode); setHistoryOpen(false) } }}
          onKeyDown={event => { if ((event.key === 'Enter' || event.key === ' ') && !generating) { event.preventDefault(); setActiveId(item.id); setNewMode(item.mode); setHistoryOpen(false) } }}
          role="button"
          tabIndex={0}
        >
          <AgriculturalAgentMascot compact />
          <div className="agent-conversation-copy">
            <strong>{item.title}</strong>
            <span>{item.mode === 'general' ? '通用问答' : greenhouses.find((greenhouse) => greenhouse.id === item.greenhouse_id)?.name ?? '大棚问答'}</span>
          </div>
          <div className="agent-conversation-actions">
            <Tooltip title="重命名"><Button type="text" size="small" icon={<EditOutlined />} onClick={(event) => { event.stopPropagation(); setRenaming(item); setRenameValue(item.title) }} /></Tooltip>
            <Tooltip title="删除"><Button type="text" danger size="small" icon={<DeleteOutlined />} onClick={(event) => { event.stopPropagation(); removeConversation(item) }} /></Tooltip>
          </div>
        </div>)}
        {!conversations.length && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="还没有对话" />}
      </div>
    </aside>

    <section className="agent-chat-shell">
      {embedded && <div className="assistant-context-bar"><span>{(activeConversation?.mode ?? newMode) === 'greenhouse' ? `当前大棚 · ${greenhouses.find(item => item.id === (activeConversation?.greenhouse_id ?? workspaceId))?.name ?? '尚未选择'}` : '通用农业问答'}{isGuestMode() ? ' · 游客演示' : ''}</span><Button size="small" type="text" onClick={() => setHistoryOpen(value => !value)}>{historyOpen ? '返回对话' : '历史 / 模式'}</Button></div>}
      {error && <Alert className="assistant-inline-alert" type="error" message={error} showIcon closable onClose={() => setError('')} action={!status && <Button size="small" onClick={() => { setError(''); setBoot(value => value + 1) }}>重新连接</Button>} />}
      {status && !status.configured && <Alert className="assistant-inline-alert" type="warning" message={status.message || 'AI 服务尚未配置，可继续查看数据或填写任务草稿。'} showIcon />}

      <header className="agent-chat-header">
        <div>
          <div className="agent-chat-title"><strong>{activeConversation?.title ?? '你好，我是棚小智'}</strong>{status?.configured && <span className="agent-live-dot" />}</div>
          <span>{(activeConversation?.mode ?? newMode) === 'greenhouse'
            ? `大棚问答：${activeGreenhouse?.name ?? '未选择'}`
            : status?.model === 'guest-model' ? '真实模型问答；游客任务仅在当前页面会话中保留' : status?.model === 'pengzhi-local-agent' ? '通用问答：使用本地农业知识库' : '农业任务助手：可查询有权限的大棚并安排农事与复查'}</span>
        </div>
        <div className="agent-status-group">
          <span><DatabaseOutlined /> 知识库 {status?.knowledge_items ?? 0} 条</span>
          <span><CloudServerOutlined /> {status?.model === 'guest-model' ? '游客 AI' : status?.model === 'pengzhi-local-agent' ? '本地智能体' : status?.model}</span>
          <span className="agent-status-ready"><CheckCircleFilled /> {status?.configured ? '可用' : '未配置'}</span>
        </div>
      </header>

      <div className="agent-mode-banner">
        <AgriculturalAgentMascot compact />
        <div>
          <strong>{(activeConversation?.mode ?? newMode) === 'greenhouse' ? '我会先读懂这个大棚，再回答你' : '你可以直接问我设施农业问题'}</strong>
          <span>{(activeConversation?.mode ?? newMode) === 'greenhouse'
            ? '环境数据、1~6小时预测、活动预警、农事任务和知识库会按问题自动检索。'
            : '适合咨询番茄/甜瓜栽培、设施环境、病害风险、数据接入和平台使用。'}</span>
        </div>
      </div>

      <div className="agent-messages">
        {messagesLoading ? <div className="page-loading"><Spin /></div> : messages.length ? messages.map((item) => <div key={item.id} className={`agent-message ${item.role}`}>
          <div className="agent-message-avatar">{item.role === 'user' ? <UserOutlined /> : <AgriculturalAgentMascot compact />}</div>
          <div className="agent-message-body">
            <div className="agent-message-meta"><strong>{item.role === 'user' ? '你' : '棚小智'}</strong><span>{new Date(item.created_at).toLocaleString('zh-CN', { hour12: false })}</span></div>
            <div className={`agent-message-content${item.status === 'error' ? ' is-error' : ''}`}>
              {item.content
                ? item.role === 'assistant'
                  ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{item.content}</ReactMarkdown>
                  : item.content
                : item.status === 'streaming' ? <span className="agent-thinking">正在整理证据</span> : '暂无内容'}
            </div>
            {item.role === 'assistant' && item.content && item.status === 'completed' && <div className="assistant-message-actions"><Button type="text" size="small" disabled={!voice.canSpeak} onClick={() => voice.speaking ? voice.stopSpeaking() : voice.speak(item.content)}>{voice.speaking ? '停止朗读' : '朗读回答'}</Button></div>}
            {item.pending_actions?.length ? <div className="assistant-pending-actions"><strong>待确认任务草稿</strong>{item.pending_actions.map((action, index) => <div key={index}><b>{action.title}</b><p>目标：{greenhouses.find(gh => gh.id === action.greenhouse_id)?.name ?? `大棚 #${action.greenhouse_id}`}</p><p>{action.description}</p><small>截止：{action.due_at ? new Date(action.due_at).toLocaleString('zh-CN') : '未设置'} · 保存为待提交任务，不执行设备操作</small></div>)}<Space><Button type="primary" loading={approvalBusy} disabled={!canManage()} onClick={() => void decideGuest(item.id, true)}>确认创建草稿</Button><Button disabled={approvalBusy} onClick={() => void decideGuest(item.id, false)}>取消</Button></Space></div> : null}
          </div>
        </div>) : <div className="agent-empty-state">
          <AgriculturalAgentMascot state={generating ? 'thinking' : 'idle'} />
          <h3>{activeConversation ? '从一个问题开始' : workspaceId ? '今天想了解本棚的什么情况？' : '你可以直接提问，也可以切换对话方式'}</h3>
          <p>{(activeConversation?.mode ?? newMode) === 'greenhouse' ? '我会结合这个大棚当前业务证据回答，而不是只给通用知识。' : '通用模式只使用农业知识库，不需要选择大棚。'}</p>
        </div>}
        {<div className="agent-quick-prompts">
          {quickPrompts.map((prompt) => <Button key={prompt} size="small" disabled={generating || !status?.configured} onClick={() => void send(prompt)}>{prompt}</Button>)}
        </div>}
        {activeTools.length > 0 && <div className="agent-tool-trace">
          <span>本轮已调用</span>
          {activeTools.map((tool) => <Tag key={tool}>{tool === 'search_agriculture_knowledge' ? '农业知识库' : tool === 'get_current_environment' ? '当前环境' : tool === 'get_future_prediction' ? '未来预测' : tool === 'get_active_warnings' ? '风险预警' : tool === 'get_farm_tasks' ? '农事任务' : label(tool)}</Tag>)}
        </div>}
        {trace.length > 0 && <div className="agent-tool-trace">
          {trace.map(item => <Tag key={item.callId} color={item.status === 'error' ? 'red' : item.status === 'running' ? 'blue' : 'green'}>
            {item.status === 'running' ? '●' : item.status === 'error' ? '!' : '✓'} {label(item.tool)}
          </Tag>)}
        </div>}
        {runId && <AgentRunCard key={runId} runId={runId} greenhouseNames={Object.fromEntries(greenhouses.map(item => [item.id, item.name]))} onStatus={setRunStatus} onRefresh={() => { if (activeId) void getAIMessages(activeId).then(items => { if (mounted.current) setMessages(items) }) }} />}
        <div ref={messageEndRef} />
      </div>

      <footer className="agent-composer">
        <div className="assistant-composer-tools">
          <Button size="small" disabled={!canManage() || generating || uploading || !(activeGreenhouse ?? greenhouses.find(item => item.id === workspaceId))} loading={uploading} onClick={() => fileRef.current?.click()}>上传叶片</Button>
          {voice.canListen && <Button size="small" danger={voice.listening} disabled={generating || uploading} onClick={() => voice.listening ? voice.stopListening() : voice.startListening()}>{voice.listening ? '结束录音' : '语音输入'}</Button>}
          {voice.speaking && <Button size="small" onClick={voice.stopSpeaking}>停止朗读</Button>}
          {canManage() && <Button size="small" disabled={generating || uploading || !workspaceId} onClick={openTaskDraft}>生成任务草稿</Button>}
          <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" hidden aria-label="上传番茄叶片" onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; if (file) void uploadLeaf(file) }} />
        </div>
        {(voice.error || voice.interim || voice.listening) && <div className="assistant-voice-note" role="status">{voice.error || voice.interim || '正在听，请说话。识别文字会先填入输入框，由你确认发送。'}</div>}
        <TextArea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          maxLength={isGuestMode() ? 1000 : 4000}
          autoSize={{ minRows: 2, maxRows: 5 }}
          disabled={generating || uploading || !status?.configured}
          aria-label="向棚小智提问"
          placeholder={status?.configured ? '问问当前大棚，Enter 发送，Shift+Enter 换行' : 'AI 服务暂不可用，请查看上方提示'}
          onPressEnter={(event) => { if (!event.shiftKey && !event.nativeEvent.isComposing && event.nativeEvent.keyCode !== 229) { event.preventDefault(); void send() } }}
        />
        <div className="agent-composer-footer">
          <span>{(activeConversation?.mode ?? newMode) === 'greenhouse' ? '关键生产操作仍需人工确认' : '知识回答会优先引用本地知识库'}</span>
          <Space>
            {lastAssistant && <Button icon={<RedoOutlined />} disabled={generating} onClick={() => void runChat({ regenerate_message_id: lastAssistant.id })}>重新生成</Button>}
            {generating
              ? <Button danger icon={<StopOutlined />} onClick={() => void stopGeneration()}>停止</Button>
              : <Button type="primary" aria-label="发送给棚小智" icon={<SendOutlined />} disabled={!input.trim() || !status?.configured || uploading} onClick={() => void send()}>发送</Button>}
          </Space>
        </div>
        <details className="assistant-voice-disclosure"><summary>语音与数据说明</summary><p>{voice.canListen ? '语音识别由浏览器提供，可能使用在线识别服务。仅在你开启时录音，最长 45 秒；文字确认后才发送。' : '当前浏览器不支持语音输入，可使用文字输入。'}回答朗读使用浏览器语音。棚内分析以可用数据为准，生产操作需要人工确认。</p></details>
      </footer>
    </section>

    <Modal title="重命名对话" open={Boolean(renaming)} onCancel={() => setRenaming(null)} onOk={() => void saveRename()} okButtonProps={{ disabled: !renameValue.trim() }} destroyOnHidden>
      <Input value={renameValue} maxLength={80} autoFocus onChange={(event) => setRenameValue(event.target.value)} onPressEnter={() => void saveRename()} />
    </Modal>
  </div>
}
