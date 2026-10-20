import { useCallback, useEffect, useRef, useState } from 'react'
import { Button, Alert, Drawer, Empty, Select, Spin, Table, Tag, message } from 'antd'
import { DownloadOutlined, FileTextOutlined, ReloadOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getDashboardSummary } from '../api/dashboardApi'
import { getGreenhouses } from '../api/greenhouseApi'
import { getEnvironmentPrediction } from '../api/predictionApi'
import { getSensorHistory } from '../api/sensorApi'
import { evaluateWarnings } from '../api/warningApi'
import { getApiErrorMessage } from '../api/client'
import { canManage } from '../utils/permissions'
import type { DashboardSummary } from '../types/dashboard'
import type { Greenhouse } from '../types/greenhouse'
import type { EnvironmentPrediction } from '../types/prediction'
import type { SensorReading } from '../types/sensor'
import type { WarningEvent } from '../types/warning'
import UnifiedEnvironmentChart from './Environment/UnifiedEnvironmentChart'
import WarningWorkspace from './Environment/WarningWorkspace'
import { environmentMetrics, type MetricKey } from './Environment/timeline'
import './Environment/environment-workspace.css'

const time = (value: string | null | undefined) => value ? new Date(value).toLocaleString('zh-CN', {month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}) : '尚无采样'

export default function EnvironmentAnalysisPage() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const requestedId = Number(params.get('greenhouse_id')) || null
  const legacyTab = params.get('tab')
  const [greenhouses, setGreenhouses] = useState<Greenhouse[]>([])
  const [greenhouseId, setGreenhouseId] = useState<number | null>(null)
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [history, setHistory] = useState<SensorReading[]>([])
  const [historyTotal, setHistoryTotal] = useState(0)
  const [prediction, setPrediction] = useState<EnvironmentPrediction | null>(null)
  const [metric, setMetric] = useState<MetricKey>('temperature')
  const [hours, setHours] = useState(24)
  const [horizon, setHorizon] = useState(6)
  const [clock, setClock] = useState(Date.now())
  const [booting, setBooting] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [bootError, setBootError] = useState('')
  const [retry, setRetry] = useState(0)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(legacyTab==='prediction')
  const [evaluating, setEvaluating] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const [selectedWarning, setSelectedWarning] = useState<WarningEvent | null>(null)
  const [notice, context] = message.useMessage()
  const generation = useRef(0)
  const chartSection = useRef<HTMLElement>(null)
  useEffect(() => {
    let active = true
    setBooting(true);setBootError('')
    void getGreenhouses({page:1,page_size:100}).then(result => {
      if (!active) return
      setGreenhouses(result.items)
      setGreenhouseId(result.items.find(g=>g.id===requestedId)?.id ?? result.items[0]?.id ?? null)
    }).catch(e=>{if(active)setBootError(getApiErrorMessage(e))}).finally(()=>{if(active)setBooting(false)})
    return () => {active=false}
  }, [requestedId,retry])
  const load = useCallback(async () => {
    if (!greenhouseId) return
    const request = ++generation.current
    setLoading(true);setError('')
    const now=Date.now(), start=new Date(now-hours*3600_000).toISOString(), end=new Date(now).toISOString()
    const query={greenhouse_id:greenhouseId,start_time:start,end_time:end,page:1,page_size:1000}
    const readHistory = async () => {
      const first=await getSensorHistory(query)
      if(first.total<=1000)return first
      const page=Math.ceil(first.total/1000)
      const last=await getSensorHistory({...query,page})
      const previous=last.items.length<1000 ? await getSensorHistory({...query,page:page-1}) : null
      return {...last,items:[...(previous?.items??[]),...last.items].slice(-1000),total:first.total}
    }
    const results=await Promise.allSettled([getDashboardSummary(greenhouseId),readHistory(),getEnvironmentPrediction(greenhouseId,horizon)])
    if(request!==generation.current)return
    const [s,h,p]=results
    setSummary(s.status==='fulfilled'?s.value:null)
    setHistory(h.status==='fulfilled'?h.value.items:[])
    setHistoryTotal(h.status==='fulfilled'?h.value.total:0)
    setPrediction(p.status==='fulfilled'?p.value:null)
    setError(results.flatMap((r,i)=>r.status==='rejected'?[`${['当前环境','历史数据','预测服务'][i]}：${getApiErrorMessage(r.reason)}`]:[]).join('；'))
    setClock(Date.now());setLoading(false)
  }, [greenhouseId,hours,horizon])
  const cancelLoad=useCallback(()=>{generation.current++},[])
  useEffect(()=>{void load();return cancelLoad},[load,cancelLoad])
  useEffect(()=>{
    const timer=window.setInterval(()=>{if(document.visibilityState==='visible'){void load();setRefreshKey(k=>k+1)}},60000)
    return()=>window.clearInterval(timer)
  },[load])
  useEffect(()=>{
    if(legacyTab==='alerts' && greenhouseId){const timer=window.setTimeout(()=>document.getElementById('environment-alerts')?.scrollIntoView({block:'start'}),180);return()=>window.clearTimeout(timer)}
    if(legacyTab==='history')chartSection.current?.scrollIntoView({block:'start'})
  },[legacyTab,greenhouseId])
  const refresh=()=>{void load();setRefreshKey(k=>k+1)}
  const evaluate=async()=>{
    if(!greenhouseId)return
    setEvaluating(true)
    try{await evaluateWarnings(greenhouseId);refresh();notice.success('环境风险研判已更新')}
    catch(e){notice.error(getApiErrorMessage(e))}finally{setEvaluating(false)}
  }
  const latest=summary?.latest_environment
  const stale=!latest || clock-Date.parse(latest.recorded_at)>2*3600_000
  const selected=environmentMetrics.find(m=>m.key===metric)!
  const chartHistory=latest && !history.some(r=>r.id===latest.id) ? [...history,latest] : history
  const exportData=()=>{
    const fields=['recorded_at',...environmentMetrics.map(m=>m.key),'source','quality_flag'] as const
    const csv='\uFEFF'+[fields.join(','),...history.map(row=>fields.map(key=>row[key]??'').join(','))].join('\r\n')
    const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}))
    const a=document.createElement('a');a.href=url;a.download=`environment-${greenhouseId}.csv`;a.click();URL.revokeObjectURL(url)
  }
  return <div className="env-unified-workspace">
    {context}
    <header className="env-page-heading"><div><h1>环境监测</h1><p>看清过去，掌握当下，预判变化。</p></div><div className="env-page-actions"><span className={stale?'env-sampling is-stale':'env-sampling'}><i/>{loading?'正在更新':stale?'等待新采样':'数据已更新'}<small>最近采样 {time(latest?.recorded_at)}</small></span><Button type="text" icon={<ReloadOutlined />} aria-label="刷新环境数据" onClick={refresh} loading={loading}/></div></header>
    {bootError && <Alert type="error" message="大棚读取失败" description={bootError} action={<Button onClick={()=>setRetry(r=>r+1)}>重试</Button>} />}
    {error && <Alert type="warning" message="部分环境信息暂不可用" description={error} action={<Button onClick={refresh}>重试</Button>}/>}
    {booting && !greenhouseId ? <Spin/> : !greenhouseId ? <Empty description="还没有可用大棚"><Button onClick={()=>navigate('/platform/data')}>创建与接入大棚</Button></Empty> : <>
      <nav className="env-metric-strip" aria-label="选择环境指标">{environmentMetrics.map(m=>{const value=latest?.[m.key];return <button type="button" key={m.key} aria-pressed={metric===m.key} onClick={()=>setMetric(m.key)}><span>{m.label}</span><strong>{typeof value==='number'?value.toFixed(m.digits):'—'}<small>{m.unit}</small></strong><em className={stale?'is-stale':''}><i/>{value===null || value===undefined?'暂无采样':stale?'历史采样':latest?.quality_flag==='valid'?'有效采样':'采样待复查'}</em></button>})}</nav>
      <section className="env-chart-section" ref={chartSection} aria-labelledby="env-chart-heading">
        <header className="env-chart-toolbar"><div><h2 id="env-chart-heading">{selected.short}变化</h2><span>历史实测与未来预测</span></div><div className="env-chart-controls"><div className="env-chart-legend"><span><i/>实测数据</span><span><i/>预测数据</span><span><i/>预测区间</span></div><Select aria-label="环境时间范围" value={hours} onChange={setHours} options={[{value:24,label:`过去24小时 + 未来${horizon}小时`},{value:168,label:`过去7天 + 未来${horizon}小时`},{value:720,label:`过去30天 + 未来${horizon}小时`}]} /><Button type="link" onClick={()=>setSettingsOpen(true)}>预测设置</Button><Button type="text" icon={<DownloadOutlined/>} aria-label="导出环境数据" onClick={exportData} disabled={!history.length}/></div></header>
        <Spin spinning={loading}><UnifiedEnvironmentChart history={chartHistory} prediction={prediction} metric={metric} now={clock} hours={hours} horizon={horizon} warning={selectedWarning}/></Spin>
        <div className="env-chart-footnote"><span>已加载 {history.length} / {historyTotal} 条记录{historyTotal>1000?' · 当前展示最近1000条':''} · {summary?.data_source_label || '来源待确认'}</span><Button type="link" aria-label="数据明细" icon={<FileTextOutlined/>} onClick={()=>setHistoryOpen(true)}>数据明细</Button><Button type="link" onClick={()=>window.dispatchEvent(new Event('pengzhi:open-assistant'))}>让棚小智解释趋势</Button></div>
      </section>
      <WarningWorkspace key={greenhouseId} greenhouseId={greenhouseId} onSelected={setSelectedWarning} refreshKey={refreshKey}/>
    </>}
    <Drawer title="环境数据明细" open={historyOpen} onClose={()=>setHistoryOpen(false)} width="min(1120px,96vw)" destroyOnHidden><p>显示当前范围已加载的原始记录，共 {history.length} 条。</p><Table<SensorReading> rowKey="id" dataSource={history} scroll={{x:850}} pagination={{pageSize:20}} columns={[{title:'采样时间',dataIndex:'recorded_at',render:time},...environmentMetrics.map(m=>({title:`${m.label} (${m.unit})`,dataIndex:m.key,render:(v:number|null)=>v===null?'—':v})),{title:'质量',dataIndex:'quality_flag'},{title:'来源',dataIndex:'source'}]}/></Drawer>
    <Drawer title="预测设置与模型信息" open={settingsOpen} onClose={()=>setSettingsOpen(false)} width={540} destroyOnHidden><section className="env-settings-section"><h3>当前大棚</h3><Select aria-label="选择目标大棚" value={greenhouseId} style={{width:'100%'}} options={greenhouses.map(g=>({value:g.id,label:g.name}))} onChange={id=>{const next=new URLSearchParams(params);next.set('greenhouse_id',String(id));setParams(next,{replace:true})}}/><h3>预测时长</h3><Select aria-label="预测时长" value={horizon} onChange={setHorizon} options={[1,3,6].map(n=>({value:n,label:`未来 ${n} 小时`}))}/><p>温度、空气湿度按可用模型输出展示；其他指标无预测时保留实测。</p></section><section className="env-settings-section"><h3>模型与来源</h3><p>服务状态：{prediction?.status ?? '暂不可用'}</p><p>{prediction?.forecast_method_labels.join(' / ') || '暂无预测方法'}</p><p>版本：{prediction?.model_version || '—'}</p><p>输入截至：{time(prediction?.input_end_time)}</p><p>生成时间：{time(prediction?.generated_at)}</p>{prediction?.warnings.map((w,i)=><p key={i}>{w}</p>)}<h3>本棚模型健康</h3><p>{prediction?.health?.explanation || '暂无到期预测与实测对照样本。'}</p>{(['temperature','humidity'] as const).map(key=>{const h=prediction?.health?.[key];return <p key={key}>{key==='temperature'?'温度':'湿度'}：验证 {h?.sample_count??0} 次 · MAE {h?.mae??'—'} · RMSE {h?.rmse??'—'} · Bias {h?.bias??'—'}</p>})}</section><Button type="primary" disabled={!canManage()||!latest} loading={evaluating} onClick={()=>void evaluate()}>重新分析环境风险</Button><Tag style={{marginLeft:10}}>每60秒刷新监测数据</Tag></Drawer>
  </div>
}
