import type { ForumPost, PostInput, ForumComment } from '../types/community'

const storage = 'pengzhi_forum_demo_v2'
const date = () => new Date().toISOString()
function initial(): ForumPost[] {
  return [{ id: 1, title: '游客示例：清晨叶片潮湿，应该补充哪些观察？', body: '这是棚友论坛的示例讨论，供体验界面。可以记录**作物阶段、观察区域、湿度采样时间**，再提出待验证问题。\n\n示例内容不是农艺结论。', category: 'question', visibility: 'public', status: 'published', review_state: 'unreviewed', fields: { crop: 'tomato', stage: '开花坐果期' }, tags: ['观察记录'], author: '示例棚友', author_id: -2, version: 1, created_at: date(), updated_at: date(), accepted_comment_id: null, can_edit: false, can_moderate: false, likes: 0, liked: false, bookmarked: false, comment_count: 0, comments: [], assets: [] }]
}
export function guestCommunity(path: string, method: string, payload: object): unknown {
  let posts: ForumPost[]
  try { posts = JSON.parse(sessionStorage.getItem(storage) || 'null') || initial() } catch { posts = initial() }
  const p = payload as Record<string, unknown>
  const save = (result: unknown) => { sessionStorage.setItem(storage, JSON.stringify(posts)); return result }
  if (path === 'forum/posts' && method === 'get') {
    let selected = posts.filter(post => (!p.q || (post.title+post.body).includes(String(p.q))) && (!p.category || post.category === p.category) && (!p.crop || post.fields.crop === p.crop) && (!p.tag || post.tags.includes(String(p.tag))) && (p.mine !== 'posts' || post.can_edit) && (p.mine !== 'bookmarks' || post.bookmarked) && (p.mine !== 'replies' || post.comments?.some(c => c.author === '游客')))
    if(p.answer==='open')selected=selected.filter(post=>post.category==='question'&&!post.accepted_comment_id)
    if(p.answer==='resolved')selected=selected.filter(post=>!!post.accepted_comment_id)
    selected.sort((a,b)=>p.sort==='liked'?b.likes-a.likes:p.sort==='discussed'?b.comment_count-a.comment_count:new Date(b.updated_at).getTime()-new Date(a.updated_at).getTime())
    const page = Number(p.page) || 1
    return { items: selected.slice((page-1)*20, page*20), total: selected.length, page }
  }
  if (path === 'forum/posts' && method === 'post') {
    const input = payload as PostInput
    const post: ForumPost = { ...initial()[0], ...input, fields: input.fields || {}, tags: input.tags || [], id: Date.now(), author: '游客', author_id: -1, can_edit: true, created_at: date(), updated_at: date(), comments: [], assets: [] }
    posts.unshift(post); return save(post)
  }
  const match = path.match(/^forum\/posts\/(\d+)(.*)$/)
  if (match) {
    const post = posts.find(item => item.id === Number(match[1]))
    if (!post) throw new Error('示例帖子不存在')
    const tail = match[2]
    if (!tail && method === 'get') return post
    if (!tail && method === 'put' && post.can_edit) {
      const input = payload as PostInput
      Object.assign(post, input, { version: post.version+1, updated_at: date() }); return save(post)
    }
    if (!tail && method === 'delete' && post.can_edit) { posts = posts.filter(item => item.id !== post.id); return save({ deleted: true }) }
    if (tail === '/comments') {
      const comment: ForumComment = { id: Date.now(), author: '游客', body: String(p.body), parent_id: Number(p.parent_id) || null, created_at: date(), can_delete: true }
      post.comments = [...(post.comments || []), comment]; post.comment_count++; return save(post)
    }
    if (tail.startsWith('/comments/') && method === 'delete') {
      const id = Number(tail.split('/')[2]); post.comments = post.comments?.filter(c => c.id !== id); post.comment_count = post.comments?.length || 0
      if (post.accepted_comment_id === id) post.accepted_comment_id = null
      return save(post)
    }
    if (tail.startsWith('/accepted/') && post.can_edit) { post.accepted_comment_id = Number(tail.split('/')[2]); return save(post) }
    if (tail === '/reactions/like') { const enabled = Boolean(p.enabled); post.likes += Number(enabled)-Number(post.liked); post.liked = enabled; return save(post) }
    if (tail === '/reactions/bookmark') { post.bookmarked = Boolean(p.enabled); return save(post) }
    if (tail === '/reports') return { id: Date.now(), status: 'guest_only' }
    if (tail === '/assist') return { analysis: '这是游客辅助入口。请登录后检索正式知识库或调用已配置模型；不会自动发布AI回复。', sources: [], mode: 'guest', published: false, notice: '未调用真实模型。' }
  }
  if (path === 'news/articles') return { items: [], total: 0, page: 1 }
  if (['news/sources', 'news/digests', 'news/jobs', 'knowledge/documents', 'ai/evaluations', 'forum/moderation/reports'].includes(path) && method === 'get') return []
  if (path === 'news/preferences' && method === 'get') return { crops: [], topics: [], enabled: false, local_hour: 8 }
  if (path === 'knowledge/search') return { items: [], method: 'guest_no_documents' }
  if (path === 'ai/traces') return { items: [], tool_calls: 0, tool_success_rate: null, token_total: 0, actual_cost: null, cost_note: '游客不读取正式追踪数据', window_note: '' }
  throw new Error('请登录后使用此功能；游客不会写入正式论坛、订阅或知识库')
}
