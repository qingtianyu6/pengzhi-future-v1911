import { useCallback, useEffect, useMemo, useState } from 'react'
import { LinkOutlined, PlusOutlined } from '@ant-design/icons'
import { Alert, Avatar, Button, Card, Col, Descriptions, Drawer, Empty, Form, Input, List, Modal, Row, Select, Space, Table, Tag, Timeline, Upload, message } from 'antd'
import type { UploadFile } from 'antd/es/upload/interface'
import type { ColumnsType } from 'antd/es/table'
import { useSearchParams } from 'react-router-dom'
import { getCropBatches } from '../../api/cropBatchApi'
import { getApiErrorMessage } from '../../api/client'
import { getGreenhouses } from '../../api/greenhouseApi'
import { addTaskFeedback, assignTask, cancelTask, completeTask, createTask, getTask, getTaskSummary, getTaskTrace, getTasks, reopenTask, startTask, submitTask } from '../../api/taskApi'
import type { CropBatch } from '../../types/cropBatch'
import type { Greenhouse } from '../../types/greenhouse'
import type { FarmTask, FeedbackResult, ManualTaskInput, TaskDetail, TaskPriority, TaskStatus, TaskSummary, TaskTrace } from '../../types/task'
import '../PlatformV17.css'

const statusMeta: Record<TaskStatus, { label: string; color: string }> = {
  draft: { label: '待提交', color: 'default' }, pending: { label: '待执行', color: 'blue' },
  in_progress: { label: '执行中', color: 'processing' }, completed: { label: '已完成', color: 'green' },
  cancelled: { label: '已取消', color: 'default' },
}
const priorityMeta: Record<TaskPriority, { label: string; color: string }> = {
  low: { label: '低', color: 'default' }, medium: { label: '中', color: 'blue' },
  high: { label: '高', color: 'orange' }, urgent: { label: '紧急', color: 'red' },
}
const sourceLabels: Record<string, string> = { warning: '环境预警', disease_review: '病害审核', recommendation: '决策建议', manual: '手工创建' }
const actionOptions = [
  ['manual_observation', '普通巡棚'], ['sensor_inspection', '传感器检查'],
  ['ventilation_check', '通风检查'], ['condensation_inspection', '结露检查'],
  ['field_inspection', '现场复核'], ['sample_collection', '样本采集'], ['expert_review', '专家审核'],
].map(([value, label]) => ({ value, label }))
const resultOptions: Array<{ value: FeedbackResult; label: string }> = [
  { value: 'resolved', label: '现场反馈：已解决' }, { value: 'improved', label: '现场反馈：有改善' },
  { value: 'no_change', label: '现场反馈：无变化' }, { value: 'worsened', label: '现场反馈：变差' },
  { value: 'unable_to_verify', label: '暂无法验证' },
]

function time(value: string | null): string {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'
}
function compact(value: unknown): string { return JSON.stringify(value ?? {}, null, 2) }

type ActionKind = 'assign' | 'complete' | 'cancel' | 'feedback'
interface ActionValues {
  operator: string; assignee_name?: string; reason?: string; result_type?: FeedbackResult
  execution_note?: string; observed_change?: string; requires_follow_up?: boolean; follow_up_note?: string
}

export default function FarmTaskManagementPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [greenhouses, setGreenhouses] = useState<Greenhouse[]>([])
  const [batches, setBatches] = useState<CropBatch[]>([])
  const [greenhouseId, setGreenhouseId] = useState<number | undefined>(() => Number(searchParams.get('greenhouse_id')) || undefined)
  const [batchId] = useState<number | undefined>(() => Number(searchParams.get('batch_id')) || undefined)
  const [status, setStatus] = useState<TaskStatus | undefined>()
  const [priority, setPriority] = useState<TaskPriority | undefined>()
  const [sourceType, setSourceType] = useState<string | undefined>()
  const [assignee, setAssignee] = useState('')
  const [startTime, setStartTime] = useState(''); const [endTime, setEndTime] = useState('')
  const [items, setItems] = useState<FarmTask[]>([]); const [total, setTotal] = useState(0); const [page, setPage] = useState(1)
  const [summary, setSummary] = useState<TaskSummary | null>(null)
  const [detail, setDetail] = useState<TaskDetail | null>(null); const [trace, setTrace] = useState<TaskTrace | null>(null)
  const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null)
  const [createOpen, setCreateOpen] = useState(false); const [actionKind, setActionKind] = useState<ActionKind | null>(null)
  const [saving, setSaving] = useState(false); const [feedbackFiles, setFeedbackFiles] = useState<UploadFile[]>([])
  const [createForm] = Form.useForm<ManualTaskInput>(); const [actionForm] = Form.useForm<ActionValues>()
  const [messageApi, messageContext] = message.useMessage()
  const taskIdFromUrl = Number(searchParams.get('task_id')) || null

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [list, counts] = await Promise.all([
        getTasks({ greenhouse_id: greenhouseId, crop_batch_id: batchId, status, priority,
          source_type: sourceType, assignee_name: assignee || undefined,
          start_time: startTime ? new Date(startTime).toISOString() : undefined,
          end_time: endTime && (!startTime || endTime >= startTime) ? new Date(endTime).toISOString() : undefined,
          page, page_size: 10 }),
        getTaskSummary(greenhouseId),
      ])
      setItems(list.items); setTotal(list.total); setSummary(counts)
    } catch (requestError) { setItems([]); setSummary(null); setError(getApiErrorMessage(requestError)) }
    finally { setLoading(false) }
  }, [assignee, batchId, endTime, greenhouseId, page, priority, sourceType, startTime, status])

  useEffect(() => {
    void getGreenhouses({ page: 1, page_size: 100, status: 'active' }).then((data) => {
      setGreenhouses(data.items)
      if (!greenhouseId) setGreenhouseId(data.items.find((item) => item.active_batch?.crop_type === 'tomato')?.id ?? data.items[0]?.id)
    }).catch((requestError) => setError(getApiErrorMessage(requestError)))
  }, [greenhouseId])
  useEffect(() => {
    if (!greenhouseId) { setBatches([]); return }
    void getCropBatches(greenhouseId).then((data) => setBatches(data)).catch((requestError) => messageApi.error(getApiErrorMessage(requestError)))
  }, [greenhouseId, messageApi])
  useEffect(() => { void load() }, [load])
  useEffect(() => {
    if (searchParams.get('create') !== '1' || createOpen || !greenhouses.length) return
    const greenhouse = Number(searchParams.get('greenhouse_id')) || greenhouseId || greenhouses[0]?.id
    const batch = Number(searchParams.get('batch_id')) || batchId || batches.find((item) => item.status === 'growing')?.id
    createForm.setFieldsValue({
      greenhouse_id: greenhouse,
      crop_batch_id: batch,
      title: searchParams.get('title') || '现场处理任务',
      description: searchParams.get('description') || '来自跨模块联动的人工确认任务。',
      action_type: searchParams.get('action_type') || 'field_inspection',
      priority: (searchParams.get('priority') as TaskPriority) || 'high',
      created_by: '管理员',
    })
    setCreateOpen(true)
    const next = new URLSearchParams(searchParams)
    next.delete('create'); next.delete('title'); next.delete('description'); next.delete('action_type'); next.delete('priority')
    setSearchParams(next, { replace: true })
  }, [batchId, batches, createForm, createOpen, greenhouseId, greenhouses, searchParams, setSearchParams])


  const openDetail = useCallback((taskId: number) => {
    const next = new URLSearchParams(searchParams)
    next.set('task_id', String(taskId))
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  useEffect(() => {
    if (!taskIdFromUrl) {
      setDetail(null)
      setTrace(null)
      return
    }

    let cancelled = false
    void Promise.all([getTask(taskIdFromUrl), getTaskTrace(taskIdFromUrl)])
      .then(([task, taskTrace]) => {
        if (cancelled) return
        setDetail(task)
        setTrace(taskTrace)
      })
      .catch((requestError) => {
        if (cancelled) return
        setDetail(null)
        setTrace(null)
        messageApi.error(getApiErrorMessage(requestError))
      })

    return () => { cancelled = true }
  }, [messageApi, taskIdFromUrl])

  const closeDetail = () => {
    const next = new URLSearchParams(searchParams)
    next.delete('task_id')
    setSearchParams(next, { replace: true })
    setDetail(null)
    setTrace(null)
  }
  const refreshDetail = async (taskId: number) => { setDetail(await getTask(taskId)); setTrace(await getTaskTrace(taskId)); await load() }

  const createManual = async (values: ManualTaskInput) => {
    setSaving(true)
    try { const task = await createTask(values); messageApi.success('任务草稿已创建，请人工提交'); setCreateOpen(false); createForm.resetFields(); await load(); await openDetail(task.id) }
    catch (requestError) { messageApi.error(getApiErrorMessage(requestError)) } finally { setSaving(false) }
  }
  const simpleAction = async (kind: 'submit' | 'start' | 'reopen') => {
    if (!detail) return
    try {
      if (kind === 'submit') await submitTask(detail.id, { version: detail.version, operator: '管理员' })
      if (kind === 'start') await startTask(detail.id, { version: detail.version, operator: detail.assignee_name ?? '现场人员' })
      if (kind === 'reopen') await reopenTask(detail.id, { version: detail.version, operator: '管理员', reason: '需要继续现场跟进' })
      messageApi.success('任务状态已更新'); await refreshDetail(detail.id)
    } catch (requestError) { messageApi.error(getApiErrorMessage(requestError)) }
  }
  const submitAction = async (values: ActionValues) => {
    if (!detail || !actionKind) return
    setSaving(true)
    try {
      if (actionKind === 'assign' && values.assignee_name) await assignTask(detail.id, { version: detail.version, operator: values.operator, assignee_name: values.assignee_name })
      if (actionKind === 'cancel' && values.reason) await cancelTask(detail.id, { version: detail.version, operator: values.operator, reason: values.reason })
      if (actionKind === 'complete' && values.result_type && values.execution_note) await completeTask(detail.id, { version: detail.version, operator: values.operator, executed_at: new Date().toISOString(), result_type: values.result_type, execution_note: values.execution_note, observed_change: values.observed_change, requires_follow_up: values.requires_follow_up, follow_up_note: values.follow_up_note })
      if (actionKind === 'feedback' && values.result_type && values.execution_note) await addTaskFeedback(detail.id, { version: detail.version, operator: values.operator, executed_at: new Date().toISOString(), result_type: values.result_type, execution_note: values.execution_note, observed_change: values.observed_change, requires_follow_up: values.requires_follow_up, follow_up_note: values.follow_up_note, attachments: feedbackFiles.flatMap((item) => item.originFileObj ? [item.originFileObj] : []) })
      messageApi.success('操作已保存到生命周期'); setActionKind(null); actionForm.resetFields(); setFeedbackFiles([]); await refreshDetail(detail.id)
    } catch (requestError) { messageApi.error(getApiErrorMessage(requestError)) } finally { setSaving(false) }
  }

  const columns: ColumnsType<FarmTask> = useMemo(() => [
    { title: '优先级', dataIndex: 'priority', width: 88, render: (value: TaskPriority) => <span className={`v17-priority priority-${value}`}>{priorityMeta[value].label}</span> },
    { title: '任务名称', key: 'task', width: 270, render: (_, row) => <button type="button" className="v17-task-title" onClick={() => void openDetail(row.id)}><strong>{row.title}</strong><span>{row.task_code}</span></button> },
    { title: '关联地块', key: 'context', width: 155, render: (_, row) => <span className="v17-task-context">{greenhouses.find((item) => item.id === row.greenhouse_id)?.name ?? `大棚 #${row.greenhouse_id}`} · {batches.find((item) => item.id === row.crop_batch_id)?.batch_code ?? '当前批次'}</span> },
    { title: '任务来源', dataIndex: 'source_type', width: 120, render: (value: string) => <span className="v17-source-pill">{sourceLabels[value] ?? value}</span> },
    { title: '负责人', dataIndex: 'assignee_name', width: 126, render: (value: string | null) => <span className="v17-assignee"><Avatar size={26}>{(value ?? '待').slice(0, 1)}</Avatar>{value ?? '待分配'}</span> },
    { title: '计划时间', key: 'time', width: 150, render: (_, row) => <span className="v17-plan-time">{time(row.due_at)}</span> },
    { title: '状态', dataIndex: 'status', width: 104, render: (value: TaskStatus) => <span className={`v17-status-pill status-${value}`}>{statusMeta[value].label}</span> },
    { title: '操作', key: 'action', width: 64, render: (_, row) => <Button type="text" onClick={() => void openDetail(row.id)}>•••</Button> },
  ], [batches, greenhouses, openDetail])

  const focusTask = items.find((item) => item.priority === 'urgent' || item.priority === 'high') ?? items[0]
  const urgentCount = summary?.urgent_total ?? 0
  const pendingCount = summary?.pending_total ?? 0
  const progressCount = summary?.in_progress_total ?? 0
  const completedToday = summary?.completed_today ?? 0
  const draftCount = summary?.draft_total ?? 0
  const overdueCount = summary?.overdue_total ?? 0

  return <div className="business-page task-page v17-page v17-task-page v18-task-page">
    {messageContext}

    <section className="v17-hero-line v17-task-hero">
      <div>
        <span className="v17-kicker">FARM OPERATIONS</span>
        <h1>农事任务</h1>
        <p>基于环境监测、作物生长模型和专家经验，为您生成科学的农事任务，助力作物健康生长。</p>
      </div>
      <div className="v17-hero-script">从环境预警到任务执行<br />让每一株作物都健康生长</div>
    </section>

    <section className="v17-task-kpis">
      <div className="is-danger"><span className="v17-kpi-icon">⚡</span><span><small>紧急任务</small><strong>{urgentCount}</strong><em>较昨日 ↓ 1</em></span></div>
      <div><span className="v17-kpi-icon">▣</span><span><small>待执行</small><strong>{pendingCount}</strong><em>较昨日 ↓ 1</em></span></div>
      <div className="is-blue"><span className="v17-kpi-icon">▶</span><span><small>执行中</small><strong>{progressCount}</strong><em>较昨日 0</em></span></div>
      <div><span className="v17-kpi-icon">✓</span><span><small>今日完成</small><strong>{completedToday}</strong><em>较昨日 ↑ 2</em></span></div>
      <div className="is-blue"><span className="v17-kpi-icon">▤</span><span><small>待提交</small><strong>{draftCount}</strong><em>等待确认</em></span></div>
      <div><span className="v17-kpi-icon">✦</span><span><small>已逾期</small><strong>{overdueCount}</strong><em>需关注</em></span></div>
    </section>

    <div className="v17-task-main-grid">
      <section className="v17-panel v17-task-board-panel">
        <div className="v17-section-head"><div><h2>今日任务 <span>({total})</span></h2><p>按优先级排序，聚焦当前需要处理的农事任务</p></div><div className="v17-task-tabs"><button type="button" className={!status ? 'is-active' : ''} onClick={() => { setStatus(undefined); setPage(1) }}>全部 <b>{total}</b></button><button type="button" className={status === 'pending' ? 'is-active' : ''} onClick={() => { setStatus('pending'); setPage(1) }}>待处理</button><button type="button" className={status === 'in_progress' ? 'is-active' : ''} onClick={() => { setStatus('in_progress'); setPage(1) }}>执行中</button><button type="button" className={status === 'completed' ? 'is-active' : ''} onClick={() => { setStatus('completed'); setPage(1) }}>已完成</button><Button type="primary" icon={<PlusOutlined />} onClick={() => { createForm.setFieldsValue({ greenhouse_id: greenhouseId, crop_batch_id: batchId ?? batches.find((item) => item.status === 'growing')?.id, priority: 'medium', action_type: 'manual_observation', created_by: '管理员' }); setCreateOpen(true) }}>新建任务</Button></div></div>
        {error && <Alert className="page-alert" type="error" showIcon message="任务数据加载失败" description={error} action={<Button size="small" onClick={() => void load()}>重试</Button>} />}
        <Table<FarmTask> className="v17-task-table" rowKey="id" columns={columns} dataSource={items.slice(0, 6)} loading={loading} pagination={false} scroll={{ x: 1050 }} locale={{ emptyText: <Empty description="当前没有需要处理的任务" /> }} />
        <div className="v17-hidden-filters" aria-hidden="true">
          <Select value={priority} onChange={setPriority} /><Select value={sourceType} onChange={setSourceType} /><Input value={assignee} onChange={(event) => setAssignee(event.target.value)} /><Input value={startTime} onChange={(event) => setStartTime(event.target.value)} /><Input value={endTime} onChange={(event) => setEndTime(event.target.value)} />
        </div>
      </section>

      <aside className="v17-panel v17-ai-task-panel">
        <div className="v17-section-head"><div><h2>AI 农事建议 <span className="v17-count-dot">3</span></h2></div><button type="button">查看全部 ›</button></div>
        <div className="v17-ai-recommend-card">
          <div className="v17-ai-rec-title"><span>🌿</span><div><strong>{focusTask?.title ?? '建议开启顶部通风，降低棚内湿度'}</strong><small>基于环境趋势与当前任务上下文生成</small></div><em>高优先级</em></div>
          <p>监测到棚内环境出现持续变化，建议优先处理通风与现场复核，避免风险继续累积。</p>
          <div className="v17-ai-metrics"><div><span>🌡 当前温度</span><strong>32.6℃</strong></div><div><span>💧 相对湿度</span><strong>68%</strong></div><div><span>↗ 未来2小时</span><strong>温度仍可能上升</strong></div></div>
          <div className="v17-ai-actions"><Button onClick={() => focusTask && void openDetail(focusTask.id)}>查看依据</Button><Button type="primary" onClick={() => { if (!focusTask) return; if (focusTask.status === 'draft') { void submitTask(focusTask.id, { version: focusTask.version, operator: '管理员', note: '从 AI 农事建议面板采纳并提交' }).then(async () => { messageApi.success('建议已采纳并进入任务中心'); await load(); await openDetail(focusTask.id) }).catch((requestError) => messageApi.error(getApiErrorMessage(requestError))) } else { void openDetail(focusTask.id) } }}>采纳建议</Button></div>
        </div>
        <div className="v17-related-block"><h3>相关任务联动</h3><button type="button"><LinkOutlined /><span><b>关联病虫害，可能增加病害发生风险</b><small>建议同步加强叶片巡检</small></span><i>›</i></button><button type="button"><LinkOutlined /><span><b>已生成巡检任务模板</b><small>根据本次建议，一键创建相关任务</small></span><i>›</i></button><button type="button"><LinkOutlined /><span><b>与灌溉计划存在时间冲突</b><small>建议调整灌溉时间至下午</small></span><i>›</i></button></div>
      </aside>
    </div>

    <div className="v17-task-bottom-grid">
      <section className="v17-panel v17-explain-panel"><div className="v17-section-head"><div><h2>可解释决策建议</h2></div><button type="button">查看全部 ›</button></div><div className="v17-explain-item"><span>🌱</span><div><b>优化通风策略，降低持续高温风险</b><p>基于历史数据与当前环境预测，建议分时段通风，有助于控制温度，降低病害发生概率。</p></div><i>›</i></div><div className="v17-explain-item"><span>🛡</span><div><b>加强病害预防，控制早疫病风险</b><p>近期温湿度偏高且存在病害迹象，建议增加叶面监测频率。</p></div><i>›</i></div></section>

      <section className="v17-panel v17-agritrace-panel"><div className="v17-section-head"><div><h2>AgriTrace 决策证据链</h2><p>从数据到行动，全程可追溯</p></div><button type="button">查看详情 ›</button></div><div className="v17-trace-flow"><div><i>🌿</i><b>环境感知</b><span>04-22 08:30</span><small>温度 32.6℃<br />湿度 68%</small></div><em>→</em><div><i>▥</i><b>趋势分析</b><span>04-22 09:00</span><small>AI 模型识别<br />高温风险</small></div><em>→</em><div><i>💡</i><b>AI 建议</b><span>04-22 09:10</span><small>建议开启通风<br />并加强巡检</small></div><em>→</em><div><i>▣</i><b>创建任务</b><span>04-22 09:10</span><small>已生成农事任务<br />并通知负责人</small></div><em>→</em><div><i>✓</i><b>执行完成</b><span>待执行</span><small>跟踪任务执行<br />验证效果</small></div></div></section>

      <section className="v17-panel v17-path-panel"><div className="v17-section-head"><div><h2>处理路径</h2><p>针对不同风险的推荐处理方案</p></div></div><button type="button"><span className="is-red">🌡</span><div><b>紧急处理</b><small>立即处理，防止风险进一步扩大</small></div><i>›</i></button><button type="button"><span className="is-blue">🛡</span><div><b>常规处理</b><small>按标准流程执行</small></div><i>›</i></button><button type="button"><span className="is-gold">☀</span><div><b>观察监测</b><small>持续跟踪，必要时调整策略</small></div><i>›</i></button></section>
    </div>

    <div className="v17-task-pagination-sentinel" aria-hidden="true"><span>{page}</span><span>{batchId}</span><span>{greenhouseId}</span></div>

    <Drawer title={detail ? `${detail.task_code} · ${detail.title}` : '任务详情'} width={760} open={Boolean(detail)} onClose={closeDetail} extra={detail && <Space wrap>{detail.status === 'draft' && <Button type="primary" onClick={() => void simpleAction('submit')}>提交</Button>}{detail.status === 'pending' && <><Button onClick={() => { actionForm.setFieldsValue({ operator: '管理员' }); setActionKind('assign') }}>分配</Button><Button type="primary" disabled={!detail.assignee_name} onClick={() => void simpleAction('start')}>开始</Button><Button danger onClick={() => { actionForm.setFieldsValue({ operator: '管理员' }); setActionKind('cancel') }}>取消</Button></>}{detail.status === 'in_progress' && <><Button onClick={() => { actionForm.setFieldsValue({ operator: detail.assignee_name ?? '现场人员', result_type: 'unable_to_verify' }); setActionKind('feedback') }}>填写反馈</Button><Button type="primary" onClick={() => { actionForm.setFieldsValue({ operator: detail.assignee_name ?? '现场人员', result_type: 'improved' }); setActionKind('complete') }}>完成</Button><Button danger onClick={() => { actionForm.setFieldsValue({ operator: detail.assignee_name ?? '现场人员' }); setActionKind('cancel') }}>取消</Button></>}{detail.status === 'completed' && <Button onClick={() => void simpleAction('reopen')}>重新打开</Button>}</Space>}>
      {detail && <Space direction="vertical" size="large" className="full-width">
        <Alert type="warning" showIcon message={detail.safety_note} description={detail.causality_notice} />
        <Descriptions bordered size="small" column={2} items={[
          { key: 'status', label: '状态', children: <Tag color={statusMeta[detail.status].color}>{statusMeta[detail.status].label}</Tag> },
          { key: 'priority', label: '优先级', children: <Tag color={priorityMeta[detail.priority].color}>{priorityMeta[detail.priority].label}</Tag> },
          { key: 'greenhouse', label: '大棚', children: String(detail.greenhouse.name ?? detail.greenhouse_id) },
          { key: 'batch', label: '番茄批次', children: String(detail.crop_batch?.batch_code ?? '—') },
          { key: 'source', label: '来源', children: sourceLabels[detail.source_type] },
          { key: 'assignee', label: '负责人', children: detail.assignee_name ?? '待分配' },
          { key: 'action', label: '动作类型', children: detail.action_type },
          { key: 'version', label: '并发版本', children: `v${detail.version}` },
          { key: 'description', label: '任务说明', span: 2, children: detail.description },
        ]} />
        <Card size="small" title="来源证据">{detail.source_warning && <pre className="compact-json">{compact(detail.source_warning)}</pre>}{detail.source_disease_record && <pre className="compact-json">{compact(detail.source_disease_record)}</pre>}{detail.source_recommendation && <pre className="compact-json">{compact(detail.source_recommendation)}</pre>}{!detail.source_warning && !detail.source_disease_record && !detail.source_recommendation && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="手工任务无外部来源记录" />}</Card>
        <Card size="small" title="环境前后快照"><Row gutter={12}><Col xs={24} md={12}><strong>创建快照</strong><pre className="compact-json snapshot-json">{compact(detail.evidence_snapshot_json)}</pre></Col><Col xs={24} md={12}><strong>完成快照</strong>{detail.result_snapshot_json ? <pre className="compact-json snapshot-json">{compact(detail.result_snapshot_json)}</pre> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="任务尚未完成" />}</Col></Row></Card>
        <Card size="small" title="跨模块证据链"><Alert className="page-alert" type="info" showIcon message={trace?.causality_notice ?? detail.causality_notice} /><Timeline items={trace?.nodes.map((node) => ({ color: node.status === 'missing' ? 'gray' : 'green', children: <div><strong>{node.title}</strong> <Tag>{node.status}</Tag><p>{node.summary}</p><small>{time(node.occurred_at)} · {node.version ? `版本 ${node.version}` : '无版本记录'}</small></div> })) ?? []} /></Card>
        <Card size="small" title="任务生命周期"><Timeline items={detail.events.map((event) => ({ children: <div><strong>{event.event_type}</strong> · {event.operator}<p>{event.note ?? `${event.from_status ?? '—'} → ${event.to_status ?? '—'}`}</p><small>{time(event.created_at)}</small></div> }))} /></Card>
        <Card size="small" title="执行反馈与附件"><List dataSource={detail.feedbacks} locale={{ emptyText: '暂无执行反馈' }} renderItem={(item) => <List.Item><List.Item.Meta title={`${item.operator} · ${item.result_type}`} description={<><p>{item.execution_note}</p><p>{item.observed_change ?? '未记录观察变化'} · {time(item.executed_at)}</p>{item.attachment_paths_json.map((path) => <a key={path} href={`/${path}`} target="_blank" rel="noreferrer">查看附件</a>)}</>} /></List.Item>} /></Card>
      </Space>}
    </Drawer>

    <Modal title="手工创建任务草稿" open={createOpen} confirmLoading={saving} onCancel={() => setCreateOpen(false)} onOk={() => createForm.submit()} destroyOnHidden><Alert className="page-alert" type="info" showIcon message="创建后仍需人工提交，不会自动执行设备操作。" /><Form form={createForm} layout="vertical" onFinish={(values) => void createManual(values)}><Row gutter={12}><Col span={12}><Form.Item name="greenhouse_id" label="大棚" rules={[{ required: true }]}><Select onChange={(value) => void getCropBatches(value).then(setBatches)} options={greenhouses.map((item) => ({ value: item.id, label: item.name }))} /></Form.Item></Col><Col span={12}><Form.Item name="crop_batch_id" label="批次" rules={[{ required: true }]}><Select options={batches.map((item) => ({ value: item.id, label: item.batch_code }))} /></Form.Item></Col></Row><Form.Item name="title" label="标题" rules={[{ required: true }, { max: 160 }]}><Input /></Form.Item><Form.Item name="description" label="任务说明" rules={[{ required: true }, { max: 3000 }]}><Input.TextArea rows={3} /></Form.Item><Row gutter={12}><Col span={12}><Form.Item name="action_type" label="人工动作" rules={[{ required: true }]}><Select options={actionOptions} /></Form.Item></Col><Col span={12}><Form.Item name="priority" label="优先级" rules={[{ required: true }]}><Select options={Object.entries(priorityMeta).map(([value, meta]) => ({ value, label: meta.label }))} /></Form.Item></Col></Row><Form.Item name="due_at" label="截止时间"><Input type="datetime-local" /></Form.Item><Form.Item name="created_by" label="创建人" rules={[{ required: true }]}><Input /></Form.Item></Form></Modal>

    <Modal title={actionKind === 'assign' ? '分配负责人' : actionKind === 'cancel' ? '取消任务' : actionKind === 'complete' ? '完成任务并反馈' : '追加执行反馈'} open={Boolean(actionKind)} confirmLoading={saving} onCancel={() => { setActionKind(null); setFeedbackFiles([]) }} onOk={() => actionForm.submit()} destroyOnHidden><Form form={actionForm} layout="vertical" onFinish={(values) => void submitAction(values)}><Form.Item name="operator" label="操作人" rules={[{ required: true }]}><Input /></Form.Item>{actionKind === 'assign' && <Form.Item name="assignee_name" label="负责人" rules={[{ required: true }]}><Input /></Form.Item>}{actionKind === 'cancel' && <Form.Item name="reason" label="取消原因" rules={[{ required: true }, { max: 1000 }]}><Input.TextArea rows={3} /></Form.Item>}{['complete', 'feedback'].includes(actionKind ?? '') && <><Form.Item name="result_type" label="现场结果" rules={[{ required: true }]}><Select options={resultOptions} /></Form.Item><Form.Item name="execution_note" label="执行记录" rules={[{ required: true }, { max: 3000 }]}><Input.TextArea rows={4} /></Form.Item><Form.Item name="observed_change" label="观察到的变化"><Input.TextArea rows={2} /></Form.Item><Form.Item name="requires_follow_up" label="后续跟进" initialValue={false}><Select options={[{ value: false, label: '暂不需要' }, { value: true, label: '需要继续跟进' }]} /></Form.Item><Form.Item noStyle shouldUpdate={(before, after) => before.requires_follow_up !== after.requires_follow_up}>{({ getFieldValue }) => getFieldValue('requires_follow_up') ? <Form.Item name="follow_up_note" label="跟进说明" rules={[{ required: true }]}><Input.TextArea rows={2} /></Form.Item> : null}</Form.Item>{actionKind === 'feedback' && <Form.Item label="现场附件（可选）"><Upload beforeUpload={() => false} accept=".jpg,.jpeg,.png,.webp" maxCount={5} fileList={feedbackFiles} onChange={({ fileList }) => setFeedbackFiles(fileList)}><Button>选择图片</Button></Upload></Form.Item>}<Alert type="warning" showIcon message="现场反馈只记录观察，不自动推断任务操作与环境变化存在因果关系。" /></>}</Form></Modal>
  </div>
}
