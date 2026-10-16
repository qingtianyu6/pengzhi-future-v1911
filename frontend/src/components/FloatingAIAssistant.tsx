import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { Button, Drawer, Dropdown, Space, Tooltip } from 'antd'
import { AudioOutlined, CloseOutlined, ExpandOutlined, CompressOutlined, MoreOutlined, MinusOutlined } from '@ant-design/icons'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { getAIStatus } from '../api/aiApi'
import { getWarnings } from '../api/warningApi'
import { getStoredToken, getStoredUser } from '../api/authApi'
import { isGuestMode } from '../api/guestMode'
import { AgriculturalAgentMascot, type MascotState } from './AgriculturalAgentMascot'
import { useMascotCompanion } from '../hooks/useMascotCompanion'
import { LiveAgriculturalMascot } from './LiveAgriculturalMascot'
import './FloatingAIAssistant.css'

const AIAssistantPage = lazy(() => import('../pages/AI/AIAssistantPage'))
type Preferences = { collapsed: boolean; hidden: boolean; right: number; bottom: number; motion: boolean }
const defaultPrefs: Preferences = { collapsed: false, hidden: false, right: 24, bottom: 24, motion: true }
function readPrefs(key: string): Preferences {
  try {
    const stored = JSON.parse(localStorage.getItem(key) || '{}')
    return { collapsed: stored.collapsed === true, hidden: stored.hidden === true, motion: stored.motion !== false,
      right: Number.isFinite(stored.right) ? Math.max(8, stored.right) : 24,
      bottom: Number.isFinite(stored.bottom) ? Math.max(8, stored.bottom) : 24 }
  } catch { return defaultPrefs }
}
function WebsiteGuide() {
  const [answer, setAnswer] = useState('棚智未来帮助你查看大棚数据、理解风险，并把人工确认的建议转成可追踪的任务。')
  const questions: Record<string, string> = {
    '平台能做什么？': '平台提供大棚档案、环境趋势与温湿度预测、番茄叶片辅助识别、农事任务和执行反馈。棚小智将这些能力放到一个问答入口。',
    '如何开始使用？': '已有账号可以进入工作台，选中大棚后向我提问。也可以进入游客模式查看示例；游客数据不代表现场实测。',
    '会自动控制设备吗？': '当前通过人工确认的任务安排现场处理。创建任务不等于已经控制通风、灌溉等硬件。',
  }
  return <section className="assistant-website-guide"><AgriculturalAgentMascot /><h2>你好，我是棚小智</h2><p className="assistant-guide-label">平台使用向导</p><p aria-live="polite">{answer}</p><div>{Object.keys(questions).map(question => <Button block key={question} onClick={() => setAnswer(questions[question])}>{question}</Button>)}</div><Space wrap><Link className="assistant-primary-link" to={getStoredToken() ? '/platform' : '/login'}>进入工作台对话</Link><Link to="/platform?mode=guest">体验示例大棚</Link></Space><small>本页提供平台介绍。工作台中的 AI 对话会关联你有权限的大棚。</small></section>
}

export function FloatingAIAssistant() {
  const location = useLocation()
  const navigate = useNavigate()
  const workbench = location.pathname.startsWith('/platform')
  const greenhouseId = workbench ? Number(new URLSearchParams(location.search).get('greenhouse_id')) || undefined : undefined
  const userKey = isGuestMode() ? 'guest' : String(getStoredUser()?.id ?? 'public')
  const prefsKey = `pengzhi_assistant_prefs_v1:${userKey}`
  const [prefs, setPrefs] = useState(() => readPrefs(prefsKey))
  const [open, setOpen] = useState(false)
  const [expanded, setExpanded] = useState(false)
  useEffect(() => { if (!open) setActivity('idle') }, [open])
  const [activity, setActivity] = useState<MascotState>('idle')
  const [available, setAvailable] = useState<boolean | null>(null)
  const [warningCount, setWarningCount] = useState<number | null>(null)
  const [blocked, setBlocked] = useState(false)
  const [voiceRequest, setVoiceRequest] = useState(0)
  const [welcome, setWelcome] = useState(false)
  const [pageVisible, setPageVisible] = useState(!document.hidden)
  const [small, setSmall] = useState(window.innerWidth <= 620)
  const [dragging, setDragging] = useState(false)
  const [reminding, setReminding] = useState(false)
  const [staticFallback, setStaticFallback] = useState(false)
  const onRendererChange = useCallback((fallback: boolean) => setStaticFallback(fallback), [])
  const dock = useRef<HTMLDivElement>(null)
  const drag = useRef<{ x: number; y: number; right: number; bottom: number; moved: boolean } | null>(null)
  const suppressClick = useRef(false)
  const collapsed = prefs.collapsed
  const companionActive = !open && !blocked && !prefs.hidden && !collapsed && pageVisible && !dragging && !welcome && !reminding && activity === 'idle'
  const companion = useMascotCompanion(companionActive, prefs.motion, `${userKey}:${greenhouseId ?? 'public'}`)
  const clamp = useCallback((next: Preferences) => ({ ...next,
    right: Math.max(8, Math.min(next.right, Math.max(8, window.innerWidth - (next.collapsed ? 52 : window.innerWidth <= 620 ? 96 : 144) - 8))),
    bottom: Math.max(12, Math.min(next.bottom, Math.max(12, window.innerHeight - (next.collapsed ? 96 : window.innerWidth <= 620 ? 216 : 276) - 8))),
  }), [])
  useEffect(() => { setPrefs(clamp(readPrefs(prefsKey))) }, [prefsKey, clamp])
  useEffect(() => { localStorage.setItem(prefsKey, JSON.stringify(prefs)) }, [prefs, prefsKey])
  useEffect(() => {
    const resize = () => { setSmall(window.innerWidth <= 620); setPrefs(previous => clamp(previous)) }
    const visibility = () => setPageVisible(!document.hidden)
    window.addEventListener('resize', resize); window.visualViewport?.addEventListener('resize', resize)
    document.addEventListener('visibilitychange', visibility)
    return () => { window.removeEventListener('resize', resize); window.visualViewport?.removeEventListener('resize', resize); document.removeEventListener('visibilitychange', visibility) }
  }, [clamp])
  useEffect(() => {
    if (sessionStorage.getItem('pengzhi_assistant_welcomed')) return
    const show = window.setTimeout(() => setWelcome(true), 700)
    const hide = window.setTimeout(() => { setWelcome(false); sessionStorage.setItem('pengzhi_assistant_welcomed', '1') }, 5200)
    return () => { window.clearTimeout(show); window.clearTimeout(hide) }
  }, [])
  useEffect(() => {
    setOpen(false); setActivity('idle'); setWelcome(false)
  }, [location.pathname, userKey])
  useEffect(() => {
    const close = () => setOpen(false)
    const restore = () => { setPrefs(previous => ({ ...previous, hidden: false, collapsed: false })); setOpen(true) }
    window.addEventListener('pengzhi:close-assistant', close); window.addEventListener('pengzhi:open-assistant', restore)
    return () => { window.removeEventListener('pengzhi:close-assistant', close); window.removeEventListener('pengzhi:open-assistant', restore) }
  }, [])
  useEffect(() => {
    const check = () => setBlocked(Array.from(document.querySelectorAll('.ant-modal-wrap, .ant-drawer-open, .site-search-layer, .mobile-nav-layer, .mobile-sider-backdrop')).some(element => {
      if (element.closest('.shelly-assistant-drawer')) return false
      const style = getComputedStyle(element)
      return style.display !== 'none' && style.visibility !== 'hidden' && element.getBoundingClientRect().width > 0
    }))
    const observer = new MutationObserver(check)
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'style'] })
    check()
    return () => observer.disconnect()
  }, [])
  useEffect(() => {
    if (!workbench || !pageVisible) return
    let active = true
    const refresh = () => { void getAIStatus().then(result => { if (active) setAvailable(result.configured) }).catch(() => { if (active) setAvailable(false) }) }
    refresh()
    const timer = window.setInterval(refresh, 60000)
    return () => { active = false; window.clearInterval(timer) }
  }, [workbench, userKey, pageVisible])
  useEffect(() => {
    if (!workbench || !greenhouseId || !pageVisible) { setWarningCount(null); return }
    let active = true
    const refresh = () => { void getWarnings({ greenhouse_id: greenhouseId, status: 'open', page: 1, page_size: 1 })
      .then(result => { if (active) setWarningCount(result.total) }).catch(() => { if (active) setWarningCount(null) }) }
    refresh(); const timer = window.setInterval(refresh, 60000)
    return () => { active = false; window.clearInterval(timer) }
  }, [workbench, greenhouseId, pageVisible])
  useEffect(() => {
    setReminding(Boolean(warningCount))
    if (!warningCount) return
    const timer = window.setTimeout(() => setReminding(false), 4800)
    return () => window.clearTimeout(timer)
  }, [warningCount, greenhouseId])
  const onActivity = useCallback((next: MascotState) => setActivity(next), [])
  const start = (voice = false) => {
    if (suppressClick.current) { suppressClick.current = false; return }
    setWelcome(false); setOpen(true)
    if (voice) setVoiceRequest(previous => previous + 1)
  }
  const supportsVoice = typeof Reflect.get(window, 'SpeechRecognition') === 'function' || typeof Reflect.get(window, 'webkitSpeechRecognition') === 'function'
  const state: MascotState = welcome && !collapsed ? 'greeting' : activity !== 'idle' ? activity : reminding ? 'reminder' : 'idle'
  const motion = !collapsed && state === 'idle' ? companion.motion : undefined
  const hintBelow = prefs.bottom > window.innerHeight - (small ? 216 : 276) - 100
  const viewWarnings = () => {
    if (!greenhouseId) return
    setWelcome(false)
    navigate(`/platform/environment?${new URLSearchParams({ greenhouse_id: String(greenhouseId), tab: 'alerts' })}`)
  }
  const warningPill = warningCount ? <button className="assistant-warning-pill" type="button" aria-label={`本棚有${warningCount}条活动预警，查看预警`} title="查看当前大棚的活动预警" onClick={viewWarnings}><span>{warningCount > 99 ? '99+' : warningCount}</span><span className="assistant-warning-unit">条</span>预警</button> : null
  const settings = { items: [
    { key: 'rest', label: companion.resting ? '起身活动' : '坐下休息', disabled: companion.quiet, onClick: () => companion.setResting(!companion.resting) },
    { key: 'motion', label: prefs.motion ? '安静陪伴 · 暂停动作' : '恢复陪伴动作', onClick: () => setPrefs(previous => ({ ...previous, motion: !previous.motion })) },
    { key: 'collapse', label: collapsed ? '展开角色' : '收起为小图标', onClick: () => setPrefs(previous => ({ ...previous, collapsed: !collapsed })) },
    { key: 'hide', label: '演示模式 · 暂时隐藏', onClick: () => setPrefs(previous => ({ ...previous, hidden: true })) },
    { key: 'reset', label: '恢复默认位置', onClick: () => setPrefs({ ...defaultPrefs }) },
  ] }
  return <>
    {!open && !blocked && !prefs.hidden && <div ref={dock} className={`pengxiaozhi-dock${collapsed ? ' is-compact' : ''}${dragging ? ' is-dragging' : ''}${pageVisible ? '' : ' is-paused'}${companion.quiet ? ' is-quiet' : ''}`} style={{ right: prefs.right, bottom: `max(${prefs.bottom}px, env(safe-area-inset-bottom, 0px))` }} data-state={state} data-motion={motion ?? 'idle'}>
      {welcome && !collapsed && <div className="assistant-welcome" role="status" style={{ right: Math.min(0, window.innerWidth - prefs.right - (small ? 205 : 225) - 8) }}>你好，我是棚小智<br /><span>{workbench ? '可以帮你查看本棚情况' : '带你了解棚智未来'}</span><button type="button" aria-label="关闭欢迎提示" onClick={() => setWelcome(false)}>×</button></div>}
      {!collapsed && <div className="assistant-dock-controls">{warningPill}<button type="button" aria-label="收起棚小智" onClick={() => setPrefs(previous => ({ ...previous, collapsed: true }))}><MinusOutlined /></button><Dropdown menu={settings} trigger={['click']}><button type="button" aria-label="棚小智设置"><MoreOutlined /></button></Dropdown></div>}
      {!welcome && !collapsed && companionActive && companion.hint && <div className={`assistant-companion-hint${hintBelow ? ' is-below' : ''}`} aria-live="off" style={{ right: Math.min(0, window.innerWidth - prefs.right - (small ? 178 : 210) - 8) }}>{companion.hint}</div>}
      {collapsed && warningPill}
      <button className="assistant-character-trigger" type="button" aria-label="打开棚小智" aria-haspopup="dialog" onClick={() => start()}
        title="点我对话，按住可以拖动"
        onPointerEnter={event => companion.onPointerEnter(event.pointerType)} onPointerLeave={companion.onPointerLeave}
        onFocus={companion.onFocus} onBlur={companion.onBlur}
        onPointerDown={event => { if (event.button !== 0) return; drag.current = { x: event.clientX, y: event.clientY, right: prefs.right, bottom: prefs.bottom, moved: false }; event.currentTarget.setPointerCapture(event.pointerId) }}
        onPointerMove={event => { companion.onPointerMove(event.pointerType); const initial = drag.current; if (!initial) return; const dx = event.clientX - initial.x; const dy = event.clientY - initial.y; if (!initial.moved && Math.hypot(dx, dy) < 6) return; initial.moved = true; setDragging(true); setPrefs(previous => clamp({ ...previous, right: initial.right - dx, bottom: initial.bottom - dy })) }}
        onPointerUp={() => { suppressClick.current = Boolean(drag.current?.moved); drag.current = null; setDragging(false) }}
        onPointerCancel={() => { drag.current = null; setDragging(false); suppressClick.current = false }}>
        {collapsed ? <AgriculturalAgentMascot state={state} showStateBadge={false}/> : <LiveAgriculturalMascot state={state} motion={motion} quiet={companion.quiet} paused={!pageVisible || dragging} onRendererChange={onRendererChange}/>}
        {collapsed && <span className="assistant-compact-label">棚小智</span>}
      </button>
      {!collapsed && <><div className="assistant-dock-actions"><button type="button" onClick={() => start()}>问一问</button>{workbench && supportsVoice && window.isSecureContext && <Tooltip title="语音输入"><button type="button" aria-label="打开棚小智语音" onClick={() => start(true)}><AudioOutlined /></button></Tooltip>}</div><span className="assistant-availability">{staticFallback && '静态形象 · '}{workbench ? available === true ? 'AI 可用' : available === false ? 'AI 暂不可用' : '连接检查中' : '平台使用向导'}</span></>}
    </div>}
    {prefs.hidden && !open && !blocked && <button className="assistant-restore" type="button" aria-label="恢复棚小智" onClick={() => setPrefs(previous => ({ ...previous, hidden: false }))}>恢复棚小智</button>}
    <Drawer rootClassName="shelly-assistant-drawer" className="ai-global-drawer" title={<span className="assistant-drawer-title"><AgriculturalAgentMascot compact /><span>棚小智<small>{workbench ? '数据有依据，任务需确认' : '棚智未来 · 平台向导'}</small></span></span>} placement="right" width={small ? '100vw' : expanded ? 'min(1120px, 96vw)' : 470} open={open} onClose={() => { setOpen(false); setVoiceRequest(0) }} destroyOnHidden
      extra={<Space><Dropdown menu={settings} trigger={['click']}><Button type="text" aria-label="棚小智面板设置" icon={<MoreOutlined />} /></Dropdown>{!small && workbench && <Button type="text" aria-label={expanded ? '收起完整工作台' : '展开完整工作台'} icon={expanded ? <CompressOutlined /> : <ExpandOutlined />} onClick={() => setExpanded(previous => !previous)} />}<Button type="text" aria-label="关闭棚小智" icon={<CloseOutlined />} onClick={() => { setOpen(false); setVoiceRequest(0) }} /></Space>} closeIcon={null}>
      {open && <div className="assistant-drawer-workspace"><div className="assistant-live-companion">
        <LiveAgriculturalMascot state={activity} quiet={companion.quiet} paused={!pageVisible} onRendererChange={onRendererChange}/>
        <div><strong>棚小智在这里</strong><span>{activity === 'thinking' ? '正在结合大棚信息思考…' : activity === 'listening' ? '我在听，请说出你的问题' : activity === 'speaking' ? '正在为你朗读回答' : activity === 'reminder' ? '请查看建议，确认后再执行' : activity === 'complete' ? '处理完成，一起看看结果吧' : activity === 'unavailable' ? '遇到了一点问题，请查看下方提示' : '可以问我棚况、预警和农事安排'}</span></div>
      </div>{workbench ? <Suspense fallback={<p role="status">正在打开棚小智…</p>}><AIAssistantPage key={`${userKey}:${greenhouseId ?? 'general'}`} embedded workspaceId={greenhouseId} expanded={expanded && !small} voiceRequest={voiceRequest} onActivity={onActivity} /></Suspense> : <WebsiteGuide />}</div>}
    </Drawer>
  </>
}
