import { useCallback, useEffect, useRef, useState } from 'react'
import { Alert, Button, Drawer, Empty, Skeleton, Tooltip, message } from 'antd'
import { ArrowRightOutlined, CheckOutlined, ClockCircleOutlined, ControlOutlined, ExperimentOutlined, FileTextOutlined, BulbOutlined, PauseCircleOutlined, PlayCircleOutlined, PoweroffOutlined, SlidersOutlined, SwapOutlined } from '@ant-design/icons'
import { useLocation, useNavigate } from 'react-router-dom'
import { simulationRequest as request, type Actions, type Snapshot } from '../../api/greenhouseSimulationApi'
import { getApiErrorMessage } from '../../api/client'
import { canOperate } from '../../utils/permissions'
import { workspaceHref } from '../../layouts/workspaceNavigation'
import SimulationControls from './SimulationControls'
import './autonomy-design.css'

const deviceNames: { key: keyof Actions; name: string; icon: typeof ControlOutlined }[] = [
  { key:'fan', name:'通风风扇', icon:ControlOutlined }, { key:'pump', name:'灌溉泵', icon:ExperimentOutlined }, { key:'lamp', name:'补光灯', icon:BulbOutlined },
]
const eventNames: Record<string,string> = { created:'建立调控会话', input_updated:'更新环境与调控目标', decision:'分析环境并计算控制方案', paused:'暂停自动托管', reset:'重置调控会话', emergency_stop:'触发紧急停止', fault_changed:'更新虚拟设备连接状态' }
const commandNames: Record<string,string> = { planned:'等待下发指令', sent:'指令已发送', mock_confirmed:'收到虚拟设备回执', gpio_confirmed:'收到 GPIO 回执', expired:'指令租约结束', failed:'指令未确认' }
function formatTime(at: number) { return new Date(at * 1000).toLocaleTimeString('zh-CN', { hour12:false }) }

function HumidityTrend({ state }: { state: Snapshot }) {
  const element = useRef<SVGSVGElement>(null), [width, setWidth] = useState(760)
  useEffect(() => {
    if (!element.current) return
    const observer = new ResizeObserver(entries => setWidth(Math.max(240, Math.round(entries[0].contentRect.width))))
    observer.observe(element.current)
    return () => observer.disconnect()
  }, [])
  const rows = state.history, height = 112, end = width - 20, currentX = 42 + (end - 42) * .79
  const points = rows.map((row, i) => [42 + (i / Math.max(1, rows.length - 1)) * (currentX - 42), 90 - row.air_humidity * .72])
  const line = points.map((p,i) => (i ? 'L' : 'M') + p.join(',')).join(' ')
  const ty = 90 - state.target.air_humidity * .72
  return <svg ref={element} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label="全棚模拟湿度历史与目标线">
    <defs><linearGradient id="humidity-fill" x1="0" y1="0" x2="0" y2="1"><stop stopColor="#b9d7bb" stopOpacity=".65"/><stop offset="1" stopColor="#e7efe4" stopOpacity=".1"/></linearGradient></defs>
    {[40,60,80,100].map(v => <g key={v}><line x1="42" y1={90-v*.72} x2={end} y2={90-v*.72} stroke="#e2e8de"/><text x="28" y={94-v*.72} textAnchor="end">{v}%</text></g>)}
    {[0,1,2,3,4,5].map(i => <line key={i} x1={42+(end-42)*i/5} y1="18" x2={42+(end-42)*i/5} y2="90" stroke="#e8ece4"/>)}
    <line x1="42" x2={end} y1={ty} y2={ty} stroke="#74aa82" strokeDasharray="6 5"/>
    <text x={end} y={ty-6} textAnchor="end" fill="#51946a">目标 {state.target.air_humidity}%</text>
    {!!points.length && <><path d={line + ` L${points[points.length-1][0]},90 L42,90 Z`} fill="url(#humidity-fill)"/><path d={line} fill="none" stroke="#006147" strokeWidth="2"/><circle cx={points[points.length-1][0]} cy={points[points.length-1][1]} r="4" fill="#008c5c"/></>}
    {!rows.length && <text x={(end+42)/2} y="54" textAnchor="middle">启动托管后记录模拟变化</text>}
    <line x1="42" y1="90" x2={end} y2="90" stroke="#bbc9c2"/>
    <text x="42" y="108">0 秒</text><text x={currentX} y="108" textAnchor="middle">当前 · {state.simulation_time} 秒</text>
  </svg>
}

export default function GreenhouseSimulationPage() {
  const [state, setState] = useState<Snapshot>(), [error, setError] = useState(''), [busy, setBusy] = useState(false)
  const [panel, setPanel] = useState<'controls'|'records'|null>(null)
  const [msg, context] = message.useMessage()
  const navigate = useNavigate(), location = useLocation(), requestVersion = useRef(0), mutating = useRef(false)
  const refresh = useCallback(async () => {
    if (mutating.current) return
    const version = ++requestVersion.current
    try { const result = await request<Snapshot>('/state'); if (version === requestVersion.current) { setState(result); setError('') } }
    catch (e) { if (version === requestVersion.current) setError(getApiErrorMessage(e)) }
  }, [])
  useEffect(() => { const requests = requestVersion; void refresh(); const timer = window.setInterval(() => void refresh(), 2000); return () => { clearInterval(timer); requests.current++ } }, [refresh])
  const action = async (fn: () => Promise<Snapshot>) => {
    if (mutating.current || !canOperate()) return
    mutating.current = true; requestVersion.current++; setBusy(true)
    try { setState(await fn()); setError('') }
    catch (e) { msg.error(getApiErrorMessage(e)) }
    finally { mutating.current = false; setBusy(false) }
  }
  const operation = (name: string) => action(() => request<Snapshot>('/operation','POST',{ action:name }))
  const manual = async () => {
    await action(() => request<Snapshot>('/state','PUT',{ mode:'manual', manual:{ fan:false,pump:false,lamp:false,led:false } }))
    setPanel('controls')
  }
  const confirmed = state?.device.confirmed, running = !!state?.running
  const activeDevices = deviceNames.filter(d => confirmed?.[d.key])
  const deviation = state ? Math.abs(state.environment.air_humidity - state.target.air_humidity) : 0
  const atTarget = deviation <= 2
  const initialDeviation = state?.history.length ? Math.abs(state.history[0].air_humidity - state.target.air_humidity) : 0
  const goalProgress = !state?.history.length ? 0 : atTarget ? 100 : initialDeviation > 0 ? Math.max(0, Math.min(100, (1 - deviation / initialDeviation) * 100)) : 0
  const cycle = !state?.decision ? 0 : !state.device.confirmed ? 3 : state.running && state.history.length ? 4 : 3
  const cycleItems = [{name:'感知',description:'采集环境数据'}, {name:'分析',description:'识别问题与成因'}, {name:'决策',description:'选择最优方案'}, {name:'执行',description:'发送控制指令'}, {name:'复核',description:'验证效果反馈'}]
  return <div className="autonomy-design">
    {context}
    <header className="autonomy-design-title"><h1>棚智自治</h1><p>围绕目标，持续感知、执行与复核。</p></header>
    {error && <Alert type="error" showIcon message="调控状态读取失败" description={error} action={<Button onClick={() => void refresh()}>重试</Button>} />}
    {!state ? !error && <Skeleton active paragraph={{ rows:12 }} /> : <>
      <div className={'autonomy-status-bar' + (state.emergency ? ' is-emergency' : '')}><div className="autonomy-pulse">ϟ</div><strong>{state.emergency ? '急停已锁定' : running ? '托管运行中' : state.mode === 'manual' ? '人工接管中' : '托管已暂停'}</strong><span className="autonomy-status-divider"/><span className="autonomy-mode-label">{state.device.mode === 'real' ? '串口控制' : '仿真运行'}</span><span className="autonomy-run-summary">近期 {state.events.filter(e => e.event === 'decision').length} 次决策 <i>·</i> 已运行 {state.simulation_time < 60 ? state.simulation_time + ' 秒' : Math.floor(state.simulation_time / 60) + ' 分钟'}</span><div className="autonomy-status-actions"><Button aria-label={running ? '暂停托管' : state.mode === 'manual' ? '启动手动控制' : '启动托管'} disabled={busy || state.emergency || !canOperate()} icon={running ? <PauseCircleOutlined/> : <PlayCircleOutlined/>} onClick={() => void operation(running ? 'pause' : 'start')}>{running ? '暂停托管' : state.mode === 'manual' ? '启动手动控制' : '启动托管'}</Button><Button aria-label="人工接管" type="primary" icon={<ControlOutlined/>} disabled={busy || !canOperate()} onClick={() => void manual()}>人工接管</Button></div></div>
      <div className="autonomy-main-grid">
        <aside className="autonomy-goals"><h2>当前生产目标</h2><button type="button" className="autonomy-target-card" onClick={() => setPanel('controls')}><span className="autonomy-drop">♧</span><span><b>稳定环境湿度</b><strong>{state.target.air_humidity}<small>%</small></strong><small>保持作物适宜的生长环境。</small></span></button><h3>约束条件</h3><ul className="autonomy-constraints"><li><ExperimentOutlined/><span>水泵连续运行</span><b>≤ 8 秒</b></li><li><SwapOutlined/><span>停机冷却间隔</span><b>≥ 12 秒</b></li><li><ClockCircleOutlined/><span>复核间隔</span><b>{state.decision?.next_evaluation_seconds ?? 2} 秒</b></li></ul>
          <div className="autonomy-device-heading"><h3>控制对象</h3><small>（{state.device.mode === 'mock' ? '虚拟设备回执' : 'GPIO 回执'}）</small></div><div className="autonomy-device-list">{deviceNames.map(({key,name,icon:Icon}) => <button type="button" key={key} onClick={() => setPanel('controls')}><Icon/><span>{name}</span><b className={confirmed?.[key] ? 'active' : ''}><i/>{confirmed ? confirmed[key] ? '已确认开启' : '已确认关闭' : '等待回执'}</b><ArrowRightOutlined/></button>)}</div>
        </aside>
        <section className="autonomy-cycle" aria-label="自主调控循环"><div className="autonomy-section-heading"><h2>当前自主循环</h2><span className="autonomy-outline-badge">{state.emergency ? '已停止' : running ? '正在执行' : '等待启动'}</span></div><ol className="autonomy-cycle-steps">{cycleItems.map((s,i) => <li key={s.name} className={(state.decision && i < cycle ? 'completed ' : '') + (running && i === cycle ? 'active' : '')}><span>{state.decision && i < cycle ? <CheckOutlined/> : ''}</span><strong>{s.name}</strong><small>{s.description}</small></li>)}</ol>
          <div className="autonomy-greenhouse-scene"><div className="autonomy-scene-command">{activeDevices.length ? activeDevices.map(d => d.name).join('、') + '已开启' : '等待调控指令'}</div><img src="/images/autonomy/greenhouse-cutaway-v1.png" alt="温室空间示意图，非实时设备画面"/><span className="autonomy-north">北<br/>♧</span><Tooltip title="当前仿真使用全棚环境模型，没有独立分区测量值"><div className="autonomy-zone-value west"><small>西侧</small><strong>—</strong></div></Tooltip><div className={'autonomy-zone-value center' + (deviation > 5 ? ' warning' : '')}><small>全棚模拟</small><strong>{state.environment.air_humidity.toFixed(1)}%</strong></div><Tooltip title="未接入独立东侧测量值"><div className="autonomy-zone-value east"><small>东侧</small><strong>—</strong></div></Tooltip><div className="autonomy-scene-zones"><span>西侧区域</span><span>中央区域</span><span>东侧区域</span></div></div>
          <div className="autonomy-current-action"><div className="autonomy-action-icon"><ControlOutlined/></div><div><h3>{state.emergency ? '已紧急停止' : running ? activeDevices.length ? '正在执行：' + activeDevices.map(d => d.name).join('、') : '正在执行：持续监测' : '等待启动自动托管'}</h3><p>{state.decision?.reason || '依据环境与目标计算调控方案。'}</p></div><span>{running ? '下次复核' : '复核间隔'}<b>{state.decision?.next_evaluation_seconds ?? 2}</b> 秒</span><div className="autonomy-action-track" role="progressbar" aria-label="湿度接近目标进度" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(goalProgress)}><i style={{width: goalProgress + '%'}}/></div></div>
          <div className="autonomy-action-note"><ClockCircleOutlined/><span>{state.error || (running ? '持续比较目标与模拟环境；满足条件后重新计算控制动作。' : '设置目标后启动托管，观察决策与设备反馈。')}</span></div>
        </section>
        <aside className="autonomy-records"><div className="autonomy-section-heading"><h2>自主运行记录</h2><span><i/>{error ? '连接异常' : '实时更新'}</span></div><ol>{state.events.slice(0,5).reverse().map((event,i) => <li key={event.at + ':' + i} className={event.error ? 'failed' : ''}><i/><time>{formatTime(event.at)}</time><div><strong>{eventNames[event.event] || event.event}</strong><p>{event.error || commandNames[event.command_status] || event.command_status}</p></div></li>)}{running && <li className="waiting"><i/><time>{state.events[0] ? formatTime(state.events[0].at) : '—'}</time><div><strong>等待复测反馈</strong><p>复核间隔 {state.decision?.next_evaluation_seconds ?? 2} 秒 · 软件仿真</p></div></li>}</ol><button className="autonomy-record-link" type="button" onClick={() => setPanel('records')}>查看完整运行记录 <ArrowRightOutlined/></button></aside>
      </div>
      <section className="autonomy-trend-card"><div><h2>目标与变化</h2><p>全棚环境湿度变化<br/><small>（模拟数据）</small></p></div><HumidityTrend state={state}/><div className="autonomy-current-reading"><small>当前模拟</small><strong>{state.environment.air_humidity.toFixed(1)}%</strong><span className={atTarget ? 'reached' : ''}>{atTarget ? '已接近目标' : '目标尚未达成'}</span></div></section>
      <footer className="autonomy-bottom-links">{[{name:'观察档案',tab:'archive'},{name:'方案比较',tab:'controls'},{name:'研究记录',tab:'studies'},{name:'农艺技能',tab:'skills'},{name:'目标编排',tab:'goals'}].map(({name,tab}) => <button type="button" key={tab} aria-label={name} onClick={() => tab === 'controls' ? setPanel('controls') : navigate(workspaceHref('/platform/research?tab='+tab,location.search))}><FileTextOutlined/>{name}</button>)}<button type="button" onClick={() => setPanel('controls')}><SlidersOutlined/>调控设置</button><span>软件仿真 · 设备回执不代表实物已运转</span></footer>
    </>}
    <Drawer title={panel === 'records' ? '自主运行记录' : '调控设置与方案比较'} width="min(1240px,98vw)" push={false} open={panel !== null} onClose={() => { setPanel(null); void refresh() }} destroyOnHidden>
      {panel === 'controls' && <SimulationControls/>}
      {panel === 'records' && <div className="autonomy-full-records">{state?.events.length ? state.events.map((event,i) => <article key={event.at+':'+i}><time>{formatTime(event.at)}</time><strong>{eventNames[event.event] || event.event}</strong><p>{event.error || event.decision?.reason || commandNames[event.command_status]}</p></article>) : <Empty description="暂无运行记录"/>}<Button icon={<PoweroffOutlined/>} danger disabled={busy || !canOperate()} onClick={() => void operation('estop')}>紧急停止</Button></div>}
    </Drawer>
  </div>
}
