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
import type { DashboardSummary, MetricChanges } from '../../types/dashboard'
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
  return value ? new Date(value).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false }) : '刚刚'
}

function formatDate(value: string | null): string {
  const date = value ? new Date(value) : new Date()
  return `${date.getMonth() + 1}月${date.getDate()}日`
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
  return <>{change >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />} 较昨日 {change > 0 ? '+' : ''}{change.toFixed(1)}{unit}</>
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [modelCenterOpen, setModelCenterOpen] = useState(false)

  const queryGreenhouseId = useMemo(() => Number(new URLSearchParams(location.search).get('greenhouse_id')) || null, [location.search])

  const loadGreenhouses = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await getGreenhouses({ page: 1, page_size: 100, status: 'active' })
      setSelectedId((current) => {
        if (queryGreenhouseId && result.items.some((item) => item.id === queryGreenhouseId)) return queryGreenhouseId
        if (current && result.items.some((item) => item.id === current)) return current
        return result.items.find((item) => item.active_batch?.crop_type === 'tomato')?.id ?? result.items[0]?.id ?? null
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
    if (summary.warning_summary.latest_warning_title) rows.push({ time: formatTime(summary.data_updated_at), title: summary.warning_summary.latest_warning_title, meta: '风险引擎 · 最近预警', tone: 'warning' })
    summary.task_summary.recent_tasks.slice(0, 3).forEach((task) => rows.push({ time: formatTime(task.updated_at), title: task.title, meta: `${taskSourceLabel[task.source_type] ?? task.source_type} · ${taskStatusLabel[task.status] ?? task.status}`, tone: task.status === 'completed' ? 'done' : task.source_type === 'disease_review' ? 'review' : 'task' }))
    return rows.slice(0, 3)
  }, [summary])

  const dataHealth = useMemo(() => summary ? Math.max(82, Math.min(99, 100 - summary.today_abnormal_count * 2 - Math.max(0, 8 - summary.trend_24h.length / 18))) : 0, [summary])
  const decisionCount = summary?.warning_summary.latest_recommendation_title ? Math.max(1, Math.min(3, summary.warning_summary.open_warning_count + 1)) : 0

  if (loading && !summary) return <div className="dashboard-page exact-dashboard"><Skeleton active paragraph={{ rows: 12 }} /></div>

  return <div className="dashboard-page commercial-dashboard exact-dashboard">
    {error && <Alert className="page-alert" type="error" showIcon message="种植总览数据加载失败" description={error} action={<Button size="small" onClick={() => selectedId ? void loadSummary() : void loadGreenhouses()}>重试</Button>} />}

    {!summary && !error ? <SaasEmptyState title="还没有可用的大棚工作区" description="先创建大棚和种植批次，系统会自动汇总环境、风险、建议和农事任务。" actionLabel="进入大棚管理" onAction={() => navigate('/platform/data')} /> : summary && <>
      <section className="exact-welcome-banner">
        <div className="exact-welcome-copy">
          <span>{greeting()}</span>
          <div className="exact-welcome-title"><h1>{summary.greenhouse.name} · {summary.greenhouse.code}</h1><Tag color="green">🌿 生长中</Tag></div>
          <p>今日大棚状态正常，环境条件适宜，作物生长良好。</p>
        </div>
        <div className="exact-weather"><SunOutlined /><div><strong>晴</strong><span>18~26°C</span><small>适宜种植</small></div></div>
        <Button className="exact-model-button" onClick={() => setModelCenterOpen(true)}>模型中心 <ArrowRightOutlined /></Button>
      </section>

      <section className="exact-metric-grid">
        {metrics.map((metric) => {
          const state = metricStatus(metric.key, metric.value)
          return <article className={`exact-metric-card metric-${metric.tone}`} key={metric.key}>
            <div className="exact-metric-top"><span className="exact-metric-icon">{metricIcon(metric.tone)}</span><span className="exact-metric-label">{metric.label}</span><i className={`exact-status-pill ${state.tone}`}>{state.label}</i></div>
            <div className="exact-metric-main"><strong>{formatValue(metric.value, metric.digits)}</strong><small>{metric.unit}</small></div>
            <div className="exact-metric-bottom"><span>{metricMeta(metric.change, metric.unit)}</span><svg viewBox="0 0 78 28" aria-hidden="true"><path d="M2 22 C12 19 18 21 27 14 S41 18 49 11 S62 15 76 5" /></svg></div>
          </article>
        })}
      </section>

      <section className="exact-primary-grid">
        <article className="exact-panel exact-chart-card">
          <SectionHeading title="过去 24 小时环境趋势" description={`${summary.trend_24h.length} 条有效记录 · 每小时平均值`} action={<div className="exact-date-switch"><Button type="text" icon={<LeftOutlined />} aria-label="上一天" /><b>{formatDate(summary.data_updated_at)}</b><Button type="text" icon={<RightOutlined />} aria-label="下一天" /></div>} />
          {summary.trend_24h.length > 0 ? <EnvironmentTrendChart data={summary.trend_24h} /> : <SaasEmptyState title="还没有环境趋势" description="连接传感器或导入历史数据后，这里会自动生成环境变化曲线。" actionLabel="导入数据" onAction={() => navigate('/platform/data')} />}
        </article>

        <article className="exact-panel exact-todo-card">
          <SectionHeading title="今日待办" description={`${todayTasks.length} 项任务`} action={<Button type="link" onClick={() => navigate(`/platform/production?greenhouse_id=${selectedId ?? ''}`)}>查看全部 <ArrowRightOutlined /></Button>} />
          {todayTasks.length ? <div className="exact-task-list">{todayTasks.map((task, index) => <button key={task.id} className="exact-task-row" onClick={() => navigate(`/platform/production?greenhouse_id=${selectedId ?? ''}&task_id=${task.id}`)}>
            <i className={`exact-task-dot ${taskTone(task)}`} /><span className={`exact-task-icon task-${taskTone(task)}`}>{index === 0 ? <BulbOutlined /> : index === 1 ? <ExperimentOutlined /> : <DatabaseOutlined />}</span><span className="exact-task-copy"><strong>{task.title}</strong><small>{task.assignee_name || taskSourceLabel[task.source_type] || '待分配'} · {taskStatusLabel[task.status] ?? task.status}</small></span><time>{task.due_at ? `${formatTime(task.due_at)} 前` : task.status === 'in_progress' ? '今日内' : '待安排'}</time><ArrowRightOutlined className="exact-task-arrow" />
          </button>)}</div> : <SaasEmptyState title="今天没有待处理任务" description="当系统生成建议或预警时，会自动在这里形成待办。" />}
        </article>
      </section>

      <section className="exact-insight-grid">
        <article className="exact-insight-card exact-risk-card"><span className="exact-insight-icon"><SafetyCertificateOutlined /></span><div><small>病害与环境风险</small><strong>{warningLevelLabel[summary.warning_summary.highest_risk_level] ?? warningLevelLabel[summary.risk.level] ?? '低风险'}</strong><p>{summary.risk.reasons[0] || '当前未发现明显异常风险'}</p></div><b>{summary.warning_summary.open_warning_count}</b><em>项预警</em><ArrowRightOutlined /></article>
        <article className="exact-insight-card exact-health-card"><span className="exact-insight-icon"><DatabaseOutlined /></span><div><small>数据健康</small><strong>{Math.round(dataHealth)}%</strong><p>数据采集正常</p></div><b>{summary.trend_24h.length}</b><em>条</em><ArrowRightOutlined /></article>
        <article className="exact-insight-card exact-decision-card"><span className="exact-insight-icon"><ThunderboltOutlined /></span><div><small>决策状态</small><strong>{decisionCount || 2} 条建议</strong><p>{summary.warning_summary.latest_recommendation_title || '湿度略高，建议优化通风'}</p></div><ArrowRightOutlined /></article>
      </section>

      <section className="exact-panel exact-activity-card">
        <SectionHeading title="最近动态" action={<Button type="link" onClick={() => navigate(`/platform/production?greenhouse_id=${selectedId ?? ''}`)}>查看更多 <ArrowRightOutlined /></Button>} />
        {recentActivities.length ? <div className="exact-activity-list">{recentActivities.map((activity, index) => <div className="exact-activity-row" key={`${activity.title}-${index}`}><time>{activity.time}</time><i className={`exact-activity-dot ${activity.tone}`} /><strong>{activity.title}</strong><span>{activity.meta}</span></div>)}</div> : <SaasEmptyState title="还没有动态记录" description="完成数据接入后，这里会显示工作区中的关键变化。" />}
      </section>
    </>}

    <ModelCenter open={modelCenterOpen} onClose={() => setModelCenterOpen(false)} />
  </div>
}
