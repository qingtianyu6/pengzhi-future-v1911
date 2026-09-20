import { useEffect, useMemo, useState } from 'react'
import {
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
import { Avatar, Badge, Button, Divider, Dropdown, Layout, Menu, Tooltip, type MenuProps } from 'antd'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { FloatingAIAssistant } from '../components/FloatingAIAssistant'
import { ServiceStatus } from '../components/ServiceStatus'
import { getGreenhouses } from '../api/greenhouseApi'
import type { Greenhouse } from '../types/greenhouse'
import { useSystemStore } from '../store/system'
import { getStoredUser, logoutAccount, type AuthUser } from '../api/authApi'

const { Header, Sider, Content } = Layout

const navigationItems = [
  { key: '/platform', icon: <HomeOutlined />, label: '种植总览' },
  { key: '/platform/data', icon: <DatabaseOutlined />, label: '大棚管理' },
  { key: '/platform/environment', icon: <LineChartOutlined />, label: '环境分析' },
  { key: '/platform/diagnosis', icon: <FileSearchOutlined />, label: '病害检测' },
  { key: '/platform/production', icon: <CheckCircleOutlined />, label: '农事任务' },
]

const menuItems: MenuProps['items'] = [
  { type: 'group', label: '工作台', children: [navigationItems[0]] },
  { type: 'group', label: '生产管理', children: navigationItems.slice(1) },
]

function formatHeaderTime(value: Date) {
  return value.toLocaleString('zh-CN', {
    year: 'numeric', month: 'long', day: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  })
}

export function AppLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const [workspaceGreenhouse, setWorkspaceGreenhouse] = useState<Greenhouse | null>(null)
  const [greenhouses, setGreenhouses] = useState<Greenhouse[]>([])
  const [now, setNow] = useState(() => new Date())
  const [authUser, setAuthUser] = useState<AuthUser | null>(() => getStoredUser())
  const navigate = useNavigate()
  const location = useLocation()
  const checkHealth = useSystemStore((state) => state.checkHealth)
  const systemStatus = useSystemStore((state) => state.status)
  const currentPageName = navigationItems.find((item) => (
    item.key === '/platform'
      ? location.pathname === '/platform'
      : location.pathname === item.key || location.pathname.startsWith(`${item.key}/`)
  ))?.label ?? '页面未找到'

  const greenhouseFromUrl = useMemo(() => Number(new URLSearchParams(location.search).get('greenhouse_id')) || null, [location.search])

  useEffect(() => { void checkHealth() }, [checkHealth])
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 60000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    void getGreenhouses({ page: 1, page_size: 100, status: 'active' })
      .then((result) => {
        setGreenhouses(result.items)
        const selected = greenhouseFromUrl ? result.items.find((item) => item.id === greenhouseFromUrl) : undefined
        setWorkspaceGreenhouse(selected ?? result.items[0] ?? null)
      })
      .catch(() => { setGreenhouses([]); setWorkspaceGreenhouse(null) })
  }, [greenhouseFromUrl])

  useEffect(() => { document.title = `${currentPageName} - 棚智未来` }, [currentPageName])

  const switchWorkspace = (greenhouse: Greenhouse) => {
    setWorkspaceGreenhouse(greenhouse)
    const params = new URLSearchParams(location.search)
    params.set('greenhouse_id', String(greenhouse.id))
    navigate(`${location.pathname}?${params.toString()}`)
  }

  const handleLogout = async () => {
    await logoutAccount()
    setAuthUser(null)
    navigate('/login', { replace: true })
  }

  const accountMenu: MenuProps['items'] = authUser ? [
    { key: 'identity', disabled: true, label: authUser.phone },
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
    <Layout className="app-shell commercial-app-shell exact-shell">
      <Sider
        className={`app-sider commercial-sider exact-sider ${collapsed ? 'is-collapsed' : ''}`}
        width={254}
        collapsedWidth={72}
        collapsed={collapsed}
        trigger={null}
      >
        <div className="brand commercial-brand exact-brand" onClick={() => navigate('/platform')} role="button" tabIndex={0} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') navigate('/platform') }}>
          <div className="brand-symbol commercial-brand-symbol exact-brand-symbol">棚</div>
          {!collapsed && <div className="commercial-brand-copy exact-brand-copy"><strong>棚智未来</strong><span>Smart Greenhouse</span></div>}
        </div>

        {!collapsed ? <Dropdown menu={{ items: workspaceMenu }} trigger={['click']} placement="bottomLeft" overlayClassName="workspace-dropdown">
          <button className="workspace-switcher exact-workspace-switcher" type="button" aria-label="切换当前大棚">
            <span>当前大棚</span>
            <div className="workspace-switcher-main"><div><strong>{workspaceGreenhouse ? `${workspaceGreenhouse.name} · ${workspaceGreenhouse.code}` : '尚未选择大棚'}</strong><small>🌱 {workspaceGreenhouse?.active_batch?.variety ? `${workspaceGreenhouse.active_batch.variety} · 生长中` : '自动跟随当前工作区'}</small></div><DownOutlined /></div>
          </button>
        </Dropdown> : <Tooltip title={workspaceGreenhouse ? `${workspaceGreenhouse.name} · ${workspaceGreenhouse.code}` : '当前大棚'} placement="right">
          <button className="workspace-switcher-collapsed" type="button" onClick={() => setCollapsed(false)}><span>{workspaceGreenhouse?.name?.slice(0, 1) || '棚'}</span></button>
        </Tooltip>}

        <Menu className="side-menu commercial-side-menu exact-side-menu" mode="inline" inlineCollapsed={collapsed} selectedKeys={[selectedKey]} items={menuItems} onClick={({ key }) => navigate(key)} />

        <div className={`sider-bottom exact-sider-bottom ${collapsed ? 'is-collapsed' : ''}`}>
          {!collapsed && <div className="sider-system-state exact-system-state"><i className={systemStatus === 'online' ? 'online' : systemStatus === 'offline' ? 'offline' : ''} /><strong>{systemStatus === 'online' ? '系统正常' : systemStatus === 'offline' ? '服务异常' : '正在检查'}</strong></div>}
          <Tooltip title="帮助中心" placement="right"><Button type="text" icon={<QuestionCircleOutlined />}>{!collapsed && '帮助中心'}</Button></Tooltip>
          <Tooltip title="系统设置" placement="right"><Button type="text" icon={<SettingOutlined />}>{!collapsed && '系统设置'}</Button></Tooltip>
          {!collapsed && <Divider className="exact-sider-divider" />}
          {!collapsed ? <Dropdown menu={{ items: accountMenu }} trigger={['click']} placement="topLeft"><button className="sider-account exact-sider-account" type="button"><Avatar size={38} className="sider-account-avatar">{authUser?.display_name.slice(0, 1) || '游'}</Avatar><span><strong>{authUser?.display_name || '游客'}</strong><small>{authUser?.organization || (authUser ? '平台用户' : '体验模式')}</small></span><DownOutlined className="sider-account-arrow" /></button></Dropdown>
          : <Tooltip title={authUser ? `${authUser.display_name} · ${authUser.organization || '平台用户'}` : '游客 · 体验模式'} placement="right"><Dropdown menu={{ items: accountMenu }} trigger={['click']} placement="topLeft"><button className="sider-account sider-account-collapsed" type="button"><Avatar size={34} className="sider-account-avatar">{authUser?.display_name.slice(0, 1) || '游'}</Avatar></button></Dropdown></Tooltip>}
          {!collapsed && <Button className="sider-back-home" type="text" icon={<HomeOutlined />} onClick={() => navigate('/home')}>返回官网</Button>}
        </div>
      </Sider>

      <Layout className="commercial-main-layout exact-main-layout">
        <Header className="app-header commercial-header exact-header">
          <Button type="text" className="sider-toggle exact-sider-toggle" aria-label={collapsed ? '展开侧边栏' : '收起侧边栏'} icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />} onClick={() => setCollapsed((current) => !current)} />
          <div className="header-context commercial-header-context exact-header-context"><span>大棚</span><b>/</b><span>{workspaceGreenhouse?.name || '小Q'}</span><b>/</b><strong>{currentPageName}</strong></div>
          <div className="header-spacer" />
          <div className="exact-header-clock"><SunOutlined /><span>{formatHeaderTime(now)} 更新</span></div>
          <Divider type="vertical" className="header-divider exact-header-divider" />
          <ServiceStatus />
          <Divider type="vertical" className="header-divider exact-header-divider" />
          <Badge count={3} size="small" offset={[-3, 4]}><Button type="text" className="header-icon-button exact-header-icon" icon={<BellOutlined />} /></Badge>
          <Avatar className="header-avatar exact-header-avatar">{authUser?.display_name.slice(0, 1) || '游'}</Avatar>
          <DownOutlined className="exact-header-chevron" />
        </Header>
        <Content className="app-content commercial-content exact-content"><Outlet /></Content>
      </Layout>
      <FloatingAIAssistant />
    </Layout>
  )
}
