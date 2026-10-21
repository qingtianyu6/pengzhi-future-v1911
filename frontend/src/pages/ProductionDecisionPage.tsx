import { useCallback, useEffect, useRef, useState } from 'react'
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
import FarmTaskManagementPage, { FarmTaskDialogs } from './Tasks/FarmTaskManagementPage'
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
  const [center, setCenter] = useState(() => params.get('tab') === 'tasks')
  const [total, setTotal] = useState(0), [search, setSearch] = useState('')
  const [calendarTasks, setCalendarTasks] = useState<FarmTask[]>([]), [calendarMonth, setCalendarMonth] = useState(() => new Date())
  const [calendarLoading, setCalendarLoading] = useState(false), [calendarError, setCalendarError] = useState('')
  useEffect(() => { const timer = window.setTimeout(() => setSearch(query.trim()), 250); return () => window.clearTimeout(timer) }, [query])
  const [msg, context] = message.useMessage()
  const generation = useRef(0)
  const load = useCallback(async () => {
    const current = ++generation.current
    setLoading(true); setError('')
    try {
      const [list, counts] = await Promise.all([
        getTasks({ greenhouse_id: gid, page, page_size: 6, sort: 'schedule', q: search || undefined,
          status: view !== 'all' && view !== 'pending' ? view : undefined,
          status_group: view === 'pending' ? 'pending' : undefined, priority, source_type: source }),
        getTaskSummary(gid),
      ])
      if (current !== generation.current) return
      if (page > Math.max(1, Math.ceil(list.total / 6))) { setPage(Math.max(1, Math.ceil(list.total / 6))); return }
      setTasks(list.items); setTotal(list.total); setSummary(counts)
      setSelected(previous => list.items.some(t => t.id === previous) ? previous : list.items[0]?.id)
    } catch (e) { if (current === generation.current) { setError(getApiErrorMessage(e)); setTasks([]); setTotal(0); setSummary(undefined); setSelected(undefined) } }
    finally { if (current === generation.current) setLoading(false) }
  }, [gid, page, search, view, priority, source])
  useEffect(() => {
    let active = true
    void getGreenhouses({ page: 1, page_size: 100, status: 'active' }).then(houses => {
      if (active) setGreenhouse(houses.items.find(h => h.id === gid) ?? houses.items[0])
    }).catch(() => { if (active) setGreenhouse(undefined) })
    return () => { active = false }
  }, [gid])
  useEffect(() => {
    if (!calendar) return
    let active = true
    const readMonth = async () => {
      setCalendarLoading(true); setCalendarError(''); setCalendarTasks([])
      const filters = { greenhouse_id: gid, page_size: 100, sort: 'schedule' as const,
        scheduled_start: new Date(calendarMonth.getFullYear(), calendarMonth.getMonth(), 1).toISOString(),
        scheduled_end: new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1, 1).toISOString() }
      try {
        const first = await getTasks({ ...filters, page: 1 }), all = [...first.items]
        for (let p = 2; active && p <= Math.ceil(first.total / 100); p++) {
          const next = await getTasks({ ...filters, page: p }); all.push(...next.items)
        }
        if (active) setCalendarTasks(all)
      } catch (e) { if (active) setCalendarError(getApiErrorMessage(e)) }
      finally { if (active) setCalendarLoading(false) }
    }
    void readMonth()
    return () => { active = false }
  }, [calendar, calendarMonth, gid])
  useEffect(() => { const requests = generation; void load(); return () => { requests.current++ } }, [load])
  useEffect(() => {
    const refresh = () => { void load() }
    window.addEventListener('guest-tasks-changed', refresh)
    return () => window.removeEventListener('guest-tasks-changed', refresh)
  }, [load])
  useEffect(() => {
    if (params.get('tab') === 'tasks') setCenter(true)
  }, [params])
  useEffect(() => {
    let alive = true
    setDetail(undefined)
    if (selected) void getTask(selected).then(data => { if (alive) setDetail(data) }).catch(e => { if (alive) msg.error(getApiErrorMessage(e)) })
    return () => { alive = false }
  }, [selected, tasks, msg])
  const currentPage = page, shown = tasks
  const task = loading ? undefined : tasks.find(t => t.id === selected)
  const viewCounts = { all: summary?.total, pending: summary ? summary.pending_total + summary.draft_total : undefined,
    in_progress: summary?.in_progress_total, completed: summary?.completed_total }
  const recommendation = detail?.source_recommendation
  const sourceSteps = recommendation?.steps ?? recommendation?.action_steps_json
  const steps = Array.isArray(sourceSteps) ? sourceSteps.filter((s): s is string => typeof s === 'string') : task?.description.split(/[\n；]/).filter(Boolean) ?? []
  const rationale = typeof recommendation?.rationale === 'string' ? recommendation.rationale : detail?.source_warning && typeof detail.source_warning.description === 'string' ? detail.source_warning.description : task?.description
  const openCenter = (id?: number, create = false, feedback = false) => {
    setParams(previous => { const next = new URLSearchParams(previous); next.delete('feedback'); if (id) next.set('task_id', String(id)); if (create) next.set('create', '1'); if (feedback) next.set('feedback', '1'); return next }, { replace: true })
    if (!id && !create) setCenter(true)
  }
  const closeCenter = () => {
    setCenter(false)
    setParams(previous => { const next = new URLSearchParams(previous); for (const key of ['create','task_id','tab','feedback']) next.delete(key); return next }, { replace: true })
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
        <div className="farm-board-toolbar"><nav aria-label="任务状态">{([['all','全部'],['pending','待处理'],['in_progress','执行中'],['completed','已完成']] as const).map(([key, title]) => <button type="button" key={key} aria-pressed={view === key} onClick={() => chooseView(key)}>{title} <span>({viewCounts[key] ?? '—'})</span></button>)}</nav><div className="farm-board-search"><Input prefix={<SearchOutlined />} placeholder="搜索任务" aria-label="搜索任务" maxLength={160} allowClear value={query} onChange={e => { setQuery(e.target.value); setPage(1) }} /><Popover trigger="click" placement="bottomRight" content={<div className="farm-task-filters"><label>优先级<Select aria-label="筛选任务优先级" allowClear placeholder="全部优先级" value={priority} onChange={v => { setPriority(v); setPage(1) }} options={['urgent','high','medium','low'].map(value => ({ value, label: label(value) }))} /></label><label>任务来源<Select aria-label="筛选任务来源" allowClear placeholder="全部来源" value={source} onChange={v => { setSource(v); setPage(1) }} options={[{ value:'manual',label:'人工安排' },{ value:'warning',label:'环境预警' },{ value:'recommendation',label:'AI 建议' },{ value:'disease_review',label:'病害复核' }]} /></label></div>}><Button aria-label="筛选任务" icon={<FilterOutlined />} className={priority || source ? 'has-filter' : ''}>筛选</Button></Popover></div></div>
        {loading ? <div className="farm-board-loading"><Skeleton active paragraph={{ rows: 7 }} /></div> : shown.length ? <div className="farm-design-rows">{shown.map(item => <button className={'farm-design-row' + (selected === item.id ? ' selected' : '')} type="button" key={item.id} aria-pressed={selected === item.id} onClick={() => setSelected(item.id)}>
          <span className="farm-row-check" aria-hidden="true">{selected === item.id && <CheckOutlined />}</span><span className="farm-row-main"><span className="farm-row-title"><strong>{item.title}</strong><small>{{manual:'人工安排',warning:'预警建议',recommendation:'决策建议',disease_review:'病害复核'}[item.source_type]}</small></span><span className="farm-row-information"><span><EnvironmentOutlined /> {zone(item)}</span><span><UserOutlined /> {item.assignee_name || '待分配'}</span><span><ClockCircleOutlined /> {date(item.planned_start_at || item.due_at)}</span></span></span><span className={'farm-status ' + item.status}>{statusLabel[item.status] || item.status}</span><RightOutlined className="farm-row-chevron" />
        </button>)}</div> : <Empty description={query || priority || source ? '没有符合筛选条件的任务' : '当前没有任务安排'} />}
        <footer className="farm-board-footer"><span>共 {total} 条任务</span><Pagination size="small" current={currentPage} pageSize={6} total={total} showSizeChanger={false} onChange={setPage} /></footer>
      </section>
      <aside className="farm-current-task" aria-label="当前任务">
        <div className="farm-task-panel-title"><h3>当前任务</h3>{task && <span className={'farm-status ' + task.status}>{statusLabel[task.status]}</span>}</div>
        {task ? <><h2>{task.title}</h2><section><h4>处理依据</h4><p className="farm-task-basis"><FileTextOutlined /><span>{rationale || '人工安排的现场任务，请核对现场条件后执行。'}</span></p></section><section><h4>执行步骤</h4><ol className="farm-task-steps">{steps.map((step, i) => <li key={i}><b>{String(i + 1).padStart(2, '0')}</b><span>{step}</span></li>)}</ol></section><section><h4>关联记录</h4><div className="farm-task-links">{task.source_warning_id && <button type="button" onClick={() => navigate(workspaceHref('/platform/environment?view=warnings&warning_id=' + task.source_warning_id, params.toString()))}><LineChartOutlined /> 环境预警 <ArrowRightOutlined /></button>}{task.source_recommendation_id && <button type="button" onClick={() => setTools(true)}><FileTextOutlined /> AI 方案 <ArrowRightOutlined /></button>}</div></section>
          <div className="farm-task-action-stack">{['pending','draft'].includes(task.status) ? <Button aria-label={task.status === 'draft' ? '提交任务' : '开始执行'} type="primary" icon={<PlayCircleOutlined />} loading={saving} disabled={!canOperate() || !detail || (task.status === 'pending' && !task.assignee_name)} onClick={() => void begin()}>{task.status === 'draft' ? '提交任务' : '开始执行'}</Button> : task.status === 'in_progress' ? <Button aria-label="记录执行反馈" type="primary" icon={<CheckOutlined />} onClick={() => openCenter(task.id, false, true)}>记录执行反馈</Button> : <Button aria-label="查看执行记录" type="primary" icon={<FileTextOutlined />} onClick={() => openCenter(task.id)}>查看执行记录</Button>}<Button aria-label="查看详情" icon={<FileTextOutlined />} onClick={() => openCenter(task.id)}>查看详情</Button></div>
          <div className="farm-follow-up"><small>复查安排</small><p><ClockCircleOutlined /> {detail?.feedbacks.find(f => f.requires_follow_up)?.follow_up_note || (task.status === 'completed' ? '查看执行反馈，按现场情况继续跟进。' : '执行后补充现场观察与效果反馈。')}</p></div>
        </> : <Empty description="选择一条任务查看处理安排" />}
      </aside>
    </div>
    <div className="farm-secondary-actions"><Button aria-label="全部任务与证据链" type="text" icon={<FileTextOutlined />} onClick={() => openCenter()}>全部任务与证据链</Button><Button aria-label="AI 建议与处置" type="text" icon={<LineChartOutlined />} onClick={() => setTools(true)}>AI 建议与处置</Button><Button aria-label="刷新任务" type="text" icon={<ReloadOutlined />} loading={loading} onClick={() => void load()}>刷新任务</Button></div>
    <Drawer title="排程日历" width="min(960px,100vw)" open={calendar} onClose={() => setCalendar(false)}>{calendarError && <Alert type="error" message="排程加载失败" description={calendarError} />}<p role="status">{calendarLoading ? '正在读取本月排程…' : `本月 ${calendarTasks.length} 条排程`}</p><Calendar onPanelChange={value => setCalendarMonth(value.toDate())} cellRender={(value, info) => info.type === 'date' ? <div className="farm-calendar-tasks">{calendarTasks.filter(t => { const scheduled = t.planned_start_at || t.due_at; return scheduled && new Date(scheduled).toLocaleDateString('zh-CN') === value.toDate().toLocaleDateString('zh-CN') }).map(t => <button key={t.id} type="button" onClick={() => { setCalendar(false); openCenter(t.id) }}><i className={t.status} />{t.title}</button>)}</div> : info.originNode} /></Drawer>
    {!center && <FarmTaskDialogs onChanged={load} />}
    <Drawer title="农事任务中心" width="min(1280px,97vw)" push={false} open={center} onClose={closeCenter} destroyOnHidden><FarmTaskManagementPage /></Drawer>
    <Drawer title="AI 建议、处置方案与证据链" width="min(1280px,97vw)" push={false} open={tools} onClose={() => { setTools(false); void load() }} destroyOnHidden><ProductionDecisionTools /></Drawer>
  </div>
}
