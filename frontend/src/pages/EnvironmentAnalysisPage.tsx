import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  DatabaseOutlined,
  FileTextOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import {
  Alert,
  Button,
  Col,
  Drawer,
  Progress,
  Row,
  Segmented,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getApiErrorMessage } from '../api/client'
import { getDashboardSummary } from '../api/dashboardApi'
import { getGreenhouses } from '../api/greenhouseApi'
import { getEnvironmentPrediction } from '../api/predictionApi'
import { createTaskFromWarning } from '../api/taskApi'
import { getSensorHistory } from '../api/sensorApi'
import { evaluateWarnings, getWarnings } from '../api/warningApi'
import { EnvironmentTrendChart } from './Dashboard/EnvironmentTrendChart'
import { EnvironmentForecastChart } from './Prediction/EnvironmentForecastChart'
import type { DashboardSummary } from '../types/dashboard'
import type { Greenhouse } from '../types/greenhouse'
import type { EnvironmentPrediction } from '../types/prediction'
import type { QualityFlag, SensorReading } from '../types/sensor'
import type { RiskLevel, WarningEvent } from '../types/warning'
import { SaasEmptyState, SectionHeading } from '../components/SaasUI'
import { ProductSkeleton } from '../components/ProductStates'

const riskMeta: Record<RiskLevel | '数据不足', { label: string; color: string; className: string }> = {
  normal: { label: '正常', color: 'green', className: 'risk-normal' },
  attention: { label: '关注', color: 'gold', className: 'risk-attention' },
  warning: { label: '预警', color: 'orange', className: 'risk-warning' },
  critical: { label: '严重', color: 'red', className: 'risk-critical' },
  数据不足: { label: '数据不足', color: 'default', className: 'risk-empty' },
}

const qualityMeta: Record<QualityFlag, { label: string; color: string }> = {
  valid: { label: '有效', color: 'green' },
  suspect: { label: '可疑', color: 'orange' },
  missing: { label: '缺失', color: 'red' },
}

function formatValue(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined ? '—' : value.toFixed(digits)
}

function formatTime(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '暂无数据'
}

function dataHealth(history: SensorReading[]): { score: number; completeness: number; continuity: number } {
  if (!history.length) return { score: 0, completeness: 0, continuity: 0 }
  const fields: Array<keyof Pick<SensorReading, 'temperature' | 'air_humidity' | 'soil_moisture' | 'light_intensity' | 'co2_concentration'>> = [
    'temperature', 'air_humidity', 'soil_moisture', 'light_intensity', 'co2_concentration',
  ]
  const cells = history.length * fields.length
  const present = history.reduce((sum, row) => sum + fields.filter((field) => row[field] !== null).length, 0)
  const completeness = cells ? present / cells * 100 : 0
  let continuity = 100
  if (history.length > 2) {
    const times = history.map((row) => new Date(row.recorded_at).getTime()).sort((a, b) => a - b)
    const deltas = times.slice(1).map((time, index) => time - times[index]).filter((delta) => delta > 0)
    const sorted = [...deltas].sort((a, b) => a - b)
    const typical = sorted[Math.floor(sorted.length / 2)] || 0
    const allowed = typical * 1.75
    const normalIntervals = deltas.filter((delta) => delta <= allowed).length
    continuity = deltas.length ? normalIntervals / deltas.length * 100 : 100
  }
  const validRate = history.filter((row) => row.quality_flag === 'valid').length / history.length * 100
  return {
    completeness: Math.round(completeness),
    continuity: Math.round(continuity),
    score: Math.round(completeness * 0.4 + continuity * 0.35 + validRate * 0.25),
  }
}

export default function EnvironmentAnalysisPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const [greenhouses, setGreenhouses] = useState<Greenhouse[]>([])
  const [greenhouseId, setGreenhouseId] = useState<number | null>(null)
  const [rangeHours, setRangeHours] = useState<24 | 168 | 720>(24)
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [history, setHistory] = useState<SensorReading[]>([])
  const [prediction, setPrediction] = useState<EnvironmentPrediction | null>(null)
  const [warnings, setWarnings] = useState<WarningEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [evaluating, setEvaluating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
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
      setSummary(null)
      setHistory([])
      setPrediction(null)
      setWarnings([])
      return
    }
    setLoading(true)
    setError(null)
    const end = new Date()
    const start = new Date(end.getTime() - rangeHours * 60 * 60 * 1000)
    try {
      const [summaryResult, historyResult, predictionResult, warningResult] = await Promise.all([
        getDashboardSummary(greenhouseId),
        getSensorHistory({ greenhouse_id: greenhouseId, start_time: start.toISOString(), end_time: end.toISOString(), page: 1, page_size: 1000 }),
        getEnvironmentPrediction(greenhouseId, 6),
        getWarnings({ greenhouse_id: greenhouseId, page: 1, page_size: 10 }),
      ])
      setSummary(summaryResult)
      setHistory(historyResult.items)
      setPrediction(predictionResult)
      setWarnings(warningResult.items)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError))
    } finally {
      setLoading(false)
    }
  }, [greenhouseId, rangeHours])

  useEffect(() => {
    setLoading(true)
    void loadGreenhouses().catch((requestError) => setError(getApiErrorMessage(requestError))).finally(() => setLoading(false))
  }, [loadGreenhouses])

  useEffect(() => { void loadWorkspace() }, [loadWorkspace])


  const createWarningTask = async (warning: WarningEvent) => {
    try {
      const task = await createTaskFromWarning(warning.id, '管理员')
      messageApi.success('已生成农事任务草稿，正在进入任务中心')
      navigate(`/platform/production?greenhouse_id=${warning.greenhouse_id}${warning.crop_batch_id ? `&batch_id=${warning.crop_batch_id}` : ''}&task_id=${task.id}`)
    } catch (requestError) {
      messageApi.error(getApiErrorMessage(requestError))
    }
  }

  const runRiskEvaluation = async () => {
    if (!greenhouseId) return
    setEvaluating(true)
    try {
      const result = await evaluateWarnings(greenhouseId)
      messageApi.success(result.created_count || result.updated_count ? '环境风险分析已更新' : '当前未发现新的风险事件')
      await loadWorkspace()
    } catch (requestError) {
      messageApi.error(getApiErrorMessage(requestError))
    } finally {
      setEvaluating(false)
    }
  }

  const health = useMemo(() => dataHealth(history), [history])
  const latest = summary?.latest_environment
  const dashboardRiskAlias: Record<string, RiskLevel | '数据不足'> = {
    normal: 'normal', attention: 'attention', warning: 'warning', critical: 'critical',
    正常: 'normal', 关注: 'attention', 预警: 'warning', 严重: 'critical', 数据不足: '数据不足',
  }
  const currentRiskKey = dashboardRiskAlias[summary?.risk.level ?? '数据不足'] ?? '数据不足'
  const currentRisk = riskMeta[currentRiskKey]
  const forecastPoints = prediction?.status === 'ready' ? prediction.predictions : []


  const historyColumns: ColumnsType<SensorReading> = [
    { title: '时间', dataIndex: 'recorded_at', width: 180, render: formatTime },
    { title: '温度', dataIndex: 'temperature', render: (value: number | null) => formatValue(value) },
    { title: '空气湿度', dataIndex: 'air_humidity', render: (value: number | null) => formatValue(value) },
    { title: '土壤湿度', dataIndex: 'soil_moisture', render: (value: number | null) => formatValue(value) },
    { title: '光照', dataIndex: 'light_intensity', render: (value: number | null) => formatValue(value) },
    { title: 'CO₂', dataIndex: 'co2_concentration', render: (value: number | null) => formatValue(value, 0) },
    { title: '质量', dataIndex: 'quality_flag', render: (value: QualityFlag) => <Tag color={qualityMeta[value].color}>{qualityMeta[value].label}</Tag> },
  ]

  if (loading && !summary && !greenhouses.length) {
    return <div className="v18-environment-page"><ProductSkeleton rows={6} /></div>
  }

  return <div className="business-page environment-workbench commercial-environment-page v18-environment-page">
    {messageContext}
    <div className="page-intro workbench-intro commercial-page-intro">
      <div>
        <span className="eyebrow">ENVIRONMENT INTELLIGENCE</span>
        <h1>环境分析</h1>
        <p>把实时指标、趋势、数据健康和风险研判放在同一个环境工作台中。</p>
      </div>
      <Space wrap>
        <Button icon={<FileTextOutlined />} onClick={() => setHistoryOpen(true)} disabled={!history.length}>数据明细</Button>
        <Button icon={<ThunderboltOutlined />} loading={evaluating} onClick={() => void runRiskEvaluation()} disabled={!latest}>分析风险</Button>
        <Button type="primary" icon={<ReloadOutlined />} onClick={() => void loadWorkspace()}>刷新</Button>
      </Space>
    </div>

    <div className="analysis-control-strip">
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
      <div className="command-field range-field">
        <span>分析范围</span>
        <Segmented value={rangeHours} onChange={(value) => setRangeHours(value as 24 | 168 | 720)} options={[
          { label: '24小时', value: 24 }, { label: '7天', value: 168 }, { label: '30天', value: 720 },
        ]} />
      </div>
      <div className="analysis-control-meta">
        <span>数据来源<b>{summary?.data_source_label ?? '暂无'}</b></span>
        <span>生育阶段<b>{summary?.active_batch?.growth_stage ?? '暂无批次'}</b></span>
        <span>最近同步<b>{formatTime(summary?.data_updated_at)}</b></span>
      </div>
    </div>

    {error && <Alert className="page-alert" type="error" showIcon message="环境分析数据加载失败" description={error} action={<Button size="small" onClick={() => void loadWorkspace()}>重试</Button>} />}

    {!greenhouseId ? <SaasEmptyState title="还没有运行中的大棚" description="创建大棚并接入环境数据后，这里会自动形成环境趋势、风险和预测。" /> : <Spin spinning={loading}>
      <Row gutter={[20, 20]} className="environment-overview-row">
        <Col xs={24} xl={16}>
          <section className="current-environment-panel surface-card surface-card-major">
            <SectionHeading title="当前环境" description={latest ? `采集时间 ${formatTime(latest.recorded_at)}` : '等待最新环境数据'} />
            <div className="environment-primary-metrics">
              <div><span>空气温度</span><strong>{formatValue(latest?.temperature)}<small>℃</small></strong></div>
              <div><span>空气湿度</span><strong>{formatValue(latest?.air_humidity)}<small>%RH</small></strong></div>
              <div><span>CO₂ 浓度</span><strong>{formatValue(latest?.co2_concentration, 0)}<small>ppm</small></strong></div>
            </div>
            <div className="environment-secondary-bars">
              <div><span>土壤湿度 <b>{formatValue(latest?.soil_moisture)}%</b></span><Progress percent={Math.max(0, Math.min(100, latest?.soil_moisture ?? 0))} showInfo={false} strokeColor="#9b7653" trailColor="#edf0ec" /></div>
              <div><span>光照强度 <b>{formatValue(latest?.light_intensity)} klx</b></span><Progress percent={Math.max(0, Math.min(100, latest?.light_intensity ?? 0))} showInfo={false} strokeColor="#d6ae33" trailColor="#edf0ec" /></div>
            </div>
          </section>
        </Col>
        <Col xs={24} xl={8}>
          <section className={`environment-status-panel surface-card risk-panel-${currentRiskKey}`}>
            <div className="environment-status-head"><span>环境状态</span><SafetyCertificateOutlined /></div>
            <strong>{currentRisk.label}</strong>
            <p>{summary?.risk.reasons?.[0] ?? '当前没有足够数据形成风险判断。'}</p>
            <div className="environment-status-metrics">
              <span>风险分<b>{summary?.risk.overall_score === null || summary?.risk.overall_score === undefined ? '—' : summary.risk.overall_score.toFixed(1)}</b></span>
              <span>数据健康<b>{history.length ? `${health.score}%` : '—'}</b></span>
              <span>待处理风险<b>{warnings.filter((item) => ['open', 'acknowledged'].includes(item.status)).length}</b></span>
            </div>
          </section>
        </Col>
      </Row>

      <Row gutter={[20, 20]} className="analysis-main-row commercial-analysis-main">
        <Col xs={24} xl={16}>
          <section className="surface-card surface-card-major chart-workspace-card commercial-trend-panel">
            <SectionHeading title="环境趋势" description={rangeHours === 24 ? '最近24小时' : rangeHours === 168 ? '最近7天' : '最近30天'} action={<Tag>{history.length} 条记录</Tag>} />
            {history.length ? <EnvironmentTrendChart data={history} /> : <SaasEmptyState title="还没有环境监测数据" description="连接传感器或导入历史数据后，系统会自动生成趋势分析。" actionLabel="前往大棚管理" onAction={() => window.location.assign('/platform/data')} />}
          </section>
        </Col>
        <Col xs={24} xl={8}>
          <section className="environment-insight-panel surface-card">
            <SectionHeading title="今日洞察" description="从数据质量、风险和预测中提取重点" />
            <div className="environment-insight-list">
              <div><DatabaseOutlined /><span><strong>数据可用度 {history.length ? `${health.score}%` : '—'}</strong><small>完整性 {health.completeness}% · 连续性 {health.continuity}%</small></span></div>
              <div><SafetyCertificateOutlined /><span><strong>{warnings.length ? `${warnings.filter((item) => ['open', 'acknowledged'].includes(item.status)).length} 个风险待处理` : '暂无风险事件'}</strong><small>{warnings[0]?.title ?? '当前环境状态稳定'}</small></span></div>
              <div><ThunderboltOutlined /><span><strong>{prediction?.status === 'ready' ? '预测服务已就绪' : '预测等待连续数据'}</strong><small>{prediction?.status === 'ready' ? `未来 ${prediction.horizon_hours} 小时趋势已生成` : '达到连续时长要求后自动开放预测'}</small></span></div>
            </div>
          </section>
        </Col>
      </Row>

      <section className="surface-card surface-card-major forecast-workspace commercial-forecast-workspace">
        <SectionHeading title="未来 1～6 小时趋势" description="用于提前安排通风、灌溉和巡棚优先级" action={prediction?.status === 'ready' ? <Tag color="green">预测服务正常</Tag> : <Tag>等待数据</Tag>} />
        {prediction?.status === 'ready' && prediction.predictions.length ? <>
          <div className="forecast-quick-grid">
            {forecastPoints.slice(0, 3).map((point) => <div className="forecast-quick-card" key={point.horizon}>
              <span>{point.horizon}h 后</span>
              <strong>{formatValue(point.temperature_c)}℃</strong>
              <small>湿度 {formatValue(point.air_humidity_pct)}%RH</small>
            </div>)}
            <div className="forecast-method-card">
              <span>本次预测</span>
              <strong>{prediction.forecast_method_labels[0] ?? '混合预测策略'}</strong>
              <small>输出 {prediction.total_output_count} 个时长结果</small>
            </div>
          </div>
          <EnvironmentForecastChart data={prediction} />
        </> : <SaasEmptyState title="还不能生成未来趋势" description={prediction?.status === 'insufficient_data' ? '至少需要连续24小时环境数据后才能生成预测。' : '暂无可用预测结果。'} />}
      </section>

      <Row gutter={[20, 20]} className="environment-bottom-row">
        <Col xs={24} xl={15}>
          <section className="surface-card risk-event-panel">
            <SectionHeading title="风险事件" description="按照严重程度和最新触发时间排序" action={<Tag color={warnings.filter((item) => ['open', 'acknowledged'].includes(item.status)).length ? 'orange' : 'green'}>{warnings.filter((item) => ['open', 'acknowledged'].includes(item.status)).length} 个待处理</Tag>} />
            {warnings.length ? <div className="warning-list-compact">{warnings.slice(0, 6).map((item) => {
              const meta = riskMeta[item.severity]
              return <div className="warning-compact-item" key={item.id}>
                <div className={`warning-dot ${meta.className}`} />
                <div><strong>{item.title}</strong><span>{item.description}</span></div>
                <div className="warning-item-meta"><Tag color={meta.color}>{meta.label}</Tag><small>{formatTime(item.last_triggered_at)}</small></div>
                {['open', 'acknowledged'].includes(item.status) && <Button className="v18-warning-task-button" size="small" onClick={() => void createWarningTask(item)}>创建任务</Button>}
              </div>
            })}</div> : <SaasEmptyState title="当前没有风险事件" description="系统会持续监测环境变化，出现异常后在这里形成可追踪的风险事件。" />}
          </section>
        </Col>
        <Col xs={24} xl={9}>
          <section className="analysis-summary-panel">
            <span className="eyebrow">ANALYSIS SUMMARY</span>
            <h3>分析摘要</h3>
            <div className="analysis-summary-numbers">
              <div><strong>{summary?.today_abnormal_count ?? 0}</strong><span>今日异常点</span></div>
              <div><strong>{prediction?.horizon_hours ?? 0}h</strong><span>预测时长</span></div>
              <div><strong>{history.length}</strong><span>历史记录</span></div>
            </div>
            <p>{prediction?.status === 'ready' ? '预测结果已与当前环境和风险事件汇总，可进入农事任务查看建议。' : '环境数据达到连续时长要求后，系统会自动开放未来趋势预测。'}</p>
          </section>
        </Col>
      </Row>
    </Spin>}

    <Drawer title="环境数据明细" width="min(1160px, 96vw)" open={historyOpen} onClose={() => setHistoryOpen(false)} destroyOnHidden>
      <Table<SensorReading> rowKey="id" dataSource={history} columns={historyColumns} scroll={{ x: 900 }} pagination={{ pageSize: 20, showSizeChanger: true }} />
    </Drawer>
  </div>
}
