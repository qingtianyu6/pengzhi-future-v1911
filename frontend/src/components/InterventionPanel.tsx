import { canManage } from '../utils/permissions'
import { useCallback, useEffect, useState } from 'react'
import { Alert, Button, Input, Modal, Select, Space, Tag, message } from 'antd'
import { getApiErrorMessage } from '../api/client'
import { evaluateWarnings, getWarnings } from '../api/warningApi'
import { getCandidates, getInterventions, recordObservation, selectCandidate, type ActionCandidate, type Intervention } from '../api/interventionApi'
import { getCases, getSimilarCases, type ProductionCase, type SimilarCases } from '../api/caseApi'
import { getDecisionSupport, type CostLevel, type DecisionSupport } from '../api/decisionSupportApi'
import type { WarningEvent } from '../types/warning'
import './InterventionPanel.css'

const energyLabel: Record<string, string> = { none: '无', low: '低', medium: '中', high: '高' }

export function InterventionPanel({ greenhouseId, onOpenTasks }: { greenhouseId: number; onOpenTasks: () => void }) {
  const [warning, setWarning] = useState<WarningEvent | null>(null)
  const [candidates, setCandidates] = useState<ActionCandidate[]>([])
  const [interventions, setInterventions] = useState<Intervention[]>([])
  const [cases, setCases] = useState<ProductionCase[]>([])
  const [similar, setSimilar] = useState<SimilarCases | null>(null)
  const [support, setSupport] = useState<DecisionSupport | null>(null)
  const [maxEnergy, setMaxEnergy] = useState<CostLevel>('high')
  const [maxLabor, setMaxLabor] = useState<CostLevel>('high')
  const [chosen, setChosen] = useState<ActionCandidate | null>(null)
  const [reason, setReason] = useState('')
  const [observationOffset, setObservationOffset] = useState<30 | 60 | null>(null)
  const [manualStatus, setManualStatus] = useState('')
  const [riskResolved, setRiskResolved] = useState<boolean | null>(null)
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [messageApi, context] = message.useMessage()

  const load = useCallback(async () => {
    setError(null)
    try {
      const [warnings, records, casePage] = await Promise.all([
        getWarnings({ greenhouse_id: greenhouseId, warning_type: 'temperature_humidity_combination', page_size: 20 }),
        getInterventions(greenhouseId),
        getCases(greenhouseId),
      ])
      const current = warnings.items.find((item) => item.crop_type === 'tomato' && ['open', 'acknowledged'].includes(item.status)) ?? null
      setWarning(current)
      setInterventions(records)
      setCases(casePage.items)
      let options: ActionCandidate[] = []
      let history: SimilarCases | null = null
      let decisionSupport: DecisionSupport | null = null
      if (current) {
        [options, history, decisionSupport] = await Promise.all([
          getCandidates(current.id), getSimilarCases(current.id),
          getDecisionSupport(current.id, maxEnergy, maxLabor),
        ])
      }
      setCandidates(options)
      setSimilar(history)
      setSupport(decisionSupport)
    } catch (err) { setError(getApiErrorMessage(err)) }
  }, [greenhouseId, maxEnergy, maxLabor])

  useEffect(() => { void load() }, [load])
  const active = warning ? interventions.find((item) => item.warning_event_id === warning.id) : undefined
  const latest = interventions[0]
  const selected = active ?? latest
  const currentCandidate = candidates.find((item) => item.id === selected?.candidate_id)

  const evaluate = async () => {
    setBusy(true)
    try { await evaluateWarnings(greenhouseId); await load(); messageApi.success('研判已更新') }
    catch (err) { messageApi.error(getApiErrorMessage(err)) }
    finally { setBusy(false) }
  }

  const confirmSelection = async () => {
    if (!chosen || reason.trim().length < 2) { messageApi.warning('请填写选择原因'); return }
    setBusy(true)
    try {
      await selectCandidate(chosen.id, reason.trim())
      setChosen(null); setReason('')
      await load()
      messageApi.success('方案已记录，任务草稿已创建')
    } catch (err) { messageApi.error(getApiErrorMessage(err)) }
    finally { setBusy(false) }
  }

  const confirmObservation = async () => {
    if (!selected || !observationOffset) return
    setBusy(true)
    try {
      await recordObservation(selected.id, observationOffset, manualStatus, riskResolved, notes)
      setObservationOffset(null); setManualStatus(''); setRiskResolved(null); setNotes('')
      await load()
      messageApi.success('复测结果已记录')
    } catch (err) { messageApi.error(getApiErrorMessage(err)) }
    finally { setBusy(false) }
  }

  return <section className="surface-card intervention-panel">
    {context}
    <div className="intervention-head"><div><span className="eyebrow">PROMAX · PRODUCTION DECISION</span><h2>高温高湿处置闭环</h2><p>比较方案证据、模拟结果和成本约束，由现场人员决定并复测。</p></div><Button disabled={!canManage()} loading={busy} onClick={() => void evaluate()}>刷新研判</Button></div>
    {error && <Alert type="error" showIcon message={error} />}
    {warning ? <><div className="intervention-warning"><Tag color="orange">当前预警</Tag><strong>{warning.title}</strong><span>风险分 {warning.risk_score.toFixed(1)} · {warning.description}</span></div>
      <div className="intervention-options">{candidates.map((option) => <article key={option.id} className={option.id === active?.candidate_id ? 'is-selected' : ''}>
        <div><strong>{option.title}</strong>{option.id === active?.candidate_id && <Tag color="green">已选择</Tag>}</div>
        <p>{option.description}</p>
        <div className="option-metrics"><span>能耗：{energyLabel[option.energy_level] ?? option.energy_level}</span><span>人工：{energyLabel[option.labor_level] ?? option.labor_level}</span><span>相似案例：{support?.candidate_evidence.find((row) => row.action_code === option.action_code)?.historical_case_count ?? 0} 次</span></div>
        {support?.candidate_evidence.find((row) => row.action_code === option.action_code) && <div className="candidate-evidence-detail">{(() => { const evidence = support.candidate_evidence.find((row) => row.action_code === option.action_code)!; return <><span>适用条件：{evidence.applicability_note}</span><span>60 分钟有实测 {evidence.measured_60min_count} 次 · 风险分下降 {evidence.observed_risk_decrease_count} 次 · 人工确认解除 {evidence.manually_resolved_count} 次</span><span>温度变化中位数 {evidence.median_temperature_change_c ?? '—'}℃ · 湿度变化中位数 {evidence.median_humidity_change_pct ?? '—'}% · 证据量 {evidence.evidence_level}</span></> })()}</div>}
        <small>{option.evidence_note}</small>
        {!active && <Button size="small" type="primary" onClick={() => setChosen(option)}>选择此方案</Button>}
      </article>)}</div>
    </> : <Alert type="info" showIcon message="当前没有番茄高温高湿预警" description="接入环境数据后点击“刷新研判”，有风险时将显示候选方案。" />}
    {warning && <div className="decision-simulation"><h3>处置前 What-if 模拟</h3><p>探索 30/60 分钟内可能的变化，区间表示当前模型的不确定性。</p>
      {support?.status === 'insufficient_context' ? <Alert type="info" message="当前数据不足，无法模拟" /> : <div className="scenario-grid">{support?.scenarios.map((scenario) => <article key={scenario.action_code}><strong>{scenario.title}</strong><Tag color={scenario.basis === 'historical_median' ? 'green' : 'gold'}>{scenario.basis === 'historical_median' ? '历史观察' : '简化假设'}</Tag>{scenario.points.map((point) => <div key={point.offset_minutes}><b>{point.offset_minutes} 分钟</b><span>风险 {point.risk_score ?? '—'}，区间 {point.risk_lower ?? '—'}–{point.risk_upper ?? '—'}</span><small>温度 {point.temperature_c ?? '—'}℃ · 湿度 {point.humidity_pct ?? '—'}%</small></div>)}<small>{scenario.note} · 参考案例 {scenario.supporting_cases} 次</small></article>)}</div>}
    </div>}
    {warning && <div className="decision-simulation"><h3>数据驱动方案比较</h3><div className="decision-cost-controls"><span>能耗上限</span><Select<CostLevel> value={maxEnergy} onChange={setMaxEnergy} options={Object.entries(energyLabel).map(([value, label]) => ({ value, label }))} /><span>人工投入上限</span><Select<CostLevel> value={maxLabor} onChange={setMaxLabor} options={Object.entries(energyLabel).map(([value, label]) => ({ value, label }))} /></div>
      {support?.outcome_model_status === 'insufficient_data' && <Alert type="info" message="实测案例不足，暂不计算方案评分；仍可查看上方历史证据与模拟。" />}
      {support?.outcome_estimates.map((row) => <div className="case-evidence" key={row.action_code}><strong>{row.title} <Tag color={row.within_cost_limit ? 'green' : 'default'}>{row.within_cost_limit ? '符合成本约束' : '超出成本约束'}</Tag></strong><span>60 分钟有效案例 {row.measured_cases} 次 · 平均风险分变化 {row.observed_risk_change_mean ?? '—'} · 约束评分 {row.comparison_score ?? '数据不足'}</span><small>{row.note}</small></div>)}<small>{support?.explanation}</small>
    </div>}
    {warning && <div className="case-memory"><h3>同类历史经验</h3>
      <p>{similar?.status === 'insufficient_context' ? '当前温湿度数据不足，暂不能匹配。' : `找到 ${similar?.total_eligible_cases ?? 0} 个可检索案例，展示最相似的 ${similar?.matches.length ?? 0} 个。`}</p>
      {similar?.action_evidence.map((row) => <div className="case-evidence" key={row.action_code}><strong>{row.action_title}</strong><span>{row.case_count} 次选择 · {row.with_60min_measurement} 次有 60 分钟数据 · {row.observed_risk_decrease_count} 次观察到风险分下降 · {row.manually_resolved_count} 次人工确认解除</span><small>温度变化中位数 {row.median_temperature_change_c ?? '—'}℃ · 湿度变化中位数 {row.median_humidity_change_pct ?? '—'}% · 证据量：{row.evidence_level}</small></div>)}
      {similar?.matches.map((row) => <div className="case-evidence" key={row.case.id}><strong>{row.case.case_code} · {row.case.selected_action_title}</strong><span>相似距离 {row.distance.toFixed(2)} · 温度 {row.case.context.temperature_c ?? '—'}℃ · 湿度 {row.case.context.air_humidity_pct ?? '—'}%</span><small>选择原因：{row.case.selection_reason}；60 分钟：{row.case.observations.find((obs) => obs.offset_minutes === 60)?.manual_status ?? '无人工观察'}</small></div>)}
      <small>{similar?.explanation ?? '历史结果仅作为观察证据。'}</small>
    </div>}
    {selected && <div className="intervention-timeline"><h3>{active ? '当前预警' : '最近一次处置'}：风险 → 决策 → 执行 → 效果</h3>
      <div className="intervention-step"><b>1</b><span>人工选择 {currentCandidate?.title ?? selected.action_type}<small>{selected.selection_reason}</small></span><Tag>{new Date(selected.selected_at).toLocaleString('zh-CN')}</Tag></div>
      <div className="intervention-step"><b>2</b><span>任务执行<small>{selected.started_at ? `开始于 ${new Date(selected.started_at).toLocaleString('zh-CN')}` : '等待任务提交并开始'}</small></span><Button size="small" onClick={onOpenTasks}>打开任务中心</Button></div>
      <div className="intervention-step"><b>3</b><span>处置前记录<small>温度 {String(selected.before_snapshot_json.temperature ?? '—')}℃ · 湿度 {String(selected.before_snapshot_json.humidity ?? '—')}% · 风险分 {String(selected.before_snapshot_json.risk_score ?? '—')}</small></span></div>
      {[30, 60].map((offset) => { const found = selected.observations.find((item) => item.offset_minutes === offset); return <div className="intervention-step" key={offset}><b>{offset === 30 ? '4' : '5'}</b><span>{offset} 分钟复测<small>{found ? `温度 ${found.temperature ?? '无数据'}℃ · 湿度 ${found.humidity ?? '无数据'}% · 风险分 ${found.risk_score ?? '无数据'} · ${found.manual_status ?? '未填人工观察'} · 风险${found.risk_resolved === null ? '待确认' : found.risk_resolved ? '已解除' : '未解除'}` : '待现场人员记录'}</small></span>{!found && <Button size="small" disabled={!selected.started_at} onClick={() => setObservationOffset(offset as 30 | 60)}>记录复测</Button>}</div> })}
      <Alert type="info" showIcon message={selected.causality_notice} />
    </div>}
    <div className="case-memory"><h3>本棚案例记录</h3>{cases.length === 0 ? <p>还没有处置案例。完成一次任务和两次复测后，这里会形成完整案例。</p> : cases.map((item) => <div className="case-evidence" key={item.id}><strong>{item.case_code} · {item.warning_title} <Tag color={item.complete ? 'green' : 'blue'}>{item.complete ? '已完成' : '进行中'}</Tag></strong><span>{item.context.growth_stage ?? '阶段未记录'} · {item.selected_action_title} · {item.execution.task_status ?? '无任务'}</span><small>选择原因：{item.selection_reason}；30/60 分钟复测：{item.observations.length}/2；执行反馈：{item.execution.feedback_notes.join('；') || '待补充'}</small></div>)}</div>
    <Modal title={`选择方案：${chosen?.title ?? ''}`} open={Boolean(chosen)} onCancel={() => setChosen(null)} onOk={() => void confirmSelection()} confirmLoading={busy} okText="人工确认并创建任务"><p>请记录为什么选择该方案。系统不会控制设备。</p><Input.TextArea value={reason} onChange={(event) => setReason(event.target.value)} rows={3} maxLength={1000} placeholder="例如：现场顶窗可用，风机待检修" /></Modal>
    <Modal title={`${observationOffset ?? ''} 分钟复测`} open={observationOffset !== null} onCancel={() => setObservationOffset(null)} onOk={() => void confirmObservation()} confirmLoading={busy} okText="保存复测"><Space direction="vertical" style={{ width: '100%' }}><Input value={manualStatus} onChange={(event) => setManualStatus(event.target.value)} placeholder="现场观察，例如叶面结露减少" maxLength={80} /><Select style={{ width: '100%' }} value={riskResolved === null ? 'unknown' : riskResolved ? 'yes' : 'no'} onChange={(value) => setRiskResolved(value === 'unknown' ? null : value === 'yes')} options={[{ value: 'unknown', label: '风险是否解除：待确认' }, { value: 'yes', label: '现场确认已解除' }, { value: 'no', label: '现场确认未解除' }]} /><Input.TextArea value={notes} onChange={(event) => setNotes(event.target.value)} rows={3} placeholder="补充说明" maxLength={2000} /></Space></Modal>
  </section>
}
