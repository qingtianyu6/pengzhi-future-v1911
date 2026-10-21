import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ArrowDownOutlined,
  ArrowRightOutlined,
  ArrowUpOutlined,
  BulbOutlined,
  FileTextOutlined,
  InfoCircleOutlined,
  DeploymentUnitOutlined,
  CheckCircleOutlined,
  CloudOutlined,
  DatabaseOutlined,
  FireOutlined,
  LeftOutlined,
  RightOutlined,
  SafetyCertificateOutlined,
  SunOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { Alert, Button, Skeleton, Tag } from 'antd'
import { getApiErrorMessage } from '../../api/client'
import { getDashboardSummary } from '../../api/dashboardApi'
import { getGreenhouses } from '../../api/greenhouseApi'
import { getSensorHistory } from '../../api/sensorApi'
import type { DashboardSummary, MetricChanges } from '../../types/dashboard'
import type { SensorReading } from '../../types/sensor'
import type { FarmTask } from '../../types/task'
import { EnvironmentTrendChart, type ChartMetric } from './EnvironmentTrendChart'
import { ModelCenter } from '../../components/ModelCenter'
import { SaasEmptyState } from '../../components/SaasUI'
import { isGuestMode } from '../../api/guestMode'
import './dashboard-design.css'
import { useLocation, useNavigate } from 'react-router-dom'

type ChangeKey = keyof MetricChanges

type MetricTone = 'temperature' | 'humidity' | 'soil' | 'light' | 'co2'

const warningLevelLabel: Record<string, string> = {
  normal: '低风险', attention: '需关注', warning: '预警', critical: '高风险',
}

const taskStatusLabel: Record<string, string> = {
  draft: '待提交', pending: '待执行', in_progress: '执行中', completed: '已完成', cancelled: '已取消',
}

const taskSourceLabel: Record<string, string> = {
  warning: '环境预警', disease_review: '病害复核', recommendation: '自动建议', manual: '人工创建',
}

function formatValue(value: number | null, digits = 1): string {
  return value === null ? '—' : value.toFixed(digits)
}

function formatTime(value: string | null): string {
  return value ? new Date(value).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false }) : '时间未知'
}

function formatDate(date: Date): string {
  return `${date.getMonth() + 1}月${date.getDate()}日`
}

function formatDueTime(value: string): string {
  const date = new Date(value)
  return `${formatDate(date)} ${formatTime(value)}`
}

function taskTone(task: FarmTask): string {
  if (task.priority === 'urgent') return 'urgent'
  if (task.status === 'completed') return 'done'
  if (task.status === 'in_progress') return 'progress'
  return task.source_type === 'disease_review' ? 'review' : 'pending'
}

function metricIcon(tone: MetricTone) {
  if (tone === 'temperature') return <FireOutlined />
  if (tone === 'humidity') return <CloudOutlined />
  if (tone === 'soil') return <BulbOutlined />
  if (tone === 'light') return <SunOutlined />
  return <CloudOutlined />
}

function metricMeta(change: number | null, unit: string) {
  if (change === null) return <>暂无同期变化</>
  return <>{change >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />} 较上次 {change > 0 ? '+' : ''}{Number.isInteger(change) ? change.toFixed(0) : change.toFixed(1)}{unit}</>
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [modelCenterOpen, setModelCenterOpen] = useState(false)
  const [chartOffset, setChartOffset] = useState(0)
  const [chartMetric, setChartMetric] = useState<ChartMetric>('all')
  const guest = isGuestMode()
  const [history, setHistory] = useState<{ greenhouseId: number; offset: number; items: SensorReading[] } | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [historyRetry, setHistoryRetry] = useState(0)

  const queryGreenhouseId = useMemo(() => Number(new URLSearchParams(location.search).get('greenhouse_id')) || null, [location.search])

  const loadGreenhouses = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await getGreenhouses({ page: 1, page_size: 100, status: 'active' })
      setSelectedId((current) => {
        if (queryGreenhouseId && result.items.some((item) => item.id === queryGreenhouseId)) return queryGreenhouseId
        if (current && result.items.some((item) => item.id === current)) return current
        return result.items[0]?.id ?? null
      })
      if (result.items.length === 0) setSummary(null)
    } catch (requestError) { setError(getApiErrorMessage(requestError)) }
    finally { setLoading(false) }
  }, [queryGreenhouseId])

  const loadSummary = useCallback(async () => {
    if (!selectedId) return
    setLoading(true)
    setError(null)
    try { setSummary(await getDashboardSummary(selectedId)) }
    catch (requestError) { setError(getApiErrorMessage(requestError)); setSummary(null) }
    finally { setLoading(false) }
  }, [selectedId])

  useEffect(() => { void loadGreenhouses() }, [loadGreenhouses])
  useEffect(() => { void loadSummary() }, [loadSummary])
  useEffect(() => { setChartOffset(0) }, [selectedId])
  useEffect(() => {
    if (!selectedId || chartOffset === 0) return
    let active = true
    const end = new Date(Date.now() - chartOffset * 24 * 60 * 60 * 1000)
    const start = new Date(end.getTime() - 24 * 60 * 60 * 1000)
    setHistoryLoading(true)
    setHistoryError(null)
    void getSensorHistory({ greenhouse_id: selectedId, start_time: start.toISOString(), end_time: end.toISOString(), page_size: 1000 })
      .then((result) => { if (active) setHistory({ greenhouseId: selectedId, offset: chartOffset, items: result.items }) })
      .catch((requestError) => { if (active) setHistoryError(getApiErrorMessage(requestError)) })
      .finally(() => { if (active) setHistoryLoading(false) })
    return () => { active = false }
  }, [selectedId, chartOffset, historyRetry])

  const metrics = useMemo(() => {
    const latest = summary?.latest_environment
    const changes = summary?.changes
    return [
      { label: '空气温度', value: latest?.temperature ?? null, unit: '℃', change: changes?.temperature ?? null, key: 'temperature' as ChangeKey, tone: 'temperature' as MetricTone, digits: 1 },
      { label: '空气湿度', value: latest?.air_humidity ?? null, unit: '%', change: changes?.air_humidity ?? null, key: 'air_humidity' as ChangeKey, tone: 'humidity' as MetricTone, digits: 0 },
      { label: '土壤湿度', value: latest?.soil_moisture ?? null, unit: '%', change: changes?.soil_moisture ?? null, key: 'soil_moisture' as ChangeKey, tone: 'soil' as MetricTone, digits: 0 },
      { label: '光照强度', value: latest?.light_intensity ?? null, unit: 'klx', change: changes?.light_intensity ?? null, key: 'light_intensity' as ChangeKey, tone: 'light' as MetricTone, digits: 1 },
      { label: 'CO₂浓度', value: latest?.co2_concentration ?? null, unit: 'ppm', change: changes?.co2_concentration ?? null, key: 'co2_concentration' as ChangeKey, tone: 'co2' as MetricTone, digits: 0 },
    ]
  }, [summary])

  const todayTasks = useMemo(() => summary?.task_summary.recent_tasks.filter((item) => ['draft', 'pending', 'in_progress'].includes(item.status)).slice(0, 3) ?? [], [summary])
  const recentActivities = useMemo(() => {
    if (!summary) return []
    const rows: Array<{ time: string; title: string; meta: string; tone: string }> = []
    if (summary.warning_summary.latest_warning_title) rows.push({ time: '—', title: summary.warning_summary.latest_warning_title, meta: '风险引擎 · 最近预警', tone: 'warning' })
    summary.task_summary.recent_tasks.slice(0, 3).forEach((task) => rows.push({ time: formatTime(task.updated_at), title: task.title, meta: `${taskSourceLabel[task.source_type] ?? task.source_type} · ${taskStatusLabel[task.status] ?? task.status}`, tone: task.status === 'completed' ? 'done' : task.source_type === 'disease_review' ? 'review' : 'task' }))
    return rows.slice(0, 3)
  }, [summary])

  const chartData = chartOffset === 0 ? summary?.trend_24h ?? [] : history?.greenhouseId === selectedId && history.offset === chartOffset ? history.items : []
  const chartEnd = new Date(Date.now() - chartOffset * 24 * 60 * 60 * 1000)
  const hasEnvironment = Boolean(summary?.latest_environment)
  const stale = Boolean(summary?.data_updated_at && Date.now() - new Date(summary.data_updated_at).getTime() > 2 * 3600_000)
  const hasWarning = Boolean(summary?.warning_summary.open_warning_count)


  const href = (path: string, extra = '') => {
    const params = new URLSearchParams(location.search)
    if (selectedId) params.set('greenhouse_id', String(selectedId))
    for (const [key, value] of new URLSearchParams(extra)) params.set(key, value)
    return path + '?' + params.toString()
  }
  const focusHref = !hasEnvironment ? href('/platform/data', 'tab=connection')
    : href('/platform/environment', stale ? 'tab=monitoring' : hasWarning ? 'tab=alerts' : 'tab=monitoring')
  const crop = summary?.active_batch?.crop_type
  const scene = crop === 'muskmelon' ? '/images/greenhouse-management/muskmelon.png'
    : crop === 'tomato' ? '/images/dashboard/tomato-greenhouse.webp' : '/images/greenhouse-management/hero.png'
  const currentDate = new Date().toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' }).replace('星期', ' · 星期')
  const heroTitle = stale ? <>先核实数据，<br/>再安排今天的工作。</>
    : !hasEnvironment ? <>连接第一份数据，<br/>让大棚状态看得见。</>
    : hasWarning ? <>棚况已更新，<br/>今天先关注{todayTasks.length ? '这两件事' : '这项预警'}。</>
    : <>棚况已更新，<br/>{todayTasks.length ? '把今天的农事逐项落实。' : '从一次日常巡检开始。'}</>
  if (loading && !summary) return <div className="dashboard-page dashboard-design"><Skeleton active paragraph={{ rows: 12 }}/></div>
  return <div className="dashboard-page dashboard-design">
    {error && <Alert type="error" showIcon message="生产工作台数据加载失败" description={error} action={<Button aria-label="重试读取工作台" size="small" onClick={() => selectedId ? void loadSummary() : void loadGreenhouses()}>重试</Button>}/>}
    {!summary && !error ? <SaasEmptyState title="还没有可用的大棚工作区" description="先创建大棚和种植批次，再接入环境记录。" actionLabel="进入大棚管理" onAction={() => navigate(href('/platform/data'))}/> : summary && <>
      <header className="dd-intro">
        <span className="dd-eyebrow">今日生产概览</span>
        <div className="dd-title-row"><h1>生产工作台</h1><span className="dd-date">{currentDate}</span>{guest && <Tag className="dd-demo-tag">游客演示</Tag>}</div>
        <p>让每一棚生长，都有据可循。</p>
      </header>

      <section className="dd-hero" aria-label="今日生产重点">
        <div className="dd-hero-visual">
          <img className="dd-hero-image" src={scene} alt="" aria-hidden="true"/>
          <div className="dd-hero-copy"><h2>{heroTitle}</h2><div className="dd-hero-actions">
            <Button type="primary" onClick={() => navigate(href('/platform/3d'))}>走进三维大棚 <ArrowRightOutlined/></Button>
            <Button aria-label="记录观察" icon={<FileTextOutlined/>} disabled={!summary.active_batch} title={!summary.active_batch ? '先建立种植批次后记录观察' : undefined} onClick={() => navigate(href('/platform/research', 'tab=archive&observe=1'))}>记录观察</Button>
          </div></div><span className="dd-scene-caption">种植场景示意</span>
        </div>
        <div className="dd-focus">
          <span className={'dd-focus-status'+(hasWarning||stale?' is-attention':'')}><i/>{stale ? '采样数据待同步' : hasWarning ? summary.warning_summary.open_warning_count+' 项待处理预警' : hasEnvironment ? '今日关注' : '环境数据待接入'}</span>
          <h2>{stale ? '先核实数据，再判断棚况' : !hasEnvironment ? '连接第一份环境数据' : summary.warning_summary.latest_warning_title?.replace(/，.*$/, '') || (todayTasks.length ? '安排今天的农事' : '结合现场情况开展巡检')}</h2>
          <p>{stale ? '最近采集已超过2小时，请先检查设备或采样记录。' : !hasEnvironment ? '接入有效采样后显示环境与风险状态。' : hasWarning && /湿度|通风/.test(summary.warning_summary.latest_warning_title||'') ? '先核实棚温，再安排通风与复测。' : summary.warning_summary.latest_recommendation_title || '结合环境变化与作物观察，逐项核实。'}</p>
          <Button type="primary" onClick={() => navigate(focusHref)}>{stale ? '核实采样记录' : !hasEnvironment ? '连接环境数据' : hasWarning ? '查看预警与建议' : '查看环境监测'} <ArrowRightOutlined/></Button>
        </div>
      </section>

      <section className="dd-environment dd-surface" aria-label="环境实况">
        <div className="dd-section-heading"><h2>环境实况</h2><span>{summary.data_updated_at ? '最近采集 '+formatDueTime(summary.data_updated_at) : '等待环境采样'}{guest ? ' · 示例数据' : ''}{stale ? ' · 历史记录' : ''}</span><Button type="link" onClick={() => navigate(href('/platform/environment'))}>查看环境监测 <ArrowRightOutlined/></Button></div>
        <div className="dd-metrics">{metrics.map(metric => <article className={'dd-metric metric-'+metric.tone} key={metric.key}>
          <span className="dd-metric-icon">{metricIcon(metric.tone)}</span><div><span className="dd-metric-label">{metric.label}</span><div className="dd-metric-value"><strong>{formatValue(metric.value, metric.digits)}</strong><small>{metric.unit}</small></div><div className={'dd-metric-change'+(metric.change!=null&&metric.change>=0?' is-up':' is-down')}>{metricMeta(metric.change,metric.unit)}</div></div>
        </article>)}</div>
      </section>

      <section className="dd-work-grid">
        <article className="dd-chart dd-surface">
          <header className="dd-chart-heading"><h2>24 小时环境趋势</h2><span>{guest ? '示例趋势 · ' : ''}{chartData.length} 条采样记录</span>
            <div className="dd-chart-tools"><div className="dd-chart-filters" role="group" aria-label="趋势指标">{([{key:'all',label:'全部'},{key:'temperature',label:'温度'},{key:'air_humidity',label:'湿度'},{key:'soil_moisture',label:'土壤湿度'}] as const).map(m=><button key={m.key} type="button" aria-pressed={chartMetric===m.key} onClick={()=>setChartMetric(m.key)}>{m.label}</button>)}</div>
              <div className="dd-date-switch"><Button type="text" size="small" icon={<LeftOutlined/>} aria-label="上一天" onClick={()=>setChartOffset(v=>v+1)}/><b>{formatDate(chartEnd)}</b><Button type="text" size="small" icon={<RightOutlined/>} aria-label="下一天" disabled={chartOffset===0} onClick={()=>setChartOffset(v=>Math.max(0,v-1))}/></div>
            </div>
          </header>
          {chartOffset>0&&historyLoading ? <Skeleton active paragraph={{rows:4}}/> : chartOffset>0&&historyError ? <Alert type="error" showIcon message="历史趋势加载失败" description={historyError} action={<Button aria-label="重试读取历史趋势" size="small" onClick={()=>setHistoryRetry(v=>v+1)}>重试</Button>}/> : chartData.length ? <EnvironmentTrendChart data={chartData} metric={chartMetric}/> : <SaasEmptyState title="该时段没有环境记录" description="这里只展示当前大棚的有效采样。" actionLabel="导入数据" onAction={()=>navigate(href('/platform/data'))}/>}
        </article>
        <article className="dd-todo dd-surface">
          <header className="dd-section-heading"><h2>今日待办</h2><span>{todayTasks.length} 项任务</span><Button type="link" onClick={()=>navigate(href('/platform/production'))}>查看全部 <ArrowRightOutlined/></Button></header>
          {todayTasks.length ? <div className="dd-task-list">{todayTasks.map((task,index)=><button type="button" key={task.id} className={'dd-task task-'+taskTone(task)} onClick={()=>navigate(href('/platform/production','task_id='+task.id))}>
            <i className="dd-task-dot"/><span className="dd-task-icon">{index===0?<DeploymentUnitOutlined/>:<BulbOutlined/>}</span><span className="dd-task-copy"><strong>{task.title}</strong><small>{task.assignee_name||taskSourceLabel[task.source_type]||'待分配'} · {taskStatusLabel[task.status]||task.status}</small></span><time dateTime={task.due_at||undefined}>{task.due_at ? ((new Date(task.due_at).toDateString()===new Date().toDateString())?formatTime(task.due_at):formatDueTime(task.due_at))+' 前' : '待安排'}</time><ArrowRightOutlined className="dd-task-arrow"/>
          </button>)}</div> : <SaasEmptyState title="没有待处理任务" description="新建农事任务后可在这里查看。" actionLabel="新建任务" onAction={()=>navigate(href('/platform/production','create=1'))}/>}
          <p className="dd-task-note"><InfoCircleOutlined/>执行前请核实现场条件，结合棚内实际情况进行操作。</p>
        </article>
      </section>

      <section className="dd-status-ribbon dd-surface" aria-label="生产状态">
        <button type="button" className="dd-status dd-status-risk" onClick={()=>navigate(href('/platform/environment','tab=alerts'))}><SafetyCertificateOutlined/><span><small>环境风险</small><strong>{summary.risk.data_status==='insufficient'&&!hasWarning?'待评估':warningLevelLabel[summary.warning_summary.highest_risk_level]||warningLevelLabel[summary.risk.level]||'待评估'}</strong><p>{summary.risk.reasons[0]||(hasEnvironment?'暂无待处理的风险事件':'接入环境数据后显示风险判断')}</p></span><ArrowRightOutlined/></button>
        <button type="button" className="dd-status dd-status-data" onClick={()=>navigate(href('/platform/environment','tab=monitoring'))}><DatabaseOutlined/><span><small>数据采集</small><strong>{stale?'数据待同步':hasEnvironment?'已接入':'待接入'}</strong><p>{summary.data_updated_at?'最近采集 '+formatDueTime(summary.data_updated_at):'暂无环境数据'}</p></span><ArrowRightOutlined/></button>
        <button type="button" className="dd-status dd-status-decision" onClick={()=>navigate(href('/platform/production'))}><ThunderboltOutlined/><span><small>决策状态</small><strong>{summary.warning_summary.latest_recommendation_title?'有最新建议':'暂无建议'}</strong><p>{summary.warning_summary.latest_recommendation_title||'等待风险研判结果'}</p></span><ArrowRightOutlined/></button>
      </section>

      <section className="dd-activity dd-surface">
        <header className="dd-section-heading"><h2>最近动态</h2><Button type="link" onClick={()=>navigate(href('/platform/production'))}>查看全部 <ArrowRightOutlined/></Button></header>
        {recentActivities.length ? <div className="dd-activity-list">{recentActivities.map((activity,i)=><div key={activity.title+i} className="dd-activity-row"><time>{activity.time}</time><i className={activity.tone}/><strong>{activity.title}</strong><span>{activity.meta}</span></div>)}</div> : <p className="dd-no-activity">还没有动态记录，接入数据或创建任务后显示。</p>}
      </section>
      <footer className="dd-footer"><CheckCircleOutlined/><nav aria-label="生产处理流程">{[['监测发现','/platform/environment'],['主动探因','/platform/investigate'],['人工确认','/platform/production'],['经验积累','/platform/research']].map(([label,path],i)=><span key={path}>{i>0&&<span aria-hidden="true">→</span>}<button type="button" onClick={()=>navigate(href(path))}>{label}</button></span>)}</nav><span>让大棚生产持续优化。</span><Button type="text" size="small" onClick={()=>setModelCenterOpen(true)}>模型说明</Button></footer>
    </>}
    <ModelCenter open={modelCenterOpen} onClose={()=>setModelCenterOpen(false)}/>
  </div>
}
