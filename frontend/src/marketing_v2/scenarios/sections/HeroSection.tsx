import Icon from '../components/Icon'
import hero from '../assets/images/scene-hero.png'

const points = [
  ['多场景适配', '覆盖多种作物', 'pin'],
  ['灵活部署', '适应不同规模', 'settings'],
  ['数据驱动', '提升生产效益', 'trend'],
  ['助力可持续', '推动绿色农业', 'users'],
]

const metrics = [
  { label: '棚内温度', value: '24.6℃', unit: '', icon: 'activity', type: 'line' },
  { label: '空气湿度', value: '62%', unit: '', icon: 'activity', type: 'line' },
  { label: '光照强度', value: '685', unit: 'μmol/m²·s', icon: 'trend', type: 'bars' },
  { label: 'CO₂浓度', value: '420', unit: 'ppm', icon: 'database', type: 'line' },
]

export default function HeroSection() {
  return (
    <section className="scene-hero">
      <img className="scene-hero__bg" src={hero} alt="现代设施农业温室场景" />
      <div className="scene-hero__wash" />
      <div className="scene-hero__inner">
        <div className="scene-hero__copy">
          <div className="eyebrow">应用场景 <span /></div>
          <h1>
            <span className="hero-title-line">从不同种植场景出发</span>
            <span className="hero-title-line hero-title-line--second">
              让更多大棚用上<span className="hero-title-accent">智能管理</span>
            </span>
          </h1>
          <div className="hero-title-underline" />
          <p>
            棚智未来面向多种设施农业种植场景，提供可落地、可扩展的智能管理方案，帮助不同地区、不同作物、不同规模的种植主体提升管理效率、降低生产风险，实现稳定增收。
          </p>
          <div className="hero-points">
            {points.map(([a, b, icon]) => (
              <div className="hero-point" key={a}>
                <Icon name={icon} />
                <strong>{a}</strong>
                <small>{b}</small>
              </div>
            ))}
          </div>
        </div>

        <div className="hero-handnote">
          不止一种大棚<br />都有更好的种植方式<i />
        </div>

        <div className="sensor-strip">
          {metrics.map((m) => (
            <div className="metric-card" key={m.label}>
              <div className="metric-card__head">
                <Icon name={m.icon} className="metric-card__icon" />
                <b>{m.label}</b>
              </div>
              <div className="metric-card__value">
                <strong>{m.value}</strong>
                {m.unit ? <em>{m.unit}</em> : null}
              </div>
              <div className="metric-card__chart" aria-hidden="true">
                {m.type === 'bars' ? (
                  <span className="metric-bars"><i /><i /><i /><i /><i /><i /><i /><i /></span>
                ) : (
                  <svg viewBox="0 0 100 28" preserveAspectRatio="none">
                    <path d="M0,24 C8,22 12,18 18,20 C24,22 28,12 34,14 C40,16 44,9 50,12 C56,14 60,6 66,10 C72,14 78,8 84,10 C90,12 94,6 100,4" />
                  </svg>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
