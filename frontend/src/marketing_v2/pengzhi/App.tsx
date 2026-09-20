import './styles.css'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { ReactElement, ReactNode } from 'react'
import sensorStation from './assets/images/sensor-station-regenerated.webp'
import dataLayers from './assets/images/data-layers-transparent.webp'
import healthyLeaf from './assets/images/leaf-healthy-transparent.webp'
import downyLeaf from './assets/images/leaf-downy-transparent.webp'
import powderyLeaf from './assets/images/leaf-powdery-transparent.webp'
import grayLeaf from './assets/images/leaf-graymold-transparent.webp'
import resultLeaf from './assets/images/leaf-result-transparent.webp'
import greenhouseInside from './assets/images/greenhouse-inside.webp'
import greenhouseSensor from './assets/images/greenhouse-sensor.webp'
import greenhouseValley from './assets/images/greenhouse-valley.webp'

type IconName =
  | 'search' | 'user' | 'database' | 'brain' | 'file' | 'nodes' | 'thermometer'
  | 'image' | 'clipboard' | 'cloud' | 'leaf' | 'spark' | 'shield' | 'link'
  | 'sun' | 'check' | 'chart' | 'book' | 'flask' | 'refresh' | 'arrow'

const pathMap: Record<IconName, ReactElement> = {
  search: <><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/></>,
  user: <><circle cx="12" cy="8" r="3.2"/><path d="M5.7 20c.4-4.1 2.5-6.1 6.3-6.1s5.9 2 6.3 6.1"/></>,
  database: <><ellipse cx="12" cy="5.5" rx="7.5" ry="3"/><path d="M4.5 5.5v6c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3v-6M4.5 11.5v6c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3v-6"/></>,
  brain: <><path d="M9.5 5.1A3.4 3.4 0 0 0 4.7 8a3.1 3.1 0 0 0 1.2 5.9A3.4 3.4 0 0 0 9.5 19M14.5 5.1A3.4 3.4 0 0 1 19.3 8a3.1 3.1 0 0 1-1.2 5.9 3.4 3.4 0 0 1-3.6 5.1M9.5 5.1V19M14.5 5.1V19M7.2 10h2.3M14.5 14h2.5"/></>,
  file: <><path d="M7 3.5h7l4 4V20H7z"/><path d="M14 3.5v4h4M10 12h5M10 15.5h5"/></>,
  nodes: <><circle cx="12" cy="5" r="2.5"/><circle cx="5" cy="18" r="2.5"/><circle cx="19" cy="18" r="2.5"/><path d="m10.6 7.1-4.1 8.7M13.4 7.1l4.1 8.7M7.5 18h9"/></>,
  thermometer: <><path d="M10 5a2 2 0 0 1 4 0v9.3a4.3 4.3 0 1 1-4 0z"/><path d="M12 8v8"/></>,
  image: <><rect x="3.5" y="4.5" width="17" height="15" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m5.5 17 4.5-4 3.5 3 2.5-2 4 3.5"/></>,
  clipboard: <><rect x="5" y="5.5" width="14" height="15" rx="2"/><path d="M9 5.5V3.8h6v1.7M9 10h6M9 14h6"/></>,
  cloud: <><path d="M7.2 18.5h10.2a4 4 0 0 0 .6-8 6.2 6.2 0 0 0-11.8 1.7 3.2 3.2 0 0 0 1 6.3z"/></>,
  leaf: <><path d="M20 4C11.5 4 5.8 7.7 5.8 13c0 3.7 3.4 6.2 6.7 4.9C17.5 16 20 10.8 20 4z"/><path d="M4 20c3.7-5.5 7.4-8.6 12-11"/></>,
  spark: <><path d="M12 3l1.2 4.1L17 9l-3.8 1.9L12 15l-1.2-4.1L7 9l3.8-1.9zM18 15l.6 2.1 1.9.9-1.9.9L18 21l-.6-2.1-1.9-.9 1.9-.9z"/></>,
  shield: <><path d="M12 3.5 19 6v5.1c0 4.4-2.5 7.8-7 9.4-4.5-1.6-7-5-7-9.4V6z"/><path d="m9 12 2 2 4-4"/></>,
  link: <><path d="M9.5 14.5 7 17a3.5 3.5 0 1 1-5-5l3-3a3.5 3.5 0 0 1 5 0M14.5 9.5 17 7a3.5 3.5 0 1 1 5 5l-3 3a3.5 3.5 0 0 1-5 0M8.5 15.5l7-7"/></>,
  sun: <><circle cx="12" cy="12" r="3.5"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1"/></>,
  check: <><circle cx="12" cy="12" r="9"/><path d="m8 12 2.5 2.5L16 9"/></>,
  chart: <><path d="M4 20V10M9 20V5M14 20v-8M19 20V3"/></>,
  book: <><path d="M4 5.5c2.8-.5 5.4.1 8 2v12c-2.6-1.9-5.2-2.5-8-2zM20 5.5c-2.8-.5-5.4.1-8 2v12c2.6-1.9 5.2-2.5 8-2z"/></>,
  flask: <><path d="M9 3h6M10 3v6l-5 8.5A2.3 2.3 0 0 0 7 21h10a2.3 2.3 0 0 0 2-3.5L14 9V3M8 15h8"/></>,
  refresh: <><path d="M19 7V3l-2 2a8 8 0 1 0 2.3 9M19 3h-4"/></>,
  arrow: <><path d="M4 12h15M14 7l5 5-5 5"/></>,
}

function Icon({ name, size = 24, className = '' }: { name: IconName; size?: number; className?: string }) {
  return <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{pathMap[name]}</svg>
}

const navItems = ['首页', '平台介绍', '核心功能', '技术亮点', '应用场景']
const navRoutes: Record<string, string> = {
  '首页': '/home', '平台介绍': '/introduction', '核心功能': '/features',
  '技术亮点': '/highlights', '应用场景': '/scenarios',
}


const diseaseItems = [
  { name: '健康叶片', img: healthyLeaf, confidence: 99, risk: '正常', advice: ['叶片状态良好', '保持当前环境参数', '继续周期性巡检'] },
  { name: '霜霉病', img: downyLeaf, confidence: 94, risk: '中风险', advice: ['及时移除重病叶', '降低棚内叶面湿度', '加强早晚通风'] },
  { name: '白粉病', img: powderyLeaf, confidence: 96, risk: '中风险', advice: ['减少叶面结露时间', '合理控制种植密度', '加强发病点巡检'] },
  { name: '灰霉病', img: grayLeaf, confidence: 92, risk: '高风险', advice: ['及时清除病叶', '加强通风降湿', '避免叶面长期潮湿'] },
]

const dataCards = [
  { icon: 'thermometer' as IconName, title: '环境数据', text: '温度、湿度、光照\nCO₂、土壤等' },
  { icon: 'image' as IconName, title: '图像数据', text: '作物叶片、果实\n生长状态图像' },
  { icon: 'clipboard' as IconName, title: '农事数据', text: '浇水、施肥、打药\n巡棚等记录' },
  { icon: 'cloud' as IconName, title: '气象数据', text: '温度、降雨、光照\n风速等外部信息' },
]

function SectionTitle({ no, title, tagline }: { no: string; title: string; tagline: string }) {
  return (
    <div className="section-title">
      <span className="section-leaf"><Icon name="leaf" size={27}/></span>
      <span className="section-no">{no}</span>
      <h2>{title}<b> · {tagline}</b></h2>
    </div>
  )
}

function HandNote({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`hand-note ${className}`}><span>{children}</span><i/></div>
}

export default function App() {
  const [selected, setSelected] = useState(3)
  const navigate = useNavigate()
  const disease = useMemo(() => diseaseItems[selected], [selected])

  useEffect(() => {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) entry.target.classList.add('in-view')
      })
    }, { threshold: 0.12 })
    document.querySelectorAll('.reveal').forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [])

  const openSearch = () => window.dispatchEvent(new CustomEvent('pengzhi:open-search'))

  return (
    <main className="pz-highlights-v2">
      <header className="topbar">
        <div className="nav-shell">
          <button className="brand" type="button" onClick={() => navigate('/home')} aria-label="棚智未来首页">
            <span className="brand-mark"><Icon name="leaf" size={36}/></span>
            <span className="brand-copy"><strong>棚智未来</strong><small>让农业更有未来</small></span>
          </button>
          <nav className="nav-links" aria-label="主导航">
            {navItems.map((item) => (
              <button key={item} className={item === '技术亮点' ? 'active' : ''} onClick={() => navigate(navRoutes[item])}>{item}</button>
            ))}
          </nav>
          <div className="nav-actions">
            <button className="icon-button" aria-label="搜索" onClick={openSearch}><Icon name="search" size={20}/></button>
            <button className="outline-btn" onClick={() => navigate('/platform?mode=guest')}><Icon name="user" size={17}/>游客模式</button>
            <button className="outline-btn compact" onClick={() => navigate('/login')}>登录</button>
            <button className="primary-btn compact" onClick={() => navigate('/register')}>注册</button>
          </div>
        </div>
      </header>

      <section id="top" className="hero" aria-labelledby="hero-title">
        <div className="hero-bg"/>
        <div className="hero-shell">
          <div className="hero-copy reveal">
            <p className="eyebrow">我们的技术 <span/></p>
            <h1 id="hero-title">让大棚<span>更聪明</span><br/>让管理<span>更简单</span></h1>
            <div className="hero-scribble"/>
            <p className="hero-description">棚智未来基于多源数据感知、智能算法分析和农业知识融合，构建面向设施农业的智能检测与管理技术体系，让数据真正转化为可执行的生产建议。</p>
            <div className="hero-highlights">
              {[
                ['database','数据更全面','多源融合感知'],
                ['brain','识别更准确','AI智能算法'],
                ['file','建议更科学','农业知识融合'],
                ['nodes','落地更友好','面向真实场景'],
              ].map(([icon,title,text]) => (
                <div className="hero-highlight" key={title}><Icon name={icon as IconName} size={27}/><strong>{title}</strong><small>{text}</small></div>
              ))}
            </div>
          </div>

          <div className="hero-visual reveal">
            <img className="sensor-station" src={sensorStation} alt="农业环境监测站" />
            <div className="glass-card source-card">
              <b>多源数据融合</b>
              <div className="source-grid">
                {dataCards.map((item) => <div key={item.title}><span><Icon name={item.icon} size={18}/></span><small>{item.title.replace('数据','')}<br/>数据</small></div>)}
              </div>
            </div>
            <div className="glass-card ai-card">
              <b>AI智能分析</b>
              <div className="ai-row"><img src={resultLeaf} alt="AI识别叶片"/><div><strong>健康</strong><small>置信度：95%</small><i><em/></i></div></div>
            </div>
            <div className="glass-card advice-card">
              <b><Icon name="spark" size={17}/>智能决策建议</b>
              <div><span className="chart-icon"><Icon name="chart" size={24}/></span><p><strong>建议：</strong><br/>当前温度偏高，建议加强通风，并适当控制灌溉频率。</p></div>
            </div>
            <HandNote className="hero-note">用技术<br/>让每一次作物成长更有把握</HandNote>
          </div>
        </div>
      </section>

      <div id="technology">
        <section className="tech-section data-section reveal">
          <div className="section-shell split-layout">
            <div>
              <SectionTitle no="01" title="多源数据融合技术" tagline="让监测更全面"/>
              <p className="section-desc">融合环境、图像、土壤、气象和农事等多源数据，构建统一的数据底座，实现温室环境与作物生长状态的全方位感知。</p>
              <div className="data-cards">
                {dataCards.map((item) => <article className="feature-card" key={item.title}><span className="feature-icon"><Icon name={item.icon} size={27}/></span><strong>{item.title}</strong><p>{item.text}</p></article>)}
              </div>
            </div>
            <div className="architecture-wrap">
              <img src={dataLayers} alt="智慧农业分层数据架构"/>
              <div className="architecture-labels"><p><b>应用层</b><span>智能决策与管理</span></p><p><b>模型层</b><span>算法分析与知识融合</span></p><p><b>数据层</b><span>多源数据采集与融合</span></p><p><b>感知层</b><span>设备采集与边缘处理</span></p></div>
              <HandNote className="side-note">把分散的数据<br/>变成有价值的信息</HandNote>
            </div>
          </div>
        </section>

        <section className="tech-section disease-section reveal">
          <div className="section-shell">
            <SectionTitle no="02" title="作物病害智能识别技术" tagline="让识别更准确"/>
            <p className="section-desc disease-desc">基于计算机视觉与深度学习算法，识别多种常见作物病害，提供可信度与防治建议，帮助种植户及早发现、及时处理。</p>
            <div className="disease-layout">
              <div className="disease-options">
                {diseaseItems.map((item, index) => <button className={selected === index ? 'disease-thumb active' : 'disease-thumb'} onClick={() => setSelected(index)} key={item.name}><img src={item.img} alt={item.name}/><span>{item.name}</span></button>)}
              </div>
              <article className="result-card">
                <h3>识别结果</h3>
                <div className="result-content"><img src={disease.img} alt={`${disease.name}识别结果`}/><div><div className="disease-name">{disease.name}<span className={disease.risk === '高风险' ? 'risk high' : 'risk'}>{disease.risk}</span></div><p>置信度：<b>{disease.confidence}%</b></p><strong>防治建议：</strong><ul>{disease.advice.map((a) => <li key={a}>{a}</li>)}</ul></div></div>
              </article>
              <HandNote className="disease-note">看得更清，<br/>才能防得更早</HandNote>
            </div>
          </div>
        </section>

        <section className="tech-section knowledge-section reveal">
          <div className="section-shell">
            <SectionTitle no="03" title="农业知识图谱与决策技术" tagline="让建议更科学"/>
            <p className="section-desc">构建作物生长规律与农业知识图谱，结合实时数据与历史经验，生成可执行的管理建议，辅助种植人员科学决策。</p>
            <div className="knowledge-layout">
              <div className="knowledge-graph">
                <div className="kg-line l1"/><div className="kg-line l2"/><div className="kg-line l3"/><div className="kg-line l4"/><div className="kg-line l5"/><div className="kg-line l6"/>
                <div className="kg-center">农业<br/>知识图谱</div>
                {[
                  ['kg-a','nodes','作物生长规律'],['kg-b','book','专家种植经验'],['kg-c','brain','病害机理知识'],
                  ['kg-d','clipboard','农事管理规范'],['kg-e','spark','环境调控经验'],['kg-f','cloud','气象影响模型'],
                ].map(([cls,icon,text]) => <div className={`kg-node ${cls}`} key={text}><Icon name={icon as IconName} size={17}/><span>{text}</span></div>)}
              </div>
              <span className="knowledge-arrow"><Icon name="arrow" size={34}/></span>
              <article className="decision-panel"><h3><Icon name="file" size={21}/>智能决策建议</h3><div><span className="decision-icon green"><Icon name="leaf" size={18}/></span><p><b>当前棚内温度偏高</b><small>建议加强通风，适当延长通风时间</small></p></div><div><span className="decision-icon blue"><Icon name="cloud" size={18}/></span><p><b>未来24小时有降雨</b><small>建议延用棚室补水设施</small></p></div><div><span className="decision-icon orange"><Icon name="sun" size={18}/></span><p><b>土壤湿度偏低</b><small>建议今日傍晚适量灌溉</small></p></div></article>
              <div className="knowledge-photo"><img src={greenhouseInside} alt="智慧温室作物场景"/></div>
              <HandNote className="knowledge-note">不仅告诉你“发生了什么”<br/>更告诉你应该怎么做</HandNote>
            </div>
          </div>
        </section>

        <section className="tech-section edge-section reveal">
          <div className="section-shell edge-shell">
            <div className="edge-copy">
              <SectionTitle no="04" title="轻量化部署与边缘计算" tagline="让应用更友好"/>
              <p className="section-desc">支持多种部署方式，适配不同规模的温室场景。边缘计算保障数据实时处理，即使在网络不稳定的环境下也能正常运行。</p>
              <div className="edge-cards">
                {[
                  ['shield','边缘计算','本地实时处理\n响应更快'],['nodes','多场景适配','单棚 / 连栋棚\n灵活部署'],['sun','低功耗设备','太阳能供电\n稳定运行'],['link','快速接入','即插即用\n易于维护'],
                ].map(([icon,title,text]) => <article className="mini-card" key={title}><Icon name={icon as IconName} size={26}/><strong>{title}</strong><p>{text}</p></article>)}
              </div>
            </div>
            <div className="edge-image"><img src={greenhouseSensor} alt="温室边缘计算与监测设备"/><div className="edge-checks">{['稳定可靠','低成本部署','适应复杂环境','支持后续扩展'].map((text) => <p key={text}><Icon name="check" size={17}/>{text}</p>)}</div></div>
          </div>
        </section>

        <section className="tech-section evolution-section reveal">
          <div className="section-shell">
            <SectionTitle no="05" title="持续迭代的算法体系" tagline="让平台不断进化"/>
            <p className="section-desc">基于真实生产数据持续优化算法模型，不断提升识别精度和决策效果，让平台在实际应用中越用越好。</p>
            <div className="evolution-layout">
              <div className="step-flow">
                <svg className="flow-line" viewBox="0 0 700 90" preserveAspectRatio="none"><path d="M15 47 C110 25, 150 65, 240 46 S380 26, 470 46 S600 64, 682 46"/></svg>
                {[
                  ['database','数据积累','真实场景数据'],['book','模型训练','持续迭代优化'],['spark','效果验证','多场景测试'],['shield','版本更新','功能不断完善'],
                ].map(([icon,title,text], i) => <div className={`flow-step s${i+1}`} key={title}><span><Icon name={icon as IconName} size={22}/></span><strong>{title}</strong><small>{text}</small></div>)}
                <span className="flow-arrow"><Icon name="arrow" size={28}/></span>
              </div>
              <div className="growth-card"><div className="growth-label">随着数据积累<br/>识别准确率持续提升</div><b>92%</b><svg viewBox="0 0 340 170" className="growth-svg"><path className="trend-line" d="M20 135 C80 130 110 115 150 105 S230 78 315 28"/><path className="trend-arrow" d="m304 31 12-4-4 12"/><g className="bars">{[45,62,78,104,132,158].map((h,i) => <rect key={i} x={32+i*49} y={166-h} width="22" height={h} rx="6"/>)}</g></svg><div className="months">{['1月','2月','3月','4月','5月','6月'].map((m)=><span key={m}>{m}</span>)}</div></div>
            </div>
          </div>
        </section>
      </div>

      <footer className="bottom-banner">
        <img src={greenhouseValley} alt="山谷智慧温室群"/>
        <div className="banner-overlay"/>
        <div className="banner-copy"><strong>以技术赋能农业</strong><span>让每一座大棚都有更大的可能</span><i/></div>
        <HandNote className="banner-note">科技，让农业更美好</HandNote>
      </footer>
    </main>
  )
}
