import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ArrowDownOutlined,
  ArrowRightOutlined,
  ArrowUpOutlined,
  BulbOutlined,
  CloudOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
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
import { EnvironmentTrendChart } from './EnvironmentTrendChart'
import { ModelCenter } from '../../components/ModelCenter'
import { SaasEmptyState, SectionHeading } from '../../components/SaasUI'
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

function metricStatus(key: ChangeKey, value: number | null) {
  if (value === null) return { label: '待采集', tone: 'muted' }
  if (key === 'temperature') return value > 30 ? { label: '偏高', tone: 'warning' } : value < 16 ? { label: '偏低', tone: 'warning' } : { label: '正常', tone: 'normal' }
  if (key === 'air_humidity') return value > 82 ? { label: '偏高', tone: 'warning' } : value < 40 ? { label: '偏低', tone: 'warning' } : { label: '正常', tone: 'normal' }
  if (key === 'soil_moisture') return value < 38 ? { label: '偏低', tone: 'warning' } : { label: '正常', tone: 'normal' }
  if (key === 'light_intensity') return value > 80 ? { label: '偏强', tone: 'attention' } : { label: '正常', tone: 'normal' }
  if (key === 'co2_concentration') return value > 1200 ? { label: '偏高', tone: 'warning' } : { label: '正常', tone: 'normal' }
  return { label: '正常', tone: 'normal' }
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

function greeting() {
  const hour = new Date().getHours()
  if (hour < 11) return '早上好，'
  if (hour < 14) return '中午好，'
  if (hour < 18) return '下午好，'
  return '晚上好，'
}

function metricMeta(change: number | null, unit: string) {
  if (change === null) return <>暂无同期变化</>
  return <>{change >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />} 较上次采样 {change > 0 ? '+' : ''}{change.toFixed(1)}{unit}</>
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

  if (loading && !summary) return <div className="dashboard-page exact-dashboard"><Skeleton active paragraph={{ rows: 12 }} /></div>

  return <div className="dashboard-page commercial-dashboard exact-dashboard">
    {error && <Alert className="page-alert" type="error" showIcon message="种植总览数据加载失败" description={error} action={<Button size="small" onClick={() => selectedId ? void loadSummary() : void loadGreenhouses()}>重试</Button>} />}

    {!summary && !error ? <SaasEmptyState title="还没有可用的大棚工作区" description="先创建大棚和种植批次，系统会自动汇总环境、风险、建议和农事任务。" actionLabel="进入大棚管理" onAction={() => navigate('/platform/data')} /> : summary && <>
      <section className="exact-welcome-banner">
        <div className="exact-welcome-copy">
          <span>{greeting()}</span>
          <div className="exact-welcome-title"><h1>今日生产概览</h1><Tag color={hasWarning ? 'orange' : hasEnvironment ? 'green' : 'default'}>{stale ? '历史数据 / 待同步' : hasWarning ? '存在预警' : hasEnvironment ? '监测中' : '待接入'}</Tag></div>
          <p>{stale ? '最近采集已超过2小时，以下为历史记录，请检查设备连接。' : hasWarning ? `当前有 ${summary.warning_summary.open_warning_count} 项待处理预警，请查看风险详情。` : hasEnvironment ? '环境数据已接入，点击下方卡片查看监测和决策详情。' : '尚无环境数据，接入传感器或导入历史数据后可查看监测结果。'}</p>
        </div>
        <div className="wb-overview-actions"><Button onClick={() => navigate(`/platform/3d?greenhouse_id=${selectedId}`)}>查看三维大棚</Button><Button type="primary" onClick={() => navigate(`/platform/production?greenhouse_id=${selectedId}`)}>查看待办 <ArrowRightOutlined /></Button><Button type="link" onClick={() => setModelCenterOpen(true)}>模型说明</Button></div>
      </section>

      {(hasWarning || stale || !hasEnvironment) && <div className="wb-priority-notice"><span>{stale ? '数据待同步' : hasWarning ? `${summary.warning_summary.open_warning_count} 项需关注` : '等待数据接入'}</span><strong>{stale ? '最近采集已超过 2 小时，请先核实数据时效。' : summary.warning_summary.latest_warning_title || '接入本棚数据后，开始监测和风险分析。'}</strong><Button type="link" onClick={() => navigate(hasEnvironment ? `/platform/environment?greenhouse_id=${selectedId}&tab=alerts` : '/platform/data?tab=connection&greenhouse_id='+selectedId)}>{hasEnvironment ? '查看依据与建议' : '前往数据接入'} <ArrowRightOutlined /></Button></div>}

      <section className="exact-metric-grid">
        {metrics.map((metric) => {
          const state = metricStatus(metric.key, metric.value)
          return <article className={`exact-metric-card metric-${metric.tone}`} key={metric.key}>
            <div className="exact-metric-top"><span className="exact-metric-icon">{metricIcon(metric.tone)}</span><span className="exact-metric-label">{metric.label}</span><i className={`exact-status-pill ${state.tone}`}>{state.label}</i></div>
            <div className="exact-metric-main"><strong>{formatValue(metric.value, metric.digits)}</strong><small>{metric.unit}</small></div>
            <div className="exact-metric-bottom"><span>{metricMeta(metric.change, metric.unit)}</span></div>
          </article>
        })}
      </section>

      <section className="wb-priority-card"><div><span className="wb-kicker">当前重点</span><h2>{summary.warning_summary.latest_recommendation_title || (hasWarning ? '先核实风险，再安排现场处理' : hasEnvironment ? '了解当前棚况，安排日常农事' : '完善本棚的数据采集')}</h2><p>{summary.risk.reasons[0] || (hasEnvironment ? '结合实时监测、预警依据与现场情况，形成可追踪的生产安排。' : '当前数据不足，接入环境记录后再进行风险研判。')}</p><div className="wb-source-tags"><span>环境记录</span><span>风险依据</span><span>人工确认</span></div></div><Button type="primary" onClick={() => navigate(hasEnvironment ? `/platform/production?greenhouse_id=${selectedId}` : `/platform/data?greenhouse_id=${selectedId}&tab=connection`)}>{hasEnvironment ? '查看处理方案' : '接入环境数据'} <ArrowRightOutlined /></Button></section>

      <section className="exact-primary-grid">
        <article className="exact-panel exact-chart-card">
          <SectionHeading title="24 小时环境趋势" description={`${chartData.length} 条记录${chartOffset === 0 ? ' · 环境采样记录' : ' · 历史原始数据（最多1000条）'}`} action={<div className="exact-date-switch"><Button type="text" icon={<LeftOutlined />} aria-label="上一天" onClick={() => setChartOffset((value) => value + 1)} /><b>{formatDate(chartEnd)}</b><Button type="text" icon={<RightOutlined />} aria-label="下一天" disabled={chartOffset === 0} onClick={() => setChartOffset((value) => Math.max(0, value - 1))} /></div>} />
          {chartOffset > 0 && historyLoading ? <Skeleton active paragraph={{ rows: 4 }} /> : chartOffset > 0 && historyError ? <Alert type="error" showIcon message="历史趋势加载失败" description={historyError} action={<Button size="small" onClick={() => setHistoryRetry((value) => value + 1)}>重试</Button>} /> : chartData.length > 0 ? <EnvironmentTrendChart data={chartData} /> : <SaasEmptyState title="该时段没有环境记录" description="连接传感器或导入历史数据后，这里会显示环境变化曲线。" actionLabel="导入数据" onAction={() => navigate('/platform/data')} />}
        </article>

        <article className="exact-panel exact-todo-card">
          <SectionHeading title="待处理任务" description={`${todayTasks.length} 项最近任务`} action={<Button type="link" onClick={() => navigate(`/platform/production?greenhouse_id=${selectedId ?? ''}`)}>查看全部 <ArrowRightOutlined /></Button>} />
          {todayTasks.length ? <div className="exact-task-list">{todayTasks.map((task, index) => <button type="button" key={task.id} className="exact-task-row" onClick={() => navigate(`/platform/production?greenhouse_id=${selectedId ?? ''}&task_id=${task.id}`)}>
            <i className={`exact-task-dot ${taskTone(task)}`} /><span className={`exact-task-icon task-${taskTone(task)}`}>{index === 0 ? <BulbOutlined /> : index === 1 ? <ExperimentOutlined /> : <DatabaseOutlined />}</span><span className="exact-task-copy"><strong>{task.title}</strong><small>{task.assignee_name || taskSourceLabel[task.source_type] || '待分配'} · {taskStatusLabel[task.status] ?? task.status}</small></span><time>{task.due_at ? `${formatDueTime(task.due_at)} 前` : '待安排'}</time><ArrowRightOutlined className="exact-task-arrow" />
          </button>)}</div> : <SaasEmptyState title="没有待处理任务" description="当系统生成建议或预警时，会自动在这里形成待办。" />}
        </article>
      </section>

      <section className="exact-insight-grid">
        <button type="button" className="exact-insight-card exact-risk-card" onClick={() => navigate(`/platform/environment?greenhouse_id=${selectedId}&tab=alerts`)}><span className="exact-insight-icon"><SafetyCertificateOutlined /></span><div><small>病害与环境风险</small><strong>{summary.risk.data_status === 'insufficient' && !hasWarning ? '待评估' : warningLevelLabel[summary.warning_summary.highest_risk_level] ?? warningLevelLabel[summary.risk.level] ?? '待评估'}</strong><p>{summary.risk.reasons[0] || (hasEnvironment ? '暂无待处理的风险事件' : '接入环境数据后显示风险判断')}</p></div><b>{summary.warning_summary.open_warning_count}</b><em>项预警</em><ArrowRightOutlined /></button>
        <button type="button" className="exact-insight-card exact-health-card" onClick={() => navigate(`/platform/environment?greenhouse_id=${selectedId}&tab=monitoring`)}><span className="exact-insight-icon"><DatabaseOutlined /></span><div><small>数据采集</small><strong>{stale ? '数据待同步' : hasEnvironment ? '已接入' : '待接入'}</strong><p>{hasEnvironment ? `最近采集 ${formatDueTime(summary.data_updated_at || summary.latest_environment!.recorded_at)}` : '暂无环境数据'}</p></div><b>{summary.trend_24h.length}</b><em>条</em><ArrowRightOutlined /></button>
        <button type="button" className="exact-insight-card exact-decision-card" onClick={() => navigate(`/platform/production?greenhouse_id=${selectedId}`)}><span className="exact-insight-icon"><ThunderboltOutlined /></span><div><small>决策状态</small><strong>{summary.warning_summary.latest_recommendation_title ? '有最新建议' : '暂无建议'}</strong><p>{summary.warning_summary.latest_recommendation_title || '等待风险研判结果'}</p></div><ArrowRightOutlined /></button>
      </section>

      <section className="wb-process-strip" aria-label="生产处理流程">{[
        ['01', '监测发现', '环境记录与风险预警', '/platform/environment'],
        ['02', '辅助研判', '结合本棚信息理解问题', '/platform/diagnosis'],
        ['03', '人工确认', '安排农事任务与执行', '/platform/production'],
        ['04', '反馈复查', '记录处理后的变化', '/platform/production?tab=tasks'],
      ].map(([step,title,description,path]) => <button key={step} type="button" onClick={() => navigate(`${path}${path.includes('?') ? '&' : '?'}greenhouse_id=${selectedId}`)}><b>{step}</b><strong>{title}</strong><small>{description}</small></button>)}</section>

      <section className="exact-panel exact-activity-card">
        <SectionHeading title="最近动态" action={<Button type="link" onClick={() => navigate(`/platform/production?greenhouse_id=${selectedId ?? ''}`)}>查看更多 <ArrowRightOutlined /></Button>} />
        {recentActivities.length ? <div className="exact-activity-list">{recentActivities.map((activity, index) => <div className="exact-activity-row" key={`${activity.title}-${index}`}><time>{activity.time}</time><i className={`exact-activity-dot ${activity.tone}`} /><strong>{activity.title}</strong><span>{activity.meta}</span></div>)}</div> : <SaasEmptyState title="还没有动态记录" description="完成数据接入后，这里会显示工作区中的关键变化。" />}
      </section>
    </>}

    <ModelCenter open={modelCenterOpen} onClose={() => setModelCenterOpen(false)} />
  </div>
}
