import hero from '../assets/images/hero-dashboard.png'
import monitor from '../assets/icons/monitor.png'
import recognition from '../assets/icons/recognition.png'
import farm from '../assets/icons/farm.png'
import decision from '../assets/icons/decision.png'
import data from '../assets/icons/data.png'
import HandNote from '../components/HandNote'

const features = [
  [monitor, '实时监测', '看得见'],
  [recognition, '智能识别', '防得早'],
  [farm, '农事管理', '管得更细'],
  [decision, '智能决策', '做得更准'],
  [data, '数据沉淀', '用得更久'],
]

export default function HeroSection() {
  return (
    <section id="hero" className="hero-section">
      <img src={hero} className="hero-section__photo" alt="智慧温室监测场景" />
      <div className="hero-section__veil" />
      <div className="leaf-blur leaf-blur--left" />
      <div className="leaf-blur leaf-blur--right" />
      <div className="hero-section__content">
        <div className="hero-copy">
          <h1><span>五大核心功能</span><span>让大棚管理<span className="accent">更简单</span></span></h1>
          <p>从环境监测到智能决策，覆盖种植管理全流程<br/>用数据和智能，让每一项农事都有依据。</p>
          <div className="hero-features">
            {features.map(([icon, label, desc]) => (
              <div className="hero-feature" key={label}>
                <img src={icon} alt="" />
                <strong>{label}</strong>
                <span>{desc}</span>
              </div>
            ))}
          </div>
        </div>
        <HandNote className="hero-note">把复杂的管理<br/>变成简单的日常</HandNote>
      </div>
    </section>
  )
}
