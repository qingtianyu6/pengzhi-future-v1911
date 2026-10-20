import { createGuestResearchTasks, guestResearchContext } from './guestDemoApi'
import type { Comparison, GrowthArchive, Observation, ResearchRecord, ScenarioCandidate } from '../types/agronomist'

interface GuestStore { records: ResearchRecord[]; observations: (Observation & { greenhouse_id: number; crop_batch_id: number })[] }
type Input = Record<string, unknown>
const key = 'pengzhi_agronomist_demo_v1'
const stamp = () => new Date().toISOString()
const protocol = ['在相同区域记录处理前观察和环境采样时间', '记录操作内容、天气和灌溉等伴随变化', '同一区域记录处理后观察，并增加可比对照区', '比较同名指标，保留反例和缺失数据']
function load(): GuestStore {
  try { return JSON.parse(sessionStorage.getItem(key) || '{"records":[],"observations":[]}') }
  catch { return { records: [], observations: [] } }
}

export function guestAgronomist(path: string, method: string, input: object): unknown {
  const p = input as Input, state = load()
  const target = path.match(/^records\/(\d+)\/actions$/)
  const item = target ? state.records.find(r => r.id === Number(target[1])) : undefined
  const gid = item?.greenhouse_id ?? Number(p.greenhouse_id)
  const { greenhouse, readings, tasks } = guestResearchContext(gid)
  const batch = greenhouse.active_batch!
  if (p.crop_batch_id && Number(p.crop_batch_id) !== batch.id) throw new Error('游客批次不属于当前大棚')
  const records = state.records.filter(r => r.greenhouse_id === gid && r.crop_batch_id === batch.id)
  const observations = state.observations.filter(o => o.greenhouse_id === gid && o.crop_batch_id === batch.id)
  const last = readings.at(-1)!
  const linked = (id: unknown, kind: string) => {
    if (!id) return undefined
    const r = records.find(r => r.id === Number(id) && r.kind === kind)
    if (!r) throw new Error('关联记录不属于当前大棚和批次')
    return structuredClone(r)
  }
  const persist = (result: unknown) => { sessionStorage.setItem(key, JSON.stringify(state)); return result }
  const add = (kind: ResearchRecord['kind'], title: string, payload: ResearchRecord['payload'], status = 'draft') => {
    const r: ResearchRecord = { id: Date.now() + state.records.length, greenhouse_id: gid, crop_batch_id: batch.id, kind, title, status, payload, version: 1, created_at: stamp(), updated_at: stamp() }
    state.records.unshift(r)
    return persist(r)
  }
  if (path === 'records' && method === 'get') return { records, tasks: tasks.map(({ id, title, status }) => ({ id, title, status })) }
  if (path === 'archive') {
    const metrics: GrowthArchive['metrics'] = {}
    for (const metric of ['temperature', 'air_humidity', 'soil_moisture'] as const) {
      const vals = readings.map(r => r[metric])
      metrics[metric] = { mean: Number((vals.reduce((a, b) => a+b, 0)/vals.length).toFixed(2)), min: Math.min(...vals), max: Math.max(...vals) }
    }
    return { greenhouse, batch, batches: [batch], latest: last, fresh: true, history: readings,
      metrics, sample_count: readings.length, observations, gaps: observations.length ? [] : ['尚未记录作物观察，可以先添加一条观察体验完整流程'],
      timeline: [...observations.map(o => ({ id: `observation-${o.id}`, at: o.observed_at, type: 'observation', title: o.note, detail: o.zone, source_id: o.id })),
        ...tasks.map(t => ({ id: `task-${t.id}`, at: t.updated_at, type: 'task', title: t.title, detail: t.status, source_id: t.id }))].sort((a, b) => b.at.localeCompare(a.at)),
      task_counts: Object.fromEntries(['draft', 'pending', 'in_progress', 'completed'].map(s => [s, tasks.filter(t => t.status === s).length])), open_warnings: 1,
      window_note: '游客示例数据；新增研究记录与关联任务保存在当前浏览器会话，刷新可继续。' } satisfies GrowthArchive
  }
  if (path === 'observations') {
    const study = linked(p.study_id, 'study')
    if (study && study.status !== 'running') throw new Error('请先启动研究')
    const metrics = (p.metrics || {}) as Record<string, number>
    if (!String(p.note || '').trim() || Object.values(metrics).some(v => !Number.isFinite(v) || v < 0) || (metrics.leaf_wetness_pct || 0) > 100) throw new Error('请填写观察内容和有效数值')
    const o = { id: Date.now(), greenhouse_id: gid, crop_batch_id: batch.id, study_id: Number(p.study_id) || null, observed_at: String(p.observed_at || stamp()), phase: String(p.phase || 'routine'), zone: String(p.zone || '全棚'), note: String(p.note), metrics }
    state.observations.push(o)
    return persist({ id: o.id })
  }
  if (path === 'scenarios') {
    const duration = Number(p.duration_minutes), intensity = Number(p.intensity)
    const candidates: ScenarioCandidate[] = ['维持当前条件（静态参照）', '通风方案', '除湿方案'].map((name, index) => {
      const timeline = Array.from({ length: duration/10 }, (_, i) => {
        const factor = (1-Math.exp(-(i+1)*10/30))/(1-Math.exp(-1)) * (index ? intensity : 0)/30
        return { minute: (i+1)*10, temperature: Number((last.temperature-(index === 2 ? 0.4 : 2.4)*factor).toFixed(1)), humidity: Number(Math.max(0, last.air_humidity-(index === 2 ? 7.8 : 5.8)*factor).toFixed(1)) }
      })
      return { name, action: index === 2 ? 'dehumidify' : 'ventilation', intensity: index ? intensity : 0, timeline, end: timeline.at(-1)! }
    })
    return add('scenario', `${duration}分钟环境方案比较`, { baseline: { sensor_record_id: last.id, recorded_at: last.recorded_at, temperature: last.temperature, humidity: last.air_humidity }, duration_minutes: duration, candidates, method: '游客示例响应系数推演', note: '示例推演，不代表真实设备响应、天气变化或生产效果。' }, 'completed')
  }
  if (path === 'studies') return add('study', String(p.question), { question: String(p.question), hypothesis: String(p.hypothesis || '检查环境与农事时间、区域差异之间的关系'), protocol, alternatives: ['外部天气', '灌溉与新增湿源', '通风时机'], source_snapshot: linked(p.scenario_id, 'scenario'), conclusion: null })
  if (path === 'goals') {
    if (p.use_ai) throw new Error('游客模式请使用结构化编排；登录并配置模型后可生成 AI 定制计划')
    const links: Record<string, ResearchRecord> = {}
    for (const kind of ['scenario', 'skill', 'study']) {
      const r = linked(p[`${kind}_id`], kind)
      if (r) { if (kind === 'skill' && r.status !== 'active') throw new Error('请选择已启用技能'); links[kind] = r }
    }
    const goal = String(p.goal)
    const humidity = /湿|通风|结露/.test(goal), heat = /温|热|降温/.test(goal), water = /水|灌溉|土壤/.test(goal)
    const action = humidity ? 'humidity_control' : heat ? 'shading_check' : water ? 'irrigation_check' : 'manual_observation'
    const names = ['采集目标基线', humidity ? '检查通风与湿源' : heat ? '检查遮阳与通风' : water ? '检查土壤与灌溉' : '开展现场检查', '复查环境与作物', '整理结果与经验']
    return add('goal', goal, { goal, links, task_ids: [], planner: '结构化目标编排 v1 · 游客体验', steps: names.map((title, i) => ({ title, action_type: i === 0 ? 'sensor_inspection' : i === 1 ? action : 'manual_observation', description: `目标：${goal}。${title}并记录实际情况。${i === 1 && links.skill ? `参考技能：${(links.skill.payload.steps || []).join('；')}` : ''}`, depends_on: i ? [i-1] : [] })) })
  }
  if (!item || item.version !== Number(p.version)) throw new Error('记录已变化，请刷新后操作')
  const action = p.action
  if (action === 'derive_skill' && item.kind === 'study') {
    const prior = records.find(r => r.kind === 'skill' && r.payload.source_study_id === item.id)
    if (prior) return prior
    return add('skill', `${item.title} · 农事技能`, { source_study_id: item.id, source_snapshot: structuredClone(item), steps: item.payload.protocol, applicability: '本批次观察条件；跨棚使用需重新核对', validation: '待验证流程，不代表已证实生产效果' })
  }
  if (action === 'start' && item.kind === 'study' && item.status === 'draft') item.status = 'running'
  else if (action === 'complete' && item.kind === 'study' && item.status === 'running') {
    const obs = observations.filter(o => o.study_id === item.id), comparisons: Comparison[] = []
    const before = obs.filter(o => o.phase === 'before'), after = obs.filter(o => o.phase === 'after')
    for (const zone of new Set(before.map(o => o.zone))) {
      const b = before.filter(o => o.zone === zone), a = after.filter(o => o.zone === zone)
      if (!a.length) continue
      if (Math.max(...b.map(o => Date.parse(o.observed_at))) >= Math.min(...a.map(o => Date.parse(o.observed_at)))) throw new Error('处理后观察时间应晚于处理前')
      for (const metric of new Set(b.flatMap(o => Object.keys(o.metrics)))) {
        const bv = b.filter(o => metric in o.metrics).map(o => o.metrics[metric]), av = a.filter(o => metric in o.metrics).map(o => o.metrics[metric])
        if (!av.length) continue
        const bm = bv.reduce((x, y) => x+y, 0)/bv.length, am = av.reduce((x, y) => x+y, 0)/av.length
        comparisons.push({ zone, metric, before: bm, after: am, delta: am-bm, before_n: bv.length, after_n: av.length })
      }
    }
    if (!comparisons.length) throw new Error('请先添加同区域同指标的处理前后观察')
    item.payload.conclusion = { comparisons, interpretation: '示例观察均值变化，不代表因果效果或独立试验重复数。', note: String(p.note || '') }
    item.status = 'completed'
  } else if (['activate', 'disable'].includes(String(action)) && item.kind === 'skill' && item.status !== 'archived') item.status = action === 'activate' ? 'active' : 'disabled'
  else if (action === 'execute' && item.kind === 'goal' && item.status === 'draft') {
    item.payload.task_ids = createGuestResearchTasks(gid, item.id, item.payload.steps as { title: string; action_type: string; description: string; depends_on: number[] }[])
    item.status = 'running'
  } else if (action === 'complete' && item.kind === 'goal' && item.status === 'running') {
    if (!item.payload.task_ids?.length || item.payload.task_ids.some(id => tasks.find(t => t.id === id)?.status !== 'completed')) throw new Error('请先完成全部关联农事任务')
    item.status = 'completed'
  } else if (action === 'archive') item.status = 'archived'
  else throw new Error('当前状态不支持该操作')
  item.version++; item.updated_at = stamp()
  return persist(item)
}
