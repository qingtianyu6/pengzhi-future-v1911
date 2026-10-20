import type { NewsArticle, NewsPreference } from '../../types/community'
import greenhouse from '../../assets/pure-scenes/greenhouse-wide-1920.webp'

export type NewsItem = NewsArticle & { public_preview?: boolean }
export interface PublicHeadlines { items: { title: string; url: string; source: string; published_at: string | null }[]; fetched_at: string; sources: { status: string }[] }
export interface PublicNewsState { saved: NewsItem[]; read: string[]; preferences: NewsPreference }
export const defaultNewsPreference: NewsPreference = { crops: [], topics: [], enabled: false, local_hour: 8 }
export const themes = [{ value: 'all', label: '全部' }, { value: 'facility', label: '设施农业' }, { value: 'cultivation', label: '种植技术' }, { value: 'disease', label: '病虫防治' }, { value: 'policy', label: '农业政策' }]
const words: Record<string, RegExp> = {
  facility: /温室|大棚|设施|greenhouse/i, cultivation: /栽培|种植|育苗|授粉|水肥|灌溉|cultivation/i,
  disease: /病害|虫害|病虫|防治|防控|disease/i, policy: /政策|通知|意见|规划|部署|policy/i,
  tomato: /番茄|西红柿|tomato/i, muskmelon: /甜瓜|香瓜|蜜瓜|muskmelon/i,
  weather: /气象|天气|阴雨|高温|低温|寒潮|weather/i, technology: /科技|技术|数字|智能|智慧|technology/i, market: /市场|价格|供需|统计|market/i,
}
export const newsUrl = (url: string) => /^https?:\/\//i.test(url) ? url : undefined
export function matchesNews(item: NewsItem, theme: string) { return theme === 'all' || item.tags.includes(theme) || !!words[theme]?.test(item.title + ' ' + item.summary) }
export function publicItems(data: PublicHeadlines | null, state: PublicNewsState): NewsItem[] {
  return (data?.items || []).filter(a => newsUrl(a.url)).map((a, i) => ({ ...a, id: -i - 1, public_preview: true, summary: '', collected_at: data!.fetched_at, tags: Object.keys(words).filter(key => words[key].test(a.title)), status: 'metadata_only', analysis: {}, bookmarked: state.saved.some(s => s.url === a.url), read_at: state.read.includes(a.url) ? data!.fetched_at : null }))
}
export function readPublicNews(key: string): PublicNewsState {
  const fallback = { saved: [], read: [], preferences: { ...defaultNewsPreference } }
  try {
    const data = JSON.parse(sessionStorage.getItem(key) || 'null')
    if (!data || typeof data !== 'object') return fallback
    return { saved: Array.isArray(data.saved) ? data.saved.filter((a: NewsItem) => a && typeof a.title === 'string' && typeof a.url === 'string' && newsUrl(a.url) && typeof a.source === 'string' && Array.isArray(a.tags) && typeof a.summary === 'string' && a.public_preview === true) : [], read: Array.isArray(data.read) ? data.read.filter((url: unknown) => typeof url === 'string') : [], preferences: { ...defaultNewsPreference, crops: Array.isArray(data.preferences?.crops) ? data.preferences.crops.filter((s: unknown) => typeof s === 'string') : [], topics: Array.isArray(data.preferences?.topics) ? data.preferences.topics.filter((s: unknown) => typeof s === 'string') : [] } }
  } catch { return fallback }
}
export function newsImage(item?: NewsItem) {
  if (!item) return greenhouse
  if (/番茄|西红柿/.test(item.title)) return '/images/news/tomato-feature-v1.png'
  if (item && /甜瓜|香瓜|蜜瓜/.test(item.title)) return '/images/greenhouse-management/muskmelon.png'
  if (item && /温室|大棚|设施|环境|通风/.test(item.title)) return greenhouse
  if (item && /育苗|幼苗|春耕/.test(item.title)) return '/homepage-v11/scene-leafy.jpg'
  return undefined
}
export function newsCategory(item?: NewsItem) {
  const title = item?.title ?? ''
  if (/政策|通知|意见|规划|部署|遗产/.test(title)) return '农业政策'
  if (/市场|价格|供需|统计|增至/.test(title)) return '市场动态'
  if (/病害|虫害|病虫|防治|防控/.test(title)) return '植保观察'
  if (/玉米|小麦|水稻|大豆|粮食/.test(title)) return '大田种植'
  if (/科技|技术|数字|智能|智慧/.test(title)) return '农业科技'
  return '农业动态'
}
export function newsDate(value: string | null) {
  if (!value) return '日期未提供'
  // SQLite UTC timestamps have no zone suffix; date-only publication dates retain their date.
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value
  const date = new Date(/(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : value + 'Z')
  return Number.isNaN(date.getTime()) ? '日期未提供' : date.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
