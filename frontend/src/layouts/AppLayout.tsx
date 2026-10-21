import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import {
  BellOutlined,
  DownOutlined,
  HomeOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  PlusOutlined,
  QuestionCircleOutlined,
  SettingOutlined,
  SunOutlined,
  SearchOutlined,
} from '@ant-design/icons'
import { Avatar, Badge, Button, ConfigProvider, Divider, Drawer, Dropdown, Input, Layout, Menu, Select, Switch, Tooltip, type MenuProps } from 'antd'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { FloatingAIAssistant } from '../components/FloatingAIAssistant'
import { useAssistantClearance } from '../hooks/useAssistantClearance'
import { isGuestMode } from '../api/guestMode'
import { communityRequest } from '../api/communityApi'
import { ServiceStatus } from '../components/ServiceStatus'
import { getGreenhouses } from '../api/greenhouseApi'
import { getWarningSummary } from '../api/warningApi'
import type { Greenhouse } from '../types/greenhouse'
import { useSystemStore } from '../store/system'
import { getStoredUser, logoutAccount, type AuthUser } from '../api/authApi'
import './platform-tokens.css'
import './workbench-refresh.css'
import { platformTheme } from '../theme'
import { allWorkspaceGroups, navigationItems, workspaceGroups, resolveWorkspace, workspaceHref } from './workspaceNavigation'
import { WorkspaceSectionNav } from './WorkspaceSectionNav'
import './platform-visual.css'
import './workspace-consolidation.css'
import './product-polish.css'
import './workspace-surfaces.css'
import './knowledge-navigation.css'
import './navigation-refresh.css'
import './operations-design.css'
import './unified-navigation.css'

const AccountSettings = lazy(() => import('../components/AccountSettings'))
const { Header, Sider, Content } = Layout

function makeMenuItems(unread: number, knowledge: {
  collapsed: boolean; expanded: boolean; toggle: () => void; openDefault: () => void
}, production: { toggle: () => void }): MenuProps['items'] {
  const items = workspaceGroups.map(group => {
    const item={key:group.id,'aria-label':group.label,icon:group.icon,
      label:group.id==='knowledge'?<Badge count={unread} size="small" offset={[10,0]}>{group.label}</Badge>:group.label}
    if (group.id === 'production' && !knowledge.collapsed) return {
      ...item, children: group.items.map(child => ({ key:child.key, label:child.label })),
      onTitleClick:production.toggle, className:'pz-production-design-nav',
    }
    if(group.id!=='knowledge'||knowledge.collapsed)return item
    return {...item,className:'pz-knowledge-nav',
      children:group.items.map(child=>({key:child.key,label:child.label})),
      onTitleClick:knowledge.openDefault,
      expandIcon:<button type="button" className="pz-knowledge-toggle" aria-label={knowledge.expanded?'收起知识社区':'展开知识社区'} aria-expanded={knowledge.expanded} aria-controls="knowledge-community-pages"
        onClick={event=>{event.preventDefault();event.stopPropagation();knowledge.toggle()}}
        onKeyDown={event=>event.stopPropagation()}><DownOutlined/></button>,
      popupClassName:'pz-knowledge-popup',
      id:'knowledge-community-pages',
    }
  })
  return items
}

function formatHeaderTime(value: Date) {
  return value.toLocaleString('zh-CN', {
    year: 'numeric', month: 'long', day: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  })
}

export function AppLayout() {
  const [isMobile, setIsMobile] = useState(() => window.matchMedia('(max-width: 620px)').matches)
  const [collapsed, setCollapsed] = useState(() => window.matchMedia('(max-width: 620px)').matches)
  const [workspaceGreenhouse, setWorkspaceGreenhouse] = useState<Greenhouse | null>(null)
  const [greenhouses, setGreenhouses] = useState<Greenhouse[]>([])
  const [now, setNow] = useState(() => new Date())
  const [authUser, setAuthUser] = useState<AuthUser | null>(() => getStoredUser())
  const [warningCount, setWarningCount] = useState<number | null>(null)
  const [newsUnread, setNewsUnread] = useState(0)
  const [accountSettingsOpen, setAccountSettingsOpen] = useState(false)
  const [utilityPanel, setUtilityPanel] = useState<'help' | 'settings' | null>(null)
  const [autoRefreshWarnings, setAutoRefreshWarnings] = useState(() => localStorage.getItem('pengzhi_auto_refresh_warnings') !== '0')
  const [reducedMotion, setReducedMotion] = useState(() => localStorage.getItem('pengzhi_reduced_motion') === '1')
  const [navigatorOpen, setNavigatorOpen] = useState(false)
  const [navigationQuery, setNavigationQuery] = useState('')
  const [knowledgeExpanded,setKnowledgeExpanded]=useState(() => ['/platform/forum','/platform/knowledge','/platform/news'].includes(window.location.pathname))
  const [productionExpanded, setProductionExpanded] = useState(true)
  const navigate = useNavigate()
  const location = useLocation()
  useAssistantClearance(location.pathname)
  const checkHealth = useSystemStore((state) => state.checkHealth)
  const systemStatus = useSystemStore((state) => state.status)
  const is3DPage = location.pathname === '/platform/3d' || location.pathname.startsWith('/platform/3d/')
  const isGreenhouseManagement = location.pathname === '/platform/data'
  const isEnvironmentWorkspace = location.pathname === '/platform/environment'
  const isInvestigationWorkspace = location.pathname === '/platform/investigate'
  const isOperationsDesign = ['/platform/production','/platform/autonomy'].includes(location.pathname)
  const { item: currentItem, group: currentGroup } = resolveWorkspace(location.pathname, location.search)
  const currentPageName = currentItem?.label ?? '页面未找到'

  const greenhouseFromUrl = useMemo(() => Number(new URLSearchParams(location.search).get('greenhouse_id')) || null, [location.search])

  useEffect(() => { void checkHealth() }, [checkHealth])
  useEffect(() => {
    let active = true
    const update = () => { void communityRequest<{ read_at: string | null }[]>('news/digests').then(rows => { if (active) setNewsUnread(rows.filter(r => !r.read_at).length) }).catch(() => { if (active) setNewsUnread(0) }) }
    update(); const timer = window.setInterval(update, 60000)
    window.addEventListener('pengzhi:news-changed', update)
    return () => { active = false; window.clearInterval(timer); window.removeEventListener('pengzhi:news-changed', update) }
  }, [])
  useEffect(() => {
    let active = true
    const refreshWarnings = () => {
      void getWarningSummary()
        .then((summary) => { if (active) setWarningCount(summary.open_total) })
        .catch(() => { if (active) setWarningCount(null) })
    }
    refreshWarnings()
    const timer = autoRefreshWarnings ? window.setInterval(refreshWarnings, 60000) : null
    window.addEventListener('pengzhi:warnings-changed', refreshWarnings)
    return () => { active = false; if (timer !== null) window.clearInterval(timer); window.removeEventListener('pengzhi:warnings-changed', refreshWarnings) }
  }, [autoRefreshWarnings])
  useEffect(() => { localStorage.setItem('pengzhi_auto_refresh_warnings', autoRefreshWarnings ? '1' : '0') }, [autoRefreshWarnings])
  useEffect(() => {
    localStorage.setItem('pengzhi_reduced_motion', reducedMotion ? '1' : '0')
    document.documentElement.classList.toggle('pengzhi-reduced-motion', reducedMotion)
    return () => document.documentElement.classList.remove('pengzhi-reduced-motion')
  }, [reducedMotion])
  useEffect(() => {
    const media = window.matchMedia('(max-width: 620px)')
    const syncSidebar = () => {
      setIsMobile(media.matches)
      setCollapsed(media.matches)
    }
    media.addEventListener('change', syncSidebar)
    return () => media.removeEventListener('change', syncSidebar)
  }, [])
  useEffect(() => { if (isMobile) setCollapsed(true) }, [location.pathname, isMobile])
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 60000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    let active = true
    const refresh = () => { void getGreenhouses({ page: 1, page_size: 100, status: 'active' })
      .then((result) => {
        if (!active) return
        setGreenhouses(result.items)
        const selected = greenhouseFromUrl ? result.items.find((item) => item.id === greenhouseFromUrl) : undefined
        const workspace = selected ?? result.items[0] ?? null
        setWorkspaceGreenhouse(workspace)
        if (workspace && !selected) {
          const params = new URLSearchParams(window.location.search)
          params.set('greenhouse_id', String(workspace.id))
          navigate(`${window.location.pathname}?${params.toString()}`, { replace: true })
        }
      })
      .catch(() => { if (active) { setGreenhouses([]); setWorkspaceGreenhouse(null) } }) }
    refresh()
    window.addEventListener('greenhouses-changed', refresh)
    return () => { active = false; window.removeEventListener('greenhouses-changed', refresh) }
  }, [greenhouseFromUrl, navigate])

  useEffect(() => { document.title = `${currentPageName} - 棚智未来` }, [currentPageName])

  const switchWorkspace = (greenhouse: Greenhouse) => {
    setWorkspaceGreenhouse(greenhouse)
    const params = new URLSearchParams(location.search)
    params.delete('task_id'); params.delete('batch_id'); params.delete('create')
    params.set('greenhouse_id', String(greenhouse.id))
    navigate(`${location.pathname}?${params.toString()}`)
  }

  const openWarnings = () => {
    const params = new URLSearchParams({ tab: 'alerts' })
    const greenhouseId = workspaceGreenhouse?.id ?? greenhouseFromUrl
    if (greenhouseId) params.set('greenhouse_id', String(greenhouseId))
    navigate(`/platform/environment?${params.toString()}`)
  }

  const handleLogout = async () => {
    try { await logoutAccount() } catch { /* Local logout still completes if the service is unavailable. */ }
    setAuthUser(null)
    navigate('/login', { replace: true })
  }

  const accountMenu: MenuProps['items'] = authUser ? [
    { key: 'identity', disabled: true, label: authUser.phone },
    { key: 'settings', icon: <SettingOutlined />, label: '账户与团队', onClick: () => setAccountSettingsOpen(true) },
    { type: 'divider' as const },
    { key: 'logout', icon: <LogoutOutlined />, danger: true, label: '退出登录', onClick: () => void handleLogout() },
  ] : [
    { key: 'login', label: '登录账号', onClick: () => navigate('/login') },
    { key: 'register', label: '注册账号', onClick: () => navigate('/register') },
  ]

  const workspaceMenu: MenuProps['items'] = [
    ...greenhouses.map((greenhouse) => ({
      key: String(greenhouse.id),
      label: <div className="workspace-option"><strong>{greenhouse.name}</strong><span>{greenhouse.code} · {greenhouse.active_batch?.variety || greenhouse.location || '未设置作物'}</span></div>,
      onClick: () => switchWorkspace(greenhouse),
    })),
    { type: 'divider' as const },
    { key: 'manage', icon: <PlusOutlined />, label: '管理大棚', onClick: () => navigate(workspaceHref('/platform/data', location.search)) },
  ]

  const openWorkspace = (key: string) => {
    const child=workspaceGroups.flatMap(group=>group.items).find(item=>item.key===key)
    if(child){navigate(workspaceHref(child.key,location.search));if(isMobile)setCollapsed(true);return}
    const group = workspaceGroups.find(group => group.id === key)
    if (!group) return
    if (group.id === 'knowledge' || group.id !== currentGroup?.id) navigate(workspaceHref(group.items[0].key, location.search))
    if (isMobile) setCollapsed(true)
  }
  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setNavigatorOpen(open => !open) } }
    window.addEventListener('keydown', shortcut)
    return () => window.removeEventListener('keydown', shortcut)
  }, [])

  return (
    <ConfigProvider theme={platformTheme}>
    <Layout id="pengzhi-platform" className={`app-shell commercial-app-shell exact-shell wb-shell pz-ui unified-navigation-shell${['/platform/forum','/platform/knowledge','/platform/news'].includes(location.pathname) ? ' forum-workspace-shell' : ''}${location.pathname === '/platform/knowledge' ? ' knowledge-library-shell' : ''}${location.pathname === '/platform/news' ? ' news-editorial-shell' : ''}${isGreenhouseManagement ? ' greenhouse-management-shell' : ''}${isEnvironmentWorkspace ? ' environment-unified-shell' : ''}${isInvestigationWorkspace ? ' investigation-unified-shell' : ''}${isOperationsDesign ? ' operations-reference-shell' : ''}`}>
      <Sider
        className={`app-sider commercial-sider exact-sider ${collapsed ? 'is-collapsed' : ''}`}
        width={240}
        collapsedWidth={72}
        collapsed={collapsed}
        trigger={null}
      >
        <div className="brand commercial-brand exact-brand" onClick={() => navigate('/platform')} role="button" tabIndex={0} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') navigate('/platform') }}>
          <div className="brand-symbol commercial-brand-symbol exact-brand-symbol">棚</div>
          {!collapsed && <div className="commercial-brand-copy exact-brand-copy"><strong>棚智未来</strong><span>让大棚更聪明</span></div>}
        </div>

        {!collapsed && <button className="pz-sider-search" type="button" onClick={() => setNavigatorOpen(true)}><SearchOutlined /><span>查找功能</span><kbd>Ctrl K</kbd></button>}
        <Menu className="side-menu commercial-side-menu exact-side-menu" mode="inline" inlineCollapsed={collapsed}
          selectedKeys={currentGroup ? [(['knowledge','production'].includes(currentGroup.id))&&!collapsed?(currentItem?.key||currentGroup.id):currentGroup.id] : []}
          openKeys={collapsed ? [] : [...(knowledgeExpanded ? ['knowledge'] : []), ...(productionExpanded ? ['production'] : [])]}
          items={makeMenuItems(newsUnread,{collapsed,expanded:knowledgeExpanded,toggle:()=>setKnowledgeExpanded(value=>!value),openDefault:()=>openWorkspace('knowledge')},{toggle:()=>setProductionExpanded(value=>!value)})}
          onClick={({ key }) => openWorkspace(key)} />

        <div className={`sider-bottom exact-sider-bottom ${collapsed ? 'is-collapsed' : ''}`}>
          <Tooltip title="帮助中心" placement="right"><Button type="text" aria-label="帮助中心" icon={<QuestionCircleOutlined />} onClick={() => setUtilityPanel('help')}>{!collapsed && '帮助中心'}</Button></Tooltip>
          <Tooltip title="系统设置" placement="right"><Button type="text" aria-label="系统设置" icon={<SettingOutlined />} onClick={() => setUtilityPanel('settings')}>{!collapsed && '系统设置'}</Button></Tooltip>
          {!collapsed && <Divider className="exact-sider-divider" />}
          {!collapsed ? <Dropdown menu={{ items: accountMenu }} trigger={['click']} placement="topLeft"><button className="sider-account exact-sider-account" type="button"><Avatar size={38} className="sider-account-avatar">{authUser?.display_name.slice(0, 1) || '游'}</Avatar><span><strong>{authUser?.display_name || '游客'}</strong><small>{authUser?.organization || (authUser ? '平台用户' : '体验模式')}</small></span><DownOutlined className="sider-account-arrow" /></button></Dropdown>
          : <Tooltip title={authUser ? `${authUser.display_name} · ${authUser.organization || '平台用户'}` : '游客 · 体验模式'} placement="right"><Dropdown menu={{ items: accountMenu }} trigger={['click']} placement="topLeft"><button className="sider-account sider-account-collapsed" type="button"><Avatar size={34} className="sider-account-avatar">{authUser?.display_name.slice(0, 1) || '游'}</Avatar></button></Dropdown></Tooltip>}
          {!collapsed && <Button className="sider-back-home" type="text" icon={<HomeOutlined />} onClick={() => navigate('/home')}>返回官网</Button>}
        </div>
      </Sider>

      {isMobile && !collapsed && <button className="mobile-sider-backdrop" type="button" aria-label="关闭导航" onClick={() => setCollapsed(true)} />}

      <Layout className="commercial-main-layout exact-main-layout">
        <Header className="app-header commercial-header exact-header">
          <Button type="text" className="sider-toggle exact-sider-toggle" aria-label={collapsed ? '展开侧边栏' : '收起侧边栏'} icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />} onClick={() => setCollapsed((current) => !current)} />
          <Dropdown menu={{ items: workspaceMenu }} trigger={['click']} placement="bottomLeft" overlayClassName="workspace-dropdown">
            <button type="button" className="wb-workspace-selector" aria-label="切换当前大棚"><strong>{workspaceGreenhouse?.name || '选择大棚'}</strong><small>{workspaceGreenhouse?.code}</small><DownOutlined /></button>
          </Dropdown>
          <div className="wb-current-page">{currentPageName}</div>
          <div className="header-spacer" />
          <Tooltip title="查找功能 · Ctrl / ⌘ K"><Button className="pz-command-trigger" aria-label="打开功能导航" icon={<SearchOutlined />} onClick={() => setNavigatorOpen(true)}><span>功能导航</span></Button></Tooltip>
          {isGuestMode() && <span className="wb-demo-label">游客体验 · 示例数据</span>}
          <div className="exact-header-clock"><SunOutlined /><span>{formatHeaderTime(now)} 当前时间</span></div>
          <Divider type="vertical" className="header-divider exact-header-divider" />
          <ServiceStatus />
          <Divider type="vertical" className="header-divider exact-header-divider" />
          <Tooltip title="查看环境预警"><Badge count={warningCount ?? 0} size="small" offset={[-3, 4]}><Button type="text" className="header-icon-button exact-header-icon" aria-label="查看环境预警" icon={<BellOutlined />} onClick={openWarnings} /></Badge></Tooltip>
          <Dropdown menu={{ items: accountMenu }} trigger={['click']}><button className="header-account-button" type="button" aria-label="账户菜单"><Avatar className="header-avatar exact-header-avatar">{authUser?.display_name.slice(0, 1) || '游'}</Avatar><DownOutlined /></button></Dropdown>
        </Header>
        <Content className={`app-content commercial-content exact-content wb-content${is3DPage ? ' is-3d-content' : ''}`}>
          <div className="wb-route-body">
            {currentGroup && currentGroup.id !== 'production' && <WorkspaceSectionNav group={currentGroup} current={currentItem} search={location.search} newsUnread={newsUnread} />}
            <div className="pz-workspace-page"><Outlet key={greenhouseFromUrl ?? 'empty'} /></div>
          </div>
        </Content>
      </Layout>
      <Drawer title="功能导航" open={navigatorOpen} onClose={() => setNavigatorOpen(false)} width={560} className="pz-navigator" destroyOnHidden>
        <Input.Search autoFocus allowClear value={navigationQuery} onChange={event => setNavigationQuery(event.target.value)} placeholder="搜索功能，例如探因、任务、知识库" aria-label="搜索平台功能" size="large" />
        <p className="pz-navigation-hint">选择工作入口，继续当前大棚的工作。</p>
        {allWorkspaceGroups.map(group => { const matches = group.items.filter(item => `${group.label}${item.label}${item.description}`.toLowerCase().includes(navigationQuery.trim().toLowerCase())); return matches.length ? <section className="pz-navigation-group" key={group.id}><h3>{group.label}</h3>{matches.map(item => <button type="button" key={item.key} onClick={() => { navigate(workspaceHref(item.key, location.search)); setNavigatorOpen(false); setNavigationQuery('') }}><span className="pz-navigation-icon">{item.icon}</span><span><strong>{item.label}</strong><small>{item.description}</small></span><span>↗</span></button>)}</section> : null })}
        {!navigationItems.some(item => `${allWorkspaceGroups.find(g => g.items.includes(item))?.label}${item.label}${item.description}`.toLowerCase().includes(navigationQuery.trim().toLowerCase())) && <div className="pz-navigation-empty">没有找到相关功能，试试“环境”“研究”或“论坛”。</div>}
      </Drawer>
      {accountSettingsOpen && <Suspense fallback={null}><AccountSettings open={accountSettingsOpen} onClose={() => setAccountSettingsOpen(false)} /></Suspense>}
      <Drawer title={utilityPanel === 'help' ? '帮助中心' : '系统设置'} open={utilityPanel !== null} onClose={() => setUtilityPanel(null)} width={360} destroyOnHidden>
        {utilityPanel === 'help' ? <div className="app-utility-panel">
          <section><h3>服务状态</h3><div className="app-utility-row"><span>{systemStatus === 'online' ? '连接正常' : systemStatus === 'offline' ? '服务未连接' : '正在检查'}</span><Button size="small" onClick={() => void checkHealth()}>重新检查</Button></div></section>
          <section><h3>常用入口</h3><div className="app-utility-actions">
            <Button block onClick={() => { setUtilityPanel(null); navigate(workspaceHref('/platform/data', location.search)) }}>管理大棚</Button>
            <Button block onClick={() => { setUtilityPanel(null); openWarnings() }}>查看环境预警</Button>
            <Button block onClick={() => { setUtilityPanel(null); navigate(workspaceHref('/platform/production?tab=tasks', location.search)) }}>查看农事任务</Button>
          </div></section>
        </div> : utilityPanel === 'settings' ? <div className="app-utility-panel">
          <section><h3>工作区</h3><Select className="app-utility-workspace" value={workspaceGreenhouse?.id} placeholder="选择当前大棚" options={greenhouses.map((item) => ({ value: item.id, label: `${item.name} · ${item.code}` }))} onChange={(id: number) => { const greenhouse = greenhouses.find((item) => item.id === id); if (greenhouse) switchWorkspace(greenhouse) }} /></section>
          <section><h3>界面偏好</h3><div className="app-utility-row"><span>自动刷新预警</span><Switch checked={autoRefreshWarnings} onChange={setAutoRefreshWarnings} /></div><div className="app-utility-row"><span>减少界面动效</span><Switch checked={reducedMotion} onChange={setReducedMotion} /></div></section>
          <section><h3>AI 运行</h3><p className="pz-settings-note">查看调用追踪、工具执行与能力评测。</p><Button block onClick={() => { setUtilityPanel(null); navigate(workspaceHref('/platform/ai-quality', location.search)) }}>AI 能力与运行</Button></section>
        </div> : null}
      </Drawer>
    </Layout>
    <FloatingAIAssistant standalone />
    </ConfigProvider>
  )
}
