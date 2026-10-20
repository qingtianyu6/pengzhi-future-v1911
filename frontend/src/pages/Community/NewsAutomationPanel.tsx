import { useCallback, useEffect, useState } from 'react'
import { Alert, App, Button, Card, Checkbox, Form, InputNumber, Modal, Space, Switch, Tag } from 'antd'
import { Link } from 'react-router-dom'
import { communityRequest as request } from '../../api/communityApi'
import { getApiErrorMessage } from '../../api/client'

type Catalog={language?:string;kind?:string;key:string;name:string;url:string;homepage:string;description:string}
type Status={enabled:boolean;use_ai:boolean;daily_ai_limit:number;digest_limit:number;calls_reserved_today:number;model_configured:boolean;model:string|null;last_run_at:string|null;last_result:Record<string,number>;cost_note:string}
type Setup={enabled:boolean;use_ai:boolean;daily_ai_limit:number;digest_limit:number;source_keys:string[];permission_confirmed:boolean;ai_authorized:boolean;local_hour:number}
export function NewsAutomationPanel({guest,manage,onChanged}:{guest:boolean;manage:boolean;onChanged:()=>Promise<void>}) {
  const {message}=App.useApp(),[catalog,setCatalog]=useState<Catalog[]>([]),[status,setStatus]=useState<Status|null>(null)
  const [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[form]=Form.useForm<Setup>()
  const load=useCallback(async()=>{try{const c=await request<Catalog[]>('news/source-catalog');setCatalog(c);if(!guest)setStatus(await request<Status>('news/automation'));setError('')}catch(e){setError(getApiErrorMessage(e))}},[guest])
  useEffect(()=>{void load();const timer=window.setInterval(()=>{if(!document.hidden)void load()},60000);return()=>window.clearInterval(timer)},[load])
  const configure=async()=>{setBusy(true);try{const [pref,sources]=await Promise.all([request<{local_hour:number}>('news/preferences'),request<{url:string;enabled:boolean}[]>('news/sources')]);const selected=catalog.filter(c=>sources.some(s=>s.url===c.url&&s.enabled)).map(c=>c.key);form.resetFields();form.setFieldsValue({enabled:status?.enabled??true,use_ai:status?.use_ai??false,daily_ai_limit:status?.daily_ai_limit??8,digest_limit:status?.digest_limit??8,local_hour:pref.local_hour,source_keys:selected.length?selected:catalog.filter(c=>c.language==='zh-CN').map(c=>c.key),permission_confirmed:false,ai_authorized:false});if(!sources.length)form.setFieldValue('enabled',true);setOpen(true)}catch(e){setError(getApiErrorMessage(e))}finally{setBusy(false)}}
  const run=async()=>{setBusy(true);setError('');try{const r=await request<{digest:{status:string};collection:{status:string}[]}>('news/automation/run','post');await load();await onChanged();message.info(r.digest.status==='published'?'今日简报已生成':r.digest.status==='already_published'?'今日简报已存在，未重复推送':'本次没有匹配的新内容；可在来源与运行查看采集状态')}catch(e){setError(getApiErrorMessage(e))}finally{setBusy(false)}}
  return <Card className="news-automation-card" title="每日 AI 农业简报" extra={<Space wrap>{guest?<Link to="/login">登录设置自动推送</Link>:<><Button disabled={!manage||busy} onClick={()=>void configure()}>配置自动简报</Button><Button type="primary" loading={busy} disabled={!manage||!status?.enabled} onClick={()=>void run()}>立即运行一次</Button></>}</Space>}>
    <p>自动检查公开订阅源，区分官方标题索引与来源摘要，整理中文要点，按关注作物和主题生成每日站内简报。后台服务运行时生效。</p>
    <Space wrap><Tag color={status?.enabled?'green':'default'}>{guest?'游客预览':status?.enabled?'自动流程已启用':'自动流程未启用'}</Tag><Tag>{status?.use_ai?'AI 摘要已授权':'来源摘要模式，未自动调用AI'}</Tag>{!guest&&<Tag>今日已预留 {status?.calls_reserved_today??'…'} / {status?.daily_ai_limit??'…'} 次模型调用</Tag>}</Space>
    {status?.last_run_at&&<p className="community-muted">最近处理：{new Date((/(?:Z|[+-]\d{2}:\d{2})$/.test(status.last_run_at)?status.last_run_at:status.last_run_at+'Z')).toLocaleString('zh-CN')} · {Object.entries(status.last_result).map(([k,v])=>`${({summarized:'已整理',cached:'缓存命中',daily_limit:'达到日限额',failed:'模型失败',insufficient_evidence:'证据不足',ai_disabled:'AI未启用',backoff:'等待重试',already_processing:'其他进程处理中',retry_exhausted:'重试上限'} as Record<string,string>)[k]||k} ${v}`).join('；')}</p>}
    {error&&<Alert type="error" message={error} action={<Button onClick={()=>void load()}>重试读取</Button>}/>}
    <p className="community-muted">只为新内容调用模型并缓存结果；失败不会伪造摘要，无新内容不推送空日报。{status?.cost_note}</p>
    {guest&&<Space wrap>{catalog.map(c=><Button key={c.key} href={c.homepage} target="_blank" rel="noopener noreferrer">{c.name}</Button>)}</Space>}
    <Modal title="配置每日自动农业简报" open={open} onCancel={()=>setOpen(false)} footer={null} destroyOnHidden>
      <Form form={form} layout="vertical" onFinish={async values=>{setBusy(true);try{await request('news/automation/setup','post',values);setOpen(false);await load();await onChanged();message.success('订阅源与定时简报已配置，可立即运行一次验收')}catch(e){message.error(getApiErrorMessage(e))}finally{setBusy(false)}}}>
        <Form.Item name="source_keys" label="选择资讯来源（中文优先）" rules={[{required:true,message:'请至少选择一个来源'}]}><Checkbox.Group options={catalog.map(c=>({label:c.name,value:c.key}))}/></Form.Item>
        {catalog.map(c=><p className="community-muted" key={c.key}>{c.description} <a href={c.homepage} target="_blank" rel="noopener noreferrer">查看机构来源</a></p>)}
        <Form.Item name="enabled" label="自动采集与每日简报" valuePropName="checked"><Switch/></Form.Item>
        <Form.Item name="local_hour" label="每天站内推送时间（北京时间整点）"><InputNumber min={0} max={23}/></Form.Item>
        <Form.Item name="digest_limit" label="每份简报最多条数"><InputNumber min={1} max={12}/></Form.Item>
        <Form.Item name="use_ai" label="自动生成中文 AI 摘要" valuePropName="checked"><Switch disabled={!status?.model_configured}/></Form.Item>
        {!status?.model_configured&&<Alert type="info" message="现有模型尚未配置，可先使用采集和来源摘要模式。"/>}
        <Form.Item name="daily_ai_limit" label="本组织每天最多自动摘要调用次数（失败也计入）"><InputNumber min={0} max={30}/></Form.Item>
        <Form.Item name="ai_authorized" valuePropName="checked"><Checkbox>允许使用已配置模型自动分析公开资讯，可能计费，并受上述每日次数限制</Checkbox></Form.Item>
        <Form.Item name="permission_confirmed" valuePropName="checked" rules={[{validator:(_,v)=>v?Promise.resolve():Promise.reject(new Error('请确认公开订阅用途'))}]}><Checkbox>确认所选公开来源用于站内标题或摘要阅读，保留出处，不批量转载全文或图片</Checkbox></Form.Item>
        <p className="community-muted">保留你已有的作物与主题偏好；服务关闭期间无法采集或推送。每天只生成一份通知，手动运行可更新当日简报。</p>
        <Button htmlType="submit" type="primary" loading={busy}>保存并启用所选配置</Button>
      </Form>
    </Modal>
  </Card>
}
