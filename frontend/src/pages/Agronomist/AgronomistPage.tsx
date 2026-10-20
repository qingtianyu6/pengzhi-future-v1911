import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { App, Alert, Button, Card, Empty, Form, Input, InputNumber, Modal, Select, Skeleton, Space, Table, Tabs, Tag, Timeline } from 'antd'
import { ArrowRightOutlined, ExperimentOutlined, ExportOutlined, PlusOutlined, ReloadOutlined, RobotOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { actOnResearchRecord, addCropObservation, compareScenarios, createAgronomyGoal, createResearchStudy, getGrowthArchive, getResearchWorkspace } from '../../api/agronomistApi'
import { getApiErrorMessage } from '../../api/client'
import { isGuestMode } from '../../api/guestMode'
import type { Comparison, GrowthArchive, ResearchRecord, ResearchWorkspace } from '../../types/agronomist'
import './agronomist.css'

const labels: Record<string, string> = { draft: '草稿', running: '进行中', completed: '已完成', active: '已启用', disabled: '已停用', archived: '已归档', pending: '待执行', in_progress: '执行中', cancelled: '已取消', routine: '日常观察', before: '处理前', after: '处理后', control: '对照区', observation: '作物观察', warning: '预警', task: '农事任务', scenario: '方案比较', study: '生产研究', skill: '农事技能', goal: '目标计划' }
const metricLabels: Record<string, string> = { plant_height_cm: '株高（cm）', flower_count: '花朵数', fruit_count: '果实数', harvest_kg: '采收重量（kg）', leaf_wetness_pct: '叶面湿润比例（%）', temperature: '空气温度', air_humidity: '空气湿度', soil_moisture: '土壤湿度' }
const date = (value: string) => new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
const options = (records: ResearchRecord[], kind: string) => records.filter(r => r.kind === kind && r.status !== 'archived').map(r => ({ value: r.id, label: r.title }))
type Step = { title: string; action_type: string; description: string; depends_on: number[] }
type ObservationValues = { note: string; zone: string; phase: string; observed_at: string; study_id?: number; metric?: string; value?: number }

function MiniChart({ series, unit }: { series: { name: string; values: number[]; color: string }[]; unit: string }) {
  const values = series.flatMap(s => s.values).filter(Number.isFinite)
  if (!values.length) return <Empty description="暂无趋势数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
  const min = Math.floor(Math.min(...values)-2), max = Math.ceil(Math.max(...values)+2)
  const y = (v: number) => 146-(v-min)/(max-min)*116
  return <div className="ag-chart"><svg viewBox="0 0 600 180" role="img" aria-label={`${unit}趋势比较`}>
    {[0, 1, 2, 3].map(i => <g key={i}><line x1="45" x2="584" y1={30+i*38.7} y2={30+i*38.7} stroke="#e5eae3" strokeDasharray="4 5" /><text x="4" y={34+i*38.7} fill="#84958a" fontSize="11">{Math.round(max-(max-min)*i/3)}{unit}</text></g>)}
    {series.map(s => <polyline key={s.name} fill="none" stroke={s.color} strokeWidth="2.6" strokeLinejoin="round" points={s.values.map((v, i) => `${45+i*535/Math.max(1, s.values.length-1)},${y(v)}`).join(' ')} />)}
    <text x="45" y="174" fontSize="11" fill="#84958a">起点</text><text x="555" y="174" fontSize="11" fill="#84958a">末点</text>
  </svg><div className="ag-legend">{series.map(s => <span key={s.name}><i style={{ background: s.color }} />{s.name}</span>)}</div></div>
}

export default function AgronomistPage() {
  const [params] = useSearchParams()
  const gid = Number(params.get('greenhouse_id'))
  return <App>{gid ? <ResearchWorkbench key={`${gid}-${params.get('batch_id') || 'current'}`} greenhouseId={gid} /> : <Card><Empty description="请先在顶部选择大棚，或在数据与管理中创建大棚" /></Card>}</App>
}

function ResearchWorkbench({ greenhouseId }: { greenhouseId: number }) {
  const { message } = App.useApp(), navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') || 'archive'
  const batchId = Number(params.get('batch_id')) || undefined
  const context = useMemo(() => ({ greenhouse_id: greenhouseId, crop_batch_id: batchId }), [greenhouseId, batchId])
  const [archive, setArchive] = useState<GrowthArchive | null>(null)
  const [workspace, setWorkspace] = useState<ResearchWorkspace>({ records: [], tasks: [] })
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [refreshing, setRefreshing] = useState(false)
  const [duration, setDuration] = useState(30), [intensity, setIntensity] = useState(30)
  const [detail, setDetail] = useState<ResearchRecord | null>(null)
  const [observationOpen, setObservationOpen] = useState(false)
  const [observationForm] = Form.useForm<ObservationValues>(), [studyForm] = Form.useForm(), [goalForm] = Form.useForm()
  const [observationStudy, setObservationStudy] = useState<number | undefined>()
  const generation = useRef(0)
  const invalidate = useCallback(() => { generation.current++ }, [])
  const guest = isGuestMode()
  const refresh = useCallback(async () => {
    const request = ++generation.current
    setRefreshing(true)
    try {
      const [a, w] = await Promise.all([getGrowthArchive(context), getResearchWorkspace(context)])
      if (request !== generation.current) return
      setArchive(a); setWorkspace(w); setError('')
    } catch (e) { if (request === generation.current) setError(getApiErrorMessage(e)) }
    finally { if (request === generation.current) setRefreshing(false) }
  }, [context])
  useEffect(() => {
    setArchive(null); setWorkspace({ records: [], tasks: [] }); setDetail(null)
    studyForm.resetFields(); goalForm.resetFields(); observationForm.resetFields(); setObservationOpen(false)
    void refresh()
    return invalidate
  }, [refresh, studyForm, goalForm, observationForm, invalidate])
  useEffect(() => {
    const update = () => { if (!document.hidden && !busy) void refresh() }
    window.addEventListener('focus', update)
    const timer = window.setInterval(update, 30000)
    return () => { window.removeEventListener('focus', update); window.clearInterval(timer) }
  }, [refresh, busy])
  const switchTab = (next: string) => setParams(previous => { const p = new URLSearchParams(previous); p.set('tab', next); return p })
  const operation = async (fn: () => Promise<unknown>, success: string, next?: string) => {
    setBusy(true)
    try { await fn(); message.success(success); await refresh(); if (next) switchTab(next) }
    catch (e) { message.error(getApiErrorMessage(e)) }
    finally { setBusy(false) }
  }
  const action = (r: ResearchRecord, name: string) => operation(() => actOnResearchRecord(r.id, r.version, name), name === 'execute' ? '任务草稿已生成，可前往农事执行' : name === 'derive_skill' ? '农事技能草稿已保存' : '记录已更新', name === 'derive_skill' ? 'skills' : undefined)
  const aiGoal = async () => {
    let values
    try { values = await goalForm.validateFields() } catch { return }
    void operation(() => createAgronomyGoal({ ...context, ...values, use_ai: true }), 'AI 定制计划已保存')
  }
  const records = workspace.records
  const byKind = (kind: string) => records.filter(r => r.kind === kind && r.status !== 'archived')
  const scenarios = byKind('scenario'), studies = byKind('study'), skills = byKind('skill'), goals = byKind('goal')
  const current = scenarios[0]
  const openObservation = (studyId?: number) => {
    setObservationStudy(studyId)
    observationForm.resetFields()
    const local = new Date(Date.now()-new Date().getTimezoneOffset()*60000).toISOString().slice(0, 16)
    observationForm.setFieldsValue({ study_id: studyId, phase: studyId ? 'before' : 'routine', zone: '全棚', observed_at: local })
    setObservationOpen(true)
  }
  const saveObservation = async (values: ObservationValues) => {
    await addCropObservation({ ...context, study_id: values.study_id, note: values.note, phase: values.phase, zone: values.zone,
      observed_at: new Date(values.observed_at).toISOString(), metrics: values.metric && values.value !== undefined ? { [values.metric]: values.value } : {} })
    setObservationOpen(false)
  }
  const exportRecords = () => {
    const blob = new Blob([JSON.stringify({ exported_at: new Date().toISOString(), mode: guest ? 'guest-demo' : 'live', archive, ...workspace }, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob), link = document.createElement('a')
    link.href = url; link.download = `棚智未来_农艺档案_${greenhouseId}.json`; link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  const statusTag = (r: ResearchRecord) => <Tag color={['completed', 'active'].includes(r.status) ? 'green' : r.status === 'running' ? 'blue' : 'default'}>{labels[r.status] || r.status} · V{r.version}</Tag>
  const recordCards = (kind: 'study' | 'skill' | 'goal') => {
    const list = byKind(kind)
    return list.length ? <div className="ag-record-list">{list.map(r => <Card key={r.id} className="ag-record">
      <div className="ag-record-head"><div><span className="ag-eyebrow">{labels[kind]} / {date(r.updated_at)}</span><h3>{r.title}</h3></div>{statusTag(r)}</div>
      {kind === 'study' && <><p>{r.payload.hypothesis}</p>{r.payload.conclusion ? <ComparisonTable rows={r.payload.conclusion.comparisons} /> : <p className="ag-muted">{r.status === 'running' ? '研究进行中，添加同一区域的处理前后观察后，可整理结果。' : '启动研究后即可关联作物观察。'}</p>}</>}
      {kind === 'skill' && <><p>{r.payload.applicability}</p><p className="ag-muted">{r.payload.validation}</p><div className="ag-chips">{(r.payload.steps || []).map((step, i) => <span key={i}>{i+1}. {typeof step === 'string' ? step : step.title}</span>)}</div></>}
      {kind === 'goal' && <><div className="ag-goal-steps">{(r.payload.steps as Step[] || []).map((step, i) => {
        const taskId = r.payload.task_ids?.[i], task = workspace.tasks.find(t => t.id === taskId)
        return <div key={i}><b>{String(i+1).padStart(2, '0')}</b><strong>{step.title}</strong><span>{task ? labels[task.status] || task.status : '待下发'}</span>{taskId && <Button type="link" size="small" onClick={() => navigate(`/platform/production?greenhouse_id=${greenhouseId}&tab=tasks&task_id=${taskId}`)}>查看任务</Button>}</div>
      })}</div><div className="ag-chips">{Object.entries(r.payload.links || {}).map(([kind, linked]) => <button type="button" key={kind} onClick={() => setDetail(linked)}>{labels[kind]}：{linked.title}</button>)}</div><p className="ag-muted">{r.payload.planner}</p></>}
      <Space wrap><Button onClick={() => setDetail(r)}>查看详情</Button>
        {kind === 'study' && r.status === 'draft' && <Button type="primary" loading={busy} onClick={() => void action(r, 'start')}>启动研究</Button>}
        {kind === 'study' && r.status === 'running' && <><Button disabled={busy} onClick={() => openObservation(r.id)}>添加关联观察</Button><Button loading={busy} onClick={() => void action(r, 'complete')}>整理研究结果</Button></>}
        {kind === 'study' && <Button disabled={busy} onClick={() => void action(r, 'derive_skill')}>沉淀为技能</Button>}
        {kind === 'skill' && <Button type={r.status === 'active' ? 'default' : 'primary'} loading={busy} onClick={() => void action(r, r.status === 'active' ? 'disable' : 'activate')}>{r.status === 'active' ? '停用技能' : '启用流程'}</Button>}
        {kind === 'skill' && r.status === 'active' && <Button onClick={() => { goalForm.setFieldValue('skill_id', r.id); switchTab('goals') }}>用于目标编排</Button>}
        {kind === 'goal' && r.status === 'draft' && <Button type="primary" loading={busy} onClick={() => void action(r, 'execute')}>生成农事任务</Button>}
        {kind === 'goal' && r.status === 'running' && <Button loading={busy} onClick={() => void action(r, 'complete')}>完成目标</Button>}
        {r.status !== 'running' && <Button type="text" disabled={busy} onClick={() => void action(r, 'archive')}>归档</Button>}
      </Space>
    </Card>)}</div> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={kind === 'skill' ? '从生产研究沉淀第一项农事技能' : kind === 'study' ? '创建第一个研究问题，开始积累本棚经验' : '输入生产目标，生成可跟踪的分步计划'} />
  }
  const scenarioSelectors = <Form.Item name="scenario_id" label="关联方案比较"><Select allowClear placeholder="可选，保存所选方案的版本快照" options={options(records, 'scenario')} /></Form.Item>
  const tabs = [
    { key: 'archive', label: '生长档案', children: <>
      <div className="ag-stats">{[{ label: '批次生长天数', value: archive?.batch?.growth_day ?? '—', suffix: '天' }, { label: '有效环境采样', value: archive?.sample_count ?? 0, suffix: '条' }, { label: '已记录作物观察', value: archive?.observations.length ?? 0, suffix: '条' }, { label: '待处理预警', value: archive?.open_warnings ?? 0, suffix: '项' }].map(s => <div key={s.label}><span>{s.label}</span><strong>{s.value}<small>{s.suffix}</small></strong></div>)}</div>
      <div className="ag-two-col"><Card className="ag-growth-card"><div className="ag-section-title"><div><span className="ag-eyebrow">GROWTH ARCHIVE</span><h2>{archive?.batch?.variety || '等待建立种植批次'}</h2></div><Tag color="green">{archive?.batch?.growth_stage || '未设置'}</Tag></div>
        <div className="ag-greenhouse-scene" aria-hidden="true"><div className="ag-greenhouse-roof" /><div className="ag-crop-rows">{Array.from({ length: 18 }, (_, i) => <span key={i}>♧</span>)}</div><span className="ag-scene-caption">批次档案 · 环境与作物观察</span></div>
        <div className="ag-batch-info"><span>定植日期 <b>{archive?.batch?.planted_at?.slice(0, 10) || '—'}</b></span><span>最新采样 <b>{archive?.latest ? date(archive.latest.recorded_at) : '暂无'}</b></span><span>采样状态 <b>{archive?.latest ? archive.fresh ? '最近两小时内' : '历史采样' : '等待接入'}</b></span></div>
        <Space wrap><Button type="primary" icon={<PlusOutlined />} disabled={!archive?.batch || busy} onClick={() => openObservation()}>记录作物观察</Button><Button onClick={() => switchTab('scenarios')}>比较管理方案 <ArrowRightOutlined /></Button></Space>
      </Card><Card title="本棚数据概况"><div className="ag-environment">{(['temperature', 'air_humidity', 'soil_moisture'] as const).map(key => <div key={key}><span>{metricLabels[key]}</span><strong>{archive?.latest?.[key] ?? '—'}<small>{key === 'temperature' ? '°C' : '%'}</small></strong><span>窗口均值 {archive?.metrics[key]?.mean ?? '—'}</span></div>)}</div>
        {(archive?.gaps || []).map(gap => <p key={gap} className="ag-gap">{gap}</p>)}<p className="ag-muted">{archive?.window_note}</p></Card></div>
      <div className="ag-two-col"><Card title="环境变化 · 有效空气湿度采样"><MiniChart unit="%" series={[{ name: '空气湿度', color: '#327c62', values: archive?.history.map(r => r.air_humidity).filter((v): v is number => v !== null) || [] }]} /></Card><Card title="生产时间线">{archive?.timeline.length ? <div className="ag-timeline"><Timeline items={archive.timeline.slice(0, 12).map(e => ({ color: e.type === 'warning' ? '#cf9439' : '#3c8064', children: <><span className="ag-eyebrow">{date(e.at)} · {labels[e.type]}</span><p>{e.title}</p><small>{labels[e.detail] || e.detail}</small></> }))} /></div> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="添加观察、任务后，这里会形成生产时间线" />}</Card></div>
      <Card title="作物观察记录"><div className="ag-table-scroll"><Table size="small" rowKey="id" pagination={{ pageSize: 8, hideOnSinglePage: true }} dataSource={archive?.observations} columns={[
        { title: '观察时间', dataIndex: 'observed_at', render: date }, { title: '区域', dataIndex: 'zone' }, { title: '阶段', dataIndex: 'phase', render: (v: string) => labels[v] }, { title: '记录', dataIndex: 'note' },
        { title: '指标', dataIndex: 'metrics', render: (m: Record<string, number>) => Object.entries(m).map(([k, v]) => `${metricLabels[k] || k}：${v}`).join('；') },
      ]} /></div></Card>
    </> },
    { key: 'scenarios', label: '方案推演', children: <>
      <Card><div className="ag-section-title"><div><span className="ag-eyebrow">SCENARIO COMPARISON</span><h2>先比较，再选择管理方案</h2><p className="ag-muted">固定同一条环境采样，比较静态参照、通风和除湿方案。</p></div></div><Space wrap><span>推演时长</span><Select aria-label="推演时长" value={duration} onChange={setDuration} options={[30, 60, 120].map(v => ({ value: v, label: `${v} 分钟` }))} /><span>方案强度</span><InputNumber aria-label="方案强度" value={intensity} min={0} max={100} onChange={v => setIntensity(v ?? 30)} /><Button type="primary" loading={busy} onClick={() => void operation(() => compareScenarios({ ...context, duration_minutes: duration, intensity }), '方案比较已保存')}>生成方案比较</Button></Space></Card>
      {current ? <Card><div className="ag-section-title"><h2>{current.title}</h2><Tag>保存于 {date(current.created_at)}</Tag></div><p className="ag-muted">采样起点：{date(current.payload.baseline!.recorded_at)} · 温度 {current.payload.baseline?.temperature}°C · 湿度 {current.payload.baseline?.humidity}%</p>
        <MiniChart unit="%" series={(current.payload.candidates || []).map((c, i) => ({ name: c.name, color: ['#a7b4a8', '#327c62', '#c69a50'][i], values: [current.payload.baseline!.humidity, ...c.timeline.map(p => p.humidity)] }))} />
        <div className="ag-candidate-grid">{current.payload.candidates?.map(c => <div key={c.name}><strong>{c.name}</strong><span>末点温度 <b>{c.end.temperature}°C</b></span><span>末点湿度 <b>{c.end.humidity}%</b></span></div>)}</div><p className="ag-muted">{current.payload.note}</p><Space wrap><Button type="primary" onClick={() => { goalForm.setFieldValue('scenario_id', current.id); switchTab('goals') }}>加入目标计划</Button><Button onClick={() => { studyForm.setFieldValue('scenario_id', current.id); switchTab('studies') }}>围绕方案开展研究</Button></Space>
      </Card> : <Card><Empty description="生成后可以查看三种方案的对比曲线，结果会保存到当前批次" /></Card>}
      {scenarios.length > 0 && <Card title="历史方案比较"><Space wrap>{scenarios.map(r => <Button key={r.id} onClick={() => setDetail(r)}>{r.title} · {date(r.created_at)}</Button>)}</Space></Card>}
    </> },
    { key: 'studies', label: '生产研究', children: <><Card><span className="ag-eyebrow">PRODUCTION RESEARCH</span><h2>把一个生产问题，变成可追踪的研究</h2><Form form={studyForm} layout="vertical" onFinish={values => void operation(() => createResearchStudy({ ...context, ...values }), '研究草案已保存')}><Form.Item name="question" label="你想弄清什么问题？" rules={[{ required: true, whitespace: true, min: 2, message: '请填写至少两个字的研究问题' }]}><Input maxLength={500} placeholder="例如：清晨叶面潮湿，是否与灌溉和通风时间有关？" /></Form.Item><Form.Item name="hypothesis" label="你的初步解释"><Input.TextArea rows={2} maxLength={2000} placeholder="可选，记录自己的判断；观察过程中可以验证它" /></Form.Item>{scenarioSelectors}<Button type="primary" htmlType="submit" loading={busy}>生成研究草案</Button></Form></Card>{recordCards('study')}</> },
    { key: 'skills', label: '农事技能', children: <><div className="ag-section-intro"><span className="ag-eyebrow">REUSABLE SKILLS</span><h2>让处理经验，成为下一次的工作方法</h2><p>从研究沉淀操作步骤、适用条件和证据。启用流程后，可以在目标编排中复用。</p></div>{recordCards('skill')}</> },
    { key: 'goals', label: '目标编排', children: <><Card><span className="ag-eyebrow">GOAL PLANNING</span><h2>告诉棚小智，你想完成什么</h2><Form form={goalForm} layout="vertical" onFinish={values => void operation(() => createAgronomyGoal({ ...context, ...values }), '目标计划已保存')}><Form.Item name="goal" label="生产目标" rules={[{ required: true, whitespace: true, min: 2, message: '请填写至少两个字的目标' }]}><Input.TextArea maxLength={500} rows={2} placeholder="例如：检查清晨湿度偏高问题，记录处理前后作物状态" /></Form.Item><div className="ag-form-grid">{scenarioSelectors}<Form.Item name="study_id" label="关联生产研究"><Select allowClear placeholder="可选" options={options(records, 'study')} /></Form.Item><Form.Item name="skill_id" label="复用农事技能"><Select allowClear placeholder="可选，选择已启用流程" options={options(records.filter(r => r.status === 'active'), 'skill')} /></Form.Item></div><Space wrap><Button type="primary" htmlType="submit" loading={busy}>生成目标计划</Button><Button icon={<RobotOutlined />} loading={busy} disabled={guest} onClick={() => void aiGoal()}>AI 定制计划</Button></Space><span className="ag-inline-note">结构化编排不调用模型；AI 定制结合本棚数据生成步骤</span></Form></Card>{recordCards('goal')}</> },
  ]
  return <div className="ag-workbench">
    <header className="ag-hero"><div><span className="ag-eyebrow"><ExperimentOutlined /> AGRONOMIST WORKSPACE</span><h1>AI 研究台</h1><p>生长有档案，决策有依据，经验可复用。</p></div><Space wrap><Button icon={<RobotOutlined />} onClick={() => window.dispatchEvent(new Event('pengzhi:open-assistant'))}>与棚小智交流</Button><Button icon={<ExportOutlined />} onClick={exportRecords} disabled={!archive}>导出档案</Button><Button aria-label="刷新研究台" icon={<ReloadOutlined />} loading={refreshing} onClick={() => void refresh()} /></Space></header>
    {guest && <Alert type="info" showIcon message="游客体验 · 数据与推演均为示例，新增记录保存在当前浏览器会话，刷新可以继续。" />}
    {error && <Alert type="error" showIcon message={error} action={<Button size="small" onClick={() => void refresh()}>重试</Button>} />}
    <div className="ag-context"><span><i />{archive?.greenhouse.name || '正在读取大棚'}</span><Select aria-label="研究批次" placeholder="当前批次" value={archive?.batch?.id} options={archive?.batches.map(b => ({ value: b.id, label: `${b.batch_code} · ${labels[b.status] || (b.status === 'growing' ? '生长中' : b.status)}` }))} onChange={value => { setParams(previous => { const p = new URLSearchParams(previous); p.set('batch_id', String(value)); return p }) }} /><span className="ag-muted">本批次 {studies.length} 项研究 · {skills.length} 项技能 · {goals.length} 个目标</span></div>
    {!archive && !error ? <Skeleton active paragraph={{ rows: 12 }} /> : <Tabs activeKey={tabs.some(t => t.key === tab) ? tab : 'archive'} onChange={switchTab} items={tabs} />}
    <Modal title="记录作物观察" open={observationOpen} onCancel={() => setObservationOpen(false)} footer={null} destroyOnHidden>
      <Form form={observationForm} layout="vertical" onFinish={values => void operation(() => saveObservation(values), '作物观察已保存')}>
        <Form.Item name="study_id" label="关联研究"><Select allowClear disabled={!!observationStudy} options={options(studies.filter(r => r.status === 'running'), 'study')} placeholder="日常观察可不关联" /></Form.Item>
        <div className="ag-form-grid"><Form.Item name="observed_at" label="观察时间" rules={[{ required: true }]}><Input type="datetime-local" /></Form.Item><Form.Item name="zone" label="观察区域" rules={[{ required: true, whitespace: true }]}><Input maxLength={80} /></Form.Item></div>
        <Form.Item name="phase" label="观察阶段"><Select options={['routine', 'before', 'after', 'control'].map(value => ({ value, label: labels[value] }))} /></Form.Item>
        <Form.Item name="note" label="观察内容" rules={[{ required: true, whitespace: true }]}><Input.TextArea rows={3} maxLength={3000} placeholder="描述叶片、花果、生长和现场操作情况" /></Form.Item>
        <div className="ag-form-grid"><Form.Item name="metric" label="数值指标"><Select allowClear placeholder="可选" options={Object.entries(metricLabels).filter(([key]) => !['temperature', 'air_humidity', 'soil_moisture'].includes(key)).map(([value, label]) => ({ value, label }))} /></Form.Item><Form.Item noStyle shouldUpdate={(a, b) => a.metric !== b.metric}>{({ getFieldValue }) => <Form.Item name="value" label="观察数值" rules={[{ required: !!getFieldValue('metric'), message: '请填写所选指标的数值' }]}><InputNumber min={0} max={getFieldValue('metric') === 'leaf_wetness_pct' ? 100 : undefined} style={{ width: '100%' }} /></Form.Item>}</Form.Item></div>
        <Button type="primary" htmlType="submit" loading={busy}>保存观察</Button>
      </Form>
    </Modal>
    <Modal title={detail?.title} open={!!detail} onCancel={() => setDetail(null)} footer={<Button onClick={() => setDetail(null)}>关闭</Button>} width={760}>
      {detail && <div className="ag-detail"><Space wrap>{statusTag(detail)}<Tag>{labels[detail.kind]}</Tag><span>{date(detail.created_at)}</span></Space>
        {detail.payload.hypothesis && <p>初步解释：{detail.payload.hypothesis}</p>}
        {detail.payload.alternatives && <><h3>备选解释</h3><ul>{detail.payload.alternatives.map(s => <li key={s}>{s}</li>)}</ul></>}
        {(detail.payload.protocol || detail.payload.steps) && <><h3>操作步骤</h3><ol>{(detail.payload.protocol || detail.payload.steps || []).map((step, i) => <li key={i}>{typeof step === 'string' ? step : `${step.title}：${step.description}`}</li>)}</ol></>}
        {detail.payload.conclusion && <><h3>观察结果</h3><ComparisonTable rows={detail.payload.conclusion.comparisons} /><p className="ag-muted">{detail.payload.conclusion.interpretation}</p></>}
        {detail.payload.candidates && <><p>采样起点：{detail.payload.baseline && date(detail.payload.baseline.recorded_at)}</p><MiniChart unit="%" series={detail.payload.candidates.map((c, i) => ({ name: c.name, color: ['#a7b4a8', '#327c62', '#c69a50'][i], values: [detail.payload.baseline!.humidity, ...c.timeline.map(p => p.humidity)] }))} /></>}
        {detail.payload.source_snapshot && <p>来源：{detail.payload.source_snapshot.title} · V{detail.payload.source_snapshot.version} · {labels[detail.payload.source_snapshot.status]}</p>}
        <p>{detail.payload.applicability}</p><p>{detail.payload.validation || detail.payload.note}</p>
      </div>}
    </Modal>
  </div>
}

function ComparisonTable({ rows }: { rows: Comparison[] }) {
  return <div className="ag-table-scroll"><Table size="small" pagination={false} rowKey={r => `${r.zone}-${r.metric}`} dataSource={rows} columns={[
    { title: '区域 / 指标', render: (_, r: Comparison) => `${r.zone} · ${metricLabels[r.metric] || r.metric}` }, { title: '处理前均值', dataIndex: 'before' }, { title: '处理后均值', dataIndex: 'after' },
    { title: '变化', dataIndex: 'delta', render: (v: number) => `${v > 0 ? '+' : ''}${Number(v.toFixed(3))}` }, { title: '记录数（前/后）', render: (_, r: Comparison) => `${r.before_n}/${r.after_n}` },
  ]} /></div>
}
