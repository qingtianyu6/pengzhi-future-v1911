import { useEffect, useMemo, useRef, useState } from 'react'
import {
  BookOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  RedoOutlined,
  SendOutlined,
  StopOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { Button, Empty, Input, Modal, Segmented, Select, Space, Spin, Tag, Tooltip, message } from 'antd'
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
import { AgriculturalAgentMascot } from '../../components/AgriculturalAgentMascot'
import type { AIChatPayload, AIConversation, AIConversationMode, AIMessage as AIMessageType, AIStatus } from '../../types/ai'
import type { Greenhouse } from '../../types/greenhouse'

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

export default function AIAssistantPage() {
  const [status, setStatus] = useState<AIStatus | null>(null)
  const [greenhouses, setGreenhouses] = useState<Greenhouse[]>([])
  const [newMode, setNewMode] = useState<AIConversationMode>('general')
  const [selectedGreenhouseId, setSelectedGreenhouseId] = useState<number>()
  const [conversations, setConversations] = useState<AIConversation[]>([])
  const [activeId, setActiveId] = useState<number | null>(null)
  const [messages, setMessages] = useState<AIMessageType[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [messagesLoading, setMessagesLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [activeTools, setActiveTools] = useState<string[]>([])
  const [renaming, setRenaming] = useState<AIConversation | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const abortRef = useRef<AbortController | null>(null)
  const messageEndRef = useRef<HTMLDivElement>(null)
  const [messageApi, messageContext] = message.useMessage()
  const [modalApi, modalContext] = Modal.useModal()

  const activeConversation = conversations.find((item) => item.id === activeId)
  const activeGreenhouse = greenhouses.find((item) => item.id === activeConversation?.greenhouse_id)
  const quickPrompts = activeConversation?.mode === 'greenhouse' ? greenhousePrompts : generalPrompts

  const loadConversations = async () => {
    const data = await getAIConversations()
    setConversations(data)
    return data
  }

  useEffect(() => {
    void Promise.all([
      getAIStatus(),
      getGreenhouses({ page: 1, page_size: 100, status: 'active' }),
      getAIConversations(),
    ]).then(([aiStatus, greenhouseData, conversationData]) => {
      setStatus(aiStatus)
      setGreenhouses(greenhouseData.items)
      setConversations(conversationData)
      setSelectedGreenhouseId(greenhouseData.items[0]?.id)
      setActiveId(conversationData[0]?.id ?? null)
    }).catch((error) => messageApi.error(getAIErrorMessage(error)))
      .finally(() => setLoading(false))
  }, [messageApi])

  useEffect(() => {
    if (!activeId) {
      setMessages([])
      return
    }
    setMessagesLoading(true)
    setActiveTools([])
    void getAIMessages(activeId).then(setMessages)
      .catch((error) => messageApi.error(getAIErrorMessage(error)))
      .finally(() => setMessagesLoading(false))
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

  const runChat = async (payload: AIChatPayload) => {
    if (!activeId || generating) return
    setGenerating(true)
    setActiveTools([])
    const controller = new AbortController()
    abortRef.current = controller
    try {
      await streamAIChat(activeId, payload, (event) => {
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
          messageApi.error(String(event.data.message || '棚小智暂时无法回答'))
        }
      }, controller.signal)
    } catch (error) {
      if (!controller.signal.aborted) messageApi.error(getAIErrorMessage(error))
    } finally {
      setGenerating(false)
      abortRef.current = null
      try {
        setMessages(await getAIMessages(activeId))
        await loadConversations()
      } catch {
        // 流式内容已经在页面显示，刷新失败不影响本轮结果。
      }
    }
  }

  const send = (content = input.trim()) => {
    if (!content) return
    void runChat({ content })
  }

  const lastAssistant = useMemo(
    () => [...messages].reverse().find((item) => item.role === 'assistant' && item.status !== 'streaming'),
    [messages],
  )

  if (loading) return <div className="page-loading"><Spin /></div>

  return <div className="agent-page">
    {messageContext}{modalContext}
    <aside className="agent-sidebar">
      <div className="agent-brand-card">
        <AgriculturalAgentMascot />
        <div><strong>棚小智 · 农业助手</strong><span>为大棚种植提供问答服务</span></div>
      </div>

      <div className="agent-new-chat">
        <span className="agent-section-label">新建对话</span>
        <Segmented
          block
          value={newMode}
          onChange={(value) => setNewMode(value as AIConversationMode)}
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
          options={greenhouses.map((item) => ({ value: item.id, label: `${item.name} · ${item.code}` }))}
        />}
        <Button type="primary" block icon={<PlusOutlined />} onClick={() => void createConversation()}>
          {newMode === 'general' ? '开始通用问答' : '开始大棚问答'}
        </Button>
      </div>

      <div className="agent-history-head"><span className="agent-section-label">历史对话</span><Tag>{conversations.length}</Tag></div>
      <div className="agent-conversation-list">
        {conversations.map((item) => <div
          key={item.id}
          className={`agent-conversation${activeId === item.id ? ' active' : ''}`}
          onClick={() => !generating && setActiveId(item.id)}
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
      <header className="agent-chat-header">
        <div>
          <strong>{activeConversation?.title ?? '你好，我是棚小智'}</strong>
          <span>{activeConversation?.mode === 'greenhouse'
            ? `大棚问答：${activeGreenhouse?.name ?? '未选择'}`
            : '通用问答：使用农业知识库，不读取任何大棚数据'}</span>
        </div>
        <Space wrap>
          <Tag color="green" icon={<BookOutlined />}>知识库 {status?.knowledge_items ?? 0} 条</Tag>
          <Tag>{status?.model === 'pengzhi-local-agent' ? '本地智能体' : status?.model}</Tag>
        </Space>
      </header>

      <div className="agent-mode-banner">
        <AgriculturalAgentMascot compact />
        <div>
          <strong>{activeConversation?.mode === 'greenhouse' ? '我会先读懂这个大棚，再回答你' : '你可以直接问我设施农业问题'}</strong>
          <span>{activeConversation?.mode === 'greenhouse'
            ? '环境数据、1~6小时预测、活动预警、农事任务和知识库会按问题自动检索。'
            : '适合咨询番茄/甜瓜栽培、设施环境、病害风险、数据接入和平台使用。'}</span>
        </div>
      </div>

      <div className="agent-messages">
        {messagesLoading ? <div className="page-loading"><Spin /></div> : messages.length ? messages.map((item) => <div key={item.id} className={`agent-message ${item.role}`}>
          <div className="agent-message-avatar">{item.role === 'user' ? <UserOutlined /> : <AgriculturalAgentMascot compact />}</div>
          <div className="agent-message-body">
            <div className="agent-message-meta"><strong>{item.role === 'user' ? '你' : '棚小智'}</strong><span>{new Date(item.created_at).toLocaleString('zh-CN', { hour12: false })}</span></div>
            <div className="agent-message-content">{item.content || (item.status === 'streaming' ? '正在整理证据…' : '暂无内容')}</div>
          </div>
        </div>) : <div className="agent-empty-state">
          <AgriculturalAgentMascot />
          <h3>{activeConversation ? '从一个问题开始' : '先选择一种对话方式'}</h3>
          <p>{activeConversation?.mode === 'greenhouse' ? '我会结合这个大棚当前业务证据回答，而不是只给通用知识。' : '通用模式只使用农业知识库，不需要选择大棚。'}</p>
        </div>}
        {activeConversation && <div className="agent-quick-prompts">
          {quickPrompts.map((prompt) => <Button key={prompt} size="small" disabled={generating} onClick={() => send(prompt)}>{prompt}</Button>)}
        </div>}
        {activeTools.length > 0 && <div className="agent-tool-trace">
          <span>本轮已调用</span>
          {activeTools.map((tool) => <Tag key={tool}>{tool === 'search_agriculture_knowledge' ? '农业知识库' : tool === 'get_current_environment' ? '当前环境' : tool === 'get_future_prediction' ? '未来预测' : tool === 'get_active_warnings' ? '风险预警' : tool === 'get_farm_tasks' ? '农事任务' : tool}</Tag>)}
        </div>}
        <div ref={messageEndRef} />
      </div>

      <footer className="agent-composer">
        <TextArea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          maxLength={4000}
          autoSize={{ minRows: 2, maxRows: 5 }}
          disabled={!activeId || generating}
          placeholder={activeId ? '问棚小智一个问题，Enter发送，Shift+Enter换行' : '请先新建或选择一条对话'}
          onPressEnter={(event) => { if (!event.shiftKey) { event.preventDefault(); send() } }}
        />
        <div className="agent-composer-footer">
          <span>{activeConversation?.mode === 'greenhouse' ? '关键生产操作仍需人工确认' : '知识回答会优先引用本地知识库'}</span>
          <Space>
            {lastAssistant && <Button icon={<RedoOutlined />} disabled={generating} onClick={() => void runChat({ regenerate_message_id: lastAssistant.id })}>重新生成</Button>}
            {generating
              ? <Button danger icon={<StopOutlined />} onClick={() => abortRef.current?.abort()}>停止</Button>
              : <Button type="primary" icon={<SendOutlined />} disabled={!activeId || !input.trim()} onClick={() => send()}>发送</Button>}
          </Space>
        </div>
      </footer>
    </section>

    <Modal title="重命名对话" open={Boolean(renaming)} onCancel={() => setRenaming(null)} onOk={() => void saveRename()} okButtonProps={{ disabled: !renameValue.trim() }} destroyOnHidden>
      <Input value={renameValue} maxLength={80} autoFocus onChange={(event) => setRenameValue(event.target.value)} onPressEnter={() => void saveRename()} />
    </Modal>
  </div>
}
