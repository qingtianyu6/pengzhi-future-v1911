import { useEffect, useMemo, useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'

const links = [
  ['/home', '首页'],
  ['/introduction', '平台介绍'],
  ['/features', '核心功能'],
  ['/highlights', '技术亮点'],
  ['/scenarios', '应用场景'],
]

function BrandMark() {
  return (
    <svg className="reference-brand-mark" viewBox="0 0 72 72" aria-hidden="true">
      <path className="brand-house" d="M11 54V27L36 10l25 17v27" />
      <path className="brand-ground" d="M7 60c14-2 25-6 34-13 8-6 13-13 18-23" />
      <path className="brand-leaf" d="M15 54c3-18 16-29 38-31-2 18-13 29-31 31-3 0-5 0-7 0Z" />
      <path className="brand-vein" d="M16 55c9-11 19-18 31-24" />
    </svg>
  )
}
function SearchIcon() {
  return <svg viewBox="0 0 28 28" aria-hidden="true"><circle cx="12" cy="12" r="7.5"/><path d="m17.5 17.5 6 6"/></svg>
}
function UserIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="3.2"/><path d="M5.8 19c.7-4.1 3-6.1 6.2-6.1s5.5 2 6.2 6.1"/></svg>
}

export function SiteLayout() {
  const { pathname } = useLocation()
  const [searchOpen, setSearchOpen] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [query, setQuery] = useState('')
  const results = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return links
    return links.filter(([, label]) => label.toLowerCase().includes(q))
  }, [query])
  useEffect(() => {
    const openSearch = () => setSearchOpen(true)
    window.addEventListener('pengzhi:open-search', openSearch)
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { setSearchOpen(false); setMobileMenuOpen(false) }
    }
    window.addEventListener('keydown', onKey)
    return () => { window.removeEventListener('keydown', onKey); window.removeEventListener('pengzhi:open-search', openSearch) }
  }, [])
  useEffect(() => {
    setMobileMenuOpen(false)
    setSearchOpen(false)
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
  }, [pathname])
  useEffect(() => {
    const locked = searchOpen || mobileMenuOpen
    document.documentElement.classList.toggle('site-scroll-locked', locked)
    return () => document.documentElement.classList.remove('site-scroll-locked')
  }, [searchOpen, mobileMenuOpen])
  const usesEmbeddedHeader = false
  return (
    <main className="site-home reference-site-home">
      {!usesEmbeddedHeader && <header className="reference-site-nav">
        <Link className="reference-brand" to="/home" aria-label="棚智未来首页">
          <BrandMark />
          <span><strong>棚智未来</strong><small>让农业更有未来</small></span>
        </Link>
        <nav className="reference-nav-links" aria-label="项目官网导航">
          {links.map(([to, label]) => <Link className={pathname === to ? 'active' : ''} aria-current={pathname === to ? 'page' : undefined} to={to} key={to}>{label}</Link>)}
        </nav>
        <div className="reference-nav-actions">
          <button className="reference-search" aria-label="搜索" onClick={() => setSearchOpen(true)}><SearchIcon /></button>
          <Link className="reference-guest" to="/platform?mode=guest"><UserIcon /> 游客模式</Link>
          <Link className="reference-login" to="/login">登录</Link>
          <Link className="reference-register" to="/register">注册</Link>
          <button className={`reference-menu-toggle ${mobileMenuOpen ? 'is-open' : ''}`} aria-label="打开导航菜单" aria-expanded={mobileMenuOpen} onClick={() => setMobileMenuOpen((v) => !v)}><span/><span/><span/></button>
        </div>
      </header>}

      {!usesEmbeddedHeader && mobileMenuOpen && <div className="mobile-nav-layer" onMouseDown={() => setMobileMenuOpen(false)}>
        <aside className="mobile-nav-drawer" aria-label="移动端导航" onMouseDown={(event) => event.stopPropagation()}>
          <div className="mobile-nav-head"><strong>导航</strong><button aria-label="关闭导航" onClick={() => setMobileMenuOpen(false)}>×</button></div>
          <nav>{links.map(([to, label]) => <Link className={pathname === to ? 'active' : ''} aria-current={pathname === to ? 'page' : undefined} to={to} key={to}><span>{label}</span><b>→</b></Link>)}</nav>
          <button className="mobile-nav-search" onClick={() => { setMobileMenuOpen(false); setSearchOpen(true) }}><SearchIcon /><span>站内搜索</span></button>
          <div className="mobile-nav-auth"><Link to="/platform?mode=guest"><UserIcon/>游客模式</Link><Link to="/login">登录</Link><Link className="primary" to="/register">注册</Link></div>
        </aside>
      </div>}
      {searchOpen && <div className="site-search-layer" role="dialog" aria-modal="true" aria-label="站内搜索" onMouseDown={() => setSearchOpen(false)}>
        <div className="site-search-panel" onMouseDown={(event) => event.stopPropagation()}>
          <div className="site-search-heading"><strong>站内搜索</strong><button onClick={() => setSearchOpen(false)} aria-label="关闭搜索">×</button></div>
          <label className="site-search-input"><SearchIcon/><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索首页、核心功能、应用场景…"/></label>
          <div className="site-search-results">{results.length ? results.map(([to,label]) => <Link key={to} to={to} onClick={() => { setSearchOpen(false); setQuery('') }}><span>{label}</span><b>→</b></Link>) : <p>没有找到对应页面</p>}</div>
        </div>
      </div>}
      <Outlet />
    </main>
  )
}
