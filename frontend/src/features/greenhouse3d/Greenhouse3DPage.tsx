import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  BulbOutlined,
  CompassOutlined,
  DownOutlined,
  CloudOutlined,
  ExperimentOutlined,
  SettingOutlined,
  SunOutlined,
  WarningOutlined,
  UpOutlined,
} from '@ant-design/icons'
import { Alert, Button, Select, Skeleton, Slider, Tooltip } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import { getApiErrorMessage } from '../../api/client'
import { getDashboardSummary } from '../../api/dashboardApi'
import { getGreenhouses } from '../../api/greenhouseApi'
import { runSimulation } from '../../api/v2DecisionApi'
import type { DashboardSummary } from '../../types/dashboard'
import type { SimulationData } from '../../types/v2Decision'
import GreenhouseExperience, { type ExperienceMode } from './scene/GreenhouseExperience'
import type { MovementInput, ViewStop, WalkPosition } from './scene/controls/FirstPersonController'
import VirtualJoystick from './VirtualJoystick'
import type { GreenhouseInteriorConfig } from './scene/config/types'
import { cropFromGreenhouse, loadGreenhouse3DConfig, saveGreenhouse3DConfig } from './configAdapter'
import Greenhouse3DConfigDrawer from './Greenhouse3DConfigDrawer'
import './greenhouse-3d.css'

type DeviceKey = 'fan' | 'pump' | 'light' | 'sprinkler'
type SandboxMode = 'REALTIME' | 'SIMULATION'

type SelectedEntity = Record<string, unknown> & { title?: unknown }

function value(v: number | null | undefined, digits = 0) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return v.toFixed(digits)
}

function simulatedValue(v: string | number | null | undefined): number | null {
  if (v === null || v === undefined || v === '') return null
  const parsed = Number(v)
  return Number.isFinite(parsed) ? parsed : null
}

function cropLabel(crop: string) {
  return ({ tomato: '番茄', cucumber: '黄瓜', pepper: '辣椒', strawberry: '草莓', lettuce: '叶菜' } as Record<string, string>)[crop] ?? crop
}

function metricIcon(metric: string) {
  if (metric === 'temperature') return <SunOutlined />
  if (metric === 'humidity') return <CloudOutlined />
  if (metric === 'soil') return <BulbOutlined />
  return <ExperimentOutlined />
}

export default function Greenhouse3DPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const greenhouseIdFromQuery = useMemo(() => Number(new URLSearchParams(location.search).get('greenhouse_id')) || null, [location.search])
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<ExperienceMode>('outside')
  const movement = useRef<MovementInput>({ x: 0, y: 0 })
  const walkPosition = useRef<WalkPosition>({ x: 14.2, z: 0, facing: '棚内' })
  const navigation = useRef<ViewStop | null>(null)
  const [selected, setSelected] = useState<SelectedEntity | null>(null)
  const [config, setConfig] = useState<GreenhouseInteriorConfig | null>(null)
  const [configOpen, setConfigOpen] = useState(false)
  const [nightMode, setNightMode] = useState(false)
  const [devices, setDevices] = useState<Record<DeviceKey, boolean>>({ fan: true, pump: false, light: false, sprinkler: false })
  const [devicePanelOpen, setDevicePanelOpen] = useState(false)
  const [sandboxMode, setSandboxMode] = useState<SandboxMode>('REALTIME')
  const [simulationAction, setSimulationAction] = useState<'ventilation' | 'shading' | 'irrigation' | 'dehumidify'>('ventilation')
  const [simulationIntensity, setSimulationIntensity] = useState(30)
  const [simulationDuration, setSimulationDuration] = useState(30)
  const [simulation, setSimulation] = useState<SimulationData | null>(null)
  const [simulationLoading, setSimulationLoading] = useState(false)

  const resolveGreenhouseId = useCallback(async () => {
    if (greenhouseIdFromQuery) return greenhouseIdFromQuery
    const result = await getGreenhouses({ page: 1, page_size: 100, status: 'active' })
    const first = result.items[0]
    if (!first) return null
    const params = new URLSearchParams(location.search)
    params.set('greenhouse_id', String(first.id))
    navigate(`${location.pathname}?${params.toString()}`, { replace: true })
    return first.id
  }, [greenhouseIdFromQuery, location.pathname, location.search, navigate])

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true)
    setError(null)
    try {
      const greenhouseId = await resolveGreenhouseId()
      if (!greenhouseId) {
        setSummary(null)
        return
      }
      const next = await getDashboardSummary(greenhouseId)
      setSummary(next)
      setConfig((current) => current?.greenhouseId === next.greenhouse.code ? current : loadGreenhouse3DConfig(next.greenhouse))
    } catch (requestError) {
      setError(getApiErrorMessage(requestError))
    } finally {
      if (!quiet) setLoading(false)
    }
  }, [resolveGreenhouseId])

  useEffect(() => { void load() }, [load])
  useEffect(() => {
    const timer = window.setInterval(() => { void load(true) }, 10000)
    return () => window.clearInterval(timer)
  }, [load])

  useEffect(() => {
    if (mode === 'outside') setSelected(null)
    if (mode !== 'inside') { movement.current.x = 0; movement.current.y = 0 }
  }, [mode])

  useEffect(() => { setSimulation(null); setSelected(null); setSandboxMode('REALTIME') }, [greenhouseIdFromQuery])

  const latest = summary?.latest_environment
  const warningCount = summary?.warning_summary.open_warning_count ?? 0
  const warning = warningCount > 0
  const hasEnvironmentData = latest !== null && latest !== undefined
  const cropNames = useMemo(() => config ? [...new Set(config.zones.map((zone) => cropLabel(zone.crop)))].join(' · ') : '—', [config])
  const lightsOn = nightMode || devices.light
  const displayedLatest = simulation?.timeline?.at(-1)

  const handleSelection = (entity: SelectedEntity) => {
    if ('作物' in entity) {
      setSelected({
        ...entity,
        温度: latest?.temperature == null ? '待接入' : `${latest.temperature.toFixed(1)}℃`,
        空气湿度: latest?.air_humidity == null ? '待接入' : `${latest.air_humidity.toFixed(0)}%`,
        土壤湿度: latest?.soil_moisture == null ? '待接入' : `${latest.soil_moisture.toFixed(0)}%`,
        EC: '待接入',
        pH: '待接入',
        数据时间: summary?.data_updated_at ? new Date(summary.data_updated_at).toLocaleTimeString('zh-CN', { hour12: false }) : '—',
      })
      return
    }
    setSelected(entity)
  }

  const toggleDevice = (key: DeviceKey) => {
    setDevices((current) => ({ ...current, [key]: !current[key] }))
    if (key === 'light') setNightMode((current) => !current)
  }

  const handleSaveConfig = (next: GreenhouseInteriorConfig) => {
    if (!summary) return
    saveGreenhouse3DConfig(summary.greenhouse.id, next)
    setConfig(next)
    setConfigOpen(false)
  }

  const handleRunSimulation = async () => {
    if (!summary) return
    setSimulationLoading(true)
    try {
      setSimulation(await runSimulation({
        greenhouse_id: summary.greenhouse.id,
        action_type: simulationAction,
        intensity: simulationIntensity,
        duration_minutes: simulationDuration,
      }))
      setSandboxMode('SIMULATION')
    } catch (requestError) {
      setError(getApiErrorMessage(requestError))
    } finally {
      setSimulationLoading(false)
    }
  }

  if (loading && (!summary || !config)) {
    return <div className="greenhouse-3d-page g3d-loading"><Skeleton active paragraph={{ rows: 12 }} /></div>
  }

  if (!summary || !config) {
    return <div className="greenhouse-3d-page g3d-empty"><Alert type="info" showIcon message="暂无可用大棚" description="请先在“大棚管理”中创建启用状态的大棚，再进入 3D 大棚。" /></div>
  }

  const batchCrop = cropFromGreenhouse({ ...summary.greenhouse, active_batch: summary.active_batch })
  const appliedGrowthStage = batchCrop && config.zones.every((zone) => zone.crop === batchCrop)
    ? summary.active_batch?.growth_stage ?? null
    : null

  return <div className={`greenhouse-3d-page ${lightsOn ? 'is-night' : 'is-day'} ${mode === 'inside' ? 'is-inside' : ''} ${selected ? 'has-selection' : ''}`}>
    {error && <Alert className="g3d-error" type="warning" showIcon closable message="3D 大棚实时数据更新失败" description={error} />}

    <GreenhouseExperience
      config={config}
      mode={mode}
      onMode={setMode}
      onSelection={handleSelection}
      lightsOn={lightsOn}
      growthStage={appliedGrowthStage}
      movement={movement}
      position={walkPosition}
      navigation={navigation}
    />

    <div className="g3d-scene-title">
      <span className="g3d-title-icon">3D</span>
      <div><strong>{summary.greenhouse.name}</strong><small>{summary.greenhouse.code} · {summary.greenhouse.location || '未设置位置'} · {appliedGrowthStage || '布局示意'}</small></div>
      <span className={`g3d-live-dot ${error ? 'offline' : ''}`} />
      <em>{error ? '数据暂不可用' : summary.data_updated_at && Date.now() - new Date(summary.data_updated_at).getTime() > 2 * 3600_000 ? '历史记录' : '10 秒刷新'}</em>
    </div>

    <div className="g3d-toolbar">
      <Tooltip title="实时模式"><button type="button" className={sandboxMode === 'REALTIME' ? 'active' : ''} onClick={() => setSandboxMode('REALTIME')}>实时</button></Tooltip>
      <Tooltip title="模拟模式"><button type="button" className={sandboxMode === 'SIMULATION' ? 'active' : ''} onClick={() => setSandboxMode('SIMULATION')}>模拟</button></Tooltip>
      <Tooltip title="切换日间/补光预览"><button type="button" className={lightsOn ? 'active' : ''} onClick={() => setNightMode((current) => !current)}>{lightsOn ? '夜间补光' : '日间模式'}</button></Tooltip>
      <button type="button" onClick={() => setConfigOpen(true)}><SettingOutlined /> 3D布局</button>
    </div>

    {mode !== 'inside' && <aside className={`g3d-telemetry ${mode === 'confirm' || mode === 'entering' ? 'is-muted' : ''}`}>
      <header><div><span>环境数据 · 布局示意</span><h3>数字孪生态势</h3></div><b className={warning ? 'warning' : 'normal'}><i />{warning ? `${warningCount} 条预警` : hasEnvironmentData ? '暂无预警' : '等待数据'}</b></header>
      <div className="g3d-metric-grid">
        <div>{metricIcon('temperature')}<span>{sandboxMode === 'SIMULATION' ? '模拟温度' : '温度'}</span><strong>{value(sandboxMode === 'SIMULATION' ? simulatedValue(displayedLatest?.temperature) : latest?.temperature, 1)}<em>℃</em></strong></div>
        <div>{metricIcon('humidity')}<span>{sandboxMode === 'SIMULATION' ? '模拟湿度' : '湿度'}</span><strong>{value(sandboxMode === 'SIMULATION' ? simulatedValue(displayedLatest?.humidity) : latest?.air_humidity)}<em>%</em></strong></div>
        <div>{metricIcon('soil')}<span>土壤</span><strong>{value(latest?.soil_moisture)}<em>%</em></strong></div>
        <div>{metricIcon('co2')}<span>CO₂</span><strong>{value(latest?.co2_concentration)}<em>ppm</em></strong></div>
        <div><SunOutlined /><span>光照</span><strong>{value(latest?.light_intensity, 1)}<em>klx</em></strong></div>
        <div><ExperimentOutlined /><span>种植</span><strong className="crop-value">{summary.active_batch?.variety || cropNames}</strong></div>
      </div>
      <footer><span>数据时间</span><b>{summary.data_updated_at ? new Date(summary.data_updated_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : '—'}</b></footer>
    </aside>}

    {mode === 'outside' && <button type="button" className="g3d-scene-hint" onClick={() => setMode('confirm')}><span /><div><b>点击进入数字孪生</b><small>查看大棚内部种植垄与设备</small></div></button>}

    {sandboxMode === 'SIMULATION' && <aside className="g3d-simulation-panel">
      <header><span>3D决策沙盘</span><small>模拟模式 · 探索性推演</small></header>
      <label>操作</label>
      <Select
        size="small"
        value={simulationAction}
        options={[
          { value: 'ventilation', label: '通风' },
          { value: 'shading', label: '遮阴' },
          { value: 'irrigation', label: '灌溉' },
          { value: 'dehumidify', label: '降湿' },
        ]}
        onChange={(next) => { setSimulationAction(next); setSimulation(null) }}
      />
      <label>强度 {simulationIntensity}%</label>
      <Slider min={0} max={60} step={10} value={simulationIntensity} onChange={(next) => { setSimulationIntensity(next); setSimulation(null) }} />
      <label>持续 {simulationDuration} 分钟</label>
      <Slider min={10} max={60} step={10} value={simulationDuration} onChange={(next) => { setSimulationDuration(next); setSimulation(null) }} />
      <Button type="primary" block size="small" loading={simulationLoading} onClick={() => void handleRunSimulation()}>开始模拟</Button>
      {simulation && <div className="g3d-simulation-result">
        {simulation.timeline.map((point) => <div key={String(point.minute)}><span>{point.minute}分钟</span><b>{point.temperature}℃ / {point.humidity}%</b></div>)}
        <p>{simulation.note}</p>
      </div>}
    </aside>}

    {mode === 'confirm' && <div className="g3d-modal-mask" onMouseDown={(event) => { if (event.currentTarget === event.target) setMode('outside') }}>
      <section className="g3d-enter-card">
        <div className="g3d-enter-head"><span className="g3d-entity-icon">棚</span><div><small>DIGITAL TWIN · {summary.greenhouse.code}</small><h2>{summary.greenhouse.name}</h2><p>{cropNames}</p></div><b className={warning ? 'warning' : 'normal'}><i />{warning ? '存在预警' : hasEnvironmentData ? '暂无预警' : '等待数据'}</b></div>
        <div className="g3d-enter-metrics"><div><span>温度</span><strong>{value(latest?.temperature, 1)}℃</strong></div><div><span>湿度</span><strong>{value(latest?.air_humidity)}%</strong></div><div><span>CO₂</span><strong>{value(latest?.co2_concentration)} ppm</strong></div><div><span>土壤湿度</span><strong>{value(latest?.soil_moisture)}%</strong></div></div>
        <p className="g3d-enter-note">进入后可使用 WASD 在大棚内部漫游，并点击种植垄、传感器和设备查看数字孪生信息。</p>
        <footer><button type="button" className="ghost" onClick={() => setMode('outside')}>取消</button><button type="button" className="primary" onClick={() => setMode('entering')}>进入大棚 <span>→</span></button></footer>
      </section>
    </div>}

    {mode === 'inside' && <>
      <VirtualJoystick inputRef={movement} positionRef={walkPosition} />
      <div className="g3d-inside-nav"><button type="button" onClick={() => setMode('outside')}>← 退出大棚</button><span>WASD 漫游 · 点击种植垄/设备查看</span><Select aria-label="切换棚内位置" className="g3d-view-select" getPopupContainer={(trigger) => trigger.parentElement ?? document.body} placeholder={<><CompassOutlined /> 切换位置</>} value={undefined} onChange={(stop: ViewStop) => { navigation.current = stop; setSelected(null) }} options={[
        { value: 'entrance', label: '大棚入口' },
        ...config.zones.map((zone) => ({ value: zone.id, label: `${zone.id} 区 · ${cropLabel(zone.crop)}` })),
      ]} /><button type="button" className="g3d-lock-control">锁定视角 · ESC 释放</button></div>
      <aside className={`g3d-device-panel ${devicePanelOpen ? 'is-expanded' : ''}`}>
        <header><div><span>设备控制</span><small>当前为前端联动演示，接口位置已预留</small></div><button type="button" aria-label={devicePanelOpen ? '收起设备控制' : '展开设备控制'} aria-expanded={devicePanelOpen} onClick={() => setDevicePanelOpen((open) => !open)}>{devicePanelOpen ? <UpOutlined /> : <DownOutlined />}</button></header>
        <div className="g3d-inside-live">
          <span>全棚实时环境</span>
          <strong>{value(latest?.temperature, 1)}℃ <i /> {value(latest?.air_humidity)}%</strong>
          <small>温度 / 空气湿度 · {summary.data_updated_at ? new Date(summary.data_updated_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false }) : '待接入'}</small>
        </div>
        {devicePanelOpen && ([
          ['fan', '负压风机', devices.fan],
          ['pump', '灌溉水泵', devices.pump],
          ['light', '补光灯组', devices.light],
          ['sprinkler', '喷淋系统', devices.sprinkler],
        ] as Array<[DeviceKey, string, boolean]>).map(([key, label, on]) => <div className="g3d-device-row" key={key}><div><b>{label}</b><span>{on ? '运行中' : '已关闭'}</span></div><button type="button" className={on ? 'switch on' : 'switch'} onClick={() => toggleDevice(key)} aria-label={`${label}${on ? '关闭' : '开启'}`}><i /></button></div>)}
      </aside>
    </>}

    {selected && <aside className="g3d-inspector">
      <button type="button" className="close" onClick={() => setSelected(null)}>×</button>
      <small>DIGITAL TWIN ENTITY</small><h3>{String(selected.title ?? '数字孪生对象')}</h3><div className="g3d-sync"><i />{'数据来源' in selected ? '前端演示' : '关联当前大棚环境数据'}</div>
      <div className="g3d-inspector-list">{Object.entries(selected).filter(([key]) => key !== 'title').map(([key, item]) => <div key={key}><span>{key}</span><b>{String(item)}</b></div>)}</div>
    </aside>}

    {warning && mode !== 'confirm' && mode !== 'entering' && <div className="g3d-warning"><WarningOutlined /><div><b>{summary.warning_summary.latest_warning_title || '当前存在环境预警'}</b><span>请前往“环境分析”查看完整预警证据与处理建议。</span></div><Button type="link" size="small" onClick={() => navigate(`/platform/environment?greenhouse_id=${summary.greenhouse.id}&tab=alerts`)}>查看</Button></div>}

    {configOpen && <Greenhouse3DConfigDrawer config={config} onClose={() => setConfigOpen(false)} onSave={handleSaveConfig} />}
  </div>
}
