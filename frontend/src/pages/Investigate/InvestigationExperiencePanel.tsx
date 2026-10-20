import { useCallback, useEffect, useState } from 'react'
import { Alert, App, Button, Card, Checkbox, Form, Input, Select, Space, Tag } from 'antd'
import { apiClient, getApiErrorMessage } from '../../api/client'
import type { ApiResponse } from '../../types/api'
import type { RecordData } from './InvestigatePage'
type Stats={verified_cases:number;training_cases:number;holdout_cases:number;observations:number;minimum_training_cases:number;learning_status:string;note:string;actions:{name:string;uses:number;helpful_rank_changes:number;mean_actual_seconds:number|null;no_effective_evidence:number}[]}
type Evaluation={cases:number;top1_agreement:number|null;labels:string[];confusion_matrix:number[][];note:string}
export function InvestigationExperiencePanel({record,gid,guest,save}:{record:RecordData|null;gid:number;guest:boolean;save:(r:RecordData)=>void}) {
  const {message}=App.useApp(),[stats,setStats]=useState<Stats|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[training,setTraining]=useState('')
  const [evaluation,setEvaluation]=useState<Evaluation|null>(null)
  const load=useCallback(async()=>{if(guest)return;try{const [s,e]=await Promise.all([apiClient.get<ApiResponse<Stats>>('/investigate/experience'),apiClient.get<ApiResponse<Evaluation>>('/investigate/evaluation')]);setStats(s.data.data);setEvaluation(e.data.data);setError('')}catch(e){setError(getApiErrorMessage(e))}},[guest])
  useEffect(()=>{void load()},[load,record?.version])
  const act=async(fn:()=>Promise<void>)=>{setBusy(true);try{await fn()}catch(e){setError(getApiErrorMessage(e))}finally{setBusy(false)}}
  return <Card title="人工核验与经验积累">
    {guest?<Alert type="info" message="游客记录不进入训练集；登录并完成真实人工核验后才累计案例。"/>:<>
      <Space wrap><Tag>人工核验案例 {stats?.verified_cases??0}</Tag><Tag>已记录观察 {stats?.observations??0}</Tag><Tag>{stats?.learning_status==='eligible_for_training'?'可尝试案例隔离训练':'核验数据不足，使用规则策略'}</Tag></Space>
      <p>{stats?.note}</p>{error&&<Alert type="error" message={error}/>}
      {record?.status==='completed'&&<Form key={record.id} layout="vertical" initialValues={{...record.payload.verification,dataset_usage:record.payload.verification?.dataset_usage??'training'}} onFinish={values=>void act(async()=>{const r=await apiClient.post<ApiResponse<RecordData>>('/investigate/'+record.id+'/verify',{...values,version:record.version});save(r.data.data);await load();message.success('人工核验已记录')})}>
        <Form.Item name="dataset_usage" label="案例用途（首次确认后固定，验证案例不参与训练）"><Select options={[{value:'training',label:'经验训练案例'},{value:'holdout',label:'保留验证案例'}]}/></Form.Item>
        <Form.Item name="cause_id" label="最终人工核验原因"><Select allowClear options={record.payload.analysis.candidates.filter(c=>c.id!=='unknown').map(c=>({value:c.id,label:c.name}))}/></Form.Item>
        <Form.Item name="method" label="核验方法或独立证据" rules={[{required:true,whitespace:true,min:4}]}><Input placeholder="例如农艺师现场复核、镜检或检测报告编号" maxLength={500}/></Form.Item>
        <Form.Item name="conclusion" label="核验结论" rules={[{required:true,whitespace:true,min:4}]}><Input.TextArea maxLength={1000}/></Form.Item>
        <Form.Item name="confirmed" valuePropName="checked"><Checkbox>我已依据人工核验确认上述原因，允许进入经验数据；未勾选则记为仍未明确</Checkbox></Form.Item>
        <Button htmlType="submit" type="primary" loading={busy}>保存人工核验</Button>
      </Form>}
      {record?.status!=='completed'&&<p className="investigate-muted">先记录最终排查结果并归档，再填写人工核验。AI的自动判断不会自行成为训练标签。</p>}
      <div className="investigate-table"><table><thead><tr><th>观察</th><th>次数</th><th>向核验目标排名改善</th><th>实际平均秒数</th><th>未获有效证据</th></tr></thead><tbody>{stats?.actions.map((a,i)=><tr key={i}><td>{a.name}</td><td>{a.uses}</td><td>{a.helpful_rank_changes}</td><td>{a.mean_actual_seconds??'未记录'}</td><td>{a.no_effective_evidence}</td></tr>)}</tbody></table></div>
      <Space wrap><Button disabled={busy} onClick={()=>void act(async()=>{const r=await apiClient.get('/investigate/training-data');const url=URL.createObjectURL(new Blob([JSON.stringify(r.data.data,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download='investigation-verified-dataset.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),5000)})}>导出本组织核验数据</Button>
        <Button disabled={busy||!gid||(stats?.training_cases??0)<30} onClick={()=>void act(async()=>{const r=await apiClient.post('/investigate/train-policy?greenhouse_id='+gid);setTraining(JSON.stringify(r.data.data,null,2))})}>训练轻量观察策略</Button></Space>
      <p className="investigate-muted">至少30个有观察的核验案例。按调查案例划分训练/测试；只有优于留出案例常量基线才启用，预测的是排名增益代理，不能宣称真实诊断准确率提升。</p>
      {training&&<pre>{training}</pre>}
      <p>训练案例 {stats?.training_cases??0} · 保留验证案例 {evaluation?.cases??0} · 回顾性首位结论一致率 {evaluation?.top1_agreement==null?'暂无可评测数据':(100*evaluation.top1_agreement).toFixed(1)+'%'}</p>
      <p className="investigate-muted">{evaluation?.note}</p>
      {!!evaluation?.cases&&<div className="investigate-table"><table><caption>混淆矩阵：行是人工核验，列是系统首位候选</caption><thead><tr><th>原因</th>{evaluation.labels.map(l=><th key={l}>{record?.payload.analysis.candidates.find(c=>c.id===l)?.name??l}</th>)}</tr></thead><tbody>{evaluation.labels.map((l,i)=><tr key={l}><th>{record?.payload.analysis.candidates.find(c=>c.id===l)?.name??l}</th>{evaluation.confusion_matrix[i].map((n,j)=><td key={j}>{n}</td>)}</tr>)}</tbody></table></div>}
    </>}
  </Card>
}
