import type { PropsWithChildren } from 'react'
import { useNavigate } from 'react-router-dom'
import './home-v11.css'

type GlyphProps = PropsWithChildren<{ size?: number; className?: string }>
const Glyph = ({ children, size = 18, className = '' }: GlyphProps) => (
  <span className={`glyph ${className}`} style={{ fontSize: size }} aria-hidden="true">{children}</span>
)
const Search = (props: Omit<GlyphProps, 'children'>) => <Glyph {...props}>⌕</Glyph>
const UserRound = (props: Omit<GlyphProps, 'children'>) => <Glyph {...props}>♙</Glyph>
const Play = (props: Omit<GlyphProps, 'children'>) => <Glyph {...props}>▶</Glyph>
const ArrowRight = (props: Omit<GlyphProps, 'children'>) => <Glyph {...props}>→</Glyph>
const ChevronRight = (props: Omit<GlyphProps, 'children'>) => <Glyph {...props}>›</Glyph>
const ScanLine = (props: Omit<GlyphProps, 'children'>) => <Glyph {...props}>◎</Glyph>
const BrainCircuit = (props: Omit<GlyphProps, 'children'>) => <Glyph {...props}>◇</Glyph>
const ClipboardCheck = (props: Omit<GlyphProps, 'children'>) => <Glyph {...props}>✓</Glyph>
const TrendingUp = (props: Omit<GlyphProps, 'children'>) => <Glyph {...props}>↗</Glyph>
const Youtube = (props: Omit<GlyphProps, 'children'>) => <Glyph {...props}>●</Glyph>
const Instagram = (props: Omit<GlyphProps, 'children'>) => <Glyph {...props}>◎</Glyph>
const MessageCircle = (props: Omit<GlyphProps, 'children'>) => <Glyph {...props}>◉</Glyph>

const A = '/homepage-v11/'

function Header() {
  const navigate = useNavigate()
  const openSearch = () => window.dispatchEvent(new CustomEvent('pengzhi:open-search'))
  return <header className="topbar">
    <div className="header-inner">
      <button className="brand brand-button" onClick={() => navigate('/home')} aria-label="棚智未来首页">
        <img src={`${A}logo.png`} alt="棚智未来" />
      </button>
      <nav className="nav-links" aria-label="主导航">
        <button className="active" onClick={() => navigate('/home')}>首页</button>
        <button onClick={() => navigate('/introduction')}>平台介绍</button>
        <button onClick={() => navigate('/features')}>核心功能</button>
        <button onClick={() => navigate('/highlights')}>技术亮点</button>
        <button onClick={() => navigate('/scenarios')}>应用场景</button>
      </nav>
      <div className="header-actions">
        <button className="icon-btn" aria-label="搜索" onClick={openSearch}><Search size={20}/></button>
        <button className="mode-btn" onClick={() => navigate('/platform?mode=guest')}><UserRound size={16}/> 游客模式</button>
        <button className="login-btn" onClick={() => navigate('/login')}>登录</button>
        <button className="signup-btn" onClick={() => navigate('/register')}>注册</button>
      </div>
    </div>
  </header>
}

const metrics = [
  { icon: 'icon-sun.png', label: '光照强度', value: '685', unit: 'μmol/m²·s', delta: '↑ +12%' },
  { icon: 'icon-temp.png', label: '温度', value: '24.6', unit: '℃', delta: '↑ +0.3℃' },
  { icon: 'icon-water.png', label: '土壤湿度', value: '62', unit: '%', delta: '↑ +5%' },
  { icon: 'icon-co2.png', label: 'CO₂浓度', value: '412', unit: 'ppm', delta: '↓ -8%' },
]

function Hero() {
  const navigate = useNavigate()
  return <section id="top" className="hero">
    <div className="hero-scene" aria-hidden="true" />
    <div className="hero-inner">
      <div className="hero-copy">
        <div className="brush-title">
          <span>让每一座大棚</span>
          <span>拥有<em>智慧生长力</em></span>
        </div>
        <p className="hero-desc">用数据感知作物，用智能守护生长。<br/>让农业管理更简单、更科学、更高效。</p>
        <div className="hero-cta">
          <button className="primary-pill" onClick={() => navigate('/login')}>进入管理平台 <ArrowRight size={18}/></button>
          <button className="video-pill" onClick={() => navigate('/introduction')}><span className="play-circle"><Play size={15}/></span>观看介绍视频</button>
        </div>
        <div className="hero-dots"><i/><i/><i/><span>科技赋能农业 智慧点亮未来</span></div>
      </div>
      <div className="hero-right-note">科技，让农业更美好<span/></div>
      <div className="hero-mid-note">看得见的生长<br/>管得住的未来</div>
      <div className="metric-row">
        {metrics.map((metric) => <div className="metric-card" key={metric.label}>
          <div className="metric-head"><img src={`${A}${metric.icon}`} alt=""/><span>{metric.label}</span></div>
          <div className="metric-value"><strong>{metric.value}</strong><small>{metric.unit}</small></div>
          <div className="spark"><span/><span/><span/><span/><span/><span/></div>
          <div className="metric-delta">{metric.delta}</div>
        </div>)}
      </div>
    </div>
    <div className="hero-wave" />
  </section>
}

const capability = [
  { img: 'icon-leaf.png', title: '环境实时监测', sub: '看得更清' },
  { img: 'icon-chart.png', title: '数据智能分析', sub: '管得更准' },
  { img: 'icon-seedling.png', title: '病害智能识别', sub: '防得更早' },
  { img: 'icon-grid.png', title: '农事科学管理', sub: '做得更轻松' },
]
function CapabilityStrip() {
  return <section id="intro" className="cap-strip"><div className="cap-inner">
    {capability.map((item, index) => <div className="cap-item" key={item.title}>
      <img src={`${A}${item.img}`} alt=""/><div><h3>{item.title}</h3><p>{item.sub}</p></div>
      {index < capability.length - 1 && <b className="divider"/>}
    </div>)}
  </div></section>
}

const features = [
  { img: 'feature-monitor.jpg', title: '环境监测与预警', desc: '实时采集大棚内温湿度、光照、CO₂等关键数据，异常及时预警。', to: '/platform/environment' },
  { img: 'feature-dashboard.jpg', title: '数据分析与决策', desc: '基于历史与实时数据，提供生长趋势分析和智能决策建议。', to: '/platform/production' },
  { img: 'feature-disease.jpg', title: '作物病害识别', desc: '融合图像识别与多源数据，精准识别病害类型并给出防治方案。', to: '/platform/diagnosis' },
  { img: 'feature-tablet.jpg', title: '农事管理与执行', desc: '提供种植计划、灌溉施肥、采收管理等一站式农事服务。', to: '/platform/production?tab=tasks' },
]

type SectionHeadingProps = { title: string; subtitle: string; side?: string }
function SectionHeading({ title, subtitle, side }: SectionHeadingProps) {
  return <div className="section-heading"><div><h2>{title}</h2><p>{subtitle}</p></div>
    {side && <div className="section-side"><span>{side}</span><img src={`${A}icon-leaf.png`} alt=""/></div>}
  </div>
}

function CoreFeatures() {
  const navigate = useNavigate()
  return <section id="core" className="core-section section-pad"><div className="content-wrap">
    <SectionHeading title="核心功能" subtitle="从感知、分析到决策，构建农业大棚的全链路智能管理体系" side="CORE FUNCTIONS"/>
    <div className="feature-grid">{features.map((feature) => <article className="feature-card" key={feature.title}>
      <img className="feature-photo" src={`${A}${feature.img}`} alt={feature.title}/><h3>{feature.title}</h3><p>{feature.desc}</p>
      <button className="round-more" aria-label={`查看${feature.title}`} onClick={() => navigate(feature.to)}><ChevronRight size={17}/></button>
    </article>)}</div>
  </div></section>
}

const outcome = [
  { Icon: ScanLine, title: '环境感知', desc: '多维度实时监测' },
  { Icon: BrainCircuit, title: '智能分析', desc: 'AI驱动数据洞察' },
  { Icon: ClipboardCheck, title: '精准管理', desc: '科学决策执行' },
  { Icon: TrendingUp, title: '增产增效', desc: '提升品质与收益' },
]
function Highlights() {
  return <section id="highlights" className="highlight-section section-pad"><div className="content-wrap">
    <div className="highlight-title"><h2>智慧大棚 · <em>看得见的改变</em></h2><p>从数据到行动，让每一份努力都有回报</p></div>
    <div className="hand-annotation">数据让种植更简单<span/></div>
    <div className="outcome-layout">
      <div className="outcome-col left-col">{outcome.slice(0, 2).map(({ Icon, title, desc }) => <div className="outcome-card" key={title}><span className="outcome-icon"><Icon size={20}/></span><div><h4>{title}</h4><p>{desc}</p></div></div>)}</div>
      <div className="greenhouse-stage"><div className="ring r1"/><div className="ring r2"/><div className="ring r3"/><img src={`${A}greenhouse-center.jpg`} alt="智慧大棚"/></div>
      <div className="outcome-col right-col">{outcome.slice(2).map(({ Icon, title, desc }) => <div className="outcome-card" key={title}><span className="outcome-icon"><Icon size={20}/></span><div><h4>{title}</h4><p>{desc}</p></div></div>)}</div>
    </div>
  </div></section>
}

const scenes = [
  { img: 'scene-tomato.jpg', title: '果蔬种植', desc: '品质更优 · 产量更高' },
  { img: 'scene-leafy.jpg', title: '叶菜种植', desc: '生长可控 · 绿色健康' },
  { img: 'scene-strawberry.jpg', title: '特色作物', desc: '精细管理 · 提升价值' },
  { img: 'scene-flower.jpg', title: '花卉种植', desc: '环境可控 · 品质稳定' },
]
function Scenes() {
  return <section id="scenes" className="scene-section section-pad"><div className="content-wrap">
    <SectionHeading title="应用场景" subtitle="适用于多种农业种植场景，助力不同用户实现数字化升级" side="APPLICATION SCENARIOS"/>
    <div className="scene-grid">{scenes.map((scene) => <article className="scene-card" key={scene.title}><img src={`${A}${scene.img}`} alt={scene.title}/><h3>{scene.title}</h3><p>{scene.desc}</p></article>)}</div>
  </div></section>
}

function Cta() {
  const navigate = useNavigate()
  return <section id="results" className="cta-section"><div className="cta-bg"/><div className="cta-inner">
    <div><h2>从一粒种子<br/>到一份丰收</h2><p>加入棚智未来，共同开启智慧农业新篇章</p></div>
    <button className="cta-button" onClick={() => navigate('/platform?mode=guest')}>立即体验 <ArrowRight size={18}/></button>
  </div></section>
}

function Footer() {
  const navigate = useNavigate()
  return <footer className="footer"><div className="footer-inner">
    <button className="footer-logo-button" onClick={() => navigate('/home')} aria-label="返回首页"><img className="footer-logo" src={`${A}logo.png`} alt="棚智未来"/></button>
    <div className="footer-nav"><button onClick={() => navigate('/home')}>首页</button><button onClick={() => navigate('/introduction')}>平台介绍</button><button onClick={() => navigate('/features')}>核心功能</button><button onClick={() => navigate('/highlights')}>技术亮点</button><button onClick={() => navigate('/scenarios')}>应用场景</button></div>
    <div className="socials"><Youtube size={16}/><Instagram size={16}/><MessageCircle size={16}/></div>
  </div><div className="copyright">© 2026 棚智未来 让农业更有未来</div></footer>
}

export default function HomeV11Page() {
  return <div className="home-v11"><Header/><main><Hero/><CapabilityStrip/><CoreFeatures/><Highlights/><Scenes/><Cta/></main><Footer/></div>
}
