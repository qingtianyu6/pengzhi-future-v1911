import { useEffect, useRef, useState } from 'react'
import { Alert, App, Button, Card, Checkbox, Collapse, Drawer, Form, Input, Select, Space, Tag, Upload } from 'antd'
import type { RecordData, Evidence } from './InvestigatePage'
import { apiClient, getApiErrorMessage } from '../../api/client'
import { fetchCommunityAsset } from '../../api/communityApi'
import { CommunityAsset } from '../../components/CommunityMarkdown'
import type { ApiResponse } from '../../types/api'

export type VisualResult = {
  schema_version: string; image_hash: string; analyzed_at: string; width: number; height: number
  quality: { issues: string[]; retake: boolean; yellow_pixel_fraction: number; occlusion: string }
  features: { key: string; suspected: boolean | null; description: string; method: string; review_reason: string }[]
  regions: { kind: string; label: string; box: number[] }[]
  classifier: { recognition_status?: string; status?: string; predicted_class_name?: string; model_version?: string; model_status?: string; note?: string }
  multimodal: { status: string; model?: string; reason?: string }; local_model: string
}
const visualLabels: Record<string,string> = { yellow_pixels:'黄色像素（未分割叶片）',yellowing:'叶片黄化',spots:'斑点',necrosis:'疑似坏死',mold:'疑似霉层',webbing:'蛛网状结构',curling:'卷叶/形态异常' }
const canonical = ['yellowing','spots','necrosis','mold','webbing','curling']
const CommunityPhoto=({assetId}:{assetId:number})=><CommunityAsset asset={{id:assetId,filename:'调查图片',media_type:'image/jpeg'}}/>
async function post<T>(url:string,data:object|FormData) {
  const response=await apiClient.post<ApiResponse<T>>(url,data,{timeout:120000,...(data instanceof FormData ? {headers:{'Content-Type':undefined}} : {})})
  return response.data.data
}
async function guestCalculate(r:RecordData,evidence:Evidence[]):Promise<RecordData> {
  const response=await fetch('/api/investigate-demo/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...r.payload,evidence,unavailable_actions:r.payload.context.unavailable_actions || []})})
  const body=await response.json()
  if(!response.ok) throw new Error(body.message || '规则重算失败')
  const calculated=body.data as RecordData
  const last=calculated.payload.history.at(-1)!
  return {...calculated,id:r.id,greenhouse_id:r.greenhouse_id,photos:r.photos,payload:{...calculated.payload,autonomy_runs:r.payload.autonomy_runs,history:[...r.payload.history,{...last,round:r.payload.history.length,previous_leader:r.payload.analysis.candidates[0].name}]}}
}
async function preview(file:File) {
  const bitmap=await createImageBitmap(file)
  const scale=Math.min(1,1000/Math.max(bitmap.width,bitmap.height))
  const canvas=document.createElement('canvas');canvas.width=bitmap.width*scale;canvas.height=bitmap.height*scale
  canvas.getContext('2d')!.drawImage(bitmap,0,0,canvas.width,canvas.height);bitmap.close()
  return canvas.toDataURL('image/jpeg',.75)
}
export function InvestigationVisionPanel({record,guest,ensure,save,compact=false,disabled=false,onBusy,initialZone='东侧'}:{record:RecordData|null;guest:boolean;ensure:()=>Promise<RecordData>;save:(r:RecordData)=>void;compact?:boolean;disabled?:boolean;onBusy?:(busy:boolean)=>void;initialZone?:string}) {
  const {message}=App.useApp()
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[action,setAction]=useState('front'),[zone,setZone]=useState('东侧')
  const [allow,setAllow]=useState(false),[available,setAvailable]=useState(false)
  const [detailsOpen,setDetailsOpen]=useState(false)
  const fileInput=useRef<HTMLInputElement>(null)
  useEffect(()=>{onBusy?.(busy)},[busy,onBusy])
  useEffect(()=>{ if(!guest) void apiClient.get<ApiResponse<{multimodal_enabled:boolean}>>('/investigate/capabilities').then(r=>setAvailable(r.data.data.multimodal_enabled)).catch(()=>setAvailable(false)) },[guest])
  const photoUnavailable=(id:string)=>!!record?.payload.context.unavailable_actions?.includes(id)||!!record?.payload.evidence.some(e=>e.action===id&&(!e.visual||!e.visual.quality.retake))
  const allPhotosDone=['front','back','plant'].every(photoUnavailable)
  useEffect(()=>{
    if(!record){setAction('front');setZone(initialZone);return}
    const next=record?.payload.analysis.next
    const unavailable=(id:string)=>!!record?.payload.context.unavailable_actions?.includes(id)||!!record?.payload.evidence.some(e=>e.action===id&&(!e.visual||!e.visual.quality.retake))
    if(next && ['front','back','plant'].includes(next.id)&&!unavailable(next.id))setAction(next.id)
    else setAction(previous=>!unavailable(previous)?previous:['front','back','plant'].find(id=>!unavailable(id))||previous)
    setZone(record?.payload.zone || initialZone)
  },[record,initialZone])
  const closed=record && (['completed','archived'].includes(record.status)||record.payload.analysis.remaining===0)
  const upload=async(file:File)=>{
    if(disabled||busy||allPhotosDone)return
    setBusy(true);setError('')
    try{
      if(file.size>8*1024*1024)throw new Error('照片请小于8MB')
      const r=await ensure()
      const data=new FormData();data.append('image',file)
      if(guest){
        const response=await fetch('/api/investigate-demo/vision',{method:'POST',body:data})
        const body=await response.json();if(!response.ok)throw new Error(body.message||'图片分析失败')
        const visual:VisualResult=body.data
        const e:Evidence={action,zone,features:{},note:'游客上传真实图片进行本地视觉分析，非真实生产记录',observed_at:new Date().toISOString(),visual}
        const updated=await guestCalculate(r,[...r.payload.evidence,e])
        updated.photos={...r.photos,[visual.image_hash]:await preview(file)}
        save(updated)
      }else{
        data.append('version',String(r.version));data.append('action',action);data.append('zone',zone);data.append('use_multimodal',String(allow))
        save(await post<RecordData>('/investigate/'+r.id+'/vision',data))
      }
      message.success('照片已分析，候选解释及下一项检查已重算')
    }catch(e){setError(getApiErrorMessage(e))}finally{setBusy(false)}
  }
  const review=async(index:number,features:Record<string,boolean|null>,reject_classifier:boolean,note:string)=>{
    if(!record)return
    setBusy(true);setError('')
    try{
      if(guest){
        const evidence=record.payload.evidence.map((e,i)=>i===index?{...e,visual_review:{...e.visual_review,...features},reject_classifier}:e)
        const updated=await guestCalculate(record,evidence)
        const old=record.payload.analysis,latest=updated.payload.analysis
        updated.payload.history=[...record.payload.history,{round:record.payload.history.length,at:new Date().toISOString(),leader:latest.candidates[0].name,previous_leader:old.candidates[0].name,
          changes:latest.candidates.map(c=>({name:c.name,before:old.candidates.find(p=>p.id===c.id)?.score||0,after:c.score})),analysis:latest}]
        save(updated)
      }else save(await post<RecordData>('/investigate/'+record.id+'/visual-review',{version:record.version,index,features,reject_classifier,note}))
      message.success('人工核查已保存，证据权重与排序已更新')
    }catch(e){setError(getApiErrorMessage(e))}finally{setBusy(false)}
  }
  const visuals=<div className="investigate-visual-grid">{record?.payload.evidence.map((e,i)=>e.visual&&<VisualCard key={i} evidence={e} photo={record.photos?.[e.visual.image_hash]} index={i} busy={busy||disabled||['completed','archived'].includes(record.status)} review={review}/>)}</div>
  if(compact){
    const photos=record?.payload.evidence.filter(e=>e.visual)||[],latest=photos.at(-1)
    return <Card id="investigation-vision" className="iw-vision-compact">
      <input ref={fileInput} type="file" accept="image/jpeg,image/png,image/webp" style={{display:'none'}} disabled={busy||disabled||!!closed||allPhotosDone} onChange={event=>{const file=event.target.files?.[0];event.target.value='';if(file)void upload(file)}}/>
      <div className="iw-photo-overview"><button className="iw-photo-thumb" type="button" aria-label="查看图片分析与修正 →" onClick={()=>latest?setDetailsOpen(true):fileInput.current?.click()}>{latest?(record?.photos?.[latest.visual!.image_hash]?<img src={record.photos[latest.visual!.image_hash]} alt="已上传叶片"/>:latest.asset_id?<CommunityPhoto assetId={latest.asset_id}/>:<span>图片证据</span>):<span className="iw-photo-placeholder">＋<small>添加叶片</small></span>}</button><div className="iw-photo-copy"><strong>{photos.length?`已添加 ${photos.length} 张照片`:'尚未添加照片'}</strong><p>{latest?`${latest.action==='back'?'叶片背面':latest.action==='plant'?'完整植株':'叶片正面'} · ${latest.zone}`:'JPG / PNG / WEBP'}</p><Button type="link" disabled={busy||disabled||!!closed||allPhotosDone} loading={busy} onClick={()=>fileInput.current?.click()}>⊕ 添加照片</Button></div></div>
      <details className="iw-photo-options"><summary>照片选项与分析详情</summary><Space wrap><Select disabled={busy||disabled||!!closed||allPhotosDone} aria-label="照片观察动作" value={action} onChange={setAction} options={[{value:'front',label:'叶片正面'},{value:'back',label:'叶片背面'},{value:'plant',label:'完整植株'}].map(o=>({...o,disabled:photoUnavailable(o.value)}))}/><Select aria-label="照片位置" value={zone} onChange={setZone} options={['东侧','中央','西侧','北侧','南侧'].map(value=>({value,label:value}))}/></Space>{!guest&&<p><Checkbox disabled={!available||busy||disabled} checked={allow} onChange={e=>setAllow(e.target.checked)}>本次启用图片模型解释（可能计费）</Checkbox></p>}<p>最大 8 MB；每次照片检查计入预算。</p>{latest&&<Button type="link" onClick={()=>setDetailsOpen(true)}>查看图片分析与修正 →</Button>}</details>
      {error&&<Alert type="error" message={error}/>}
      <Drawer title="图片证据 · 分析与人工修正" open={detailsOpen} onClose={()=>setDetailsOpen(false)} width={900} className="iw-detail-drawer" destroyOnHidden>{visuals}</Drawer>
    </Card>
  }
  return <Card id="investigation-vision" title={compact?undefined:'智能视觉 · 上传即分析'} className={compact?'iw-vision-compact'+(record?.payload.evidence.some(e=>e.visual)?' has-photos':''):undefined}>
    <p>{compact?'上传清晰的正面、背面或整株照片。':'上传正面、背面或整株照片。运行本地质量、颜色分析与现有番茄分类器；自动线索需人工复核。'}</p>
    <Space wrap><Select disabled={busy||disabled||!!closed||allPhotosDone} aria-label="照片观察动作" value={action} onChange={setAction} options={[{value:'front',label:'叶片正面'},{value:'back',label:'叶片背面'},{value:'plant',label:'完整植株'}].map(o=>({...o,disabled:photoUnavailable(o.value)}))} />
      <Select aria-label="照片位置" value={zone} onChange={setZone} options={['东侧','中央','西侧','北侧','南侧'].map(value=>({value,label:value}))} />
      <Upload accept="image/jpeg,image/png,image/webp" showUploadList={false} disabled={busy||disabled||!!closed||allPhotosDone} beforeUpload={file=>{void upload(file);return false}}><Button type="primary" loading={busy} disabled={disabled||!!closed||allPhotosDone}>{allPhotosDone?'图片检查已完成':'上传并自动分析照片'}</Button></Upload>
    </Space>
    {!guest&&<p><Checkbox disabled={!available||busy||disabled} checked={allow} onChange={e=>setAllow(e.target.checked)}>本次启用图片模型解释（可能计费）</Checkbox></p>}
    <p className="investigate-muted">JPG / PNG / WEBP · 最大 8 MB · 每次照片检查计入预算</p>
    {error&&<Alert type="error" message={error}/>}
    {visuals}
  </Card>
}
function VisualCard({evidence:e,photo,index,busy,review}:{evidence:Evidence;photo?:string;index:number;busy:boolean;review:(i:number,f:Record<string,boolean|null>,reject:boolean,note:string)=>Promise<void>}) {
  const v=e.visual!
  const [url,setUrl]=useState(photo||''),[failed,setFailed]=useState(false),[form]=Form.useForm()
  useEffect(()=>{if(!e.asset_id)return;let local='',active=true;void fetchCommunityAsset(e.asset_id).then(blob=>{local=URL.createObjectURL(blob);if(active)setUrl(local);else URL.revokeObjectURL(local)}).catch(()=>setFailed(true));return()=>{active=false;if(local)URL.revokeObjectURL(local)}},[e.asset_id])
  useEffect(()=>{form.setFieldsValue({features:Object.fromEntries(Object.entries(e.visual_review||{}).map(([k,value])=>[k,value===null?'reject':value?'yes':'no'])),reject:e.reject_classifier||false})},[e,form])
  return <div className="investigate-visual-card"><h3>照片#{index+1} · {e.zone} · {e.action==='back'?'叶片背面':e.action==='plant'?'完整植株':'叶片正面'}</h3>
    {url?<div className="investigate-image-frame" style={{width:Math.min(v.width,420*v.width/v.height)}}><img style={{width:'100%',height:'auto',maxHeight:'none'}} src={url} alt={'调查照片'+(index+1)}/>{v.regions.filter(r=>r.kind==='color_pixels').map((r,i)=><div className="investigate-region" key={i} title={r.label} style={{left:r.box[0]*100+'%',top:r.box[1]*100+'%',width:(r.box[2]-r.box[0])*100+'%',height:(r.box[3]-r.box[1])*100+'%'}} />)}</div>:<p>{failed?'此附件限原上传者读取；保留分析记录。':'读取图片中…'}</p>}
    {v.regions.length>0&&<small>图上仅标注实际黄色像素范围，不是病害检测框。</small>}
    <p><Tag>{v.local_model}</Tag><Tag>多模态：{v.multimodal.status}</Tag></p>
    <p>分类器：{v.classifier.model_version||'未就绪'} · {v.classifier.recognition_status||v.classifier.status} · {v.classifier.predicted_class_name||'无可靠类别输出'}</p>
    {v.multimodal.reason&&<p>{v.multimodal.reason}</p>}
    {v.quality.issues.length>0?<Alert type="warning" message="建议重拍或人工复核" description={v.quality.issues.join('；')}/>:<Tag color="green">基础曝光/纹理检查未触发问题（不保证图像可诊断）</Tag>}
    <p className="investigate-muted">{v.quality.occlusion}</p>
    {v.features.map((f,i)=><div key={i}><b>{visualLabels[f.key]} · {f.suspected===null?'不可判断':f.suspected?'可疑/测得':'未触发检测条件'}</b><p>{f.description}</p><small>{f.method} · {f.review_reason}</small></div>)}
    <Collapse items={[{key:'review',label:'确认、修正或拒绝视觉证据',children:<Form form={form} layout="vertical" onFinish={values=>{const features=Object.fromEntries(Object.entries(values.features||{}).filter(([,value])=>value!=null).map(([k,value])=>[k,value==='reject'?null:value==='yes']));void review(index,features,!!values.reject,values.note||'人工核查')}}>
      <p>模型未输出的特征可由你现场补查。留空不作确认；“拒绝”会移除该自动线索。操作不消耗新的检查次数。</p>
      {canonical.map(f=><Form.Item key={f} name={['features',f]} label={visualLabels[f]}><Select allowClear placeholder="尚未核查" options={[{value:'yes',label:'已核查：有'},{value:'no',label:'已核查：未见'},{value:'reject',label:'拒绝/无法判断该线索'}]}/></Form.Item>)}
      <Form.Item name="reject" valuePropName="checked"><Checkbox>不采用该照片的六分类候选</Checkbox></Form.Item>
      <Form.Item name="note" label="核查说明"><Input.TextArea maxLength={1000}/></Form.Item>
      <Button type="primary" htmlType="submit" disabled={busy}>保存人工核查并重算</Button>
      <Button disabled={busy} onClick={()=>void review(index,Object.fromEntries(canonical.map(k=>[k,null])),true,'人工拒绝全部自动视觉线索')}>拒绝全部自动线索</Button>
    </Form>}]} />
  </div>
}
