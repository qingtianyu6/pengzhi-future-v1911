import { useCallback, useEffect, useState } from 'react'
import { Alert, Button, Card, Empty, List, Spin } from 'antd'
import { communityRequest } from '../../api/communityApi'
import { getApiErrorMessage } from '../../api/client'

type Headlines={items:{title:string;url:string;source:string;published_at:string|null}[];fetched_at:string;notice:string;sources:{status:string}[]}
export function ChineseNewsPreview(){
  const [data,setData]=useState<Headlines>(),[error,setError]=useState(''),[loading,setLoading]=useState(false)
  const load=useCallback(async()=>{setLoading(true);try{setData(await communityRequest<Headlines>('news/public-headlines'));setError('')}catch(e){setError(getApiErrorMessage(e))}finally{setLoading(false)}},[])
  useEffect(()=>{void load()},[load])
  return <Card title="中文农业资讯 · 官方标题速览" extra={<Button loading={loading} onClick={()=>void load()}>刷新速览</Button>}>
    {error&&<Alert type="error" message={error}/>}
    <Spin spinning={loading}><p className="community-muted">{data?.notice||'正在读取农业农村部公开栏目，保留原始出处；不写入你的组织订阅记录。'}</p>
      {data?.sources.some(s=>s.status!=='ok')&&<Alert type="warning" message="部分栏目暂不可访问，未编造缺失资讯。"/>}
      <List dataSource={data?.items||[]} locale={{emptyText:loading?'正在获取公开标题':<Empty description="暂无可读取的官方标题，可稍后重试"/>}} renderItem={item=><List.Item><List.Item.Meta title={<a href={item.url} target="_blank" rel="noopener noreferrer">{item.title}</a>} description={`${item.source} · ${item.published_at||'来源未提供日期'}`}/></List.Item>}/>
      {data&&<p className="community-muted">读取时间：{new Date(data.fetched_at).toLocaleString('zh-CN')} · 每小时缓存，刷新速览不会重复抓取全文。</p>}
    </Spin>
  </Card>
}
