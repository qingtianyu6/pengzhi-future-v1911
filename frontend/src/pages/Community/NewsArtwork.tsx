import { useEffect, useRef, useState } from 'react'
import { communityRequest } from '../../api/communityApi'
import { newsCategory, newsImage, newsUrl, type NewsItem } from './newsPresentation'

type Result = { status: string; image_url: string | null; article_url?: string; alt?: string }
const cache = new Map<string, { expires: number; result: Promise<Result> }>()
const waiting: (() => void)[] = []
let active = 0
function queued<T>(work: () => Promise<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    const run = () => { active++; void work().then(resolve, reject).finally(() => { active--; waiting.shift()?.() }) }
    if (active < 3) run(); else waiting.push(run)
  })
}
function originalImage(item: NewsItem): Promise<Result> {
  const publicItem = item.public_preview || item.id < 0
  if (publicItem && !/^https?:\/\/(?:www|zzys)\.moa\.gov\.cn\/.+\/t\d{8}_\d+\.htm(?:[?#].*)?$/.test(item.url)) return Promise.resolve({ status: 'unsupported', image_url: null })
  const key = `${publicItem ? 'public' : item.id}:${item.url}`
  const previous = cache.get(key)
  if (previous && previous.expires > Date.now()) return previous.result
  const result = queued(async () => {
    if (!publicItem) return communityRequest<Result>(`news/articles/${item.id}/image`)
    const response = await fetch('/api/community-public/news/article-image?' + new URLSearchParams({ url: item.url }), { signal: AbortSignal.timeout(22000) })
    if (!response.ok) throw new Error('原文图片暂不可用')
    return (await response.json()).data as Result
  }).catch(() => ({ status: 'unavailable', image_url: null }))
  cache.set(key, { expires: Date.now() + 60000, result })
  if (cache.size > 256) cache.delete(cache.keys().next().value!)
  return result
}

export default function NewsArtwork({ item }: { item?: NewsItem }) {
  const host = useRef<HTMLDivElement>(null)
  const [result, setResult] = useState<{ key: string; data: Result }>()
  const [failed, setFailed] = useState<string>()
  const key = item?.url ?? ''
  const id = item?.id
  const preview = item?.public_preview
  useEffect(() => {
    if (!key || id == null) return
    let alive = true
    const load = () => { void originalImage({ url: key, id, public_preview: preview } as NewsItem).then(data => { if (alive) setResult({ key, data }) }) }
    if (!('IntersectionObserver' in window)) { load(); return () => { alive = false } }
    const observer = new IntersectionObserver(entries => { if (entries.some(entry => entry.isIntersecting)) { observer.disconnect(); load() } }, { rootMargin: '160px' })
    if (host.current) observer.observe(host.current)
    return () => { alive = false; observer.disconnect() }
  }, [key, id, preview])
  const original = result?.key === key && result.data.status === 'found' ? newsUrl(result.data.image_url ?? '') : undefined
  const image = original && failed !== original ? original : !item ? newsImage(item) : undefined
  const visible = image && failed !== image
  return <div ref={host} className="news-artwork" data-image-kind={visible ? original ? 'original' : 'illustration' : 'category'}>
    {visible ? <img src={image} alt={original ? result?.data.alt || item?.title || '新闻原文配图' : ''} title={original ? '原文配图 · ' + item?.source : '农业场景示意'} loading="lazy" decoding="async" referrerPolicy="no-referrer" onError={() => setFailed(image)} /> : <div className="news-category-art" role="img" aria-label={newsCategory(item) + '分类配图'} data-category={newsCategory(item)}><span>棚智农讯</span><strong>{newsCategory(item)}</strong><i aria-hidden="true" /><small>FIELD NOTES</small></div>}
  </div>
}
