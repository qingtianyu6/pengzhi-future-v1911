import { useCallback, useEffect, useState } from 'react'
import { App, Alert, Button, Card, Checkbox, Empty, Select, Space, Table, Tag } from 'antd'
import { communityRequest as request } from '../../api/communityApi'
import { getApiErrorMessage } from '../../api/client'
import { getStoredUser } from '../../api/authApi'
import { isGuestMode } from '../../api/guestMode'
import type { Evaluation, TraceSummary } from '../../types/community'
import './community.css'
export default function AIQualityPage() { return <App><Quality /></App> }
function Quality() {
  const { message, modal } = App.useApp()
  const [traces, setTraces] = useState<TraceSummary | null>(null), [runs, setRuns] = useState<Evaluation[]>([]), [chosen, setChosen] = useState<number>(), [compare, setCompare] = useState<number>()
  const [error, setError] = useState(''), [busy, setBusy] = useState(false)
  const [modelAuthorized, setModelAuthorized] = useState(false)
  const guest = isGuestMode(), canRun = !guest && ['admin', 'agronomist'].includes(getStoredUser()?.role || '')
  const load = useCallback(async () => {
    try { const [t, r] = await Promise.all([request<TraceSummary>('ai/traces'), request<Evaluation[]>('ai/evaluations')]); setTraces(t); setRuns(r); setError('') }
    catch (e) { setError(getApiErrorMessage(e)) }
  }, [])
  useEffect(() => { void load() }, [load])
  const current = runs.find(r => r.id === chosen) || runs[0], other = runs.find(r => r.id === compare)
  const modelEvaluation = async () => {
    setBusy(true)
    try { const r = await request<Evaluation>('ai/evaluations', 'post', { mode: 'model', paid_model_authorized: modelAuthorized }); setChosen(r.id); await load(); message.success('模型响应评测记录已保存') }
    catch (e) { message.error(getApiErrorMessage(e)) } finally { setBusy(false) }
  }
  return <div className="community-page"><header className="community-hero"><div><span className="community-eyebrow">AI EVALUATION & OBSERVABILITY</span><h1>AI 能力与运行</h1><p>查看实际调用、工具执行状态与可复现检查结果。</p></div><Space wrap><Button onClick={() => void load()}>刷新运行记录</Button><Button type="primary" loading={busy} disabled={!canRun} onClick={async () => { setBusy(true); try { const r = await request<Evaluation>('ai/evaluations', 'post', { mode: 'local' }); setChosen(r.id); message.success('本地评测已完成'); await load() } catch (e) { message.error(getApiErrorMessage(e)) } finally { setBusy(false) } }}>运行本地评测</Button></Space></header>
    {guest && <Alert type="info" message="游客不读取正式运行记录，也不会运行付费模型评测。" />}
    {error && <Alert type="error" message={error} />}
    <div className="community-stats">{[{ label: '实际工具调用', value: traces?.tool_calls ?? '—' }, { label: '工具成功率', value: traces?.tool_success_rate == null ? '—' : (traces.tool_success_rate*100).toFixed(1)+'%' }, { label: '实际返回Token', value: traces?.token_total ?? '—' }, { label: '可核实计费金额', value: traces?.actual_cost ?? '未提供' }].map(s => <div key={s.label}><span>{s.label}</span><strong>{s.value}</strong></div>)}</div>
    <Card title="农业问题测试集"><Space wrap><Checkbox checked={modelAuthorized} onChange={e => setModelAuthorized(e.target.checked)}>同意调用已配置模型进行8项评测，可能产生服务费用</Checkbox><Button disabled={!canRun || !modelAuthorized} loading={busy} onClick={() => void modelEvaluation()}>评测当前模型</Button></Space><p className="community-muted">本地评测不调用模型；模型评测仅在明确授权后运行。记录来源和行为检查，并保留回答供人工复核，不作为农艺准确率。不同版本仅比较相同测试集的实际记录。</p><Space wrap><Select aria-label="当前评测记录" placeholder="当前记录" value={current?.id} style={{ minWidth: 220 }} options={runs.map(r => ({ value: r.id, label: '#'+r.id+' · '+r.model_version+' · '+r.suite_version }))} onChange={setChosen} /><Select aria-label="对比评测记录" allowClear placeholder="选择同一测试集记录对比" value={compare} style={{ minWidth: 220 }} options={runs.filter(r => r.id !== current?.id && r.suite_version === current?.suite_version).map(r => ({ value: r.id, label: '#'+r.id+' · '+r.model_version }))} onChange={setCompare} /></Space>{current ? <><p><Tag>{current.suite_version}</Tag><Tag>{current.model_version}</Tag>通过 {current.passed}/{current.total} 项 {other && '；对比记录通过 '+other.passed+'/'+other.total+' 项'}</p><div className="community-table"><Table pagination={false} rowKey="case" dataSource={current.results} columns={[{ title: '测试项', dataIndex: 'case' }, { title: '结果', render: (_, row) => <Tag color={row.passed ? 'green' : 'red'}>{row.passed ? '通过' : '未通过'}</Tag> }, { title: '耗时', dataIndex: 'elapsed_ms', render: v => v+'ms' }, { title: '验证依据', render: (_, row) => <Button type="link" onClick={() => modal.info({ title: row.case, width: 760, content: <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(row.evidence || { error: row.error_code }, null, 2)}</pre> })}>查看实际记录</Button> }, ...(other ? [{ title: '对比记录', render: (_: unknown, row: Evaluation['results'][number]) => other.results.find(r => r.case === row.case)?.passed ? '通过' : '未通过' }] : [])]} /></div></> : <Empty description="尚未执行评测；不预置虚构评分" image={Empty.PRESENTED_IMAGE_SIMPLE} />}</Card>
    <Card title="棚小智调用追踪"><p className="community-muted">{traces?.window_note} · {traces?.cost_note}</p><div className="community-table"><Table size="small" pagination={{ pageSize: 10 }} rowKey="id" dataSource={traces?.items} columns={[{ title: '运行ID', dataIndex: 'run_id' }, { title: '操作', dataIndex: 'operation' }, { title: '状态', dataIndex: 'status' }, { title: '耗时', dataIndex: 'elapsed_ms', render: v => v+'ms' }, { title: '错误类型', dataIndex: 'error_code' }, { title: '时间', dataIndex: 'created_at', render: v => new Date(v).toLocaleString('zh-CN') }]} /></div></Card>
  </div>
}
