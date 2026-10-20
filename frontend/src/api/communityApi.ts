import { apiClient } from './client'
import { isGuestMode } from './guestMode'
import { guestCommunity } from './communityGuest'
import type { ApiResponse } from '../types/api'

export async function communityRequest<T>(path: string, method = 'get', data: object = {}): Promise<T> {
  if(['news/source-catalog','news/public-headlines'].includes(path) && method==='get'){const r=await fetch('/api/community-public/'+path);const body=await r.json();if(!r.ok)throw new Error(body.message||'来源目录读取失败');return body.data as T}
  if (((isGuestMode() && path === 'knowledge/search') || path === 'knowledge/catalog') && method === 'get') {
    const query=new URLSearchParams(Object.entries(data).filter(([,v])=>v!=null&&v!=='').map(([k,v])=>[k,String(v)]))
    const response=await fetch('/api/community-public/knowledge?'+query)
    const body=await response.json()
    if (!response.ok) throw new Error(body.message||'公共资料读取失败')
    return body.data as T
  }
  if (isGuestMode()) return guestCommunity(path, method, data) as T
  const response = await apiClient.request<ApiResponse<T>>({ url: '/community/' + path, method,
    timeout: path.includes('automation/run') ? 540000 : path.includes('ai/evaluations') ? 540000 : path.includes('/analy') || path.includes('/assist') ? 90000 : 60000,
    ...(method === 'get' ? { params: data } : { data }) })
  return response.data.data
}
export async function uploadCommunity<T>(path: string, body: FormData): Promise<T> {
  if (isGuestMode()) throw new Error('请登录后上传，游客文件不会写入正式平台')
  const response = await apiClient.post<ApiResponse<T>>('/community/' + path, body, { headers: { 'Content-Type': undefined }, timeout: 90000 })
  return response.data.data
}
export async function fetchCommunityAsset(id: number) {
  const response = await apiClient.get('/community/forum/assets/' + id, { responseType: 'blob' })
  return response.data as Blob
}
