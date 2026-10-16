import { canManage } from '../utils/permissions'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, Button, Empty, Progress, Select, Skeleton, Space, Table, Tag, message } from 'antd'
import { BranchesOutlined, CheckCircleOutlined, ClockCircleOutlined, ExperimentOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { useLocation, useNavigate } from 'react-router-dom'
import { getApiErrorMessage } from '../api/client'
import { getGreenhouses } from '../api/greenhouseApi'
import { executeDecisionPlan, generateDecisionPlans, getDecisionPlans, getGreenhouseRisk, recalculateRisk } from '../api/v2DecisionApi'
import type { Greenhouse } from '../types/greenhouse'
import type { DecisionPlan, RiskEvent, RiskItem } from '../types/v2Decision'
import './DiseaseTimeMachinePage.css'

const levelColor: Record<string, string> = { 低: 'green', 中: 'gold', 高: 'orange', 极高: 'red' }

function scoreText(value: number) {
  return `${Math.round(value)} 分`
}

export default function DiseaseTimeMachinePage() {
  const location = useLocation()
  const navigate = useNavigate()
  const [greenhouses, setGreenhouses] = useState<Greenhouse[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(Number(new URLSearchParams(location.search).get('greenhouse_id')) || null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [risks, setRisks] = useState<RiskItem[]>([])
  const [riskEvent, setRiskEvent] = useState<RiskEvent | null>(null)
  const [plans, setPlans] = useState<DecisionPlan[]>([])
  const [busy, setBusy] = useState(false)
  const [historical, setHistorical] = useState(false)

  const selectedGreenhouse = useMemo(() => greenhouses.find((item) => item.id === selectedId) ?? null, [greenhouses, selectedId])
  const topRisk = useMemo(() => [...risks].sort((a, b) => b.risk_72h - a.risk_72h)[0] ?? null, [risks])
  const greenhouseIdFromUrl = Number(new URLSearchParams(location.search).get('greenhouse_id')) || null

  const loadGreenhouses = useCallback(async () => {
    const result = await getGreenhouses({ page: 1, page_size: 100, status: 'active' })
    setGreenhouses(result.items)
    setSelectedId((current) => current && result.items.some((item) => item.id === current) ? current : result.items[0]?.id ?? null)
  }, [])

  const loadRisk = useCallback(async (greenhouseId: number) => {
    setLoading(true)
    setError(null)
    setRisks([])
    setRiskEvent(null)
    setPlans([])
    try {
      const result = await getGreenhouseRisk(greenhouseId)
      setHistorical(Boolean(result.current_environment.recorded_at && Date.now() - new Date(String(result.current_environment.recorded_at)).getTime() > 2 * 3600_000))
      setRisks(result.risks)
      setRiskEvent(result.top_event)
      if (result.top_event) setPlans(await getDecisionPlans(result.top_event.id))
    } catch (requestError) {
      setError(getApiErrorMessage(requestError))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void loadGreenhouses().catch((requestError) => { setError(getApiErrorMessage(requestError)); setLoading(false) }) }, [loadGreenhouses])
  useEffect(() => {
    if (greenhouseIdFromUrl && greenhouses.some((item) => item.id === greenhouseIdFromUrl)) setSelectedId(greenhouseIdFromUrl)
  }, [greenhouseIdFromUrl, greenhouses])
  useEffect(() => { if (selectedId) void loadRisk(selectedId) }, [selectedId, loadRisk])

  const handleRecalculate = async () => {
    if (!selectedId) return
    setBusy(true)
    try {
      const event = await recalculateRisk(selectedId, selectedGreenhouse?.active_batch?.crop_type, selectedGreenhouse?.active_batch?.growth_stage)
      setRiskEvent(event)
      await loadRisk(selectedId)
      setRiskEvent(event)
      const nextPlans = await generateDecisionPlans(event.id)
      setPlans(nextPlans)
      message.success('已生成风险事件和候选处置方案')
    } catch (requestError) {
      message.error(getApiErrorMessage(requestError))
    } finally {
      setBusy(false)
    }
  }

  const handleGeneratePlans = async () => {
    if (!riskEvent) return
    setBusy(true)
    try {
      setPlans(await generateDecisionPlans(riskEvent.id))
      message.success('候选方案已更新')
    } catch (requestError) {
      message.error(getApiErrorMessage(requestError))
    } finally {
      setBusy(false)
    }
  }

  const handleExecute = async (plan: DecisionPlan) => {
    setBusy(true)
    try {
      const result = await executeDecisionPlan(plan.id)
      message.success('已生成农事任务草稿')
      navigate(`/platform/production?greenhouse_id=${plan.greenhouse_id}&tab=tasks&task_id=${result.task.id}`)
    } catch (requestError) {
      message.error(getApiErrorMessage(requestError))
    } finally {
      setBusy(false)
    }
  }

  if (loading && greenhouses.length === 0) return <div className="disease-time-machine-page"><Skeleton active paragraph={{ rows: 12 }} /></div>

  return <div className="disease-time-machine-page">
    {historical && <Alert type="warning" showIcon message="依据历史记录推演，请勿将以下结果视为当前现场状态。" />}
    {error && <Alert type="warning" showIcon message="病害时间机数据加载失败" description={error} />}

    <section className="dtm-hero">
      <div>
        <span><ClockCircleOutlined /> Disease Time Machine</span>
        <h1>病害时间机</h1>
        <p>基于最近环境数据、连续高湿、昼夜温差、生育期敏感度和历史画像，推演未来 24/48/72 小时环境病害压力。0～100分为规则风险指数，不代表发病概率；当前规则尚未完成本棚现场校准。</p>
      </div>
      <Space wrap>
        <Select
          value={selectedId ?? undefined}
          style={{ width: 260 }}
          placeholder="选择大棚"
          options={greenhouses.map((item) => ({ value: item.id, label: `${item.name} · ${item.active_batch?.variety || item.code}` }))}
          onChange={(value) => { setSelectedId(value); const params = new URLSearchParams(location.search); params.set('greenhouse_id', String(value)); navigate(`${location.pathname}?${params.toString()}`, { replace: true }) }}
        />
        <Button type="primary" icon={<ThunderboltOutlined />} loading={busy} disabled={!selectedId || !canManage()} onClick={handleRecalculate}>重新计算并生成方案</Button>
      </Space>
    </section>

    {topRisk ? <section className="dtm-focus">
      <div className="dtm-focus-main">
        <Tag color={levelColor[topRisk.risk_level] || 'default'}>{topRisk.risk_level}风险</Tag>
        <h2>{selectedGreenhouse?.name || '当前大棚'} · {topRisk.disease_name}</h2>
        <p>{topRisk.explanation}</p>
      </div>
      <div className="dtm-risk-steps">
        {[['当前', topRisk.current_score], ['24h', topRisk.risk_24h], ['48h', topRisk.risk_48h], ['72h', topRisk.risk_72h]].map(([label, value]) => <div key={label}>
          <span>{label}</span>
          <Progress type="circle" percent={Math.round(value as number)} format={(percent) => `${percent}分`} size={78} strokeColor={(value as number) >= 80 ? '#d4380d' : (value as number) >= 60 ? '#fa8c16' : (value as number) >= 30 ? '#d4a106' : '#2f9e44'} />
        </div>)}
      </div>
    </section> : <Empty description="当前大棚环境数据不足，无法计算病害风险" />}

    <section className="dtm-grid">
      <div className="dtm-panel">
        <header><ExperimentOutlined /><strong>病害风险列表</strong></header>
        <Table
          rowKey="disease_type"
          size="small"
          pagination={false}
          dataSource={risks}
          columns={[
            { title: '病害', dataIndex: 'disease_name' },
            { title: '当前', render: (_, row) => scoreText(row.current_score) },
            { title: '24h', render: (_, row) => scoreText(row.risk_24h) },
            { title: '48h', render: (_, row) => scoreText(row.risk_48h) },
            { title: '72h', render: (_, row) => scoreText(row.risk_72h) },
            { title: '趋势', dataIndex: 'trend' },
            { title: '等级', render: (_, row) => <Tag color={levelColor[row.risk_level] || 'default'}>{row.risk_level}</Tag> },
          ]}
        />
      </div>

      <div className="dtm-panel">
        <header><BranchesOutlined /><strong>风险为什么会上升</strong></header>
        {topRisk?.factors.contributions.slice(0, 6).map((item) => <div className="dtm-factor" key={item.key}>
          <span>{item.label}</span>
          <Progress percent={Math.round(item.value)} size="small" showInfo={false} />
          <b>+{item.value.toFixed(1)}分</b>
        </div>)}
      </div>
    </section>

    <section className="dtm-panel">
      <header>
        <CheckCircleOutlined />
        <strong>智能处置方案</strong>
        <Button size="small" disabled={!riskEvent || !canManage()} loading={busy} onClick={handleGeneratePlans}>生成/刷新方案</Button>
      </header>
      <div className="dtm-plan-list">
        {plans.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="请先重新计算风险事件，或基于已生成事件刷新方案" />}
        {plans.map((plan) => <article className="dtm-plan" key={plan.id}>
          <div>
            <Tag color="green">规则评分 {plan.score}</Tag>
            <h3>{plan.plan_name}</h3>
            <p>{plan.rationale}</p>
            <small>探索性估计：{plan.expected_result_json.risk_before} → {plan.expected_result_json.risk_after} 分；需复测验证</small>
          </div>
          <Button type="primary" loading={busy} disabled={!canManage()} onClick={() => void handleExecute(plan)}>生成任务草稿</Button>
        </article>)}
      </div>
    </section>
  </div>
}
