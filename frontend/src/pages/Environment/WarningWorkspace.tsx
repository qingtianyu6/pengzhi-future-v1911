import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alert, Button, Drawer, Empty, Input, Modal, Pagination, Space, Spin, message } from 'antd'
import { ArrowRightOutlined, RightOutlined } from '@ant-design/icons'
import { acknowledgeWarning, dismissWarning, getWarning, getWarnings, resolveWarning } from '../../api/warningApi'
import { createTaskFromWarning, getTasks } from '../../api/taskApi'
import { getApiErrorMessage } from '../../api/client'
import { getStoredUser } from '../../api/authApi'
import { canManage } from '../../utils/permissions'
import { InterventionPanel } from '../../components/InterventionPanel'
import type { WarningDetail, WarningEvent, WarningList, WarningStatus } from '../../types/warning'
import type { FarmTask } from '../../types/task'

const groups = [{ key: 'open', label: '待处理' }, { key: 'acknowledged', label: '处理中' }, { key: 'resolved', label: '已恢复' }, { key: 'dismissed', label: '已忽略' }] as const
const severity: Record<string, string> = { attention: '需关注', warning: '预警', critical: '严重', normal: '提示' }
const time = (value: string | null) => value ? new Date(value).toLocaleString('zh-CN', {month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}) : '—'

export default function WarningWorkspace({ greenhouseId, onSelected, refreshKey }: { greenhouseId: number; onSelected: (warning: WarningEvent | null) => void; refreshKey: number }) {
  const navigate = useNavigate()
  const [tab, setTab] = useState<WarningStatus>('open')
  const [page, setPage] = useState(1)
  const [lists, setLists] = useState<Partial<Record<WarningStatus, WarningList>>>({})
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<WarningDetail | null>(null)
  const [detailError, setDetailError] = useState('')
  const [tasks, setTasks] = useState<FarmTask[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const [action, setAction] = useState<'acknowledge' | 'resolve' | 'dismiss' | 'task' | null>(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [recordsOpen, setRecordsOpen] = useState(false)
  const [rulesOpen, setRulesOpen] = useState(false)
  const [notice, context] = message.useMessage()
  const reload = useCallback(() => setRevision(r => r + 1), [])
  useEffect(() => {
    let active = true
    setLoading(true); setError('')
    void Promise.all(groups.map(g => getWarnings({greenhouse_id:greenhouseId,status:g.key,page:g.key===tab?page:1,page_size:g.key===tab?5:1}).then(result => [g.key, result] as const)))
      .then(results => {
        if (!active) return
        const data = Object.fromEntries(results) as Record<WarningStatus, WarningList>
        setLists(data)
        setSelectedId(current => data[tab].items.some(w => w.id === current) ? current : data[tab].items[0]?.id ?? null)
      }).catch(e => { if (active) setError(getApiErrorMessage(e)) }).finally(() => { if(active) setLoading(false) })
    return () => { active = false }
  }, [greenhouseId, tab, page, revision, refreshKey])
  useEffect(() => {
    let active = true
    setDetail(null); setDetailError('')
    if (selectedId === null) { onSelected(null); return }
    void getWarning(selectedId).then(result => {
      if (active) { setDetail(result); onSelected(result) }
    }).catch(e => { if(active) {setDetailError(getApiErrorMessage(e));onSelected(null)} })
    return () => { active = false }
  }, [selectedId, greenhouseId, revision, refreshKey, onSelected])
  useEffect(() => {
    let active = true
    void getTasks({greenhouse_id:greenhouseId,source_type:'warning',page_size:100}).then(result => { if(active) setTasks(result.items) }).catch(() => { if(active) setTasks([]) })
    return () => { active = false }
  }, [greenhouseId, revision])
  const relatedTask = detail ? tasks.find(t => t.source_warning_id === detail.id && t.status !== 'cancelled') : undefined
  const completed = detail?.status === 'resolved'
  const ignored = detail?.status === 'dismissed'
  const stage = completed || ignored ? -1 : !detail?.acknowledged_at ? 1 : relatedTask?.status === 'completed' ? 3 : 2
  const finishedSteps = [true, Boolean(detail?.acknowledged_at), relatedTask?.status === 'completed', completed]
  const recommendation = detail?.recommendations.find(r => r.status !== 'rejected' && r.status !== 'superseded')
  const apply = async () => {
    if (!detail || !action) return
    if (action !== 'task' && note.trim().length < 2) { notice.warning('请填写至少两个字的现场说明'); return }
    setBusy(true)
    try {
      if (action === 'task') {
        const task = await createTaskFromWarning(detail.id, getStoredUser()?.display_name || '体验用户')
        setTasks(current => [task, ...current.filter(t => t.id !== task.id)])
        notice.success('已关联农事任务，请在任务中确认与安排执行')
      } else if (action === 'acknowledge') {
        await acknowledgeWarning(detail.id, note.trim()); setTab('acknowledged'); setPage(1); notice.success('已确认，转入处理中')
      } else if (action === 'resolve') {
        await resolveWarning(detail.id, note.trim()); setTab('resolved'); setPage(1); notice.success('复查结果已记录')
      } else {
        await dismissWarning(detail.id, note.trim()); setTab('dismissed'); setPage(1); notice.success('已记录忽略原因')
      }
      setAction(null); setNote(''); reload(); window.dispatchEvent(new Event('pengzhi:warnings-changed'))
    } catch (e) { notice.error(getApiErrorMessage(e)) }
    finally { setBusy(false) }
  }
  const chooseAction = (next: typeof action) => { setAction(next); setNote('') }
  const total = lists[tab]?.total ?? 0
  return <section id="environment-alerts" className="env-warning-workspace" aria-labelledby="env-warnings-heading">
    {context}
    <header className="env-warning-heading"><div><h2 id="env-warnings-heading"><button type="button" aria-label="预警与处置" onClick={() => document.getElementById('environment-alerts')?.scrollIntoView({behavior:'smooth'})}>预警与处置</button></h2><span className="env-warning-count">{lists.open?.total ?? '—'} 项待处理</span></div><Space><Button type="link" onClick={() => setRecordsOpen(true)}>处置与复测记录</Button><Button type="link" onClick={() => setRulesOpen(true)}>预警依据</Button></Space></header>
    <div className="env-response-columns">
      <div className="env-alerts-column"><nav className="env-alert-tabs" aria-label="预警处理状态">{groups.map(g => <button key={g.key} type="button" aria-pressed={tab===g.key} onClick={() => {setTab(g.key);setPage(1)}}>{g.label} <small>{lists[g.key]?.total ?? '—'}</small></button>)}</nav>
        {error ? <Alert type="error" message="预警读取失败" description={error} action={<Button onClick={reload}>重试</Button>} /> : <Spin spinning={loading}><div className="env-alert-list">{lists[tab]?.items.map(w => <button className={`env-alert-row ${w.severity}`} key={w.id} type="button" aria-pressed={selectedId===w.id} onClick={() => setSelectedId(w.id)}><i /><div><strong>{w.title}</strong><span>{time(w.last_triggered_at)} · {severity[w.severity] ?? '待核实'}</span><p>{w.description}</p></div><RightOutlined /></button>)}{!loading && !total && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={`暂无${groups.find(g=>g.key===tab)?.label}预警`} />}</div></Spin>}
        {total > 5 && <Pagination simple current={page} total={total} pageSize={5} onChange={setPage} />}
      </div>
      <div className="env-response-detail" aria-live="polite">
        {detailError ? <Alert type="error" message="预警详情读取失败" description={detailError} action={<Button onClick={reload}>重试</Button>} /> : !selectedId ? <div className="env-response-empty"><h3>从变化中发现问题，让处理有迹可循</h3><p>选择左侧预警，查看依据、安排任务并记录现场复查。</p></div> : !detail ? <Spin /> : <>
          <span className="env-selected-label">当前选中 · {ignored?'已忽略':completed?'已恢复':severity[detail.severity]}</span><h3>{recommendation?.title || detail.title}</h3>
          <p className="env-response-rationale">{recommendation?.rationale || detail.description}</p>
          {recommendation?.action_steps_json.length ? <ol className="env-response-steps">{recommendation.action_steps_json.map((step,i) => <li key={i}>{step}</li>)}</ol> : <p className="env-response-rationale">暂无具体处置建议，请结合采样记录进行现场核实。</p>}
          <small className="env-rule-source">依据：{detail.rule_version} · {detail.greenhouse_name}</small>
          {!ignored && <ol className="env-handling-progress" aria-label="预警处理进度">{['发现异常','确认情况','安排处理','复查结果'].map((label,i) => <li key={label} className={finishedSteps[i]?'is-done':stage===i?'is-current':''} aria-current={stage===i?'step':undefined}><i>{finishedSteps[i]?'✓':i+1}</i><strong>{label}</strong></li>)}</ol>}
          {relatedTask && <p className="env-related-task">关联任务：<Button type="link" onClick={() => navigate(`/platform/production?greenhouse_id=${greenhouseId}&task_id=${relatedTask.id}`)}>{relatedTask.title} <ArrowRightOutlined /></Button></p>}
          {detail.resolution_note && <p className="env-resolution-note">复查记录：{detail.resolution_note}</p>}
          {ignored && <p className="env-resolution-note">忽略记录：{detail.dismissed_reason || '未填写说明'}</p>}
          {detail.acknowledgement_note && !completed && !ignored && <p className="env-resolution-note">现场确认：{detail.acknowledgement_note}</p>}
          <Space wrap className="env-response-actions">{detail.status==='open' && <Button type="primary" disabled={!canManage()} onClick={() => chooseAction('acknowledge')}>开始处理</Button>}{['open','acknowledged'].includes(detail.status) && <>{relatedTask ? <Button onClick={() => navigate(`/platform/production?greenhouse_id=${greenhouseId}&task_id=${relatedTask.id}`)}>查看处理任务</Button> : <Button disabled={!canManage()} onClick={() => chooseAction('task')}>创建农事任务</Button>}<Button disabled={!canManage()} onClick={() => chooseAction('resolve')}>记录复查结果</Button><Button type="text" disabled={!canManage()} onClick={() => chooseAction('dismiss')}>忽略</Button></>}</Space>
          {recommendation?.safety_note && <small className="env-response-caution">{recommendation.safety_note}</small>}
        </>}
      </div>
    </div>
    <Modal title={action==='task'?'创建关联农事任务':action==='acknowledge'?'确认并开始处理':action==='resolve'?'记录复查并解除预警':'忽略预警'} open={action!==null} onCancel={() => setAction(null)} onOk={() => void apply()} confirmLoading={busy} okText="确认" cancelText="取消" destroyOnHidden>
      <p>{action==='task'?'按当前预警生成或关联任务草稿，执行前仍需确认。不会自动控制设备。':action==='resolve'?'请填写现场复查结果。已进入正式处置流程的预警，需要先完成任务及规定复测。':'记录现场核实情况，处理过程会保留在预警记录中。'}</p>
      {action!=='task' && <Input.TextArea aria-label="现场处理说明" value={note} onChange={e => setNote(e.target.value)} maxLength={500} rows={3} placeholder="填写核实情况、复查结果或忽略原因" />}
    </Modal>
    <Drawer title="本棚处置与复测记录" width="min(1100px, 96vw)" open={recordsOpen} onClose={() => {setRecordsOpen(false);reload()}} destroyOnHidden><InterventionPanel greenhouseId={greenhouseId} onOpenTasks={() => navigate(`/platform/production?greenhouse_id=${greenhouseId}`)} /></Drawer>
    <Drawer title="预警依据" width={520} open={rulesOpen} onClose={() => setRulesOpen(false)}><h3>{detail?.title ?? '请选择一条预警'}</h3><p>规则版本：{detail?.rule_version ?? '—'}</p><p>作物：{detail?.crop_type ?? '—'} · 生育期：{detail?.growth_stage ?? '—'}</p><pre className="env-evidence-json">{JSON.stringify(detail?.evidence_json ?? {},null,2)}</pre><p>预警来自作物规则与采样记录；现场情况和复查记录仍需人工确认。</p></Drawer>
  </section>
}
