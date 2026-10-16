import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import {
  AppstoreOutlined,
  BellOutlined,
  CheckCircleOutlined,
  DatabaseOutlined,
  DownOutlined,
  FileSearchOutlined,
  HomeOutlined,
  LineChartOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  PlusOutlined,
  QuestionCircleOutlined,
  SettingOutlined,
  SunOutlined,
} from '@ant-design/icons'
import { Avatar, Badge, Button, ConfigProvider, Divider, Drawer, Dropdown, Layout, Menu, Select, Switch, Tooltip, type MenuProps } from 'antd'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { WorkbenchAssistantRail } from '../components/WorkbenchAssistantRail'
import { isGuestMode } from '../api/guestMode'
import { ServiceStatus } from '../components/ServiceStatus'
import { getGreenhouses } from '../api/greenhouseApi'
import { getWarningSummary } from '../api/warningApi'
import type { Greenhouse } from '../types/greenhouse'
import { useSystemStore } from '../store/system'
import { getStoredUser, logoutAccount, type AuthUser } from '../api/authApi'
import './workbench-refresh.css'

const AccountSettings = lazy(() => import('../components/AccountSettings'))
const { Header, Sider, Content } = Layout

const navigationItems = [
  { key: '/platform', icon: <HomeOutlined />, label: '生产总览' },
  { key: '/platform/environment', icon: <LineChartOutlined />, label: '监测与预警' },
  { key: '/platform/diagnosis', icon: <FileSearchOutlined />, label: '病害诊断' },
  { key: '/platform/production', icon: <CheckCircleOutlined />, label: '农事执行' },
  { key: '/platform/3d', icon: <AppstoreOutlined />, label: '三维大棚' },
  { key: '/platform/data', icon: <DatabaseOutlined />, label: '数据与管理' },
]

const menuItems: MenuProps['items'] = [
  { type: 'group', label: '日常生产', children: navigationItems.slice(0, 4) },
  { type: 'group', label: '资产与场景', children: navigationItems.slice(4) },
]

function formatHeaderTime(value: Date) {
  return value.toLocaleString('zh-CN', {
    year: 'numeric', month: 'long', day: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  })
}

export function AppLayout() {
  const [isMobile, setIsMobile] = useState(() => window.matchMedia('(max-width: 620px)').matches)
  const [collapsed, setCollapsed] = useState(() => window.matchMedia('(max-width: 620px)').matches)
  const [wide, setWide] = useState(() => window.matchMedia('(min-width: 1280px)').matches)
  const [workspaceGreenhouse, setWorkspaceGreenhouse] = useState<Greenhouse | null>(null)
  const [greenhouses, setGreenhouses] = useState<Greenhouse[]>([])
  const [now, setNow] = useState(() => new Date())
  const [authUser, setAuthUser] = useState<AuthUser | null>(() => getStoredUser())
  const [warningCount, setWarningCount] = useState<number | null>(null)
  const [accountSettingsOpen, setAccountSettingsOpen] = useState(false)
  const [utilityPanel, setUtilityPanel] = useState<'help' | 'settings' | null>(null)
  const [autoRefreshWarnings, setAutoRefreshWarnings] = useState(() => localStorage.getItem('pengzhi_auto_refresh_warnings') !== '0')
  const [reducedMotion, setReducedMotion] = useState(() => localStorage.getItem('pengzhi_reduced_motion') === '1')
  const navigate = useNavigate()
  const location = useLocation()
  const checkHealth = useSystemStore((state) => state.checkHealth)
  const systemStatus = useSystemStore((state) => state.status)
  const is3DPage = location.pathname === '/platform/3d' || location.pathname.startsWith('/platform/3d/')
  const isTimeMachine = location.pathname.startsWith('/platform/disease-time-machine')
  const diseaseSection = isTimeMachine || location.pathname.startsWith('/platform/diagnosis')
  const docked = wide && !is3DPage
  const currentPageName = isTimeMachine ? '病害时间机' : navigationItems.find((item) => (
    item.key === '/platform'
      ? location.pathname === '/platform'
      : location.pathname === item.key || location.pathname.startsWith(`${item.key}/`)
  ))?.label ?? '页面未找到'

  const greenhouseFromUrl = useMemo(() => Number(new URLSearchParams(location.search).get('greenhouse_id')) || null, [location.search])

  useEffect(() => { void checkHealth() }, [checkHealth])
  useEffect(() => {
    let active = true
    const refreshWarnings = () => {
      void getWarningSummary()
        .then((summary) => { if (active) setWarningCount(summary.open_total) })
        .catch(() => { if (active) setWarningCount(null) })
    }
    refreshWarnings()
    const timer = autoRefreshWarnings ? window.setInterval(refreshWarnings, 60000) : null
    return () => { active = false; if (timer !== null) window.clearInterval(timer) }
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
    const media = window.matchMedia('(min-width: 1280px)')
    const update = () => setWide(media.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
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
    { key: 'manage', icon: <PlusOutlined />, label: '管理大棚', onClick: () => navigate('/platform/data') },
  ]

  const selectedKey = navigationItems.find((item) => item.key === '/platform'
    ? location.pathname === '/platform'
    : location.pathname === item.key || location.pathname.startsWith(`${item.key}/`))?.key ?? location.pathname

  return (
    <ConfigProvider theme={{ token: { colorPrimary: '#24694e', colorInfo: '#24694e', colorText: '#223e34', colorTextSecondary: '#718176', colorBgLayout: '#f5f5ef', colorBorderSecondary: '#e3e8de', borderRadius: 10, borderRadiusLG: 15 } }}>
    <Layout className={`app-shell commercial-app-shell exact-shell wb-shell${docked ? ' has-assistant-rail' : ''}`}>
      <Sider
        className={`app-sider commercial-sider exact-sider ${collapsed ? 'is-collapsed' : ''}`}
        width={208}
        collapsedWidth={72}
        collapsed={collapsed}
        trigger={null}
      >
        <div className="brand commercial-brand exact-brand" onClick={() => navigate('/platform')} role="button" tabIndex={0} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') navigate('/platform') }}>
          <div className="brand-symbol commercial-brand-symbol exact-brand-symbol">棚</div>
          {!collapsed && <div className="commercial-brand-copy exact-brand-copy"><strong>棚智未来</strong><span>Smart Greenhouse</span></div>}
        </div>

        <Menu className="side-menu commercial-side-menu exact-side-menu" mode="inline" inlineCollapsed={collapsed} selectedKeys={[isTimeMachine ? '/platform/diagnosis' : selectedKey]} items={menuItems} onClick={({ key }) => navigate(`${key}${workspaceGreenhouse ? `?greenhouse_id=${workspaceGreenhouse.id}` : ''}`)} />

        <div className={`sider-bottom exact-sider-bottom ${collapsed ? 'is-collapsed' : ''}`}>
          <Tooltip title="帮助中心" placement="right"><Button type="text" icon={<QuestionCircleOutlined />} onClick={() => setUtilityPanel('help')}>{!collapsed && '帮助中心'}</Button></Tooltip>
          <Tooltip title="系统设置" placement="right"><Button type="text" icon={<SettingOutlined />} onClick={() => setUtilityPanel('settings')}>{!collapsed && '系统设置'}</Button></Tooltip>
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
            {diseaseSection && <nav className="wb-section-tabs" aria-label="病害诊断功能">{[
              { key: 'identify', name: '叶片识别', path: '/platform/diagnosis' },
              { key: 'time', name: '病害时间机', path: '/platform/disease-time-machine' },
              { key: 'history', name: '识别与复核记录', path: '/platform/diagnosis', view: 'history' },
            ].map(item => <button key={item.key} type="button" aria-current={(isTimeMachine ? item.key === 'time' : new URLSearchParams(location.search).get('view') === 'history' ? item.key === 'history' : item.key === 'identify') ? 'page' : undefined} onClick={() => navigate(`${item.path}?${new URLSearchParams({ ...(greenhouseFromUrl ? { greenhouse_id: String(greenhouseFromUrl) } : {}), ...(item.view ? { view: item.view } : {}) })}`)}>{item.name}</button>)}</nav>}
            <Outlet key={greenhouseFromUrl ?? 'empty'} />
          </div>
          <aside className={docked ? 'wb-assistant-rail' : 'wb-floating-host'} aria-label="棚小智与今日待办"><WorkbenchAssistantRail greenhouseId={greenhouseFromUrl ?? undefined} docked={docked} /></aside>
        </Content>
      </Layout>
      {accountSettingsOpen && <Suspense fallback={null}><AccountSettings open={accountSettingsOpen} onClose={() => setAccountSettingsOpen(false)} /></Suspense>}
      <Drawer title={utilityPanel === 'help' ? '帮助中心' : '系统设置'} open={utilityPanel !== null} onClose={() => setUtilityPanel(null)} width={360} destroyOnHidden>
        {utilityPanel === 'help' ? <div className="app-utility-panel">
          <section><h3>服务状态</h3><div className="app-utility-row"><span>{systemStatus === 'online' ? '连接正常' : systemStatus === 'offline' ? '服务未连接' : '正在检查'}</span><Button size="small" onClick={() => void checkHealth()}>重新检查</Button></div></section>
          <section><h3>常用入口</h3><div className="app-utility-actions">
            <Button block onClick={() => { setUtilityPanel(null); navigate('/platform/data') }}>管理大棚</Button>
            <Button block onClick={() => { setUtilityPanel(null); openWarnings() }}>查看环境预警</Button>
            <Button block onClick={() => { setUtilityPanel(null); navigate('/platform/production') }}>查看农事任务</Button>
          </div></section>
        </div> : utilityPanel === 'settings' ? <div className="app-utility-panel">
          <section><h3>工作区</h3><Select className="app-utility-workspace" value={workspaceGreenhouse?.id} placeholder="选择当前大棚" options={greenhouses.map((item) => ({ value: item.id, label: `${item.name} · ${item.code}` }))} onChange={(id: number) => { const greenhouse = greenhouses.find((item) => item.id === id); if (greenhouse) switchWorkspace(greenhouse) }} /></section>
          <section><h3>界面偏好</h3><div className="app-utility-row"><span>自动刷新预警</span><Switch checked={autoRefreshWarnings} onChange={setAutoRefreshWarnings} /></div><div className="app-utility-row"><span>减少界面动效</span><Switch checked={reducedMotion} onChange={setReducedMotion} /></div></section>
        </div> : null}
      </Drawer>
    </Layout>
    </ConfigProvider>
  )
}
