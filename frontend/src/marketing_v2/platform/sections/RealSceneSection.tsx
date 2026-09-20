import SectionTitle from '../components/SectionTitle'
import greenhouse from '../assets/images/greenhouse-wide.png'
import sensor from '../assets/images/sensor-transparent.png'
import devices from '../assets/images/hero-devices.png'
import team from '../assets/images/team-greenhouse.png'

const cards = [
  { image: greenhouse, title: '真实种植场景', desc: '在真实大棚中测试与优化', cls: 'real-card__img--cover', visualCls: '' },
  { image: sensor, title: '部署采集设备', desc: '稳定采集环境数据', cls: 'real-card__img--contain', visualCls: 'real-card__visual--transparent' },
  { image: devices, title: '平台实际界面', desc: '数据清晰，操作简单', cls: 'real-card__img--contain real-card__img--device', visualCls: 'real-card__visual--transparent' },
  { image: team, title: '团队实地调试', desc: '持续迭代，不断改进', cls: 'real-card__img--cover', visualCls: '' },
]

export default function RealSceneSection() {
  return (
    <section className="real-section page-section">
      <div className="page-section__inner">
        <SectionTitle title="走进真实的大棚" subtitle={'从实际种植场景出发，按照真实管理流程设计，持续迭代。\n不做只停留在演示里的系统。'} />
        <div className="real-grid">
          {cards.map((card) => <article className="real-card" key={card.title}><div className={`real-card__visual ${card.visualCls}`}><img className={card.cls} src={card.image} alt="" /></div><strong>{card.title}</strong><p>{card.desc}</p></article>)}
        </div>
      </div>
    </section>
  )
}
