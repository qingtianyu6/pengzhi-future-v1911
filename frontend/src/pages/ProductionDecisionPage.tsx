import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Alert, Button, Calendar, Drawer, Empty, Input, Pagination, Popover, Select, Skeleton, message } from 'antd'
import { ArrowRightOutlined, CalendarOutlined, CheckOutlined, ClockCircleOutlined, EnvironmentOutlined, FileTextOutlined, FilterOutlined, LineChartOutlined, PlayCircleOutlined, PlusOutlined, ReloadOutlined, RightOutlined, SearchOutlined, UserOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getGreenhouses } from '../api/greenhouseApi'
import { getTask, getTasks, getTaskSummary, startTask, submitTask } from '../api/taskApi'
import { getApiErrorMessage } from '../api/client'
import { getStoredUser } from '../api/authApi'
import { canManage, canOperate } from '../utils/permissions'
import { label } from '../utils/labels'
import { workspaceHref } from '../layouts/workspaceNavigation'
import type { FarmTask, TaskDetail, TaskSummary } from '../types/task'
import type { Greenhouse } from '../types/greenhouse'
import FarmTaskManagementPage from './Tasks/FarmTaskManagementPage'
import ProductionDecisionTools from './ProductionDecisionTools'
import './production-design.css'

type View = 'all' | 'pending' | 'in_progress' | 'completed'
const statusLabel: Record<string, string> = { draft: '待提交', pending: '待处理', in_progress: '执行中', completed: '已完成', cancelled: '已取消' }
function date(value: string | null) {
  if (!value) return '时间待安排'
  const d = new Date(value)
  const today = new Date().toLocaleDateString('zh-CN')
  return (d.toLocaleDateString('zh-CN') === today ? '今天' : d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })) + ' ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}
function zone(task: FarmTask) {
  const evidence = task.evidence_snapshot_json
  const region = evidence.region_name ?? evidence.zone_name
  return typeof region === 'string' ? region : '全棚'
}

export default function ProductionDecisionPage() {
  const [params, setParams] = useSearchParams(), navigate = useNavigate()
  const gid = Number(params.get('greenhouse_id')) || undefined
  const [greenhouse, setGreenhouse] = useState<Greenhouse>()
  const [tasks, setTasks] = useState<FarmTask[]>([]), [summary, setSummary] = useState<TaskSummary>()
  const [selected, setSelected] = useState<number>(), [detail, setDetail] = useState<TaskDetail>()
  const [view, setView] = useState<View>('all'), [query, setQuery] = useState(''), [page, setPage] = useState(1)
  const [priority, setPriority] = useState<string>(), [source, setSource] = useState<string>()
  const [error, setError] = useState(''), [loading, setLoading] = useState(true), [saving, setSaving] = useState(false)
  const [calendar, setCalendar] = useState(false), [tools, setTools] = useState(false)
  const [center, setCenter] = useState(() => Boolean(params.get('create') || params.get('task_id') || params.get('tab') === 'tasks'))
  const [msg, context] = message.useMessage()
  const generation = useRef(0)
  const load = useCallback(async () => {
    const current = ++generation.current
    setLoading(true); setError('')
    try {
      const [houses, first, counts] = await Promise.all([getGreenhouses({ page: 1, page_size: 100, status: 'active' }), getTasks({ greenhouse_id: gid, page: 1, page_size: 100 }), getTaskSummary(gid)])
      const all = [...first.items]
      // Keep search, pagination and status counts complete even when the API paginates.
      for (let p = 2; all.length < first.total; p++) {
        const next = await getTasks({ greenhouse_id: gid, page: p, page_size: 100 })
        if (!next.items.length) break
        all.push(...next.items)
      }
      const scheduledTime = (task: FarmTask) => {
        const value = task.planned_start_at || task.due_at
        return value ? new Date(value).getTime() : Number.POSITIVE_INFINITY
      }
      all.sort((a,b) => scheduledTime(a) - scheduledTime(b))
      if (current !== generation.current) return
      setGreenhouse(houses.items.find(h => h.id === gid) ?? houses.items[0])
      setTasks(all); setSummary(counts)
      setSelected(previous => all.some(t => t.id === previous) ? previous : all.find(t => t.status === 'pending')?.id ?? all[0]?.id)
    } catch (e) { if (current === generation.current) { setError(getApiErrorMessage(e)); setTasks([]); setSummary(undefined) } }
    finally { if (current === generation.current) setLoading(false) }
  }, [gid])
  useEffect(() => { const requests = generation; void load(); return () => { requests.current++ } }, [load])
  useEffect(() => {
    const refresh = () => { void load() }
    window.addEventListener('guest-tasks-changed', refresh)
    return () => window.removeEventListener('guest-tasks-changed', refresh)
  }, [load])
  useEffect(() => {
    if (params.get('create') || params.get('task_id') || params.get('tab') === 'tasks') setCenter(true)
  }, [params])
  useEffect(() => {
    let alive = true
    setDetail(undefined)
    if (selected) void getTask(selected).then(data => { if (alive) setDetail(data) }).catch(e => { if (alive) msg.error(getApiErrorMessage(e)) })
    return () => { alive = false }
  }, [selected, tasks, msg])
  const filtered = useMemo(() => tasks.filter(t =>
    (view === 'all' || (view === 'pending' ? ['pending', 'draft'].includes(t.status) : t.status === view)) &&
    (!priority || t.priority === priority) && (!source || t.source_type === source) &&
    (!query.trim() || (t.title + t.description + (t.assignee_name ?? '') + t.task_code).includes(query.trim()))
  ), [tasks, view, priority, source, query])
  const currentPage = Math.min(page, Math.max(1, Math.ceil(filtered.length / 6)))
  const shown = filtered.slice((currentPage - 1) * 6, currentPage * 6)
  const task = tasks.find(t => t.id === selected)
  const recommendation = detail?.source_recommendation
  const sourceSteps = recommendation?.steps ?? recommendation?.action_steps_json
  const steps = Array.isArray(sourceSteps) ? sourceSteps.filter((s): s is string => typeof s === 'string') : task?.description.split(/[\n；]/).filter(Boolean) ?? []
  const rationale = typeof recommendation?.rationale === 'string' ? recommendation.rationale : detail?.source_warning && typeof detail.source_warning.description === 'string' ? detail.source_warning.description : task?.description
  const openCenter = (id?: number, create = false) => {
    setParams(previous => { const next = new URLSearchParams(previous); if (id) next.set('task_id', String(id)); if (create) next.set('create', '1'); return next }, { replace: true })
    setCenter(true)
  }
  const closeCenter = () => {
    setCenter(false)
    setParams(previous => { const next = new URLSearchParams(previous); for (const key of ['create','task_id','tab']) next.delete(key); return next }, { replace: true })
    void load()
  }
  async function begin() {
    if (!task || !canOperate() || saving) return
    setSaving(true)
    try {
      const input = { version: task.version, operator: getStoredUser()?.display_name || task.assignee_name || '体验用户' }
      if (task.status === 'draft') await submitTask(task.id, input)
      else await startTask(task.id, input)
      msg.success(task.status === 'draft' ? '任务已提交' : '任务已开始执行')
      await load()
    } catch (e) { msg.error(getApiErrorMessage(e)); await load() }
    finally { setSaving(false) }
  }
  const chooseView = (value: View) => { setView(value); setPage(1) }
  return <div className="farm-execution-design">
    {context}
    <header className="farm-design-heading"><div><span className="farm-eyebrow">PRODUCTION OPERATIONS</span><h1>农事执行</h1><p>任务有安排，执行有记录，效果可复查。</p></div><div className="farm-heading-actions"><Button aria-label="排程日历" icon={<CalendarOutlined />} onClick={() => setCalendar(true)}>排程日历</Button><Button aria-label="新建任务" type="primary" icon={<PlusOutlined />} disabled={!canManage() || !greenhouse} onClick={() => openCenter(undefined, true)}>新建任务</Button></div></header>
    <div className="farm-crop-context"><span className="farm-crop-symbol" aria-hidden="true"><svg viewBox="0 0 28 30" fill="none"><path d="M13 9C1 6 1 26 14 27c13-1 13-21 1-18M14 12l-6-7 7 3 3-5-1 7 6-2-6 6M14 8V2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg></span><strong>{{tomato:'番茄',muskmelon:'甜瓜',other:'其他作物',unknown:'未设置作物'}[greenhouse?.active_batch?.crop_type || 'unknown']}</strong><i>·</i><span>{greenhouse?.active_batch?.growth_stage || '暂无种植批次'}</span><i>·</i><span>负责人 <b>{greenhouse?.manager_name || '待分配'}</b></span></div>
    {error && <Alert type="error" showIcon message="农事任务加载失败" description={error} action={<Button onClick={() => void load()}>重试</Button>} />}
    <div className="farm-design-stats">
      <div><span>待处理</span><strong>{summary ? summary.pending_total + summary.draft_total : '—'}{!!summary?.urgent_total && <small className="farm-status urgent">! &nbsp; 紧急 {summary.urgent_total}</small>}</strong></div>
      <div><span>执行中</span><strong>{summary?.in_progress_total ?? '—'}</strong></div><div><span>今日完成</span><strong>{summary?.completed_today ?? '—'}</strong></div><div><span>待提交</span><strong>{summary?.draft_total ?? '—'}</strong></div>
    </div>
    <div className="farm-design-workspace">
      <section className="farm-design-board" aria-label="任务安排">
        <h2>任务安排</h2>
        <div className="farm-board-toolbar"><nav aria-label="任务状态">{([['all','全部'],['pending','待处理'],['in_progress','执行中'],['completed','已完成']] as const).map(([key, title]) => <button type="button" key={key} aria-pressed={view === key} onClick={() => chooseView(key)}>{title} <span>({tasks.filter(t => key === 'all' || (key === 'pending' ? ['pending','draft'].includes(t.status) : t.status === key)).length})</span></button>)}</nav><div className="farm-board-search"><Input prefix={<SearchOutlined />} placeholder="搜索任务" aria-label="搜索任务" allowClear value={query} onChange={e => { setQuery(e.target.value); setPage(1) }} /><Popover trigger="click" placement="bottomRight" content={<div className="farm-task-filters"><label>优先级<Select aria-label="筛选任务优先级" allowClear placeholder="全部优先级" value={priority} onChange={v => { setPriority(v); setPage(1) }} options={['urgent','high','medium','low'].map(value => ({ value, label: label(value) }))} /></label><label>任务来源<Select aria-label="筛选任务来源" allowClear placeholder="全部来源" value={source} onChange={v => { setSource(v); setPage(1) }} options={[{ value:'manual',label:'人工安排' },{ value:'warning',label:'环境预警' },{ value:'recommendation',label:'AI 建议' },{ value:'disease_review',label:'病害复核' }]} /></label></div>}><Button aria-label="筛选任务" icon={<FilterOutlined />} className={priority || source ? 'has-filter' : ''}>筛选</Button></Popover></div></div>
        {loading ? <div className="farm-board-loading"><Skeleton active paragraph={{ rows: 7 }} /></div> : shown.length ? <div className="farm-design-rows">{shown.map(item => <button className={'farm-design-row' + (selected === item.id ? ' selected' : '')} type="button" key={item.id} aria-pressed={selected === item.id} onClick={() => setSelected(item.id)}>
          <span className="farm-row-check" aria-hidden="true">{selected === item.id && <CheckOutlined />}</span><span className="farm-row-main"><span className="farm-row-title"><strong>{item.title}</strong><small>{{manual:'人工安排',warning:'预警建议',recommendation:'决策建议',disease_review:'病害复核'}[item.source_type]}</small></span><span className="farm-row-information"><span><EnvironmentOutlined /> {zone(item)}</span><span><UserOutlined /> {item.assignee_name || '待分配'}</span><span><ClockCircleOutlined /> {date(item.planned_start_at || item.due_at)}</span></span></span><span className={'farm-status ' + item.status}>{statusLabel[item.status] || item.status}</span><RightOutlined className="farm-row-chevron" />
        </button>)}</div> : <Empty description={query || priority || source ? '没有符合筛选条件的任务' : '当前没有任务安排'} />}
        <footer className="farm-board-footer"><span>共 {filtered.length} 条任务</span><Pagination size="small" current={currentPage} pageSize={6} total={filtered.length} showSizeChanger={false} onChange={setPage} /></footer>
      </section>
      <aside className="farm-current-task" aria-label="当前任务">
        <div className="farm-task-panel-title"><h3>当前任务</h3>{task && <span className={'farm-status ' + task.status}>{statusLabel[task.status]}</span>}</div>
        {task ? <><h2>{task.title}</h2><section><h4>处理依据</h4><p className="farm-task-basis"><FileTextOutlined /><span>{rationale || '人工安排的现场任务，请核对现场条件后执行。'}</span></p></section><section><h4>执行步骤</h4><ol className="farm-task-steps">{steps.map((step, i) => <li key={i}><b>{String(i + 1).padStart(2, '0')}</b><span>{step}</span></li>)}</ol></section><section><h4>关联记录</h4><div className="farm-task-links">{task.source_warning_id && <button type="button" onClick={() => navigate(workspaceHref('/platform/environment?view=warnings&warning_id=' + task.source_warning_id, params.toString()))}><LineChartOutlined /> 环境预警 <ArrowRightOutlined /></button>}<button type="button" onClick={() => setTools(true)}><FileTextOutlined /> AI 方案 <ArrowRightOutlined /></button></div></section>
          <div className="farm-task-action-stack">{['pending','draft'].includes(task.status) ? <Button aria-label={task.status === 'draft' ? '提交任务' : '开始执行'} type="primary" icon={<PlayCircleOutlined />} loading={saving} disabled={!canOperate() || !detail || (task.status === 'pending' && !task.assignee_name)} onClick={() => void begin()}>{task.status === 'draft' ? '提交任务' : '开始执行'}</Button> : task.status === 'in_progress' ? <Button aria-label="记录执行反馈" type="primary" icon={<CheckOutlined />} onClick={() => openCenter(task.id)}>记录执行反馈</Button> : <Button aria-label="查看执行记录" type="primary" icon={<FileTextOutlined />} onClick={() => openCenter(task.id)}>查看执行记录</Button>}<Button aria-label="查看详情" icon={<FileTextOutlined />} onClick={() => openCenter(task.id)}>查看详情</Button></div>
          <div className="farm-follow-up"><small>复查安排</small><p><ClockCircleOutlined /> {detail?.feedbacks.find(f => f.requires_follow_up)?.follow_up_note || (task.status === 'completed' ? '查看执行反馈，按现场情况继续跟进。' : '执行后补充现场观察与效果反馈。')}</p></div>
        </> : <Empty description="选择一条任务查看处理安排" />}
      </aside>
    </div>
    <div className="farm-secondary-actions"><Button type="text" icon={<FileTextOutlined />} onClick={() => openCenter()}>全部任务与证据链</Button><Button type="text" icon={<LineChartOutlined />} onClick={() => setTools(true)}>AI 建议与处置</Button><Button type="text" icon={<ReloadOutlined />} loading={loading} onClick={() => void load()}>刷新任务</Button></div>
    <Drawer title="排程日历" width="min(960px,100vw)" open={calendar} onClose={() => setCalendar(false)}><Calendar cellRender={(value, info) => info.type === 'date' ? <div className="farm-calendar-tasks">{tasks.filter(t => { const scheduled = t.planned_start_at || t.due_at; return scheduled && new Date(scheduled).toLocaleDateString('zh-CN') === value.toDate().toLocaleDateString('zh-CN') }).map(t => <button key={t.id} type="button" onClick={() => { setSelected(t.id); setCalendar(false) }}><i className={t.status} />{t.title}</button>)}</div> : info.originNode} /></Drawer>
    <Drawer title="农事任务中心" width="min(1280px,97vw)" push={false} open={center} onClose={closeCenter} destroyOnHidden><FarmTaskManagementPage /></Drawer>
    <Drawer title="AI 建议、处置方案与证据链" width="min(1280px,97vw)" push={false} open={tools} onClose={() => { setTools(false); void load() }} destroyOnHidden><ProductionDecisionTools /></Drawer>
  </div>
}
