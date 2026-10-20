import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Button } from 'antd'
import type { ContentAsset } from '../types/community'
import { fetchCommunityAsset } from '../api/communityApi'

export function CommunityMarkdown({ children }: { children: string }) {
  return <div className="community-markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={{
    a: ({ href, children }) => href && /^(https?:\/\/|\/platform\/)/i.test(href) ? <a href={href} target="_blank" rel="noopener noreferrer">{children}</a> : <span>{children}</span>,
    img: ({ alt }) => <span className="community-muted">[图片：{alt || '请使用受控附件上传'}]</span>,
  }}>{children}</ReactMarkdown></div>
}
export function CommunityAsset({ asset }: { asset: ContentAsset }) {
  const [url, setUrl] = useState(''), [error, setError] = useState(false)
  useEffect(() => {
    let active = true, owned = ''
    void fetchCommunityAsset(asset.id).then(blob => { owned = URL.createObjectURL(blob); if (active) setUrl(owned); else URL.revokeObjectURL(owned) }).catch(() => { if (active) setError(true) })
    return () => { active = false; if (owned) URL.revokeObjectURL(owned) }
  }, [asset.id])
  return error ? <span>附件无法读取</span> : url ? asset.media_type.startsWith('image/') ? <figure><img src={url} alt={asset.filename} style={{ maxWidth: '100%', maxHeight: 420, objectFit: 'contain' }} /><figcaption>{asset.filename}</figcaption></figure> : <Button href={url} download={asset.filename}>下载 {asset.filename}</Button> : <span>读取附件中…</span>
}
