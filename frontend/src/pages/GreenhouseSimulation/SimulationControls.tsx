import { useCallback, useEffect, useRef, useState } from 'react'
import { Alert, Button, Card, Col, Descriptions, Input, InputNumber, Row, Select, Slider, Space, Spin, Statistic, Switch, Table, Tag, Typography, message } from 'antd'
import { ExperimentOutlined, PauseOutlined, PlayCircleOutlined, ReloadOutlined, StopOutlined } from '@ant-design/icons'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
echarts.use([LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])
import { simulationRequest as request, type Actions, type Comparison, type Environment, type Mode, type Scenario, type Snapshot } from '../../api/greenhouseSimulationApi'
import { getApiErrorMessage } from '../../api/client'
import { isGuestMode } from '../../api/guestMode'
import './simulation.css'

const metrics: { key: keyof Environment; label: string; unit: string; min: number; max: number; step: number }[] = [
  { key: 'air_temperature', label: '空气温度', unit: '℃', min: -10, max: 60, step: .1 },
  { key: 'air_humidity', label: '空气湿度', unit: '%', min: 0, max: 100, step: .1 },
  { key: 'soil_temperature', label: '土壤温度', unit: '℃', min: -10, max: 60, step: .1 },
  { key: 'soil_moisture', label: '土壤含水率', unit: '%', min: 0, max: 100, step: .1 },
  { key: 'light_lux', label: '光照强度', unit: 'lux', min: 0, max: 100000, step: 100 },
]
const devices: { key: keyof Actions; label: string }[] = [{ key: 'fan', label: '通风风扇' }, { key: 'pump', label: '灌溉水泵' }, { key: 'lamp', label: '补光灯' }, { key: 'led', label: '指示灯' }]
const modeNames = { manual: '手动接管', threshold: '基础自动 · 规则控制', predictive: '预测优化 · 候选动作搜索' }
const statusNames: Record<string, string> = { planned: '计划执行', sent: '命令已发送', mock_confirmed: '虚拟 GPIO 已确认', gpio_confirmed: 'STM32 GPIO 已确认', failed: '发送失败 / 状态未知', expired: '租约结束 / 输出待查询' }
const defaults: Environment = { air_temperature: 26, air_humidity: 65, soil_temperature: 24, soil_moisture: 55, light_lux: 16000 }

function Trend({ rows }: { rows: (Environment & { time: number })[] }) {
  const element = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!element.current) return
    const chart = echarts.init(element.current)
    chart.setOption({ tooltip: { trigger: 'axis' }, legend: { data: metrics.map(m => m.label), top: 0 },
      grid: { left: 55, right: 65, top: 60, bottom: 40 }, xAxis: { type: 'category', name: '秒', data: rows.map(r => r.time) },
      yAxis: [{ type: 'value', name: '℃ / %' }, { type: 'value', name: 'lux' }],
      series: metrics.map(m => ({ name: m.label, type: 'line', showSymbol: false, smooth: true, yAxisIndex: m.key === 'light_lux' ? 1 : 0, data: rows.map(r => r[m.key]) })) })
    const observer = new ResizeObserver(() => chart.resize()); observer.observe(element.current)
    return () => { observer.disconnect(); chart.dispose() }
  }, [rows])
  return <div className="simulation-trend" ref={element} aria-label="模拟环境变化曲线" />
}

export default function GreenhouseSimulationPage() {
  const [state, setState] = useState<Snapshot | null>(null)
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [draft, setDraft] = useState<Environment>(defaults)
  const [target, setTarget] = useState<Environment>(defaults)
  const [manual, setManual] = useState<Actions>({ fan: false, pump: false, lamp: false, led: false })
  const [mode, setMode] = useState<Mode>('threshold')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [demo, setDemo] = useState(true)
  const [sceneName, setSceneName] = useState('我的演示场景')
  const [seed, setSeed] = useState(42)
  const [steps, setSteps] = useState(120)
  const [comparison, setComparison] = useState<Comparison | null>(null)
  const [msg, context] = message.useMessage()
  const accept = useCallback((s: Snapshot, sync = false) => {
    setState(s); setError('')
    if (sync) { setDraft(s.environment); setTarget(s.target); setMode(s.mode); setManual(s.planned) }
  }, [])
  useEffect(() => {
    let alive = true
    let loading = false
    const load = async (initial = false) => {
      if (loading) return
      loading = true
      try {
        const s = await request<Snapshot>('/state')
        if (alive) accept(s, initial)
        if (initial) { const list = await request<Scenario[]>('/scenarios'); if (alive) setScenarios(list) }
      } catch (e) { if (alive) setError(getApiErrorMessage(e)) }
      finally { loading = false }
    }
    void load(true)
    const timer = window.setInterval(() => void load(), 2000)
    return () => { alive = false; window.clearInterval(timer) }
  }, [accept])
  async function act(fn: () => Promise<void>) {
    if (busy) return
    setBusy(true)
    try { await fn() } catch (e) { setError(getApiErrorMessage(e)) } finally { setBusy(false) }
  }
  async function operation(action: string) { accept(await request<Snapshot>('/operation', 'POST', { action }), action === 'reset') }
  async function apply(start: boolean) {
    accept(await request<Snapshot>('/state', 'PUT', { environment: draft, target, mode, ...(mode === 'manual' ? { manual } : {}) }))
    if (start) await operation('start')
    else { await operation('evaluate'); msg.success('后端已重新计算并下发；单次指令租约为4秒') }
  }
  const chartRows = state?.history ?? []
  return <div className="greenhouse-simulation">
    {context}
    <div className="simulation-hero"><div><Tag color="green">棚智自治</Tag><Tag>SIMULATION INPUT</Tag>
      <Typography.Title level={2}>AI 温室模拟调控</Typography.Title>
      <Typography.Paragraph>设定环境，观察决策，追踪每一条设备指令。</Typography.Paragraph></div>
      <Space direction="vertical"><Tag color={state?.device.mode === 'real' ? 'orange' : 'cyan'}>{state?.device.mode === 'real' ? '真实串口模式' : '虚拟设备模式'}</Tag>
        <Space><span>演示引导</span><Switch checked={demo} onChange={setDemo} /></Space></Space></div>
    <Alert showIcon type="info" message="全部环境参数为模拟输入；示例目标仅用于演示，不是农业生产标准。GPIO 回执不代表实体设备已运转。" />
    {isGuestMode() && <Alert type="success" message="游客演示使用独立虚拟会话，通过真实后端计算；无法访问实体串口。" />}
    {demo && <Card size="small"><Space wrap><Tag>01 选择异常场景</Tag>→<Tag>02 调整参数与目标</Tag>→<Tag>03 启动自动调控</Tag>→<Tag>04 查看候选动作与虚拟反馈</Tag>→<Tag>05 观察变化 / 暂停 / 重置</Tag></Space></Card>}
    {(error || state?.error) && <Alert type="error" showIcon message={error || state?.error} />}
    {!state && !error && <Spin />}
    <Row gutter={[16,16]}>{metrics.map(m => <Col xs={12} lg={m.key === 'light_lux' ? 8 : 4} key={m.key}>
      <Card size="small"><Statistic title={m.label + ' · 模拟'} value={state?.environment[m.key] ?? 0} precision={m.key === 'light_lux' ? 0 : 1} suffix={m.unit} /></Card></Col>)}</Row>
    <Row gutter={[16,16]}><Col xs={24} xl={11}>
      <Card title="模拟环境与调控目标" extra={<Tag>后端统一校验</Tag>}>
        <Select aria-label="模拟场景" placeholder="选择模拟场景" value={state?.scenario_id} style={{ width: '100%', marginBottom: 20 }} disabled={busy}
          options={[...scenarios.map(s => ({ value: s.id, label: s.name })), { value: 'custom', label: '自定义环境' }]}
          onChange={id => void act(async () => { accept(await request<Snapshot>('/state','PUT',{ scenario_id: id }),true) })} />
        <div className="simulation-parameter-head"><span>模拟输入</span><span>环境目标 · 提交后生效</span></div>
        {metrics.map(m => <div className="simulation-parameter" key={m.key}>
          <label>{m.label} <small>{m.unit}</small></label><div className="simulation-inputs">
            <InputNumber aria-label={m.label + '输入'} min={m.min} max={m.max} step={m.step} value={draft[m.key]} onChange={v => v !== null && setDraft(d => ({ ...d, [m.key]: v }))} />
            <InputNumber aria-label={m.label + '目标'} min={m.min} max={m.max} step={m.step} value={target[m.key]} onChange={v => v !== null && setTarget(d => ({ ...d, [m.key]: v }))} /></div>
          <Slider aria-label={m.label + '滑块'} min={m.min} max={m.max} step={m.step} value={draft[m.key]} onChange={v => setDraft(d => ({ ...d, [m.key]: v }))} /></div>)}
        <Space.Compact style={{ width:'100%', marginBottom:16 }}><Input aria-label="自定义场景名称" value={sceneName} maxLength={60} onChange={e => setSceneName(e.target.value)} />
          <Button disabled={busy || !sceneName.trim()} onClick={() => void act(async () => {
            const saved = await request<Scenario>('/scenarios','POST',{ name:sceneName,environment:draft })
            setScenarios(await request<Scenario[]>('/scenarios'))
            accept(await request<Snapshot>('/state','PUT',{ scenario_id:saved.id }),true)
            msg.success('自定义场景已保存')
          })}>保存自定义场景</Button></Space.Compact>
        <Select aria-label="控制模式" value={mode} style={{ width: '100%', marginBottom: 16 }} onChange={setMode}
          options={Object.entries(modeNames).map(([value,label]) => ({ value,label }))} />
        {mode === 'manual' && <Space wrap className="simulation-manual">{devices.map(d => <Space key={d.key}>{d.label}<Switch aria-label={d.label + '手动开关'} checked={manual[d.key]} onChange={v => setManual(a => ({ ...a, [d.key]: v }))} /></Space>)}</Space>}
        <Space wrap><Button type="primary" icon={<PlayCircleOutlined />} disabled={busy || state?.emergency} onClick={() => void act(() => apply(true))}>启动{mode === 'manual' ? '手动控制' : '自动调控'}</Button>
          <Button disabled={busy || state?.emergency} onClick={() => void act(() => apply(false))}>提交并单次计算</Button>
          <Button aria-label="暂停" icon={<PauseOutlined />} disabled={busy} onClick={() => void act(() => operation('pause'))}>暂停</Button>
          <Button aria-label="重置" icon={<ReloadOutlined />} disabled={busy} onClick={() => void act(() => operation('reset'))}>重置</Button>
          <Button aria-label="紧急停止" danger icon={<StopOutlined />} onClick={() => void operation('estop').catch(e => setError(getApiErrorMessage(e)))}>紧急停止</Button></Space>
      </Card></Col><Col xs={24} xl={13}>
      <Card title="控制链路与执行证据" extra={<Tag color={state?.running ? 'green' : 'default'}>{state?.running ? '运行中' : state?.emergency ? '急停锁定' : '已暂停'}</Tag>}>
        <Descriptions size="small" column={{ xs: 1, md: 2 }} items={[
          { key:'mode',label:'当前模式',children:state && modeNames[state.mode] },
          { key:'clock',label:'模拟时间',children:`${state?.simulation_time ?? 0} 秒` },
          { key:'link',label:'连接',children:state?.device.connected ? '协议已连接' : '未连接 / 待确认' },
          { key:'status',label:'命令状态',children:statusNames[state?.device.status ?? 'planned'] },
          { key:'seq',label:'最近回执编号',children:state?.device.last_ack?.sequence ?? '—' },
          { key:'physical',label:'实体运行验证',children:<Tag>HARDWARE_PENDING</Tag> },
        ]} />
        <Typography.Paragraph type="secondary">当前已提交目标：{metrics.map(m => `${m.label} ${state?.target[m.key] ?? '—'}${m.unit}`).join(' / ')}</Typography.Paragraph>
        <Table size="small" pagination={false} rowKey="key" dataSource={devices} columns={[
          { title:'设备',dataIndex:'label' },
          { title:'控制器计划',render:(_,d) => state?.planned[d.key] ? '开启' : '关闭' },
          { title:state?.device.mode === 'real' ? 'GPIO 回执' : '虚拟 GPIO 回执',render:(_,d) => state?.device.confirmed ? (state.device.confirmed[d.key] ? '设置为开' : '设置为关') : '未知' },
        ]} />
        <Typography.Paragraph className="simulation-reason">{state?.decision?.reason ?? '等待提交环境并启动控制。'}</Typography.Paragraph>
        {state?.decision?.constraints.map(c => <Tag key={c}>{c}</Tag>)}
        <Typography.Paragraph type="secondary">控制每2秒评估；页面离开15秒自动暂停。急停后需要重置。无加热、除湿或遮阳设备时，部分目标可能无法达到。</Typography.Paragraph>
        {state?.device.mode === 'mock' && <Space wrap><span>故障注入</span>{[{value:'disconnect',label:'模拟断连'},{value:'timeout',label:'模拟超时'},{value:'none',label:'恢复连接'}].map(f => <Button key={f.value} disabled={busy} onClick={() => void act(async () => accept(await request<Snapshot>('/fault','POST',{fault:f.value}))) }>{f.label}</Button>)}</Space>}
        {state?.device.oled && <pre className="simulation-oled">虚拟 OLED · SIM INPUT{'\n'}{metrics.map(m => `${m.label}: ${state.device.oled?.[m.key]} ${m.unit}`).join('\n')}</pre>}
      </Card>
      <Card title="模拟环境变化曲线"><Trend rows={chartRows} /></Card>
    </Col></Row>
    <Card title="最近一次可行候选动作" extra={<Tag>每次重新计算</Tag>}><Table size="small" rowKey={r => JSON.stringify(r.action)} pagination={false} dataSource={state?.decision?.candidates ?? []} columns={[
      { title:'风扇', render:(_,r) => r.action.fan ? '开' : '关' },{ title:'水泵',render:(_,r) => r.action.pump ? '开' : '关' },{ title:'补光灯',render:(_,r) => r.action.lamp ? '开' : '关' },
      { title:'预测总代价（越小越好）',dataIndex:'score',render:(v: number | null) => v === null ? '规则/手动不计算代价' : v.toFixed(5) },
    ]} /></Card>
    <Card title="控制策略对比实验" extra={<ExperimentOutlined />}>
      <Alert type="warning" message="软件仿真对比结果，非真实温室实验。相同初值、目标和扰动序列；不保证预测优化优于规则控制。" />
      <Space wrap className="simulation-experiment"><span>随机种子</span><InputNumber aria-label="随机种子" min={0} max={2147483647} value={seed} onChange={v => v !== null && setSeed(v)} />
        <span>步数（每步2秒）</span><InputNumber aria-label="实验步数" min={10} max={600} value={steps} onChange={v => v !== null && setSteps(v)} />
        <Button loading={busy} onClick={() => void act(async () => setComparison(await request<Comparison>('/experiment','POST',{initial:draft,target,seed,steps})))}>运行对比实验</Button></Space>
      <Table size="small" rowKey="mode" pagination={false} dataSource={comparison?.results ?? []} scroll={{x:800}} columns={[
        {title:'策略',dataIndex:'mode',render:(m:Mode) => modeNames[m]},
        {title:'平均归一化目标偏差',dataIndex:'mean_target_deviation',render:(v:number) => v.toFixed(4)},
        {title:'控制步数',dataIndex:'control_steps'}, {title:'开启时长 / 秒',render:(_,r) => `风扇${r.on_seconds.fan} / 泵${r.on_seconds.pump} / 灯${r.on_seconds.lamp}`},
        {title:'启停次数',dataIndex:'switches'}, {title:'能耗代理（非kWh）',dataIndex:'energy_proxy',render:(v:number) => v.toFixed(3)}, {title:'灌溉秒数',dataIndex:'irrigation_seconds'},
      ]} />
      {comparison && <Typography.Text type="secondary">已运行：seed={comparison.parameters.seed}，steps={comparison.parameters.steps}。这是当前模型与参数下的结果，不构成实棚性能结论。</Typography.Text>}
    </Card>
    <Row gutter={[16,16]}><Col xs={24} xl={12}><Card title="设备执行与决策日志"><Table size="small" rowKey={(_,i) => String(i)} dataSource={state?.events ?? []} pagination={{pageSize:6}} columns={[
      {title:'时间',dataIndex:'at',render:(v:number) => new Date(v*1000).toLocaleTimeString()}, {title:'事件',dataIndex:'event'}, {title:'状态',dataIndex:'command_status',render:(v:string) => statusNames[v] ?? v}, {title:'异常',dataIndex:'error'},
    ]} /></Card></Col><Col xs={24} xl={12}><Card title="串口协议收发日志"><div className="simulation-wire">{state?.wire_logs.slice(-24).map((l,i) => <div key={i}><Tag>{l.direction}</Tag><code>{l.frame}</code></div>)}</div></Card></Col></Row>
  </div>
}
