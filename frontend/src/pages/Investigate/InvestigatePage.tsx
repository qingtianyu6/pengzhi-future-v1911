import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { Alert, App, Button, Card, Collapse, Empty, Form, Input, InputNumber, Select, Space, Spin, Tag, Timeline, Drawer, Segmented } from 'antd'
import { useSearchParams } from 'react-router-dom'
import { apiClient, getApiErrorMessage } from '../../api/client'
import { isGuestMode } from '../../api/guestMode'
import { getAIStatus } from '../../api/aiApi'
import { getGreenhouses } from '../../api/greenhouseApi'
import { CommunityAsset, CommunityMarkdown } from '../../components/CommunityMarkdown'
import type { ApiResponse } from '../../types/api'
import { LeafOutlined } from './InvestigationSymbols'
import { InvestigationSpatialMap } from './InvestigationSpatialMap'
import './investigate.css'
import './investigation-workspace.css'
const RiskPanel = lazy(() => import('../DiseaseTimeMachinePage'))
const RecognitionPanel = lazy(() => import('../Diagnosis/DiseaseDiagnosisPage'))
import { InvestigationVisionPanel, type VisualResult } from './InvestigationVisionPanel'
import { InvestigationExperiencePanel } from './InvestigationExperiencePanel'

type Action = { id: string; name: string; target: string; features: string[]; score: number; cost_minutes: number; reason: string; distinguishes: string[]; discrimination: number; missing_ratio: number; cost_penalty: number; can_execute?: boolean }
type Candidate = { id: string; name: string; score: number; support: string[]; conflict: string[]; missing: string[]; key_features: string[]; sources: { title: string; url: string }[] }
export type Evidence = { action: string; zone: string; features: Record<string, boolean>; note: string; humidity?: number; temperature?: number; observed_at: string; asset_id?: number; sensor_id?: number; visual?: VisualResult; visual_review?: Record<string,boolean|null>; reject_classifier?: boolean; height_cm?: number; duration_seconds?: number; data_source?: string }
type Analysis = { candidates: Candidate[]; rankings: Action[]; plan: Action[]; next: Action | null; remaining: number; summary: string; score_note: string; rule_version: string; evidence_ledger?: object[]; spatial?: {coverage: string; points: object[]} }
type Snapshot = { unavailable_actions?: string[]; source: string; crop?: string; batch?: object; latest: { id: number; recorded_at: string; air_humidity: number | null } | null; fresh?: boolean; operations?: object[]; history: object[]; gaps?: string[]; warnings: object[]; diseases: object[]; knowledge: { id: string; title: string; sources: { name: string; url?: string }[] }[]; position_note?: string }
type AutoRun = { at: string; state: string; steps: {name:string;count:number;detail:string}[] }
export type RecordData = { greenhouse_id?: number; id: number; version: number; status: string; photos?: Record<string, string>; payload: { autonomy_runs?: AutoRun[]; verification?: {cause_id?:string;method:string;conclusion:string;confirmed:boolean;dataset_usage?:'training'|'holdout'}; question: string; zone: string; budget: number; context: Snapshot; evidence: Evidence[]; analysis: Analysis; final_note: string | null; history: { round: number; at: string; leader: string; previous_leader?: string; changes: { name: string; before: number; after: number }[]; analysis: Analysis }[] } }
const zones = ['东侧', '中央', '西侧', '北侧', '南侧']
const actionNames: Record<string, string> = {front:'叶片正面',back:'叶片背面',plant:'完整植株',neighbors:'邻株检查',local:'异常区补测',normal:'正常区补测',irrigation:'灌溉记录',ventilation:'通风记录',symptom:'症状描述',history:'历史环境核查'}
const featureLabels: Record<string, string> = {yellowing:'叶片黄化',spots:'叶面斑点',necrosis:'疑似坏死',curling:'卷叶/形态异常', local_humid: '异常区高湿', humidity_gap: '区域湿度差异', poor_ventilation: '通风不畅', localized: '局部发生', mold: '叶背霉层', spreading: '相邻植株也异常', webbing: '叶背蛛网/活动小点', stippling: '密集点状失绿', irrigation_changed: '灌溉异常变化', wilting: '整株萎蔫' }
const localTime = () => new Date(Date.now()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,16)
const key = 'pengzhi-investigations-v1'
const readGuest = (): RecordData[] => { try { return JSON.parse(sessionStorage.getItem(key) || '[]') } catch { return [] } }
async function request<T>(path: string, method = 'get', data?: object): Promise<T> {
  const response = await apiClient.request<ApiResponse<T>>({ url: '/investigate'+path, method, data, timeout: 90000 })
  return response.data.data
}
async function demo(data: object): Promise<RecordData> {
  const response = await fetch('/api/investigate-demo/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
  const body = await response.json()
  if (!response.ok) throw new Error(typeof body.message === 'string' ? body.message : '证据格式无效或超过调查预算')
  return body.data
}
export default function InvestigatePage() { return <App><Investigation /></App> }
function Investigation() {
  const { message, modal } = App.useApp()
  const [params, setParams] = useSearchParams(), guest = isGuestMode()
  const [panel,setPanel] = useState<string | null>(params.get('panel'))
  const [mode,setMode] = useState<'auto'|'guided'>('auto')
  const [running,setRunning] = useState(false), [paused,setPaused] = useState(false), [runError,setRunError]=useState(false)
  const runToken=useRef(0), inFlight=useRef(false), pausedRef=useRef(false)
  const modeRef=useRef(mode); modeRef.current=mode
  const [visionBusy,setVisionBusy]=useState(false)
  const openPanel=(value:string|null)=>{setPanel(value);setParams(previous=>{const next=new URLSearchParams(previous);if(value)next.set('panel',value);else next.delete('panel');return next},{replace:true})}
  useEffect(()=>setPanel(params.get('panel')),[params])
  useEffect(()=>()=>{runToken.current++},[])
  const [gid, setGid] = useState(Number(params.get('greenhouse_id')) || 0)
  const [greenhouses, setGreenhouses] = useState<{ value: number; label: string }[]>([])
  const [records, setRecords] = useState<RecordData[]>([]), [current, setCurrent] = useState<RecordData | null>(null)
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [actionId, setActionId] = useState('')
  const [explanation, setExplanation] = useState('')
  const [showAllCandidates,setShowAllCandidates]=useState(false)
  const [modelReady, setModelReady] = useState<boolean | null>(null)
  useEffect(() => { void getAIStatus().then(s => setModelReady(s.configured)).catch(() => setModelReady(false)) }, [])
  const [finish, setFinish] = useState(''), [startForm] = Form.useForm(), [form] = Form.useForm()
  const startZone=Form.useWatch('zone',startForm) as string|undefined
  const load = useCallback(async () => {
    if (!gid) return
    const list = guest ? readGuest().filter(r=>(r.greenhouse_id ?? 101)===gid) : await request<RecordData[]>('?greenhouse_id='+gid)
    setRecords(list); setCurrent(list[0] || null); setError('');setRunError(false); pausedRef.current=false;setPaused(false)
  }, [gid, guest])
  useEffect(() => { void getGreenhouses({ page: 1, page_size: 100 }).then(r => {
    setGreenhouses(r.items.map(g => ({ value: g.id, label: g.name })))
    if (!gid && r.items[0]) setGid(r.items[0].id)
  }).catch(e => setError(getApiErrorMessage(e))) }, [gid])
  useEffect(() => { void load().catch(e => setError(getApiErrorMessage(e))) }, [load])
  useEffect(() => {
    const next = current?.payload.analysis.next
    setActionId(next?.id || ''); form.resetFields(); setExplanation('')
    if(current)startForm.setFieldsValue({question:current.payload.question,zone:current.payload.zone,budget:current.payload.budget,unavailable_actions:current.payload.context.unavailable_actions||[]})
    form.setFieldsValue({ zone: next?.id === 'normal' ? zones.find(z => z !== current?.payload.zone) : current?.payload.zone, observed_at: localTime() })
  }, [current, form, startForm])
  const act = async (fn: () => Promise<void>) => {
    setBusy(true); setError('')
    try { await fn() } catch (e) { setError(getApiErrorMessage(e)); message.error(getApiErrorMessage(e)) } finally { setBusy(false) }
  }
  const persist = (record: RecordData) => {
    setCurrent(record); setRecords(old => [record, ...old.filter(r => r.id !== record.id)])
    if (guest) { try { sessionStorage.setItem(key, JSON.stringify([record, ...readGuest().filter(r => r.id !== record.id)].slice(0,20))) } catch { throw new Error('浏览器会话空间不足，请减少照片体积或登录保存正式档案') } }
  }
  const run = async (record:RecordData) => {
    if(inFlight.current || ['completed','archived'].includes(record.status))return
    const token=++runToken.current
    inFlight.current=true;setRunning(true);setError('');setRunError(false)
    try {
      let result:RecordData
      if(guest){
        const calculated=await demo({...record.payload,unavailable_actions:record.payload.context.unavailable_actions||[]})
        result={...record,...calculated,id:record.id,greenhouse_id:record.greenhouse_id??gid,photos:record.photos,payload:{...calculated.payload,history:record.payload.history,autonomy_runs:[...(record.payload.autonomy_runs||[]).slice(-19),{at:new Date().toISOString(),state:calculated.payload.analysis.next?'waiting_for_evidence':'review_required',steps:[
          {name:'已有证据',count:record.payload.evidence.length,detail:'已整理本次提交的观察与图片'},
          {name:'环境与生产记录',count:0,detail:'本次示例未关联正式监测记录'},
          {name:'候选解释与观察排序',count:calculated.payload.analysis.candidates.length,detail:'后端规则已重新计算，等待现场证据'}]}]}}
      }else result=await request<RecordData>('/'+record.id+'/refresh','post',{version:record.version})
      if(token===runToken.current)persist(result)
    } catch(e){if(token===runToken.current){setError(getApiErrorMessage(e));setRunError(true)}}
    finally{inFlight.current=false;if(token===runToken.current)setRunning(false)}
  }
  const save=(record:RecordData)=>{
    const next={...record,greenhouse_id:record.greenhouse_id??gid,payload:{...record.payload,autonomy_runs:record.payload.autonomy_runs??current?.payload.autonomy_runs}}
    persist(next)
    if(modeRef.current==='auto' && !pausedRef.current)void run(next)
  }
  const newInvestigation=()=>{
    if(running||busy||visionBusy)return
    runToken.current++;setCurrent(null);setRunError(false);setExplanation('');setError('');setFinish('');startForm.resetFields();pausedRef.current=false;setPaused(false)
  }
  const start = (values: { question: string; zone: string; budget: number }) => act(async () => {
    if (!gid) throw new Error('请先选择大棚')
    const record = guest ? { ...await demo(values), id: Date.now(), greenhouse_id:gid } : await request<RecordData>('', 'post', { ...values, greenhouse_id: gid })
    save(record)
  })
  const submit = (values: { zone: string; note?: string; humidity?: number; temperature?: number; features?: Record<string, boolean>; sensor_id?: number; observed_at: string }) => act(async () => {
    if (!current) return
    const evidence: Evidence = { ...values, action: actionId, note: values.note || '', features: Object.fromEntries(Object.entries(values.features || {}).filter(([key,value]) => value != null && action?.features.includes(key)).map(([key,value]) => [key, Number(value) === 1])), observed_at: new Date(values.observed_at).toISOString() }
    const record = guest ? { ...await demo({ ...current.payload, unavailable_actions:current.payload.context.unavailable_actions||[], evidence: [...current.payload.evidence, evidence] }), id: current.id, photos: current.photos }
      : await request<RecordData>('/'+current.id+'/evidence', 'post', { version: current.version, evidence })
    save({...record,payload:{...record.payload,history:guest?[...current.payload.history,{...record.payload.history.at(-1)!,round:current.payload.history.length}]:record.payload.history}}); message.success('证据已加入，候选解释和观察排序已重新计算')
  })
  const p = current?.payload, analysis = p?.analysis
  const latestRound = p?.history.at(-1)
  const changedLeader = latestRound?.previous_leader && latestRound.previous_leader !== latestRound.leader
  const action = analysis?.rankings.find(a => a.id === actionId)
  const closed = ['completed','archived'].includes(current?.status || '') || !analysis?.remaining
  const latestPhoto=p?.evidence.filter(e=>e.visual).at(-1)
  const displaySteps=[
    {name:p?.context.history.length?`已读取 ${p.context.history.length} 条环境记录`:'环境记录待补充',detail:p?.context.latest?'基于已关联的传感器数据进行分析。':'当前调查尚未关联可用监测记录。',source:'环境数据',ready:!!p?.context.latest},
    {name:p?.context.knowledge.length?'已查询相关农业知识':'农业知识待关联',detail:p?.context.knowledge.length?'检索症状特征与发生条件。':'本轮暂无检索匹配资料。',source:'农业知识库',ready:!!p?.context.knowledge.length},
    {name:latestPhoto?`已分析${actionNames[latestPhoto.action]}照片`:'叶片照片待补充',detail:latestPhoto?'图片特征已纳入证据，可人工修正。':'上传清晰照片以辅助比较候选原因。',source:'图片观察',ready:!!latestPhoto},
  ]
  const completedChecks=displaySteps.filter(s=>s.ready).length
  const locked=busy||running||visionBusy
  const closePanel=()=>openPanel(null)
  return <div className={`investigate-page iw-workspace${current?' has-case':''}`}>
    <header className="investigate-hero iw-hero"><div><small>AGRICULTURAL INVESTIGATION</small><h1 aria-label="棚智探因">棚智探因</h1><p>描述异常，上传叶片，让 AI 沿着证据主动排查。</p></div><Space wrap><Button onClick={()=>openPanel('history')}>调查记录{records.length>0?` · ${records.length}`:''}</Button><Button type="primary" disabled={locked} onClick={newInvestigation}>＋ 新建调查</Button></Space>{error&&<Alert type="error" showIcon message={error} action={<Button disabled={locked} onClick={()=>void act(load)}>重新读取</Button>}/>}</header>
    <div className="iw-toolbar"><Segmented aria-label="排查模式" value={mode} disabled={locked} options={[{value:'auto',label:'AI 自主排查'},{value:'guided',label:'引导排查'}]} onChange={value=>{setMode(value as 'auto'|'guided');pausedRef.current=false;setPaused(false);if(value==='auto'&&current)void run(current)}}/><span>{mode==='auto'?'自动查询与分析，现场检查时请你补充。':'自主选择检查 · 逐步补充证据'}</span><Select aria-label="调查大棚" disabled={locked} value={gid||undefined} options={greenhouses} onChange={value=>{runToken.current++;setGid(value);setParams(previous=>{const q=new URLSearchParams(previous);q.set('greenhouse_id',String(value));return q},{replace:true})}}/></div>

    <div className="iw-entry">
      <section className="iw-question"><div className="iw-section-title"><h2>描述异常</h2><span>01 / 问题</span></div>
        <Form name="investigation-start" form={startForm} layout="vertical" onFinish={v=>void start(v)} initialValues={{zone:'东侧',budget:3}} disabled={locked||!!current}>
          <Form.Item name="question" label="农业问题" rules={[{required:true,whitespace:true,min:4,message:'请描述至少4个字的问题，或直接上传叶片照片'}]}><Input.TextArea rows={2} maxLength={2000} placeholder="例如：东侧番茄叶片发黄，中央湿度正常，是什么原因？"/></Form.Item>
          <div className="iw-start-options"><Form.Item name="zone" label="异常位置"><Select options={zones.map(value=>({value,label:value}))}/></Form.Item><Form.Item name="budget" label="检查预算"><Select options={[{value:1,label:'1 次'},{value:2,label:'2 次'},{value:3,label:'3 次'},{value:0,label:'10 次'}]}/></Form.Item><Button type="primary" htmlType="submit" loading={busy} disabled={locked||!!current}>{current?(current.status==='completed'?'本次调查已归档':'调查进行中'):'开始调查 →'}</Button></div>
          <Collapse ghost items={[{key:'conditions',label:'设置可用检查条件',children:<Form.Item name="unavailable_actions" label="当前无法执行的检查"><Select mode="multiple" allowClear options={Object.entries(actionNames).map(([value,label])=>({value,label}))}/></Form.Item>}]}/>
        </Form>
      </section>
      <section className="iw-photo"><div className="iw-section-title"><h2>上传叶片</h2><span>02 / 图片</span></div><InvestigationVisionPanel compact disabled={busy||running} onBusy={setVisionBusy} initialZone={startZone} record={current} guest={guest} save={save} ensure={async()=>{
        if(current)return current
        if(!gid)throw new Error('请先选择大棚')
        const raw=startForm.getFieldsValue()
        if(!raw.question?.trim())startForm.setFieldValue('question','请排查这张番茄叶片照片中的异常')
        const values=await startForm.validateFields()
        const r=guest?{...await demo(values),id:Date.now(),greenhouse_id:gid}:await request<RecordData>('','post',{...values,greenhouse_id:gid})
        persist(r);return r
      }}/></section>
    </div>
    <div className="iw-context-strip"><span>♧ {p?'已整理本轮问题、环境与图片线索。':'等待问题与图片证据。'}</span><span className="iw-context-outcome">{p?'✓ 本轮分析已更新。':'开始后自动分析。'}</span><button type="button" aria-label="分析说明" onClick={()=>openPanel('about')}>ⓘ</button></div>
    <Spin spinning={busy}>
{p && analysis ? <>
      <section className={`pz-investigation-result${changedLeader ? ' has-change' : ''}`} aria-live="polite"><div><span className="pz-section-kicker">第 {latestRound?.round ?? p.history.length} 轮分析 · {p.evidence.length} 项补充观察</span><h2>{current?.status === 'completed' ? '调查已归档' : changedLeader ? '新证据，带来了新的调查方向' : '当前优先核查'}：{latestRound?.leader || analysis.candidates[0]?.name || '原因待核实'}</h2><p>{changedLeader ? `此前优先调查「${latestRound.previous_leader}」，现调整为「${latestRound.leader}」。具体支持与冲突见下方候选解释。` : p.final_note || analysis.summary}</p><small>{analysis.score_note}</small></div><div className="pz-budget-display"><b>{analysis.remaining}</b><span>剩余检查次数</span></div></section>
      <div className="investigate-columns">
        <section className="iw-evidence"><Card title="问题与证据"><h3 className="iw-evidence-question">{p.question}</h3><div className="iw-evidence-summary">{latestPhoto&&<div className="iw-evidence-preview">{current?.photos?.[latestPhoto.visual!.image_hash]?<img src={current.photos[latestPhoto.visual!.image_hash]} alt="本轮叶片证据"/>:latestPhoto.asset_id?<CommunityAsset asset={{id:latestPhoto.asset_id,filename:'叶片证据',media_type:'image/jpeg'}}/>:null}</div>}<div className="iw-evidence-facts"><span><LeafOutlined/>{latestPhoto?`${actionNames[latestPhoto.action]}已加入调查`:'叶片照片待补充'}</span><span>♧ {p.context.latest?.air_humidity!=null?`中央空气湿度 ${p.context.latest.air_humidity}% · 最近实测`:'环境数据待关联或补测'}</span><span>⌖ 异常位置 <b>{p.zone}</b> · 人工标记</span></div></div>
          <InvestigationSpatialMap zone={p.zone} counts={Object.fromEntries(zones.map(z=>[z,p.evidence.filter(e=>e.zone===z).length]))} onSelect={z=>modal.info({ title: z+'关联观察', okText:'用此区域补测', onOk:()=>{const detail=document.querySelector<HTMLDetailsElement>('.iw-observation-form');if(detail)detail.open=true;setActionId(z===p.zone?'local':'normal');form.resetFields();form.setFieldsValue({zone:z,observed_at:localTime()})}, content: <>{p.evidence.filter(e => e.zone === z).map((e,i) => <p key={i}>{actionNames[e.action]}：{e.note || '结构化测量'} · {e.humidity != null ? e.humidity+'%RH' : ''}</p>)}{!p.evidence.some(e => e.zone === z) && '暂无观察；图中区域为人工标记，不是已测热力图。'}</> })}/>
          <p className="iw-position-note investigate-muted">{p.context.position_note || '示例不含已知传感器坐标。'}</p>
          <details className="iw-source-details"><summary>＋ 补充证据与查看来源</summary>          {p.evidence.slice(-2).map((e,i) => <div className="investigate-evidence" key={e.action+i}><b>#{Math.max(0,p.evidence.length-2)+i+1} {e.zone} · {actionNames[e.action]}</b><p>{e.visual && (current?.photos?.[e.visual.image_hash]?<img className="iw-evidence-photo" src={current.photos[e.visual.image_hash]} alt="本轮叶片证据"/>:e.asset_id?<CommunityAsset asset={{id:e.asset_id,filename:'叶片证据',media_type:'image/jpeg'}}/>:null)}{e.note}</p><small>{new Date(e.observed_at).toLocaleString()}</small>{e.humidity != null && <p>湿度 {e.humidity}% · 温度 {e.temperature ?? '未填'}℃</p>}{Object.entries(e.features).map(([k,v]) => <Tag key={k}>{featureLabels[k]}：{v ? '有' : '未见'}</Tag>)}{e.asset_id && !e.visual && <CommunityAsset asset={{ id: e.asset_id, filename: '调查图片', media_type: 'image/jpeg' }} />}{!e.visual && current?.photos?.[e.action] && <img src={current.photos[e.action]} alt="游客观察图片" />}</div>)}
          <Collapse items={[{ key: 'context', label: '现有环境、预警与识别记录快照', children: <><p>历史记录仅作为背景，不能证明异常区当前状态。识别标签未必经过人工复核。</p><pre>{JSON.stringify({ crop: p.context.crop, batch: p.context.batch, latest: p.context.latest, fresh: p.context.fresh, gaps: p.context.gaps, warnings: p.context.warnings, diseases: p.context.diseases, operations: p.context.operations, history: p.context.history }, null, 2)}</pre></> }]} />
          <p className="investigate-muted">{analysis.spatial?.coverage}</p><Collapse items={[{key:'ledger',label:'多模态证据与空间测点',children:<pre>{JSON.stringify({evidence:analysis.evidence_ledger,spatial:analysis.spatial},null,2)}</pre>}]}/><h4>依据与知识</h4>{p.context.knowledge.length ? p.context.knowledge.map(k => <p key={k.id}>{k.title}{k.sources.map((s,i) => <span key={i}> · {s.url ? <a href={s.url} target="_blank" rel="noreferrer">{s.name}</a> : s.name}</span>)}</p>) : <p>暂无关联资料</p>}</details>
        </Card></section>
        <section className="iw-candidates"><Card title="候选原因"><p className="investigate-muted iw-candidate-intro">随证据动态调整，尚待核实</p>{analysis.candidates.slice(0,showAllCandidates?undefined:3).map((c,i) => <details className="investigate-candidate" key={c.id} open={false}><summary><span className="pz-candidate-rank">{String(i+1).padStart(2,'0')}</span><div className="iw-candidate-heading"><h3 title={c.name}>{({microclimate:"局部环境差异",leaf_mold:"叶霉等叶部病害",mites:"叶螨等虫害",water_stress:"灌溉或根区水分异常",leaf_spot:"叶斑类表现（待鉴别）",unknown:"其他原因 / 证据不足"} as Record<string,string>)[c.id]||c.name}{i===0&&<Tag className="iw-priority-tag">优先核查</Tag>}</h3><small>{c.support[0] || c.missing[0] || '仍需补充鉴别线索'}</small></div><span className="pz-candidate-score"><b>{c.score}</b><small>证据支持分</small></span></summary>
          <h4>支持线索</h4>{c.support.length ? c.support.map(s => <p key={s}>{s}</p>) : <p>尚无直接支持证据</p>}<h4>冲突或反对</h4>{c.conflict.length ? c.conflict.map(s => <p className="investigate-conflict" key={s}>{s}</p>) : <p>暂无；不代表已排除其他解释</p>}
          <Collapse items={[{ key:'missing', label: '缺少信息与关键鉴别特征', children: <><p>仍缺：{c.missing.join('；') || '本规则特征已填写，仍需人工复核'}</p><p>关键特征：{c.key_features.join('；') || '保留未知原因'}</p></> }]} />{c.sources.map(s => <p key={s.url}><a href={s.url} target="_blank" rel="noreferrer">{s.title}</a></p>)}
        </details>)}{analysis.candidates.length>3&&<Button type="link" className="iw-more-candidates" onClick={()=>setShowAllCandidates(v=>!v)}>{showAllCandidates?'收起其他候选':`查看其余 ${analysis.candidates.length-3} 个候选原因`}</Button>}<button type="button" className="iw-risk-link" onClick={()=>openPanel('risk')}><span>环境风险参考</span><small>查看病害时间机与历史环境关联</small><b>↗</b></button></Card></section>
        <section className="iw-autonomy"><Card title={<><LeafOutlined/>{mode==='auto'?'AI 自主排查':'引导排查'}</>}>
          <div className="iw-autonomy-state" role="status"><span className={running?'iw-status-dot is-running':'iw-status-dot'}/><strong>{running?'正在读取与分析':runError?'运行中断，请重试':closed?'本轮分析已结束':paused?'自主排查已暂停':mode==='auto'?'等待补充现场证据':'按你的节奏逐步排查'}</strong></div>
          <p className="investigate-muted">{mode==='auto'?'补充证据后自动更新分析，并选择下一项检查。':'选择检查项目，提交实际观察后更新判断。'}</p>
          <ol className="iw-run-steps iw-raw-run-steps">{(p.autonomy_runs?.at(-1)?.steps||[{name:'整理已有线索',count:p.evidence.length,detail:'已完成初步候选分析'}]).map(step=><li key={step.name}><span>✓</span><div><b>{step.name}</b><small>{step.detail}{step.count>0?` · ${step.count} 项`:''}</small></div></li>)}</ol>
          <p className="iw-stage-summary">{completedChecks?`已完成 ${completedChecks} 项资料分析`:'候选原因已生成'} · {analysis.next&&!closed?'需要 1 项现场证据':'本轮等待人工复核'}。</p>
          <ol className="iw-display-steps">{displaySteps.map(step=><li key={step.name} className={step.ready?'is-done':'is-unavailable'}><i>{step.ready?'✓':'–'}</i><div><b>{step.name}</b><p>{step.detail}</p></div><span>{step.source}</span></li>)}{analysis.next&&!closed&&<li className="is-waiting"><i>•</i><div><b>等待补充：{analysis.next.name.replace(/^拍摄/,'')}</b><p>{analysis.next.target}</p></div></li>}</ol>
          <div className="iw-next-label">下一步：{analysis.next?.name||'人工复核本轮线索'}</div>{analysis.next && !closed ? <><Tag className="iw-cost-tag">约{analysis.next.cost_minutes}分钟</Tag><h3>{analysis.next.name}</h3><p className="iw-next-target">{analysis.next.target}</p><p className="iw-next-reason">{analysis.next.reason}</p><p className="iw-observation-score">观察价值 {analysis.next.score}</p><p className="investigate-muted iw-budget-plan">本轮预算内的候选检查：{analysis.plan.map(a => a.name).join(' → ')}。每次提交后重新排序，后续安排会随证据变化。</p></> : <Empty description={closed ? '预算已用完或调查已归档' : '已无新的结构化鉴别项，请人工复核'} image={Empty.PRESENTED_IMAGE_SIMPLE} />}
          {!closed&&<Button block className="iw-upload-next" disabled={locked} onClick={()=>{if(['front','back','plant'].includes(analysis.next?.id||'')){document.querySelector<HTMLInputElement>('#investigation-vision input[type=file]')?.click()}else{const d=document.querySelector<HTMLDetailsElement>('.iw-observation-form');if(d)d.open=true}}}>↥ {['front','back','plant'].includes(analysis.next?.id||'')?'上传'+actionNames[analysis.next!.id]+'照片':'补充现场观察'}</Button>}
          {!closed&&<Button type="primary" block className="iw-submit-next" disabled={locked} onClick={()=>{const detail=document.querySelector<HTMLDetailsElement>('.iw-observation-form');if(detail){detail.open=true;detail.scrollIntoView({behavior:'smooth',block:'center'})}}}>提交证据，继续{mode==='auto'?'自主排查':'分析'} →</Button>}
          {!closed && <details className="iw-observation-form"><summary>补充本次检查结果</summary><Form name="investigation-observation" form={form} layout="vertical" disabled={busy||running||visionBusy} onFinish={v => void submit(v)}><Form.Item label="本次检查"><Select aria-label="本次检查" value={actionId || undefined} options={analysis.rankings.map(a => ({ value: a.id, label: a.name, disabled: a.can_execute===false }))} onChange={value => { setActionId(value); form.resetFields(); form.setFieldsValue({ zone: value === 'normal' ? zones.find(z => z !== p.zone) : p.zone, observed_at: localTime() }) }} /></Form.Item>
            <Form.Item name="zone" label="观察位置" rules={[{ required: true }]}><Select options={zones.map(value => ({ value, label: value }))} /></Form.Item>
            <Form.Item name="observed_at" label="观察时间" rules={[{ required: true }]}><Input type="datetime-local" /></Form.Item>
            {action?.features.filter(f => !['local_humid','humidity_gap'].includes(f)).map(f => <Form.Item key={action.id+f} name={['features',f]} label={featureLabels[f]}><Select allowClear placeholder="未检查 / 不确定" options={[{ value: 1, label: '是 / 看到了' }, { value: 0, label: '否 / 已检查未见' }]} /></Form.Item>)}
            {['local','normal'].includes(actionId) && <><Form.Item name="humidity" label="湿度（%RH）"><InputNumber min={0} max={100} style={{ width:'100%' }} /></Form.Item><Form.Item name="temperature" label="温度（℃）"><InputNumber min={-20} max={60} style={{ width:'100%' }} /></Form.Item><Form.Item name="height_cm" label="测量高度（厘米，可选）"><InputNumber min={0} max={500}/></Form.Item>{!guest && <Form.Item name="sensor_id" label="或关联本棚有效采样ID"><InputNumber min={1} precision={0} /></Form.Item>}</>}
            <Form.Item name="duration_seconds" label="实际检查用时（秒，可选）"><InputNumber min={0} max={36000}/></Form.Item><Form.Item name="note" label="观察说明"><Input.TextArea rows={3} maxLength={2000} placeholder="记录实际看到的结果、测量高度与设备；不确定的特征留空" /></Form.Item>
            <Button type="link" htmlType="button" onClick={() => { document.getElementById('investigation-vision')?.scrollIntoView({behavior:'smooth',block:'center'}) }}>上传照片作为新证据</Button><Button type="primary" htmlType="submit" loading={busy} disabled={running||visionBusy||!action}>提交证据并重新分析</Button>
          </Form></details>}
          <div className="iw-autonomy-controls">{runError&&<Button disabled={locked} onClick={()=>current&&void run(current)}>重新运行分析</Button>}{mode==='auto' && !closed && <Button disabled={busy||visionBusy} onClick={()=>{if(!paused){pausedRef.current=true;setPaused(true)}else{pausedRef.current=false;setPaused(false);void run(current!)}}}>{paused?'继续自主排查':'暂停自动更新'}</Button>}<Button onClick={()=>openPanel('process')}>查看执行记录</Button></div>

        </Card></section>
      </div>
      <section className="iw-progress"><header><h2>调查进展</h2><Button type="link" onClick={()=>openPanel('history')}>查看完整记录与人工核验 →</Button></header><ol>{(p.history.length>1?[p.history[0],p.history[p.history.length-1]]:p.history).map(h=><li key={h.at+h.round}><small>{new Date(h.at).toLocaleTimeString('zh-CN', {hour:'2-digit',minute:'2-digit'})}</small><b>{h.round===0?'接收问题与已有证据':'完成证据分析，更新调查方向'}</b><span>{h.previous_leader&&h.previous_leader!==h.leader?'新证据改变了优先调查方向':h.round===0?'已关联大棚与本轮提交的线索。':'当前优先核查：'+h.leader}</span></li>)}</ol><div className="iw-task-entry"><Button disabled={guest||!p.verification?.confirmed} href={!guest&&p.verification?.confirmed?'/platform/production?create=1&greenhouse_id='+gid:undefined}>♧ 核实后创建农事任务</Button><small>处理建议确认后再安排执行。</small></div></section>
</> : <div className="iw-empty-workbench"><section><h2>问题与证据</h2><div className="iw-empty-evidence"><LeafOutlined/><p>描述异常或上传叶片，开始收集本轮证据。</p></div><InvestigationSpatialMap zone={startZone||'东侧'} counts={{}} onSelect={z=>startForm.setFieldValue('zone',z)}/></section><section><h2>候选原因 <small>随证据动态调整，尚待核实</small></h2><div className="iw-no-candidates">提交问题后生成候选原因</div><button type="button" className="iw-risk-link" onClick={()=>openPanel('risk')}>环境风险参考（病害时间机）<b>›</b></button></section><section className="iw-empty-auto"><h2><LeafOutlined/>AI 自主排查</h2><span className="iw-empty-status">等待开始</span><p className="iw-stage-summary">提交问题后，自动整理证据并选择检查。</p><ol className="iw-display-steps">{['环境记录','农业知识','图片观察'].map(name=><li key={name} className="is-unavailable"><i>–</i><div><b>{name}待关联</b><p>开始调查后显示实际处理结果。</p></div></li>)}<li className="is-waiting"><i>•</i><div><b>等待描述异常或上传叶片</b><p>从你发现的问题开始。</p></div></li></ol><div className="iw-next-label">下一步：提供问题与证据</div><Button block type="primary" onClick={()=>document.getElementById('investigation-vision')?.querySelector<HTMLInputElement>('input[type="file"]')?.click()}>上传叶片，补充线索</Button><Button block onClick={()=>document.querySelector<HTMLTextAreaElement>('.iw-question textarea')?.focus()}>先描述异常 →</Button></section><section className="iw-progress iw-empty-progress"><header><h2>调查进展</h2><Button type="link" onClick={()=>openPanel('history')}>查看完整记录 ›</Button></header><p>调查开始后，在这里查看各轮分析与判断变化。</p></section></div>}</Spin>
    <Drawer title="调查记录与人工复核" open={panel==='history'} onClose={closePanel} width={1000} destroyOnHidden className="iw-detail-drawer">
      <div className="iw-drawer-content"><Select aria-label="历史调查" placeholder="选择本棚调查记录" disabled={locked} style={{width:'100%',marginBottom:20}} value={current?.id} options={records.map(r=>({value:r.id,label:r.payload.question+' · '+(r.status==='completed'?'已归档':'待核实')}))} onChange={id=>{setCurrent(records.find(r=>r.id===id)||null);pausedRef.current=true;setPaused(true)}}/>
      {p&&analysis?<><Collapse items={[{key:'observations',label:`全部观察与图片证据 · ${p.evidence.length} 项`,children:p.evidence.length?p.evidence.map((e,i)=><section className="iw-history-observation" key={i}><h3>#{i+1} {e.zone} · {actionNames[e.action]}</h3><p>{e.note||'结构化观察记录'}</p><small>{new Date(e.observed_at).toLocaleString()}</small>{e.humidity!=null&&<p>湿度 {e.humidity}%RH · 温度 {e.temperature??'未填'}℃</p>}{Object.entries(e.features).map(([k,v])=><Tag key={k}>{featureLabels[k]||k}：{v?'有':'未见'}</Tag>)}{e.visual&&<><p>图片分析：{e.visual.classifier.predicted_class_name||'无可靠病害类别'} · {e.visual.local_model}</p>{current?.photos?.[e.visual.image_hash]?<img src={current.photos[e.visual.image_hash]} alt={'观察照片'+(i+1)}/>:e.asset_id?<CommunityAsset asset={{id:e.asset_id,filename:'观察照片',media_type:'image/jpeg'}}/>:null}</>}</section>):<Empty description="尚未提交现场观察"/>}]} /><Card title="调查时间线 · 判断如何变化"><Timeline items={p.history.map(h => ({ children: <><b>第{h.round}轮 · 优先调查：{h.leader}</b>{h.previous_leader && <p>上一轮：{h.previous_leader}</p>}<p>{h.changes.map(c => c.name+' '+c.before+'→'+c.after).join('；')}</p><small>{new Date(h.at).toLocaleString()}</small><Collapse items={[{ key:'snapshot',label:'查看该轮完整候选与观察排序',children:<pre>{JSON.stringify(h.analysis,null,2)}</pre> }]} /></> }))} />
        {current?.status !== 'completed' && <Space.Compact style={{ width:'100%' }}><Input aria-label="最终排查记录" value={finish} onChange={e => setFinish(e.target.value)} placeholder="填写人工排查结果或仍待核实事项（至少4字）" /><Button disabled={locked||finish.trim().length<4} onClick={() => void act(async () => { if (guest) save({ ...current!, status:'completed', payload:{ ...p,final_note:finish } }); else save(await request<RecordData>('/'+current?.id+'/finish','post',{ version: current?.version,note:finish })); setFinish('') })}>记录并归档</Button></Space.Compact>}
        {!guest && <Button href={'/platform/research?greenhouse_id='+gid}>返回关联大棚 AI 研究台</Button>}
      </Card>
</>:<Empty description="还没有调查记录"/>}
      <Button onClick={()=>openPanel('recognition')}>查看既有叶片识别与复核记录 →</Button>
      <InvestigationExperiencePanel record={current} gid={gid} guest={guest} save={persist}/></div>
    </Drawer>
    <Drawer title="环境风险参考 · 病害时间机" open={panel==='risk'} onClose={closePanel} width={1080} destroyOnHidden className="iw-detail-drawer">{panel==='risk'&&<Suspense fallback={<Spin/>}><RiskPanel/></Suspense>}</Drawer>
    <Drawer title="叶片识别与复核记录" open={panel==='recognition'} onClose={closePanel} width={1100} destroyOnHidden className="iw-detail-drawer">{panel==='recognition'&&<Suspense fallback={<Spin/>}><RecognitionPanel viewOverride="history"/></Suspense>}</Drawer>
    <Drawer title="自主排查执行记录" open={panel==='process'} onClose={closePanel} width={640} destroyOnHidden><div className="iw-process-log">{paused&&<Alert type="info" message={running?'暂停将在当前请求返回后生效；后续证据不再自动触发分析。':'自动更新已暂停，已有分析结果保留。'}/>}<p>仅列出实际完成的读取和计算；现场拍摄、测量需由你完成。</p>{p?.autonomy_runs?.length?p.autonomy_runs.slice().reverse().map((r,i)=><section className="iw-run-log-entry" key={r.at+i}><h3>{new Date(r.at).toLocaleString()}</h3>{r.steps.map(step=><p key={step.name}>✓ {step.name} · {step.detail}（{step.count} 项）</p>)}<Tag>{r.state==='waiting_for_evidence'?'等待补充证据':'待人工复核'}</Tag></section>):<Empty description="尚无自主排查执行记录"/>}{p&&analysis&&<section><h3>分析详情</h3>          <Collapse items={[{ key:'scores', label:'查看完整观察评分与排序', children: analysis.rankings.map(a => <div key={a.id}><h4>{a.name} · {a.score}</h4><p>区分度{a.discrimination} × 缺失度{a.missing_ratio.toFixed(2)} − {a.cost_penalty} × {a.cost_minutes}分钟</p><p>{a.distinguishes.join('、')}</p></div>) }]} />
          <Button disabled={guest || modelReady !== true || running || visionBusy} loading={busy} onClick={() => void act(async () => { const r = await request<{ mode: string; text: string }>('/'+current?.id+'/explain','post'); setExplanation((r.mode === 'rules_only' ? '模型不可用 · ' : '模型解释 · ')+r.text) })}>让棚小智解释（调用已配置模型）</Button>
          {explanation && <CommunityMarkdown>{explanation}</CommunityMarkdown>}</section>}</div></Drawer>
    <Drawer title="分析说明" open={panel==='about'} onClose={closePanel} width={520}><p>{guest?'本次为独立体验调查，记录与图片保存在当前浏览器会话。':'记录按现有组织与大棚权限保存。'}</p><p>自主排查自动整理已有记录、运行证据评分与下一项观察选择；不代替现场拍摄、测量，也不会自动操作设备。</p><p>支持分是可解释的规则评分，不是病害概率。形成处置方案前请人工复核。</p><p>{guest?'当前使用本地视觉与规则分析。':modelReady?'模型已配置，可主动点击棚小智解释；图片模型需单独勾选授权。':'模型未配置或不可用，本地视觉与规则分析仍可使用。'}</p></Drawer>
  </div>
}
