import { useEffect, useRef, useState } from 'react'
import { Alert, Button, Empty, Input, Tag } from 'antd'
import type { KnowledgeDocument } from '../../types/community'
import './knowledge-reader.css'

export default function KnowledgeDocumentReader({ record, chunkId }: { record: KnowledgeDocument; chunkId?: number }) {
  const [query, setQuery] = useState('')
  const list = useRef<HTMLDivElement>(null)
  const chunks = record.chunks ?? []
  const terms = query.normalize('NFKC').trim().toLocaleLowerCase().split(/\s+/).filter(Boolean)
  const visible = chunks.filter(chunk => terms.every(term => (chunk.position + ' ' + chunk.content).normalize('NFKC').toLocaleLowerCase().includes(term)))
  const hasTarget = chunks.some(chunk => chunk.id === chunkId)
  const focusTarget = () => {
    const target = list.current?.querySelector<HTMLElement>(`[data-chunk-id="${chunkId}"]`)
    target?.scrollIntoView({ block: 'nearest' })
    target?.focus({ preventScroll: true })
  }
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const target = list.current?.querySelector<HTMLElement>(`[data-chunk-id="${chunkId}"]`)
      target?.scrollIntoView({ block: 'nearest' })
      target?.focus({ preventScroll: true })
    }, 350)
    return () => window.clearTimeout(timer)
  }, [record.id, chunkId])
  return <section className="knowledge-reader" aria-label="文档原文阅读">
    {record.applicability && <p className="knowledge-reader-context">{record.applicability}</p>}
    {record.error && <Alert type="error" message={record.error} />}
    <div className="knowledge-reader-toolbar">
      <Input.Search allowClear value={query} onChange={event => setQuery(event.target.value)} placeholder="搜索段落、页码或关键词" aria-label="搜索文档片段" />
      {hasTarget && <Button onClick={() => { setQuery(''); window.requestAnimationFrame(focusTarget) }}>定位引用片段</Button>}
    </div>
    <div className="knowledge-reader-meta"><span>{query ? `匹配 ${visible.length} / ${chunks.length} 个片段` : `共 ${chunks.length} 个原文片段`}</span>{record.source_url && /^https?:\/\//i.test(record.source_url) && <a href={record.source_url} target="_blank" rel="noopener noreferrer">打开文档出处 ↗</a>}</div>
    <div className="knowledge-reader-chunks" ref={list}>
      {visible.length ? visible.map(chunk => <article key={chunk.id} data-chunk-id={chunk.id} className={`knowledge-reader-chunk${chunk.id === chunkId ? ' is-cited' : ''}`} aria-current={chunk.id === chunkId ? 'location' : undefined} tabIndex={-1}>
        <header><Tag>{chunk.position}</Tag>{chunk.id === chunkId && <span>本次引用</span>}</header><p>{chunk.content}</p>
      </article>) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={query ? '没有匹配的原文片段' : '此文档暂无可阅读的文字片段'}>{query && <Button onClick={() => setQuery('')}>清除片段搜索</Button>}</Empty>}
    </div>
  </section>
}
