import { useEffect, useRef, useState } from 'react'
import { Alert, Button, Card, Descriptions, Space, Tag, message } from 'antd'
import { apiClient } from '../../api/client'
import { label } from '../../utils/labels'
import { canManage } from '../../utils/permissions'

interface Run {
  id: number; status: string; result: string
  approvals: Array<{ id: number; status: string; tool: string; arguments: Record<string, unknown>; risk: string }>
  rechecks: Array<{ id: number; status: string; due_at: string; task_id: number }>
}
const labels: Record<string, string> = { CREATED: '已创建', RUNNING: '处理中', WAITING_APPROVAL: '等待你确认', WAITING_RECHECK: '等待复查', EVALUATING: '评估中', COMPLETED: '已完成', FAILED: '失败', CANCELLED: '已取消' }
const tools: Record<string, string> = { create_task_draft: '创建任务草稿', create_farm_task: '创建待执行人工任务', update_farm_task: '更新任务安排', close_farm_task: '记录任务完成', schedule_recheck: '安排后续复查', save_case_memory: '保存复盘记录', generate_greenhouse_report: '生成大棚报告' }
const fields: Record<string, string> = { greenhouse_id: '目标大棚', task_id: '任务编号', title: '任务名称', description: '检查要求', priority: '优先级', action_type: '操作类型', due_at: '截止时间', planned_start_at: '计划开始', operation: '操作', assignee_name: '负责人', minutes: '复查间隔（分钟）', metric: '复查指标', target_min: '目标下限', target_max: '目标上限', version: '记录版本', case_id: '案例编号' }
const terminal = new Set(['COMPLETED', 'FAILED', 'CANCELLED'])

export default function AgentRunCard({ runId, onRefresh, greenhouseNames = {}, onStatus }: { runId: number; onRefresh: () => void; greenhouseNames?: Record<number, string>; onStatus?: (status: string) => void }) {
  const [run, setRun] = useState<Run>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  const statusCallback = useRef(onStatus)
  const busyRef = useRef(false)
  const mounted = useRef(false)
  useEffect(() => { statusCallback.current = onStatus }, [onStatus])
  useEffect(() => {
    mounted.current = true
    let active = true; let timer: number | undefined
    const load = async () => {
      if (busyRef.current) { timer = window.setTimeout(() => void load(), 3000); return }
      try {
        const response = await apiClient.get(`/agent/runs/${runId}`)
        if (!active) return
        const value = response.data.data as Run
        setRun(value); setError(''); statusCallback.current?.(value.status)
        if (!terminal.has(value.status)) timer = window.setTimeout(() => void load(), 3000)
      } catch { if (active) { setError('任务处理状态暂时无法获取，请重试。'); timer = window.setTimeout(() => void load(), 8000) } }
    }
    void load()
    return () => { active = false; mounted.current = false; window.clearTimeout(timer) }
  }, [runId, reload])
  const act = async (action: string, approvalId?: number) => {
    if (busyRef.current) return
    busyRef.current = true; setBusy(true)
    try {
      const response = await apiClient.post(`/agent/runs/${runId}/${action}`, { approval_id: approvalId }, { timeout: 120000 })
      if (!mounted.current) return
      setRun(response.data.data); statusCallback.current?.(response.data.data.status)
      onRefresh(); window.dispatchEvent(new Event('pengzhi:tasks-changed'))
    } catch (cause) { if (mounted.current) message.error(cause instanceof Error ? cause.message : '操作失败') }
    finally { busyRef.current = false; if (mounted.current) { setBusy(false); setReload(value => value + 1) } }
  }
  if (!run || run.id !== runId) return error ? <Alert type="error" message={error} action={<Button size="small" onClick={() => setReload(value => value + 1)}>重试</Button>} /> : <p role="status">正在读取任务处理状态…</p>
  return <Card size="small" title={<Space>本轮处理<Tag>{labels[run.status] || run.status}</Tag></Space>}>
    {error && <Alert type="warning" message={error} />}
    {run.approvals.filter(approval => approval.status === 'pending').map(approval => <div className="assistant-pending-actions" key={approval.id}>
      <strong>请核对：{tools[approval.tool] ?? '更新业务记录'}</strong>
      <Descriptions size="small" column={1} items={Object.entries(approval.arguments).filter(([key]) => key in fields).map(([key, value]) => ({ key, label: fields[key], children: value === null ? '未设置' : key === 'greenhouse_id' ? greenhouseNames[Number(value)] ?? `大棚 #${value}` : key.endsWith('_at') ? new Date(String(value)).toLocaleString('zh-CN') : label(String(value)) }))} />
      <p>确认后仅保存相应业务记录，不代表已经执行设备操作或完成现场处置。</p>
      <Space wrap><Button type="primary" loading={busy} disabled={!canManage()} onClick={() => void act('approve', approval.id)}>确认此操作</Button><Button disabled={busy} onClick={() => void act('reject', approval.id)}>取消此操作</Button></Space>
    </div>)}
    {run.rechecks.map(check => <p key={check.id}>任务 #{check.task_id} · {new Date(check.due_at).toLocaleString('zh-CN')} 复查 · {labels[check.status] || label(check.status)}</p>)}
    {!terminal.has(run.status) && <Button danger size="small" loading={busy} onClick={() => void act('cancel')}>停止本轮处理</Button>}
  </Card>
}
