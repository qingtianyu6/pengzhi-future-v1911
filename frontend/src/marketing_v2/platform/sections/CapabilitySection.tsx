import SectionTitle from '../components/SectionTitle'
import bg from '../assets/images/capability-greenhouse.png'
import { Icon } from '../components/Icons'

const cards = [
  { cls: 'cap-card--env', icon: 'sensor' as const, title: '环境监测', desc: '温度、湿度、光照等变化随时掌握' },
  { cls: 'cap-card--disease', icon: 'bug' as const, title: '病害识别', desc: '拍照上传，快速辅助判断常见病害' },
  { cls: 'cap-card--farm', icon: 'farm' as const, title: '农事管理', desc: '浇水、施肥、巡棚等操作轻松记录' },
  { cls: 'cap-card--assistant', icon: 'assistant' as const, title: '智能助手', desc: '结合当前情况给出简单易懂的管理建议' },
]

export default function CapabilitySection() {
  return (
    <section className="capability-section page-section">
      <div className="page-section__inner page-section__inner--wide">
        <SectionTitle title="平台能做什么？" subtitle="从环境感知到智能决策，覆盖大棚管理的全过程。" note={<>一个平台，<br />让种植更简单。</>} />
      </div>
      <div className="capability-stage">
        <img src={bg} alt="温室智能管理场景" />
        <div className="capability-stage__shade" />
        <div className="capability-stage__inner">
          {cards.map((card) => <div className={`cap-card ${card.cls}`} key={card.title}><span><Icon name={card.icon} /></span><div><strong>{card.title}</strong><p>{card.desc}</p></div></div>)}
        </div>
      </div>
    </section>
  )
}
