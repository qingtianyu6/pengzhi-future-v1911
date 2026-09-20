import { useNavigate } from 'react-router-dom'
import Brand from './Brand'
import { SearchIcon, UserIcon } from './Icons'

const nav = ['首页', '平台介绍', '核心功能', '技术亮点', '应用场景']
const navRoutes: Record<string, string> = {
  '首页': '/home', '平台介绍': '/introduction', '核心功能': '/features',
  '技术亮点': '/highlights', '应用场景': '/scenarios',
}

export default function Header() {
  const navigate = useNavigate()
  const go = (label: string) => navigate(navRoutes[label])
  const openSearch = () => window.dispatchEvent(new CustomEvent('pengzhi:open-search'))
  return (
    <header className="site-header">
      <div className="site-header__inner">
        <button className="brand-button" onClick={() => navigate('/home')}><Brand /></button>
        <nav className="top-nav" aria-label="主导航">
          {nav.map((label) => <button key={label} onClick={() => go(label)} className={label === '核心功能' ? 'is-active' : ''}>{label}</button>)}
        </nav>
        <div className="header-actions">
          <button className="icon-button" aria-label="搜索" onClick={openSearch}><SearchIcon /></button>
          <button className="outline-button compact" onClick={() => navigate('/platform?mode=guest')}><UserIcon />游客模式</button>
          <button className="outline-button" onClick={() => navigate('/login')}>登录</button>
          <button className="solid-button" onClick={() => navigate('/register')}>注册</button>
        </div>
      </div>
    </header>
  )
}
