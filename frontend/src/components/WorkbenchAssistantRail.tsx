import { useCallback, useEffect, useState } from 'react'
import { Button, Skeleton } from 'antd'
import { ArrowRightOutlined } from '@ant-design/icons'
import { useLocation, useNavigate } from 'react-router-dom'
import { getDashboardSummary } from '../api/dashboardApi'
import type { DashboardSummary } from '../types/dashboard'
import { FloatingAIAssistant } from './FloatingAIAssistant'

const taskLabels: Record<string, string> = {draft:'待提交',pending:'待执行',in_progress:'执行中',completed:'已完成',cancelled:'已取消'}

export function WorkbenchAssistantRail({greenhouseId,docked}:{greenhouseId?:number;docked:boolean}) {
  const location=useLocation(),navigate=useNavigate()
  const [summary,setSummary]=useState<DashboardSummary|null>(null)
  const [failed,setFailed]=useState(false)
  const [retry,setRetry]=useState(0)
  useEffect(()=>{
    setSummary(null);setFailed(false)
    if(!docked||!greenhouseId)return
    let active=true
    const refresh=()=>{if(document.hidden)return;void getDashboardSummary(greenhouseId).then(value=>{if(active){setSummary(value);setFailed(false)}}).catch(()=>{if(active)setFailed(true)})}
    refresh()
    const timer=window.setInterval(refresh,60000)
    const refreshEvents=['greenhouses-changed','pengzhi:tasks-changed','guest-tasks-changed']
    refreshEvents.forEach(event=>window.addEventListener(event,refresh))
    document.addEventListener('visibilitychange',refresh)
    return()=>{active=false;window.clearInterval(timer);refreshEvents.forEach(event=>window.removeEventListener(event,refresh));document.removeEventListener('visibilitychange',refresh)}
  },[docked,greenhouseId,location.pathname,location.search,retry])
  const showTasks=useCallback((taskId?:number)=>{
    const params=new URLSearchParams(greenhouseId?{greenhouse_id:String(greenhouseId)}:{})
    if(taskId)params.set('task_id',String(taskId))
    navigate('/platform/production?'+params)
  },[navigate,greenhouseId])
  const tasks=summary?.task_summary.recent_tasks.filter(task=>['draft','pending','in_progress'].includes(task.status)).slice(0,3)??[]
  return <>
    <section className={docked?'wb-assistant-card':undefined}>
      {docked&&<div className="wb-rail-heading"><strong><i/>本棚重点</strong><span>棚小智协作</span></div>}
      <FloatingAIAssistant/>
      {docked&&<><div className="wb-assistant-summary">
        {!greenhouseId?'选择大棚后，我会结合本棚信息帮助你理解风险和安排农事。':failed?<span>本棚摘要暂时无法读取。<Button type="link" size="small" onClick={()=>setRetry(value=>value+1)}>重试</Button></span>:summary?<><strong>{summary.warning_summary.open_warning_count?'本棚有 '+summary.warning_summary.open_warning_count+' 项待处理预警。':'先了解当前棚况。'}</strong><span>{summary.warning_summary.latest_recommendation_title||summary.risk.reasons[0]||'可以向我询问环境、风险与农事安排；处理建议需人工确认。'}</span><small>{summary.data_source_label||'数据来源待确认'}{summary.data_updated_at?' · '+new Date(summary.data_updated_at).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'}):''}</small></>:<Skeleton active title={false} paragraph={{rows:2}}/>}
      </div><Button type="primary" block onClick={()=>showTasks()}>查看建议与任务 <ArrowRightOutlined/></Button><button className="wb-rail-chat-link" type="button" onClick={()=>window.dispatchEvent(new Event('pengzhi:open-assistant'))}>向棚小智提问 →</button></>}
    </section>
    {docked&&<section className="wb-todo-card"><div className="wb-rail-heading"><strong>当前待办</strong><button type="button" onClick={()=>showTasks()}>全部 →</button></div>
      {failed?<p className="wb-rail-empty">待办读取失败，可进入农事执行查看。</p>:!summary&&greenhouseId?<Skeleton active title={false} paragraph={{rows:2}}/>:tasks.length?tasks.map(task=><button className="wb-rail-task" type="button" key={task.id} onClick={()=>showTasks(task.id)}><i className={task.priority==='urgent'?'is-urgent':''}/><span><strong>{task.title}</strong><small>{task.assignee_name||'待分配'} · {taskLabels[task.status]||task.status}</small></span></button>):<p className="wb-rail-empty">{greenhouseId?'当前没有待处理任务':'选择大棚后显示待办'}</p>}
    </section>}
  </>
}

