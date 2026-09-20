import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ClockCircleOutlined,
  ForkOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  ScheduleOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import {
  Alert,
  Button,
  Drawer,
  Progress,
  Segmented,
  Select,
  Space,
  Tag,
  message,
} from 'antd'
import { useSearchParams } from 'react-router-dom'
import { getApiErrorMessage } from '../api/client'
import { acceptDecision, getCurrentDecisions, rejectDecision } from '../api/decisionApi'
import { getGreenhouses } from '../api/greenhouseApi'
import { createTaskFromWarning, getTaskSummary, getTaskTrace, getTasks } from '../api/taskApi'
import FarmTaskManagementPage from './Tasks/FarmTaskManagementPage'
import { SaasEmptyState, SectionHeading } from '../components/SaasUI'
import type { CurrentDecision, DecisionRecommendation } from '../types/decision'
import type { Greenhouse } from '../types/greenhouse'
import type { FarmTask, TaskSummary, TaskTrace } from '../types/task'

const priorityMeta: Record<string, { label: string; color: string }> = {
  low: { label: '低', color: 'default' },
  medium: { label: '中', color: 'blue' },
  high: { label: '高', color: 'orange' },
  urgent: { label: '紧急', color: 'red' },
}

const taskStatusMeta: Record<string, { label: string; color: string }> = {
  draft: { label: '待提交', color: 'default' },
  pending: { label: '待执行', color: 'blue' },
  in_progress: { label: '执行中', color: 'processing' },
  completed: { label: '已完成', color: 'green' },
  cancelled: { label: '已取消', color: 'default' },
}

function time(value: string | null): string {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'
}

function shortTime(value: string | null): string {
  return value ? new Date(value).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false }) : '—'
}

function riskWeight(level: string | null): number {
  if (level === 'critical' || level === '严重') return 92
  if (level === 'warning' || level === '预警') return 72
  if (level === 'attention' || level === '关注') return 48
  if (level === 'normal' || level === '正常') return 18
  return 0
}

export default function ProductionDecisionPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [greenhouses, setGreenhouses] = useState<Greenhouse[]>([])
  const [greenhouseId, setGreenhouseId] = useState<number | null>(null)
  const [decision, setDecision] = useState<CurrentDecision | null>(null)
  const [taskSummary, setTaskSummary] = useState<TaskSummary | null>(null)
  const [tasks, setTasks] = useState<FarmTask[]>([])
  const [trace, setTrace] = useState<TaskTrace | null>(null)
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null)
  const [taskView, setTaskView] = useState<'pending' | 'progress' | 'done'>('pending')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [taskCenterOpen, setTaskCenterOpen] = useState(false)
  const [messageApi, messageContext] = message.useMessage()

  const loadGreenhouses = useCallback(async () => {
    const result = await getGreenhouses({ page: 1, page_size: 100, status: 'active' })
    setGreenhouses(result.items)
    const fromUrl = Number(searchParams.get('greenhouse_id')) || null
    setGreenhouseId((current) => {
      if (current && result.items.some((item) => item.id === current)) return current
      if (fromUrl && result.items.some((item) => item.id === fromUrl)) return fromUrl
      return result.items[0]?.id ?? null
    })
  }, [searchParams])

  const loadWorkspace = useCallback(async () => {
    if (!greenhouseId) {
      setDecision(null)
      setTaskSummary(null)
      setTasks([])
      setTrace(null)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const [decisionResult, summaryResult, taskPage] = await Promise.all([
        getCurrentDecisions(greenhouseId),
        getTaskSummary(greenhouseId),
        getTasks({ greenhouse_id: greenhouseId, page: 1, page_size: 20 }),
      ])
      setDecision(decisionResult)
      setTaskSummary(summaryResult)
      setTasks(taskPage.items)
      setSelectedTaskId((current) => current && taskPage.items.some((item) => item.id === current) ? current : taskPage.items[0]?.id ?? null)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError))
    } finally {
      setLoading(false)
    }
  }, [greenhouseId])

  useEffect(() => {
    void loadGreenhouses().catch((requestError) => setError(getApiErrorMessage(requestError)))
  }, [loadGreenhouses])
  useEffect(() => { void loadWorkspace() }, [loadWorkspace])
  useEffect(() => {
    if (!selectedTaskId) {
      setTrace(null)
      return
    }
    void getTaskTrace(selectedTaskId).then(setTrace).catch(() => setTrace(null))
  }, [selectedTaskId])

  const review = async (item: DecisionRecommendation, accepted: boolean) => {
    try {
      if (accepted) await acceptDecision(item.id, '管理人员确认采纳')
      else await rejectDecision(item.id, '管理人员确认暂不采纳')
      messageApi.success(accepted ? '建议已采纳' : '建议已保留为未采纳记录')
      await loadWorkspace()
    } catch (requestError) {
      messageApi.error(getApiErrorMessage(requestError))
    }
  }

  const createTask = async (item: DecisionRecommendation) => {
    try {
      const task = await createTaskFromWarning(item.warning_event_id, '管理员')
      messageApi.success('已生成农事任务草稿')
      setSelectedTaskId(task.id)
      await loadWorkspace()
    } catch (requestError) {
      messageApi.error(getApiErrorMessage(requestError))
    }
  }

  const acceptedRecommendations = decision?.recommendations.filter((item) => item.status === 'accepted').length ?? 0
  const pendingRecommendations = decision?.recommendations.filter((item) => item.status === 'pending_review') ?? []
  const primaryRecommendation = pendingRecommendations[0] ?? decision?.recommendations[0] ?? null
  const riskScore = riskWeight(decision?.current_risk_level ?? null)

  const filteredTasks = useMemo(() => {
    if (taskView === 'pending') return tasks.filter((item) => ['draft', 'pending'].includes(item.status))
    if (taskView === 'progress') return tasks.filter((item) => item.status === 'in_progress')
    return tasks.filter((item) => item.status === 'completed')
  }, [taskView, tasks])

  const pathComparison = useMemo(() => {
    const highRisk = riskScore >= 70
    return [
      {
        name: '优先处置',
        badge: '推荐路径',
        tone: 'recommended',
        response: '立即进入人工检查或任务确认',
        evidence: '沿用当前风险证据和系统建议',
        exposure: highRisk ? '较低' : '低',
      },
      {
        name: '继续观察',
        badge: '备选路径',
        tone: 'observe',
        response: '等待下一时段数据后再复核',
        evidence: '需要新增环境数据重新研判',
        exposure: highRisk ? '较高' : '中',
      },
    ]
  }, [riskScore])

  return <div className="business-page production-workbench commercial-production-page">
    {messageContext}
    <div className="page-intro workbench-intro commercial-page-intro">
      <div>
        <span className="eyebrow">FARM OPERATIONS</span>
        <h1>今日农事中心</h1>
        <p>把 AI 建议、任务执行和 AgriTrace 证据链放进一个可操作的生产工作台。</p>
      </div>
      <Space wrap>
        <Button icon={<ScheduleOutlined />} onClick={() => setTaskCenterOpen(true)}>任务中心</Button>
        <Button type="primary" icon={<ReloadOutlined />} loading={loading} onClick={() => void loadWorkspace()}>刷新</Button>
      </Space>
    </div>

    <div className="production-control-strip">
      <div className="command-field">
        <span>目标大棚</span>
        <Select
          value={greenhouseId}
          placeholder="请选择大棚"
          onChange={(value) => {
            setGreenhouseId(value)
            const next = new URLSearchParams(searchParams)
            next.set('greenhouse_id', String(value))
            setSearchParams(next, { replace: true })
          }}
          options={greenhouses.map((item) => ({ value: item.id, label: `${item.name} · ${item.code}` }))}
        />
      </div>
      <div className="production-context commercial-production-context">
        <span>当前风险<strong>{decision?.current_risk_level ?? '暂无风险证据'}</strong></span>
        <span>生育阶段<strong>{decision?.growth_stage ?? '暂无批次'}</strong></span>
        <span>数据来源<strong>{decision?.data_source === 'sensor' ? '传感器数据' : decision?.data_source === 'import' ? '导入数据' : '暂无'}</strong></span>
      </div>
    </div>

    {error && <Alert className="page-alert" type="error" showIcon message="农事任务数据加载失败" description={error} />}
    {!greenhouseId ? <SaasEmptyState title="还没有运行中的大棚" description="先创建大棚并接入环境数据，系统会在这里形成决策与任务闭环。" /> : <>
      <div className="production-kpi-strip">
        <div><span>紧急</span><strong>{taskSummary?.urgent_total ?? 0}</strong></div>
        <div><span>待执行</span><strong>{taskSummary?.pending_total ?? 0}</strong></div>
        <div><span>执行中</span><strong>{taskSummary?.in_progress_total ?? 0}</strong></div>
        <div><span>今日完成</span><strong>{taskSummary?.completed_today ?? 0}</strong></div>
        <div><span>待审核建议</span><strong>{pendingRecommendations.length}</strong></div>
        <div><span>已采纳建议</span><strong>{acceptedRecommendations}</strong></div>
      </div>

      <div className="farm-ops-grid">
        <section className="task-board surface-card surface-card-major">
          <SectionHeading title="今日任务" description="按任务状态快速处理当前生产事项" action={<Segmented value={taskView} onChange={(value) => setTaskView(value as 'pending' | 'progress' | 'done')} options={[{ label: '待处理', value: 'pending' }, { label: '进行中', value: 'progress' }, { label: '已完成', value: 'done' }]} />} />
          {filteredTasks.length ? <div className="commercial-task-list">{filteredTasks.slice(0, 8).map((task) => <button key={task.id} className={`commercial-task-row ${selectedTaskId === task.id ? 'is-selected' : ''}`} onClick={() => setSelectedTaskId(task.id)}>
            <i className={`task-priority-dot priority-${task.priority}`} />
            <span className="task-row-copy"><strong>{task.title}</strong><small>{task.task_code} · {task.assignee_name || '待分配'} · {task.action_type}</small></span>
            <span className="task-row-meta"><Tag color={taskStatusMeta[task.status]?.color}>{taskStatusMeta[task.status]?.label ?? task.status}</Tag><small>{task.due_at ? `截止 ${shortTime(task.due_at)}` : '无固定截止时间'}</small></span>
          </button>)}</div> : <SaasEmptyState title={taskView === 'done' ? '今天还没有已完成任务' : '当前没有待处理任务'} description={taskView === 'done' ? '完成任务后会自动沉淀到 AgriTrace 证据链。' : '出现环境风险、病害复核或人工任务后，会自动进入这里。'} />}
        </section>

        <aside className="ai-decision-panel">
          <div className="ai-decision-head"><span><ThunderboltOutlined /> AI 建议</span><Tag color={riskScore >= 70 ? 'orange' : 'green'}>{decision?.current_risk_level ?? '暂无风险'}</Tag></div>
          {primaryRecommendation ? <>
            <h2>{primaryRecommendation.title}</h2>
            <p>{primaryRecommendation.rationale}</p>
            <div className="ai-risk-meter"><span>风险权重<b>{riskScore}</b></span><Progress percent={riskScore} showInfo={false} strokeColor={riskScore >= 70 ? '#e66b4e' : '#13815f'} trailColor="rgba(255,255,255,.18)" /></div>
            <div className="ai-action-preview"><span>建议动作</span>{primaryRecommendation.action_steps_json.slice(0, 3).map((step, index) => <div key={`${primaryRecommendation.id}-${index}`}><b>{index + 1}</b><p>{step}</p></div>)}</div>
            <div className="ai-decision-actions">
              {primaryRecommendation.status === 'pending_review' && <><Button onClick={() => void review(primaryRecommendation, false)}>暂不采纳</Button><Button type="primary" onClick={() => void review(primaryRecommendation, true)}>采用建议</Button></>}
              {primaryRecommendation.status === 'accepted' && <Button type="primary" icon={<ScheduleOutlined />} onClick={() => void createTask(primaryRecommendation)}>生成任务</Button>}
            </div>
          </> : <SaasEmptyState title="暂时没有新的 AI 建议" description="系统会结合当前风险、生育阶段和预测结果持续研判。" />}
        </aside>
      </div>

      <div className="decision-workbench-grid">
        <section className="surface-card decision-recommendation-card commercial-recommendation-panel">
          <SectionHeading title="可解释决策建议" description="每条建议都保留判断依据、执行步骤与人工确认状态" action={<Tag color={decision?.recommendations.length ? 'green' : 'default'}>{decision?.recommendations.length ?? 0} 条建议</Tag>} />
          {decision?.recommendations.length ? <div className="recommendation-stack">{decision.recommendations.map((item) => <div className="recommendation-card" key={item.id}>
            <div className="recommendation-head">
              <div>
                <Space size={6}><Tag color={priorityMeta[item.priority]?.color}>{priorityMeta[item.priority]?.label ?? item.priority}</Tag><Tag>{item.action_type}</Tag></Space>
                <h3>{item.title}</h3>
              </div>
              <Tag color={item.status === 'accepted' ? 'green' : item.status === 'rejected' ? 'default' : 'gold'}>{item.status === 'accepted' ? '已采纳' : item.status === 'rejected' ? '未采纳' : '待审核'}</Tag>
            </div>
            <div className="decision-evidence-box"><span>判断依据</span><p>{item.rationale}</p></div>
            <div className="decision-steps">{item.action_steps_json.map((step, index) => <div key={`${item.id}-${index}`}><strong>{index + 1}</strong><span>{step}</span></div>)}</div>
            <div className="recommendation-footer"><span><ClockCircleOutlined /> 建议时机：{time(item.execute_before)}</span><Space>{item.status === 'pending_review' && <><Button size="small" onClick={() => void review(item, false)}>暂不采纳</Button><Button size="small" type="primary" onClick={() => void review(item, true)}>采纳建议</Button></>}{item.status === 'accepted' && <Button size="small" type="primary" icon={<ScheduleOutlined />} onClick={() => void createTask(item)}>生成任务</Button>}</Space></div>
          </div>)}</div> : <SaasEmptyState title="暂无风险证据" description="当环境或病害出现需要处置的风险时，系统会生成可解释建议。" />}
        </section>

        <section className="surface-card path-decision-panel">
          <SectionHeading title="处置路径" description="对比不同处置方式的风险暴露" action={<ForkOutlined />} />
          <div className="risk-score-line"><div><span>当前风险权重</span><strong>{riskScore}</strong></div><Progress percent={riskScore} showInfo={false} strokeColor={riskScore >= 70 ? '#e66b4e' : '#13815f'} /></div>
          <div className="path-comparison-list">{pathComparison.map((path) => <div className={`path-option ${path.tone}`} key={path.name}><div><strong>{path.name}</strong><Tag color={path.tone === 'recommended' ? 'green' : 'default'}>{path.badge}</Tag></div><span>响应：{path.response}</span><span>证据：{path.evidence}</span><span>风险暴露：<b>{path.exposure}</b></span></div>)}</div>
          <div className="path-note"><SafetyCertificateOutlined /> 路径对比用于安排处置优先级，最终操作由管理人员确认。</div>
        </section>
      </div>

      <section className="agritrace-showcase">
        <div className="agritrace-heading"><div><span className="eyebrow">AGRITRACE</span><h2>决策证据链</h2><p>从数据采集到农事执行，每一步都留下可追溯证据。</p></div>{trace && <Tag color="green">任务 #{trace.task_id}</Tag>}</div>
        {trace?.nodes.length ? <div className="agritrace-flow">{trace.nodes.map((node, index) => <div className="agritrace-node" key={`${node.type}-${node.id}-${index}`}>
          <div className={`agritrace-dot ${node.status === 'critical' ? 'critical' : node.status === 'completed' ? 'completed' : ''}`}>{String(index + 1).padStart(2, '0')}</div>
          <time>{shortTime(node.occurred_at)}</time>
          <strong>{node.title}</strong>
          <span>{node.type}</span>
          <p>{node.summary}</p>
          {index < trace.nodes.length - 1 && <i />}
        </div>)}</div> : <SaasEmptyState title="选择一条任务查看完整证据链" description="环境采集、风险分析、AI 建议、任务创建和执行反馈会按时间串联。" />}
        {trace?.causality_notice && <div className="agritrace-notice">{trace.causality_notice}</div>}
      </section>
    </>}

    <Drawer title="农事任务中心" width="min(1280px, 97vw)" open={taskCenterOpen} onClose={() => { setTaskCenterOpen(false); void loadWorkspace() }} destroyOnHidden>
      <div className="embedded-task-center"><FarmTaskManagementPage /></div>
    </Drawer>
  </div>
}
