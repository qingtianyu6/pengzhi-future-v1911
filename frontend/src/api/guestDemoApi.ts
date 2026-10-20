import { AxiosError } from 'axios'
import type { CropBatch } from '../types/cropBatch'
import type { DeviceBinding, GreenhouseDevice, Greenhouse } from '../types/greenhouse'
import type { DiseaseRecord, DiseaseIdentification, DiseaseModelStatus } from '../types/disease'
import type { EnvironmentPrediction } from '../types/prediction'
import type { WarningEvent } from '../types/warning'
import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import type { CurrentDecision, DecisionRecommendation, RecommendationStatus } from '../types/decision'
import type { FarmTask } from '../types/task'
import type { DecisionPlan, GreenhouseRiskResponse, RiskEvent, RiskItem } from '../types/v2Decision'
import { isGuestMode } from './guestMode'

const now = new Date()
const iso = (offsetMinutes = 0) => new Date(now.getTime() + offsetMinutes * 60_000).toISOString()

const demoBatch: CropBatch = {
  id: 9001,
  greenhouse_id: 101,
  batch_code: 'DEMO-TOMATO-01',
  variety: '番茄 · 金棚一号',
  crop_type: 'tomato',
  planted_at: iso(-42 * 24 * 60),
  expected_harvest_at: iso(48 * 24 * 60),
  growth_stage: '开花坐果期',
  growth_day: 42,
  stage_updated_at: iso(-80),
  is_stage_manually_set: false,
  status: 'growing',
  created_at: iso(-42 * 24 * 60),
  updated_at: iso(-20),
}

const demoGreenhouses: Greenhouse[] = [
  {
    id: 101,
    code: 'GUEST-A01',
    name: '游客体验番茄棚',
    location: '山东莘县演示基地',
    area_mu: '3.6',
    status: 'active',
    manager_name: '体验用户',
    created_at: iso(-90 * 24 * 60),
    updated_at: iso(-15),
    active_batch: demoBatch,
  },
  {
    id: 102,
    code: 'GUEST-B02',
    name: '游客体验甜瓜棚',
    location: '寿光智慧园区',
    area_mu: '2.8',
    status: 'active',
    manager_name: '体验用户',
    created_at: iso(-72 * 24 * 60),
    updated_at: iso(-30),
    active_batch: { ...demoBatch, id: 9002, greenhouse_id: 102, batch_code: 'DEMO-MELON-01', variety: '甜瓜 · 绿宝', crop_type: 'muskmelon', growth_stage: '果实膨大期' },
  },
]

// Guest changes remain local to this tab and never reach business tables.
try {
  const saved: unknown = JSON.parse(sessionStorage.getItem('pengzhi-greenhouses-v1') || 'null')
  if (Array.isArray(saved) && saved.every(g => g && typeof g.id === 'number' && typeof g.name === 'string' && typeof g.code === 'string' && typeof g.area_mu === 'string' && ['active','paused','closed'].includes(g.status))) {
    demoGreenhouses.splice(0, demoGreenhouses.length, ...(saved as Greenhouse[]))
  }
} catch { /* start with the isolated example workspace */ }
function saveGuestGreenhouses() {
  sessionStorage.setItem('pengzhi-greenhouses-v1',JSON.stringify(demoGreenhouses))
}

function guestDevices(greenhouseId: number): GreenhouseDevice[] {
  let bindings: Record<string, DeviceBinding[]> = {}
  try { bindings = JSON.parse(sessionStorage.getItem('pengzhi-device-bindings-v1') || '{}') } catch { /* empty session */ }
  const rows: GreenhouseDevice[] = [101, 102].includes(greenhouseId)
    ? [{greenhouse_id:greenhouseId,device_id:'DEMO-SENSOR',name:'环境传感器',kind:'environment',registered:false,last_seen:iso(),online:true}] : []
  for (const device of bindings[String(greenhouseId)] || []) {
    const row = rows.find(r=>r.device_id===device.device_id)
    if(row) Object.assign(row,device,{registered:true})
    else rows.push({...device,greenhouse_id:greenhouseId,registered:true,last_seen:null,online:false})
  }
  return rows
}
function guestGreenhouseState(g: Greenhouse): Greenhouse {
  const devices=guestDevices(g.id)
  return {...g,last_recorded_at:[101,102].includes(g.id)?iso():null,
    data_status:[101,102].includes(g.id)?'current':'no_data',device_count:devices.length,
    online_device_count:devices.filter(d=>d.online).length}
}

const readings = Array.from({ length: 24 }, (_, index) => {
  const hour = index - 23
  const wave = Math.sin((index / 24) * Math.PI * 2)
  return {
    id: 7000 + index,
    greenhouse_id: 101,
    recorded_at: iso(hour * 60),
    device_id: 'DEMO-SENSOR',
    temperature: Number((24.8 + wave * 3.2).toFixed(1)),
    air_humidity: Math.round(68 - wave * 8),
    soil_moisture: Math.round(54 + wave * 4),
    light_intensity: Number(Math.max(0, 34 + wave * 28).toFixed(1)),
    co2_concentration: Math.round(760 + wave * 90),
    source: 'sensor',
    quality_flag: 'valid',
  }
})

const warning = {
  id: 501,
  greenhouse_id: 101,
  crop_batch_id: 9001,
  crop_type: 'tomato',
  crop_rule_version: 'demo-rule-v1',
  crop_match_status: 'matched',
  cross_region_warning: false,
  expert_calibration_required: false,
  warning_code: 'DEMO-WARN-001',
  warning_type: 'humidity_risk',
  severity: 'attention',
  risk_score: 62,
  certainty: 'possible',
  title: '夜间湿度偏高，建议加强通风',
  description: '过去 2 小时空气湿度偏高，叶面结露风险上升。',
  evidence_json: { air_humidity: 82, temperature: 22.6 },
  forecast_start_at: iso(30),
  forecast_end_at: iso(180),
  status: 'open',
  fingerprint: 'guest-demo-warning',
  rule_version: 'demo-rule-v1',
  forecast_service_version: 'demo',
  forecast_methods_json: { method: 'guest-demo' },
  data_source: 'sensor',
  calibration_status: 'demo',
  first_triggered_at: iso(-70),
  last_triggered_at: iso(-12),
  acknowledged_at: null,
  acknowledged_by: null,
  acknowledgement_note: null,
  resolved_at: null,
  resolved_by: null,
  resolution_note: null,
  dismissed_at: null,
  dismissed_reason: null,
  created_at: iso(-70),
  updated_at: iso(-12),
}

function currentGuestWarning(gid: number): WarningEvent {
  let saved: Partial<WarningEvent> = {}
  try { saved = JSON.parse(sessionStorage.getItem(`pengzhi-warning-${gid}`) || '{}') } catch { /* new session */ }
  const gh=demoGreenhouses.find(g=>g.id===gid)
  return {...warning,...saved,greenhouse_id:gid,crop_batch_id:gh?.active_batch?.id??null,crop_type:gh?.active_batch?.crop_type??'unknown'} as WarningEvent
}

const tasks: FarmTask[] = [
  {
    id: 801,
    task_code: 'DEMO-TASK-001',
    greenhouse_id: 101,
    crop_batch_id: 9001,
    crop_type: 'tomato',
    source_type: 'warning',
    source_id: 501,
    source_warning_id: 501,
    source_disease_record_id: null,
    source_recommendation_id: 601,
    title: '开启顶窗通风 30 分钟',
    description: '降低夜间湿度，减少叶面结露。',
    action_type: 'ventilation',
    priority: 'high',
    status: 'pending',
    assignee_name: '现场执行员',
    planned_start_at: iso(20),
    due_at: iso(120),
    requires_manual_confirmation: true,
    safety_note: '请确认外部风速和降雨情况后执行。',
    evidence_snapshot_json: { warning_id: 501 },
    result_snapshot_json: null,
    version: 1,
    created_by: '游客演示',
    created_at: iso(-45),
    updated_at: iso(-20),
    started_at: null,
    completed_at: null,
    cancelled_at: null,
    cancellation_reason: null,
  },
  {
    id: 802,
    task_code: 'DEMO-TASK-002',
    greenhouse_id: 101,
    crop_batch_id: 9001,
    crop_type: 'tomato',
    source_type: 'manual',
    source_id: null,
    source_warning_id: null,
    source_disease_record_id: null,
    source_recommendation_id: null,
    title: '巡检滴灌管路',
    description: '检查 A 区滴灌压力和堵塞情况。',
    action_type: 'manual_observation',
    priority: 'medium',
    status: 'in_progress',
    assignee_name: '农技员',
    planned_start_at: iso(-30),
    due_at: iso(240),
    requires_manual_confirmation: true,
    safety_note: '仅记录观察结果，不自动控制设备。',
    evidence_snapshot_json: {},
    result_snapshot_json: null,
    version: 2,
    created_by: '游客演示',
    created_at: iso(-120),
    updated_at: iso(-18),
    started_at: iso(-20),
    completed_at: null,
    cancelled_at: null,
    cancellation_reason: null,
  },
]

const initialTask = { ...tasks[0] }

function guestTaskPage(config: InternalAxiosRequestConfig) {
  const filters = config.params ?? {}
  const filtered = tasks.filter((task) =>
    (!filters.greenhouse_id || task.greenhouse_id === Number(filters.greenhouse_id)) &&
    (!filters.status || task.status === filters.status) &&
    (!filters.priority || task.priority === filters.priority) &&
    (!filters.source_type || task.source_type === filters.source_type) &&
    (!filters.assignee_name || task.assignee_name?.includes(String(filters.assignee_name)))
  )
  const number = Number(filters.page) || 1
  const size = Number(filters.page_size) || 10
  return { items: filtered.slice((number - 1) * size, number * size), total: filtered.length, page: number, page_size: size }
}

function guestTaskSummary(greenhouseId?: number) {
  const current = tasks.filter((task) => !greenhouseId || task.greenhouse_id === greenhouseId)
  return {
    draft_total: current.filter((task) => task.status === 'draft').length,
    pending_total: current.filter((task) => task.status === 'pending').length,
    in_progress_total: current.filter((task) => task.status === 'in_progress').length,
    completed_today: current.filter((task) => task.status === 'completed').length,
    overdue_total: 0,
    urgent_total: current.filter((task) => task.priority === 'urgent' && task.status !== 'completed').length,
  }
}

function createGuestTask(input: Record<string, unknown>) {
  const greenhouseId = Number(input.greenhouse_id) || 101
  const batch = demoGreenhouses.find(g=>g.id===greenhouseId)?.active_batch
  if (!batch) throw new Error('请先为目标大棚创建种植批次')
  const id = Math.max(...tasks.map((item) => item.id), 800) + 1
  const task: FarmTask = {
    ...initialTask,
    id,
    task_code: `GUEST-TASK-${id}`,
    greenhouse_id: greenhouseId,
    crop_batch_id: batch.id,
    crop_type: batch.crop_type,
    source_type: 'manual',
    source_id: null,
    source_warning_id: null,
    source_disease_record_id: null,
    source_recommendation_id: null,
    title: String(input.title || '新建农事任务'),
    description: String(input.description || ''),
    action_type: String(input.action_type || 'manual_observation'),
    priority: (['low', 'medium', 'high', 'urgent'].includes(String(input.priority)) ? String(input.priority) : 'medium') as FarmTask['priority'],
    status: 'draft',
    assignee_name: null,
    planned_start_at: input.planned_start_at ? String(input.planned_start_at) : null,
    due_at: input.due_at ? String(input.due_at) : null,
    created_by: String(input.created_by || '游客'),
    created_at: iso(),
    updated_at: iso(),
    started_at: null,
    completed_at: null,
    cancelled_at: null,
    version: 1,
  }
  tasks.unshift(task)
  window.dispatchEvent(new Event('guest-tasks-changed'))
  return task
}

const recommendation = {
  id: 601,
  warning_event_id: 501,
  greenhouse_id: 101,
  title: '分段通风并复测湿度',
  action_type: 'ventilation',
  priority: 'high',
  status: 'pending',
  recommendation_text: '建议先开启顶窗 30 分钟，复测湿度后再决定是否延长通风。',
  evidence_json: { confidence: 0.78 },
  safety_note: '执行前确认棚外无强降雨。',
  created_at: iso(-35),
  updated_at: iso(-10),
}

const guestRecommendationStatuses = new Map<number, RecommendationStatus>()

function demoRecommendation(greenhouseId: number): DecisionRecommendation {
  const guestRecommendationStatus = guestRecommendationStatuses.get(greenhouseId) ?? 'pending_review'
  return {
    id: recommendation.id,
    warning_event_id: warning.id,
    greenhouse_id: greenhouseId,
    crop_batch_id: greenhouseId === 102 ? 9002 : 9001,
    crop_type: greenhouseId === 102 ? 'muskmelon' : 'tomato',
    crop_rule_version: 'demo-rule-v1',
    recommendation_code: 'DEMO-VENT-001',
    priority: 'high',
    action_type: 'ventilation',
    title: recommendation.title,
    rationale: recommendation.recommendation_text,
    action_steps_json: ['检查棚外风速和降雨情况', '分段开启顶窗通风 30 分钟', '复测棚内温湿度并记录'],
    execute_before: iso(120),
    safety_note: recommendation.safety_note,
    status: guestRecommendationStatus,
    rule_version: 'demo-rule-v1',
    generated_at: recommendation.created_at,
    reviewed_at: guestRecommendationStatus === 'pending_review' ? null : iso(),
    review_note: null,
    task_draft: null,
  }
}

function demoCurrentDecision(greenhouseId: number): CurrentDecision {
  return {
    greenhouse_id: greenhouseId,
    crop_batch_id: greenhouseId === 102 ? 9002 : 9001,
    crop_type: greenhouseId === 102 ? 'muskmelon' : 'tomato',
    crop_rule_version: 'demo-rule-v1',
    crop_match_status: 'matched',
    cross_crop_warning: false,
    cross_region_warning: false,
    validation_status: 'demo',
    decision_scope: 'guest-demo',
    forecast_strategy: 'demo',
    growth_stage: greenhouseId === 102 ? '果实膨大期' : '开花坐果期',
    data_source: 'sensor',
    calibration_status: 'demo',
    current_risk_level: 'attention',
    future_risk_timeline: [],
    recommendations: [demoRecommendation(greenhouseId)],
    disclaimer: '游客体验数据不会存档，不可用于实际生产决策。',
  }
}

function taskDetail(task = tasks[0]) {
  const greenhouse = demoGreenhouses.find((item) => item.id === task.greenhouse_id) ?? demoGreenhouses[0]
  return {
    ...task,
    greenhouse,
    crop_batch: greenhouse.active_batch,
    source_warning: task.source_warning_id ? currentGuestWarning(task.greenhouse_id) : null,
    source_disease_record: null,
    source_recommendation: task.source_recommendation_id ? { ...recommendation, steps: demoRecommendation(task.greenhouse_id).action_steps_json, rationale: recommendation.recommendation_text } : null,
    events: [
      { id: 1, task_id: task.id, event_type: 'created', from_status: null, to_status: task.status, operator: '游客演示', note: '临时体验数据，不会存档', payload_json: {}, created_at: task.created_at },
    ],
    feedbacks: [],
    attachments: [],
    causality_notice: '游客模式下只演示流程，操作不会写入数据库。',
  }
}

function risk() {
  return {
    data_status: 'sufficient',
    growth_stage: '开花坐果期',
    component_scores: { humidity: 62, temperature: 35 },
    overall_score: 48,
    level: 'attention',
    reasons: ['夜间湿度偏高，建议关注通风窗口。'],
    rule_version: 'demo-rule-v1',
    crop_type: 'tomato',
    rule_scope: 'guest-demo',
    expert_calibration_required: false,
    disclaimer: '游客演示数据仅用于体验，不作为生产建议。',
  }
}

const demoRisk: RiskItem = {
  disease_type: 'gray_mold',
  disease_name: '灰霉病',
  current_score: 42,
  risk_24h: 51,
  risk_48h: 59,
  risk_72h: 66,
  risk_level: '高',
  trend: '上升',
  factors: {
    contributions: [
      { key: 'humidity', label: '连续高湿', feature_score: 82, weight: 0.4, value: 32.8 },
      { key: 'temperature', label: '昼夜温差', feature_score: 55, weight: 0.2, value: 11 },
    ],
    features: { air_humidity: 82, temperature: 24.8 },
    rule: { version: 'guest-demo' },
  },
  explanation: '近期湿度偏高，未来 72 小时病害风险可能上升。',
}

function demoRiskEvent(greenhouseId: number): RiskEvent {
  return {
    id: greenhouseId * 10 + 1,
    greenhouse_id: greenhouseId,
    crop_batch_id: greenhouseId === 102 ? 9002 : 9001,
    risk_type: 'disease',
    disease_type: demoRisk.disease_type,
    crop_type: greenhouseId === 102 ? 'muskmelon' : 'tomato',
    growth_stage: greenhouseId === 102 ? '果实膨大期' : '开花坐果期',
    current_score: demoRisk.current_score,
    risk_24h: demoRisk.risk_24h,
    risk_48h: demoRisk.risk_48h,
    risk_72h: demoRisk.risk_72h,
    risk_level: demoRisk.risk_level,
    trend: demoRisk.trend,
    factors_json: demoRisk.factors,
    explanation: demoRisk.explanation,
    status: 'open',
    created_at: iso(),
  }
}

function demoDecisionPlans(greenhouseId: number): DecisionPlan[] {
  return [
    {
      id: greenhouseId * 10 + 2,
      risk_event_id: greenhouseId * 10 + 1,
      greenhouse_id: greenhouseId,
      task_id: null,
      plan_name: '提前通风 30 分钟',
      actions_json: [{ type: 'ventilation', intensity: 30, duration_minutes: 30 }],
      expected_result_json: { risk_before: 66, risk_after: 43 },
      score: 86,
      status: 'draft',
      rationale: '缩短棚内高湿持续时间，并在通风后复测环境。',
      created_at: iso(),
    },
  ]
}

function demoGreenhouseRisk(greenhouseId: number): GreenhouseRiskResponse {
  const greenhouse = demoGreenhouses.find((item) => item.id === greenhouseId) ?? demoGreenhouses[0]
  return {
    greenhouse_id: greenhouse.id,
    crop_type: greenhouse.active_batch?.crop_type ?? 'unknown',
    growth_stage: greenhouse.active_batch?.growth_stage ?? null,
    data_status: 'sufficient',
    current_environment: guestReadings(greenhouseId).at(-1) ?? {},
    risks: guestReadings(greenhouseId).length ? [demoRisk] : [],
    top_event: guestRiskEvents.get(greenhouseId) ?? null,
  }
}

function dashboardSummary(greenhouseId = 101) {
  const greenhouse = demoGreenhouses.find(g=>g.id===greenhouseId) ?? demoGreenhouses[0]
  const currentReadings = guestReadings(greenhouse.id)
  return {
    greenhouse,
    active_batch: greenhouse.active_batch,
    latest_environment: currentReadings.at(-1) ?? null,
    changes: { temperature: 1.2, air_humidity: -3, soil_moisture: 1, light_intensity: 5.4, co2_concentration: -28 },
    risk: risk(),
    today_abnormal_count: 1,
    trend_24h: currentReadings,
    data_source: 'sensor',
    data_source_label: '游客演示传感器',
    data_updated_at: currentReadings.at(-1)?.recorded_at ?? null,
    empty_state: !currentReadings.length,
    warning_summary: {
      highest_risk_level: 'attention',
      open_warning_count: currentReadings.length && ['open','acknowledged'].includes(currentGuestWarning(greenhouseId).status) ? 1 : 0,
      latest_warning_id: 501,
      latest_warning_title: warning.title,
      future_risk_timeline: [],
      latest_recommendation_id: 601,
      latest_recommendation_title: recommendation.title,
      forecast_strategy: 'demo',
      validation_status: 'demo',
      cross_region_warning: false,
    },
    task_summary: { ...guestTaskSummary(greenhouse.id), recent_tasks: tasks.filter(t=>t.greenhouse_id===greenhouse.id), source_distribution: { warning: 1, manual: 1 } },
  }
}

function apiData(data: unknown, message = '游客模式临时演示数据，不会存档') {
  return { code: 200, message, data }
}

function page(items: unknown[], pageNumber = 1, pageSize = 10) {
  return { items: items.slice((pageNumber-1)*pageSize, pageNumber*pageSize), total: items.length, page: pageNumber, page_size: pageSize }
}

function response(config: InternalAxiosRequestConfig, data: unknown): AxiosResponse {
  persistResearchTasks()
  return { data: apiData(data), status: 200, statusText: 'OK', headers: {}, config }
}

function pathOf(config: InternalAxiosRequestConfig) {
  const base = typeof window === 'undefined' ? 'http://guest.local' : window.location.origin
  return new URL(config.url ?? '/', base).pathname.replace(/^\/api/, '')
}

const guestRiskEvents = new Map<number, RiskEvent>()
const guestPlans = new Map<number, DecisionPlan>()
const diseaseRecords: DiseaseRecord[] = []
const classes = [{ key: 'healthy', name: '健康叶片' }, { key: 'early_blight', name: '早疫病' }, { key: 'late_blight', name: '晚疫病' }, { key: 'leaf_mold', name: '叶霉病' }, { key: 'septoria_leaf_spot', name: '斑枯病' }, { key: 'yellow_leaf_curl_virus', name: '番茄黄化曲叶病毒病' }]
function guestReadings(gid: number) { if (![101,102].includes(gid)) return []; return readings.map(r => ({ ...r, greenhouse_id: gid, temperature: r.temperature + (gid === 102 ? 1.5 : 0) })) }
function fail(config: InternalAxiosRequestConfig, message: string, status = 422): never {
  throw new AxiosError(message, String(status), config, undefined, { ...response(config, null), status, data: { code: status, message, data: null } })
}
function guestPrediction(gid: number, horizon = 6): EnvironmentPrediction {
  const history = guestReadings(gid), last = history.at(-1)!
  return {
    greenhouse_id: gid, status: last ? 'ready' : 'insufficient_data', forecast_service_status: last ? 'ready' : 'insufficient_data', forecast_method: 'guest_demo', forecast_method_labels: ['游客示例趋势'], model_status: 'under_evaluation', effective_model_status: 'baseline_ready', ml_candidate_status: 'under_evaluation', forecast_strategy: 'per_target_per_horizon_hybrid', ml_output_count: 0, total_output_count: horizon*2,
    crop: '示例作物', crop_type: gid === 102 ? 'muskmelon' : 'tomato', crop_match_status: gid === 102 ? 'mismatched' : 'matched_public_tomato', model_name: '游客趋势示例', model_type: 'demo', model_version: 'guest-demo', training_crop: '示例', training_region: '示例', training_domain: 'guest', validation_status: 'under_evaluation', calibration_status: 'not_calibrated', decision_scope: 'decision_support', cross_crop_warning: false, cross_region_warning: false, input_data_source: 'demo', input_end_time: last?.recorded_at??null, history_hours: 24, horizon_hours: horizon, rules_status: 'rules_unavailable', warnings: ['仅为游客示例，不是实际模型预测'], generated_at: iso(), health: null,
    history: history.map(r => ({ timestamp: r.recorded_at, temperature_c: r.temperature, air_humidity_pct: r.air_humidity })),
    predictions: last ? Array.from({length:horizon},(_,i)=>({forecast_time:iso((i+1)*60),horizon:i+1,temperature_c:last.temperature+(i+1)*0.2,air_humidity_pct:last.air_humidity-(i+1),par_umol_m2_s:null,lower_bounds:{air_temperature_c:last.temperature-2,air_humidity_pct:last.air_humidity-8},upper_bounds:{air_temperature_c:last.temperature+3,air_humidity_pct:last.air_humidity+8},forecast_method:'guest_demo',method_version:'demo',methods:{},units:{}})) : []
  }
}
function demoResponse(config: InternalAxiosRequestConfig): AxiosResponse | null {
  restoreResearchTasks()
  const path = pathOf(config)
  const method = (config.method ?? 'get').toLowerCase()
  const payload = typeof config.data === 'string' ? JSON.parse(config.data) as Record<string, unknown> : {}
  const gid = Number(config.params?.greenhouse_id ?? payload.greenhouse_id ?? new URLSearchParams(window.location.search).get('greenhouse_id')) || 101
  const greenhouse = demoGreenhouses.find(g=>g.id===gid) ?? demoGreenhouses[0]
  const batch = greenhouse?.active_batch
  if (path.startsWith('/auth/') || path.startsWith('/guest/ai/')) return null

  if (path === '/models/overview') {
    const metric={mae:null,rmse:null,improvement_pct:null,method:'demo'}
    return response(config,{environment:{name:'游客环境趋势示例',version:'demo',status:'demo',prediction_window_hours:6,algorithms:['示例趋势'],training_crop:'示例',temperature_h1:metric,humidity_h1:metric},disease:{name:'游客病害流程示例',version:'demo',status:'under_evaluation',architecture:'示例',class_count:6,confidence_threshold:null,internal_accuracy:null,internal_macro_f1:null,accepted_accuracy:null,external_accuracy:null,external_macro_f1:null}})
  }
  if (path === '/health') return response(config, { service: 'pengzhi-api', status: 'healthy', version: 'guest-demo', database: 'connected' })
  if (path === '/greenhouses/management-summary') {
    const devices=demoGreenhouses.flatMap(g=>guestDevices(g.id))
    return response(config,{total:demoGreenhouses.length,connected:demoGreenhouses.filter(g=>[101,102].includes(g.id)).length,
      device_count:devices.length,online_devices:devices.filter(d=>d.online).length,online_window_minutes:120})
  }
  const deviceMatch=path.match(/^\/greenhouses\/(\d+)\/devices(?:\/([^/]+))?$/)
  if(deviceMatch){
    const greenhouseId=Number(deviceMatch[1])
    if(!demoGreenhouses.some(g=>g.id===greenhouseId))return fail(config,'大棚不存在',404)
    if(method==='get')return response(config,guestDevices(greenhouseId))
    let bindings: Record<string,DeviceBinding[]>={}
    try{bindings=JSON.parse(sessionStorage.getItem('pengzhi-device-bindings-v1')||'{}')}catch{/* empty session */}
    const key=String(greenhouseId)
    if(method==='delete')bindings[key]=(bindings[key]||[]).filter(d=>d.device_id!==decodeURIComponent(deviceMatch[2]||''))
    else{
      if(!/^[A-Za-z0-9_.:-]{1,80}$/.test(String(payload.device_id||'')) || !String(payload.name||'').trim())return fail(config,'请填写有效设备编号和名称',422)
      const device={device_id:String(payload.device_id),name:String(payload.name).trim(),kind:String(payload.kind||'environment')}
      bindings[key]=[...(bindings[key]||[]).filter(d=>d.device_id!==device.device_id),device]
    }
    sessionStorage.setItem('pengzhi-device-bindings-v1',JSON.stringify(bindings))
    return response(config,null)
  }
  if (path === '/greenhouses') {
    if (method === 'get') {
      const q=String(config.params?.keyword || '').toLowerCase()
      const rows=demoGreenhouses.map(guestGreenhouseState).filter(g=>(!config.params?.status || g.status===config.params.status) && (!q || `${g.name} ${g.code} ${g.location}`.toLowerCase().includes(q)))
      return response(config, page(rows, Number(config.params?.page) || 1, Number(config.params?.page_size) || 100))
    }
    if(demoGreenhouses.some(g=>g.code===String(payload.code)))return fail(config,'大棚编号已存在',409)
    const created: Greenhouse = { id: Date.now(), code: String(payload.code), name: String(payload.name), location: String(payload.location), area_mu: String(payload.area_mu), status: (['active','paused','closed'].includes(String(payload.status)) ? payload.status : 'active') as Greenhouse['status'], manager_name: String(payload.manager_name || ''), created_at: iso(), updated_at: iso(), active_batch: null }
    demoGreenhouses.push(created); saveGuestGreenhouses()
    window.dispatchEvent(new Event('greenhouses-changed'))
    return response(config, created)
  }
  const greenhouseMatch = path.match(/^\/greenhouses\/(\d+)$/)
  if (greenhouseMatch) {
    const index=demoGreenhouses.findIndex(g=>g.id===Number(greenhouseMatch[1]))
    if(index<0) return fail(config,'大棚不存在',404)
    if(method==='delete') { const deleted=demoGreenhouses.splice(index,1)[0]; saveGuestGreenhouses(); for(let i=tasks.length-1;i>=0;i--)if(tasks[i].greenhouse_id===deleted.id)tasks.splice(i,1); window.dispatchEvent(new Event('greenhouses-changed')); return response(config,null) }
    if(method!=='get') { if(payload.code && demoGreenhouses.some((g,i)=>i!==index && g.code===payload.code))return fail(config,'大棚编号已存在',409); Object.assign(demoGreenhouses[index],payload,{updated_at:iso()}); saveGuestGreenhouses() }
    return response(config,guestGreenhouseState(demoGreenhouses[index]))
  }
  const cropMatch = path.match(/^\/greenhouses\/(\d+)\/crop-batches$/)
  if (cropMatch) {
    const gh=demoGreenhouses.find(g=>g.id===Number(cropMatch[1])); if(!gh)return fail(config,'大棚不存在',404)
    if(method==='get')return response(config,gh.active_batch ? [gh.active_batch] : [])
    gh.active_batch={...demoBatch,...payload,id:Date.now(),greenhouse_id:gh.id} as typeof demoBatch; saveGuestGreenhouses()
    return response(config,gh.active_batch)
  }
  if (path.match(/^\/crop-batches\/\d+$/)) return response(config, { ...demoBatch, ...(config.data ? JSON.parse(String(config.data)) : {}) })
  if (path.match(/^\/greenhouses\/\d+\/profile$/)) return response(config, { greenhouse: demoGreenhouses[0], active_batch: demoBatch, latest_environment: readings.at(-1), open_warning_count: 1 })

  if (path === '/dashboard/summary') return response(config, dashboardSummary(gid))
  if (path === '/predictions/environment') return response(config, guestPrediction(gid,Number(config.params?.horizon_hours)||6))
  if (path === '/sensors/latest') return response(config, guestReadings(gid).at(-1))
  if (path === '/sensors/history') return response(config, { items: guestReadings(gid), total: readings.length, page: 1, page_size: readings.length, start_time: readings[0].recorded_at, end_time: readings.at(-1)?.recorded_at, source_note: '游客演示数据' })
  if (path === '/sensors/import-preview') return response(config, { filename: 'guest-demo.csv', total_rows: 24, recognized_columns: { recorded_at: '时间', temperature: '温度' }, available_metrics: ['temperature', 'air_humidity', 'soil_moisture'], time_start: readings[0].recorded_at, time_end: readings.at(-1)?.recorded_at, interval_minutes: 60, duplicate_time_rows: 0, invalid_time_rows: 0, out_of_range_rows: 0, completeness_rate: 100, continuity_rate: 100, valid_range_rate: 100, quality_score: 96, quality_level: '优秀', import_ready: true, issues: ['游客模式仅预览，不会导入数据库'], sample_rows: readings.slice(0, 5) })
  if (path === '/sensors/import-file') return fail(config, '游客支持示例预览；正式导入请登录账号')
  if (path === '/v1/ingest/status') return response(config, { endpoint: '/api/v1/ingest/sensor-data', auth_required: true, header_name: 'Authorization / X-Sensor-Key', accepted_metrics: ['temperature', 'air_humidity', 'soil_moisture', 'light_intensity', 'co2_concentration'], max_batch_size: 1000 })

  if (path === '/warnings/summary') {
    const rows=demoGreenhouses.filter(g=>guestReadings(g.id).length).map(g=>currentGuestWarning(g.id))
    const active=rows.filter(w=>['open','acknowledged'].includes(w.status))
    return response(config,{open_total:rows.filter(w=>w.status==='open').length,attention_total:active.length,warning_total:0,critical_total:0,acknowledged_total:rows.filter(w=>w.status==='acknowledged').length,resolved_today:rows.filter(w=>w.status==='resolved').length,latest_warning:rows[0]??null,greenhouse_distribution:Object.fromEntries(demoGreenhouses.map(g=>[g.name,active.filter(w=>w.greenhouse_id===g.id).length]))})
  }
  if (path === '/warnings') {
    const rows=guestReadings(gid).length?[currentGuestWarning(gid)]:[]
    const selected=rows.filter(w=>(!config.params?.status||w.status===config.params.status)&&(!config.params?.warning_type||w.warning_type===config.params.warning_type))
    return response(config,page(selected,Number(config.params?.page)||1,Number(config.params?.page_size)||10))
  }
  if (path === '/warnings/evaluate') return response(config,{greenhouse_id:gid,crop_batch_id:batch?.id??null,crop_type:batch?.crop_type??'unknown',crop_rule_version:'demo-rule-v1',crop_match_status:'matched',cross_region_warning:false,expert_calibration_required:false,growth_stage:batch?.growth_stage??null,current_risk:risk(),future_risks:[],skipped_count:0,data_quality_issues:[],calibration_status:'demo',cross_crop_warning:false,created_count:0,updated_count:0,warnings:guestReadings(gid).length?[currentGuestWarning(gid)]:[],recommendations:guestReadings(gid).length?[demoRecommendation(gid)]:[],forecast_status:guestReadings(gid).length?'ready':'insufficient_data',data_source:'demo',decision_scope:'guest-demo',evaluated_at:iso()})
  const warningMatch = path.match(/^\/warnings\/(\d+)$/)
  if(warningMatch){
    if(Number(warningMatch[1])!==501||!guestReadings(gid).length)return fail(config,'预警不存在',404)
    return response(config,{...currentGuestWarning(gid),greenhouse_name:greenhouse.name,batch_code:batch?.batch_code??null,growth_stage:batch?.growth_stage??null,recommendations:[demoRecommendation(gid)]})
  }
  const warningAction=path.match(/^\/warnings\/(\d+)\/(acknowledge|resolve|dismiss)$/)
  if(warningAction){
    if(Number(warningAction[1])!==501||!guestReadings(gid).length)return fail(config,'预警不存在',404)
    const item=currentGuestWarning(gid), action=warningAction[2]
    if(!['open','acknowledged'].includes(item.status))return fail(config,'当前预警已结束',409)
    if(action==='acknowledge' && item.status!=='open')return fail(config,'只有待处理预警可以确认',409)
    const updated={...item,updated_at:new Date().toISOString()}
    if(action==='acknowledge')Object.assign(updated,{status:'acknowledged',acknowledged_at:new Date().toISOString(),acknowledged_by:'体验用户',acknowledgement_note:String(payload.note||'已确认')})
    if(action==='resolve')Object.assign(updated,{status:'resolved',resolved_at:new Date().toISOString(),resolved_by:'体验用户',resolution_note:String(payload.note||'已复查')})
    if(action==='dismiss')Object.assign(updated,{status:'dismissed',dismissed_at:new Date().toISOString(),dismissed_reason:String(payload.reason||'')})
    sessionStorage.setItem(`pengzhi-warning-${gid}`,JSON.stringify(updated))
    return response(config,updated)
  }
  if (path.match(/^\/warnings\/\d+\/decision-support$/)) return response(config, { status: 'ready', candidate_evidence: [], current_risk_score: 62, scenarios: [], outcome_model_status: 'observational_estimates', outcome_estimates: [], explanation: '游客模式下展示决策支持样例，不会存档。' })
  if (path.match(/^\/warnings\/\d+\/candidates$/)) return response(config, [{ id: 701, warning_event_id: 501, action_code: 'ventilation', title: '通风降湿', description: '开启顶窗并记录 30 分钟后变化', action_type: 'ventilation', expected_response_minutes: 30, energy_level: 'low', labor_level: 'low', evidence_note: '演示证据', status: 'available' }])
  if (path.match(/^\/warnings\/\d+\/similar-cases$/)) return response(config, { status: 'ready', total_eligible_cases: 0, matches: [], action_evidence: [], explanation: '游客模式暂无可检索的历史案例。' })
  if (path === '/cases') return response(config, { items: [], total: 0 })

  if (path === '/tasks') return response(config, method === 'get' ? guestTaskPage(config) : createGuestTask(config.data ? JSON.parse(String(config.data)) : {}))
  if (path === '/tasks/summary') return response(config, guestTaskSummary(Number(config.params?.greenhouse_id) || undefined))
  const taskMatch = path.match(/^\/tasks\/(\d+)$/)
  if (taskMatch) return response(config, taskDetail(tasks.find((item) => item.id === Number(taskMatch[1])) ?? tasks[0]))
  const taskTraceMatch = path.match(/^\/tasks\/(\d+)\/trace$/)
  if (taskTraceMatch) {
    const task = tasks.find((item) => item.id === Number(taskTraceMatch[1])) ?? tasks[0]
    return response(config, { task_id: task.id, nodes: [{ type: 'task', id: task.id, title: task.title, status: task.status, occurred_at: task.created_at, source: '游客会话', version: task.version, summary: task.description }], causality_notice: '游客模式任务仅在当前浏览器会话中存在。' })
  }
  const taskActionMatch = path.match(/^\/tasks\/(\d+)\/(submit|assign|start|complete|cancel|reopen|feedback|evaluate)$/)
  if (taskActionMatch) {
    const task = tasks.find((item) => item.id === Number(taskActionMatch[1])) ?? tasks[0]
    const action = taskActionMatch[2]
    if (action === 'start') {
      const dep = task.evidence_snapshot_json?.agronomist_goal as { depends_on_task_ids?: number[] } | undefined
      if (dep?.depends_on_task_ids?.some(id => tasks.find(t => t.id === id)?.status !== 'completed')) return fail(config, '请先完成目标编排中的前置任务', 409)
    }
    const input = config.data && typeof config.data === 'string' ? JSON.parse(config.data) : {}
    if (action === 'feedback') return response(config, { id: Date.now(), task_id: task.id, operator: '游客', executed_at: iso(), result_type: 'improved', execution_note: '游客临时反馈', observed_change: null, attachment_paths_json: [], environment_snapshot_json: {}, requires_follow_up: false, follow_up_note: null, created_at: iso(), updated_at: iso() })
    if (action === 'evaluate') return response(config, null)
    task.status = action === 'submit' || action === 'reopen' ? 'pending' : action === 'start' ? 'in_progress' : action === 'complete' ? 'completed' : action === 'cancel' ? 'cancelled' : task.status
    if (action === 'assign') task.assignee_name = String(input.assignee_name || '游客')
    task.version += 1
    task.updated_at = iso()
    if (action === 'start') task.started_at = iso()
    if (action === 'complete') task.completed_at = iso()
    if (action === 'cancel') task.cancelled_at = iso()
    window.dispatchEvent(new Event('guest-tasks-changed'))
    return response(config, taskDetail(task))
  }
  if (path.match(/^\/tasks\/\d+\/evaluation$/)) return response(config, null)
  if (path.match(/^\/tasks\/from-warning\/\d+$/)) {
    const existing=tasks.find(t=>t.greenhouse_id===gid && t.source_warning_id===501 && t.status!=='cancelled')
    if(existing)return response(config,existing)
    const task=createGuestTask({title:'风险现场复核',description:'根据当前预警进行现场检查',greenhouse_id:gid,action_type:'field_inspection',priority:'high'})
    Object.assign(task,{source_type:'warning',source_id:501,source_warning_id:501})
    sessionStorage.setItem('pengzhi_warning_tasks_v1',JSON.stringify(tasks.filter(t=>t.source_type==='warning' && t.id>802)))
    return response(config,task)
  }
  if (path.match(/^\/tasks\/from-disease\/\d+$/)) return response(config, createGuestTask({title:'病害现场复核',greenhouse_id:gid,action_type:'field_inspection',priority:'high'}))

  if (path === '/diseases/model-status') return response(config, { service_status:'demo', model_status:'under_evaluation', model_version:'guest-demo', target_crop:'tomato', supported_classes:classes, input_size:224, confidence_threshold:0.7, internal_metrics_summary:{}, external_metrics_summary:{}, validation_status:'under_evaluation', limitations:['游客仅展示预设示例，不对上传照片进行真实分类'] } satisfies DiseaseModelStatus)
  if (path === '/diseases/identify') {
    const data=config.data as FormData, target=Number(data.get('greenhouse_id')), gh=demoGreenhouses.find(g=>g.id===target)
    if(gh?.active_batch?.crop_type!=='tomato')return fail(config,'请选择番茄批次')
    const result: DiseaseIdentification={record_id:Date.now(),recognition_status:'review_required',predicted_class:'leaf_mold',predicted_class_name:'叶霉病（游客示例）',confidence:0.86,top3_predictions:[{class_key:'leaf_mold',class_name:'叶霉病（示例）',confidence:0.86},{class_key:'early_blight',class_name:'早疫病（示例）',confidence:0.09},{class_key:'healthy',class_name:'健康叶片（示例）',confidence:0.05}],model_version:'guest-demo',target_crop:'tomato',validation_status:'under_evaluation',limitations:['预设游客示例，并非对上传图片的真实诊断'],safety_notice:'游客结果仅演示流程；正式识别请登录并人工复核。',duplicate_image:false}
    diseaseRecords.unshift({id:result.record_id,greenhouse_id:target,crop_batch_id:gh.active_batch.id,crop_type:'tomato',image_path:'',image_sha256:'guest',original_filename:(data.get('image') as File)?.name || '游客图片',predicted_class:result.predicted_class,predicted_class_name:result.predicted_class_name,confidence:result.confidence,top3_predictions:result.top3_predictions,recognition_status:result.recognition_status,model_version:'guest-demo',model_status:'under_evaluation',validation_status:'under_evaluation',review_status:'unreviewed',reviewed_class:null,review_note:null,created_at:iso(),updated_at:iso()})
    return response(config,result)
  }
  if (path === '/diseases/records') return response(config, page(diseaseRecords.filter(r=>r.greenhouse_id===gid), Number(config.params?.page) || 1, Number(config.params?.page_size) || 10))
  if (path.match(/^\/diseases\/records\/\d+\/review$/)) { const record=diseaseRecords.find(r=>r.id===Number(path.split('/')[3])); if(!record)return fail(config,'记录不存在',404); Object.assign(record,payload); return response(config,record) }

  if (path === '/decisions/current') return response(config, demoCurrentDecision(Number(config.params?.greenhouse_id) || 101))
  if (path.match(/^\/decisions\/\d+\/(accept|reject)$/)) {
    guestRecommendationStatuses.set(gid, path.endsWith('/accept') ? 'accepted' : 'rejected')
    return response(config, demoRecommendation(gid))
  }
  if (path.match(/^\/decisions\/\d+$/)) return response(config, demoRecommendation(gid))
  const riskMatch = path.match(/^\/risk\/greenhouse\/(\d+)$/)
  if (riskMatch) return response(config, demoGreenhouseRisk(Number(riskMatch[1])))
  if (path === '/risk/recalculate') {
    const payload = config.data ? JSON.parse(String(config.data)) : {}
    const event=demoRiskEvent(Number(payload.greenhouse_id)||101); guestRiskEvents.set(event.greenhouse_id,event); return response(config,event)
  }
  if (path === '/decision/generate') { const event=[...guestRiskEvents.values()].find(e=>e.id===Number(payload.risk_event_id)); if(!event)return fail(config,'请先计算风险'); const plans=demoDecisionPlans(event.greenhouse_id); plans.forEach(p=>{if(!guestPlans.has(p.id))guestPlans.set(p.id,p)}); return response(config,plans.map(p=>guestPlans.get(p.id))) }
  if(path === '/decision')return response(config,[...guestPlans.values()].filter(p=>p.risk_event_id===Number(config.params?.risk_event_id)))
  if (path.match(/^\/decision\/\d+\/execute$/)) {
    const plan=guestPlans.get(Number(path.split('/')[2])); if(!plan)return fail(config,'方案不存在',404)
    const task=(plan.task_id ? tasks.find(t=>t.id===plan.task_id) : undefined) ?? createGuestTask({greenhouse_id:plan.greenhouse_id,title:plan.plan_name,description:plan.rationale,action_type:'ventilation_check',priority:'high'})
    task.source_type='recommendation'; task.source_id=plan.id; task.evidence_snapshot_json={decision_plan:{id:plan.id,plan_name:plan.plan_name},risk_event:{id:plan.risk_event_id}}
    plan.task_id=task.id;plan.status='executed'
    return response(config,{plan,task:taskDetail(task)})
  }
  if (path === '/simulation/run') {
    const duration=Number(payload.duration_minutes)||30,intensity=Number(payload.intensity)||0,last=guestReadings(gid).at(-1)!
    const timeline=Array.from({length:Math.floor(duration/10)},(_,i)=>{const factor=(1-Math.exp(-(i+1)*10/30))/(1-Math.exp(-1))*intensity/30;return {minute:(i+1)*10,temperature:Number((last.temperature-2.4*factor).toFixed(1)),humidity:Number(Math.max(0,Math.min(100,last.air_humidity-5.8*factor)).toFixed(1)),co2:last.co2_concentration}})
    return response(config,{id:null,greenhouse_id:gid,action_type:payload.action_type,intensity,duration_minutes:duration,baseline:{temperature:last.temperature,humidity:last.air_humidity},timeline,estimated_risk_after:null,note:'游客示例模拟，不代表真实设备响应或生产效果。'})
  }
  if (path === '/interventions') return response(config, [])
  if (path.match(/^\/candidates\/\d+\/select$/) || path.match(/^\/interventions\/\d+\/observations$/)) return response(config, { id: 1001, warning_event_id: 501, candidate_id: 701, task_id: 801, action_type: 'ventilation', selection_reason: '游客演示选择', status: 'simulated', selected_at: iso(), started_at: null, finished_at: null, before_snapshot_json: {}, observations: [], causality_notice: '游客模式不会存档。' })

  return fail(config, '此操作尚不支持游客体验，请登录后使用', 501)
}

export function createGuestDemoAdapter(fallback: AxiosAdapter): AxiosAdapter {
  return async (config) => {
    if (isGuestMode()) {
      const demo = demoResponse(config)
      if (demo) return demo
    }
    return fallback(config)
  }
}

let researchTasksRestored = false
function restoreResearchTasks() {
  if (researchTasksRestored) return
  researchTasksRestored = true
  try {
    const stored: FarmTask[] = [...JSON.parse(sessionStorage.getItem('pengzhi_research_tasks_v1') || '[]'),...JSON.parse(sessionStorage.getItem('pengzhi_warning_tasks_v1') || '[]')]
    for (const task of stored) if (!tasks.some(t => t.id === task.id)) tasks.push(task)
  } catch { sessionStorage.removeItem('pengzhi_research_tasks_v1') }
}
function persistResearchTasks() {
  sessionStorage.setItem('pengzhi_research_tasks_v1', JSON.stringify(tasks.filter(t => t.evidence_snapshot_json?.agronomist_goal)))
}
export function guestResearchContext(gid: number) {
  restoreResearchTasks()
  const greenhouse = demoGreenhouses.find(g => g.id === gid)
  if (!greenhouse) throw new Error('游客大棚不存在')
  return { greenhouse, readings: guestReadings(gid), tasks: tasks.filter(t => t.greenhouse_id === gid) }
}
export function createGuestResearchTasks(gid: number, goalId: number, steps: { title: string; action_type: string; description: string; depends_on: number[] }[]) {
  restoreResearchTasks()
  const ids: number[] = []
  for (const [index, step] of steps.entries()) {
    const task = createGuestTask({ greenhouse_id: gid, ...step })
    task.evidence_snapshot_json = { ...task.evidence_snapshot_json, agronomist_goal: { id: goalId, step: index, depends_on_task_ids: step.depends_on.map(i => ids[i]) } }
    ids.push(task.id)
  }
  persistResearchTasks()
  return ids
}
