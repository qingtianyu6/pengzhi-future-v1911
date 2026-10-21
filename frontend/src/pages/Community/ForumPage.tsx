import { useCallback, useEffect, useState } from 'react'
import { App, Alert, Button, Card, Checkbox, Collapse, Empty, Form, Input, List, Modal, Pagination, Select, Space, Spin, Skeleton, Tag, Upload } from 'antd'
import { CommentOutlined, PlusOutlined, LikeOutlined, LikeFilled, StarOutlined, StarFilled, FilterOutlined, FileTextOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { communityRequest as request, uploadCommunity } from '../../api/communityApi'
import { getApiErrorMessage } from '../../api/client'
import { getStoredUser } from '../../api/authApi'
import { isGuestMode } from '../../api/guestMode'
import { getResearchWorkspace } from '../../api/agronomistApi'
import { CommunityAsset, CommunityMarkdown } from '../../components/CommunityMarkdown'
import type { ContentAsset, ForumAnalysis, ForumPost, ForumReport, Page, PostInput } from '../../types/community'
import type { ResearchRecord } from '../../types/agronomist'
import './community.css'
import './forum-refresh.css'

const categories = [{ value: 'question', label: '种植求助' }, { value: 'experience', label: '农事经验' }, { value: 'research', label: '生产研究' }, { value: 'discussion', label: '棚友交流' }]
const crops = [{ value: 'tomato', label: '番茄' }, { value: 'muskmelon', label: '甜瓜' }]
const times = (s: string) => new Date(s).toLocaleString('zh-CN')
const shortTime=(s:string)=>new Date(s).toLocaleString('zh-CN',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})
const excerpt=(text:string)=>text.replace(/!\[([^\]]*)\]\([^)]*\)/g,'$1').replace(/\[([^\]]+)\]\([^)]*\)/g,'$1').replace(/[*_`>#]/g,'').replace(/\s+/g,' ').trim()
export default function ForumPage() { return <App><Forum /></App> }
function Forum() {
  const { message, modal } = App.useApp(), navigate = useNavigate()
  const [params, setParams] = useSearchParams(), guest = isGuestMode()
  const selected = Number(params.get('post')) || null, gid = Number(params.get('greenhouse_id')) || undefined
  const [list, setList] = useState<Page<ForumPost>>({ items: [], total: 0, page: 1 }), [detail, setDetail] = useState<ForumPost | null>(null)
  const [loading, setLoading] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState('')
  const [search, setSearch] = useState(''), [category, setCategory] = useState<string>(), [crop, setCrop] = useState<string>(), [tag, setTag] = useState(''), [mine, setMine] = useState(''), [page, setPage] = useState(1)
  const [answer,setAnswer]=useState('all'),[sort,setSort]=useState('recent')
  const [searchDraft,setSearchDraft]=useState('')
  const resetFilters=()=>{setSearch('');setSearchDraft('');setCategory(undefined);setCrop(undefined);setTag('');setMine('');setAnswer('all');setSort('recent');setPage(1)}
  const hasFilters=!!(search||category||crop||tag||mine||answer!=='all'||sort!=='recent')
  const [editor, setEditor] = useState(false), [editing, setEditing] = useState<ForumPost | null>(null), [assets, setAssets] = useState<ContentAsset[]>([])
  const [form] = Form.useForm<PostInput>(), [commentForm] = Form.useForm(), [replyId, setReplyId] = useState<number>()
  const [analysis, setAnalysis] = useState<ForumAnalysis | null>(null), [report, setReport] = useState(false), [reason, setReason] = useState('')
  const [reports, setReports] = useState<ForumReport[] | null>(null), [studies, setStudies] = useState<ResearchRecord[]>([])
  const body = Form.useWatch('body', form) || ''
  const isAdmin = getStoredUser()?.role === 'admin'
  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      if (selected) setDetail(await request<ForumPost>('forum/posts/' + selected))
      else setList(await request<Page<ForumPost>>('forum/posts', 'get', { q: search, category, crop, tag, mine, page, answer, sort }))
    } catch (e) { setError(getApiErrorMessage(e)) }
    finally { setLoading(false) }
  }, [selected, search, category, crop, tag, mine, page, answer, sort])
  useEffect(() => { void load() }, [load])
  const act = async (fn: () => Promise<unknown>, success: string) => {
    setBusy(true)
    try { await fn(); message.success(success); await load() } catch (e) { message.error(getApiErrorMessage(e)) } finally { setBusy(false) }
  }
  const openPost = (id?: number) => setParams(previous => { const p = new URLSearchParams(previous); if (id) p.set('post', String(id)); else p.delete('post'); return p })
  const openEditor = async (post?: ForumPost) => {
    const reference=params.get('reference_url')||''
    const referenceUrl=/^https?:\/\/[^\s]+$/i.test(reference)?reference:''
    setEditing(post || null); setAssets(post?.assets || []); form.resetFields()
    form.setFieldsValue(post ? { ...post, asset_ids: post.assets?.map(a => a.id) } : { title: params.get('topic')?.slice(0,180)||'', body: params.get('topic')?'参考资料：'+params.get('topic')+(referenceUrl?'\n原始出处：'+referenceUrl:'')+'\n\n我的作物、现场情况与问题：':'', category: 'question', visibility: 'organization', fields: {references:referenceUrl?[referenceUrl]:[]}, tags: [] })
    setEditor(true)
    if (gid) { try { const w = await getResearchWorkspace({ greenhouse_id: gid }); setStudies(w.records.filter(r => r.kind === 'study' && r.status === 'completed')) } catch { setStudies([]) } }
  }
  const save = (input: PostInput) => act(async () => {
    const post = await request<ForumPost>(editing ? 'forum/posts/' + editing.id : 'forum/posts', editing ? 'put' : 'post', { ...input, asset_ids: assets.map(a => a.id), version: editing?.version })
    setEditor(false); openPost(post.id)
  }, guest ? '已保存到游客会话' : '帖子已保存')
  const research = () => {
    if (!gid) { message.info('请先选择大棚'); return }
    if (!detail) return
    void act(async () => {
      const r = await request<{ research_id: number; greenhouse_id: number }>('forum/posts/' + detail.id + '/research', 'post', { greenhouse_id: gid })
      navigate('/platform/research?greenhouse_id=' + r.greenhouse_id + '&tab=studies')
    }, '研究草稿已创建')
  }
  const linkResearch = () => {
    if (!detail || !gid) return
    let researchId: number | undefined
    modal.confirm({ title: '关联审核后的经验', content: <Select style={{ width: '100%' }} placeholder="选择本棚研究" options={studies.map(s => ({ value: s.id, label: s.title }))} onChange={value => { researchId = value }} />,
      onOk: async () => { if (!researchId) throw new Error('请选择研究'); await request('forum/posts/' + detail.id + '/research', 'post', { greenhouse_id: gid, research_id: researchId, confirmed: true }); message.success('经验来源已关联') } })
  }
  return <div className={`community-page forum-page${selected?' is-detail':''}`}>
    <header className="community-hero"><div><span className="community-eyebrow">GROW TOGETHER</span><h1>棚友论坛</h1><p>交流种植问题，分享田间经验。</p></div><Space wrap>{isAdmin && <Button onClick={() => void request<ForumReport[]>('forum/moderation/reports').then(setReports).catch(e => message.error(getApiErrorMessage(e)))}>举报与审核</Button>}<Button type="primary" aria-label="发布帖子" icon={<PlusOutlined />} onClick={() => void openEditor()}>发布帖子</Button></Space></header>{guest&&<p className="forum-scenario-note">体验区预置 8 则情景讨论，昵称与经历为虚构；你发布的内容仅保存在当前浏览器会话。</p>}
    {error && <Alert type="error" message={error} action={<Button onClick={() => void load()}>重试</Button>} />}
    {selected ? <><Button className="community-back" onClick={() => openPost()}>← 返回论坛</Button>{loading ? <Spin /> : detail && <>
      <Card><Space wrap><Tag>{categories.find(c => c.value === detail.category)?.label}</Tag><Tag>{detail.visibility === 'public' ? '公开' : detail.visibility === 'private' ? '仅自己' : '组织内'}</Tag><Tag>{detail.review_state === 'reviewed' ? '经验已审核' : '待核实讨论'}</Tag>{detail.status === 'hidden' && <Tag color="orange">已隐藏</Tag>}</Space><h2>{detail.title}</h2><p className="community-muted">{detail.author} · {times(detail.updated_at)} · V{detail.version}</p>
      <CommunityMarkdown>{detail.body}</CommunityMarkdown>
      <div className="community-agriculture">{Object.entries(detail.fields).filter(([key, value]) => key !== 'references' && value).map(([key, value]) => <span key={key}><b>{{ crop: '作物', variety: '品种', stage: '生育阶段', issue: '问题类型', environment: '环境条件', attempted: '已尝试措施', observation: '观察结果' }[key] || key}</b>{String(value)}</span>)}</div>
      {detail.fields.references?.map(url => <p key={url}><a href={url} target="_blank" rel="noopener noreferrer">参考来源：{url}</a></p>)}
      <Space wrap>{detail.tags.map(t => <Tag key={t}>{t}</Tag>)}</Space>
      <div className="community-assets">{detail.assets?.map(a => <CommunityAsset key={a.id} asset={a} />)}</div>
      <Space wrap><Button loading={busy} onClick={() => void act(() => request('forum/posts/' + detail.id + '/reactions/like', 'put', { enabled: !detail.liked }), '点赞已更新')}>{detail.liked ? '取消点赞' : '点赞'} {detail.likes}</Button><Button onClick={() => void act(() => request('forum/posts/' + detail.id + '/reactions/bookmark', 'put', { enabled: !detail.bookmarked }), '收藏已更新')}>{detail.bookmarked ? '取消收藏' : '收藏帖子'}</Button><Button onClick={() => setReport(true)}>举报</Button>{detail.can_edit && <><Button onClick={() => void openEditor(detail)}>编辑帖子</Button><Button danger onClick={() => modal.confirm({ title: '删除这篇帖子？', onOk: async () => { await request('forum/posts/' + detail.id, 'delete'); openPost() } })}>删除帖子</Button></>}{detail.can_moderate && <><Button onClick={() => void act(() => request('forum/posts/' + detail.id + '/moderation', 'post', { action: 'review', note: '管理员已检查讨论经验，作为待验证研究参考' }), '审核已记录')}>审核经验</Button><Button onClick={() => void act(() => request('forum/posts/' + detail.id + '/moderation', 'post', { action: detail.status === 'hidden' ? 'restore' : 'hide', note: '管理员人工处理' }), '状态已更新')}>{detail.status === 'hidden' ? '恢复展示' : '隐藏帖子'}</Button></>}</Space>
      </Card>
      <Card title="棚小智协作"><p className="community-muted">辅助结果仅向你展示。论坛讨论不会自动成为可信知识。</p><Space wrap><Button loading={busy} onClick={() => void act(async () => setAnalysis(await request('forum/posts/' + detail.id + '/assist', 'post', { use_model: false })), '参考资料已检索')}>检索相关知识</Button><Button loading={busy} disabled={guest} onClick={() => void act(async () => setAnalysis(await request('forum/posts/' + detail.id + '/assist', 'post', { use_model: true })), '辅助分析已生成')}>AI 辅助分析</Button><Button disabled={guest} onClick={research}>创建研究草稿</Button><Button disabled={guest || detail.review_state !== 'reviewed'} onClick={() => void act(async () => { if (!gid) return; const w = await getResearchWorkspace({ greenhouse_id: gid }); setStudies(w.records.filter(r => r.kind === 'study')); }, '研究列表已读取')}>读取可关联研究</Button><Button disabled={!studies.length || detail.review_state !== 'reviewed'} onClick={linkResearch}>关联审核经验</Button></Space></Card>
      <Card title={'讨论与回答 · ' + detail.comment_count}><List dataSource={detail.comments || []} locale={{ emptyText: '写下第一条回复' }} renderItem={c => <List.Item><div className="community-comment"><Space wrap><strong>{c.author}</strong><small>{times(c.created_at)}</small>{c.parent_id && <Tag>回复 #{c.parent_id}</Tag>}{detail.accepted_comment_id === c.id && <Tag color="green">已采纳</Tag>}</Space><CommunityMarkdown>{c.body}</CommunityMarkdown><Space wrap><Button type="link" onClick={() => setReplyId(c.id)}>回复</Button>{detail.can_edit && detail.category === 'question' && detail.accepted_comment_id !== c.id && <Button type="link" onClick={() => void act(() => request('forum/posts/' + detail.id + '/accepted/' + c.id, 'put'), '答案已采纳')}>采纳答案</Button>}{c.can_delete && <Button type="link" danger onClick={() => void act(() => request('forum/posts/' + detail.id + '/comments/' + c.id, 'delete'), '评论已删除')}>删除回复</Button>}</Space></div></List.Item>} />
      {replyId && <Tag closable onClose={() => setReplyId(undefined)}>回复 #{replyId}</Tag>}<Form name="forum-comment" form={commentForm} onFinish={values => void act(async () => { await request('forum/posts/' + detail.id + '/comments', 'post', { ...values, parent_id: replyId }); commentForm.resetFields(); setReplyId(undefined) }, '回复已保存')}><Form.Item name="body" rules={[{ required: true, whitespace: true }]}><Input.TextArea aria-label="回复内容" rows={3} maxLength={5000} placeholder="分享你的观察与建议；未经核实的判断请说明" /></Form.Item><Button htmlType="submit" type="primary" loading={busy}>发表回复</Button></Form></Card>
    </>}</> : <>
      <div className="forum-navigation"><nav className="forum-categories" aria-label="论坛分类">{[{value:'',label:'全部讨论'},...categories].map(c=><button key={c.value} type="button" aria-pressed={(category||'')===c.value} onClick={()=>{setCategory(c.value||undefined);setPage(1)}}>{c.label}</button>)}</nav><Input.Search className="forum-search" aria-label="搜索帖子" placeholder="搜索问题或经验" allowClear value={searchDraft} onChange={e=>setSearchDraft(e.target.value)} onSearch={value=>{setSearch(value);setPage(1)}}/></div>
      <div className="forum-toolbar">
        <Select aria-label="帖子排序" value={sort} onChange={value=>{setSort(value);setPage(1)}} options={[{value:'recent',label:'最近更新'},{value:'discussed',label:'讨论最多'},{value:'liked',label:'点赞最多'}]}/>
        <Select aria-label="作物筛选" allowClear placeholder="全部作物" options={crops} value={crop} onChange={value=>{setCrop(value);setPage(1)}}/>
        <details className="forum-more-filters"><summary><FilterOutlined/> 更多筛选</summary><div className="forum-filter-popover"><Select aria-label="解答状态" value={answer} onChange={value=>{setAnswer(value);setPage(1)}} options={[{value:'all',label:'全部解答状态'},{value:'open',label:'待解答的求助'},{value:'resolved',label:'已采纳答案'}]}/><Input aria-label="标签筛选" placeholder="按标签筛选" value={tag} onChange={e=>{setTag(e.target.value);setPage(1)}}/><Button type={mine==='replies'?'primary':'text'} onClick={()=>{setMine(mine==='replies'?'':'replies');setPage(1)}}>我的回复</Button></div></details>
        {hasFilters&&<Button type="text" className="forum-clear" onClick={resetFilters}>重置筛选</Button>}
        <div className="forum-personal"><Button type="text" aria-label="我的帖子" icon={<FileTextOutlined/>} aria-pressed={mine==='posts'} onClick={()=>{setMine(mine==='posts'?'':'posts');setPage(1)}}>我的帖子</Button><Button type="text" aria-label="我的收藏" icon={<StarOutlined/>} aria-pressed={mine==='bookmarks'} onClick={()=>{setMine(mine==='bookmarks'?'':'bookmarks');setPage(1)}}>我的收藏</Button></div>
      </div>
      <Spin spinning={loading}><div className="community-post-list forum-discussions" aria-label="讨论列表" aria-busy={loading}>{loading&&!list.items.length?<div className="forum-loading" role="status" aria-label="正在读取讨论"><Skeleton active title paragraph={{rows:3}}/></div>:list.items.length?list.items.map(post=><article key={post.id} className="forum-post">
        <div className="forum-author-avatar" aria-hidden="true">{post.author.slice(0,1)||'棚'}</div><div className="forum-post-content"><div className="community-post-meta"><span className="forum-author">{post.author}</span><span className="forum-dot">·</span><time dateTime={post.updated_at}>{shortTime(post.updated_at)}</time><Tag>{categories.find(c=>c.value===post.category)?.label||'棚友交流'}</Tag>{post.accepted_comment_id&&<Tag color="green" title="提问者已采纳此讨论的回答">已采纳答案</Tag>}</div>
        <h2><button type="button" className="community-title-button" onClick={()=>openPost(post.id)}>{post.title}</button></h2><p className="community-excerpt">{excerpt(post.body)}</p>
        <div className="forum-post-footer"><div className="forum-post-tags">{post.fields.crop&&<span>{crops.find(c=>c.value===post.fields.crop)?.label||post.fields.crop}</span>}{post.tags.map(t=><span key={t}>{t}</span>)}</div><div className="forum-post-actions"><Button type="text" icon={<CommentOutlined/>} onClick={()=>openPost(post.id)} aria-label={'查看回复：'+post.title}>{post.comment_count} <span>回复</span></Button><Button type="text" loading={busy} icon={post.liked?<LikeFilled/>:<LikeOutlined/>} aria-label={(post.liked?'取消点赞':'点赞')+'帖子：'+post.title} aria-pressed={post.liked} onClick={()=>void act(()=>request('forum/posts/'+post.id+'/reactions/like','put',{enabled:!post.liked}),'点赞已更新')}>{post.likes} <span>赞</span></Button><Button type="text" disabled={busy} icon={post.bookmarked?<StarFilled/>:<StarOutlined/>} aria-label={(post.bookmarked?'取消收藏':'收藏')+'帖子：'+post.title} aria-pressed={post.bookmarked} onClick={()=>void act(()=>request('forum/posts/'+post.id+'/reactions/bookmark','put',{enabled:!post.bookmarked}),'收藏已更新')}>{post.bookmarked?'已收藏':'收藏'}</Button></div></div></div>
        {post.assets?.find(a=>a.media_type.startsWith('image/'))&&<div className="forum-post-thumbnail"><CommunityAsset asset={post.assets.find(a=>a.media_type.startsWith('image/'))!}/></div>}
      </article>):error?<div className="forum-empty"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂时无法读取讨论"/><Button onClick={()=>void load()}>重新加载讨论</Button></div>:<div className="forum-empty"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={mine==='bookmarks'?'还没有收藏的讨论':mine==='posts'?'还没有发布讨论':mine==='replies'?'还没有参与回复':hasFilters?'没有找到符合条件的讨论':'从一个现场观察开始，和棚友一起交流'}/><div className="forum-empty-actions">{mine==='posts'||!hasFilters?<Button type="primary" onClick={()=>void openEditor()}>{mine==='posts'?'发布一篇讨论':'发起第一篇讨论'}</Button>:<Button onClick={resetFilters}>{mine?'浏览全部讨论':'清除筛选条件'}</Button>}{mine==='posts'&&<Button onClick={resetFilters}>浏览全部讨论</Button>}</div></div>}</div></Spin>
      <div className="forum-pagination"><span>{list.total?`共 ${list.total} 篇讨论`:'期待你的种植发现'}</span><Pagination current={page} pageSize={20} total={list.total} onChange={setPage} hideOnSinglePage/></div>
    </>}

    <Modal title={editing ? '编辑帖子' : '发布棚友帖子'} open={editor} onCancel={() => setEditor(false)} width={900} footer={null} destroyOnHidden>
      <Form name="forum-post-editor" form={form} layout="vertical" onFinish={input => void save(input)}><Form.Item name="title" label="帖子标题" rules={[{ required: true, whitespace: true, min: 2 }]}><Input maxLength={160} /></Form.Item><div className="community-form-grid"><Form.Item name="category" label="分类"><Select options={categories} /></Form.Item><Form.Item name="visibility" label="发布范围"><Select options={[{ value: 'organization', label: '组织内' }, { value: 'public', label: '公开给已登录棚友' }, { value: 'private', label: '仅自己' }]} /></Form.Item></div><Form.Item name="body" label="正文（支持 Markdown）" rules={[{ required: true, whitespace: true, min: 2 }]}><Input.TextArea rows={7} maxLength={20000} /></Form.Item><Collapse items={[{ key: 'preview', label: '预览正文', children: <CommunityMarkdown>{body}</CommunityMarkdown> }, { key: 'agriculture', label: '补充农业信息（可选）', children: <><div className="community-form-grid"><Form.Item name={['fields', 'crop']} label="作物类型"><Select allowClear options={crops} /></Form.Item><Form.Item name={['fields', 'variety']} label="品种"><Input maxLength={100} /></Form.Item><Form.Item name={['fields', 'stage']} label="生育阶段"><Input maxLength={60} /></Form.Item><Form.Item name={['fields', 'issue']} label="问题类型"><Input maxLength={100} /></Form.Item></div>{[['environment', '环境条件'], ['attempted', '已尝试的处理方式'], ['observation', '观察结果']].map(([key, label]) => <Form.Item key={key} name={['fields', key]} label={label}><Input.TextArea rows={2} maxLength={1500} /></Form.Item>)}<Form.Item name={['fields', 'references']} label="参考来源"><Select mode="tags" tokenSeparators={[' ']} placeholder="输入原文网址后按回车" /></Form.Item></> }]} />
      <Form.Item name="tags" label="标签"><Select mode="tags" maxCount={8} placeholder="输入标签后按回车" /></Form.Item>
      {studies.length > 0 && <Form.Item name="research_source_id" label="关联已完成研究（可选）"><Select allowClear options={studies.map(s => ({ value: s.id, label: s.title }))} /></Form.Item>}
      <Form.Item name="publish_confirmed" valuePropName="checked"><Checkbox>分享研究时，我已检查正文不包含私密大棚信息，并确认发布研究总结</Checkbox></Form.Item>
      <Upload disabled={guest || busy} showUploadList={false} accept=".jpg,.jpeg,.png,.webp,.pdf,.txt,.md" beforeUpload={file => { void act(async () => { const data = new FormData(); data.append('file', file); const a = await uploadCommunity<ContentAsset>('forum/assets', data); setAssets(previous => [...previous, a]) }, '附件已上传'); return false }}><Button disabled={guest || assets.length >= 8}>上传图片或附件</Button></Upload><Space wrap>{assets.map(a => <Tag key={a.id} closable onClose={() => setAssets(previous => previous.filter(x => x.id !== a.id))}>{a.filename}</Tag>)}</Space><p className="community-muted">正文预览不加载外部图片；图片通过受控附件展示。单个附件不超过8MB。</p><Button type="primary" htmlType="submit" loading={busy}>确认发布</Button></Form>
    </Modal>
    <Modal title="棚小智辅助分析 · 仅自己可见" open={!!analysis} onCancel={() => setAnalysis(null)} footer={<Button onClick={() => setAnalysis(null)}>关闭</Button>} width={720}>{analysis && <><CommunityMarkdown>{analysis.analysis}</CommunityMarkdown>{analysis.sources.map(s => <div key={s.id}><h3>{s.title}</h3>{s.sources.map((source, i) => <p key={i}>{source.url ? <a href={source.url} target="_blank" rel="noopener noreferrer">{source.name}</a> : source.name} · {source.position || s.position}</p>)}</div>)}<Alert type="info" message={analysis.notice} /></>}</Modal>
    <Modal title="举报内容" open={report} onCancel={() => setReport(false)} confirmLoading={busy} onOk={() => { if (reason.trim().length < 2) { message.info('请填写举报原因'); return }; void act(async () => { await request('forum/posts/' + selected + '/reports', 'post', { reason }); setReport(false); setReason('') }, '举报已记录') }}><Input.TextArea aria-label="举报原因" value={reason} onChange={e => setReason(e.target.value)} maxLength={1000} /></Modal>
    <Modal title="本组织举报处理" open={!!reports} onCancel={() => setReports(null)} footer={null}><List dataSource={reports || []} renderItem={r => <List.Item><div><strong>{r.title}</strong><p>{r.reason}</p><Tag>{r.status}</Tag><Space><Button onClick={() => { setReports(null); openPost(r.post_id) }}>查看并审核</Button><Button onClick={() => void act(async () => { await request('forum/posts/' + r.post_id + '/moderation', 'post', { action: 'dismiss', note: '管理员检查后保留原帖' }); setReports(await request('forum/moderation/reports')) }, '举报已处理')}>保留原帖</Button></Space></div></List.Item>} /></Modal>
  </div>
}
