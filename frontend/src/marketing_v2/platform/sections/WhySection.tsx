import SectionTitle from '../components/SectionTitle'
import sensor from '../assets/images/sensor-transparent.png'
import phone from '../assets/images/phone-greenhouse.png'
import disease from '../assets/images/disease-leaf.png'
import notebook from '../assets/images/farm-notebook.png'
import greenhouse from '../assets/images/greenhouse-wide.png'

const cards = [
  { image: sensor, title: '传感器数据很多', desc: '温度、湿度、光照……但分散在不同设备' },
  { image: phone, title: '手机里信息零散', desc: '不同软件、不同平台，不方便统一查看' },
  { image: disease, title: '病害发现靠经验', desc: '发现问题时，往往不确定是什么病害' },
  { image: notebook, title: '农事记录容易忘', desc: '浇水、施肥、打药……靠纸笔很难追溯' },
  { image: greenhouse, title: '很难形成完整依据', desc: '缺少长期数据支持，不利于科学决策' },
]

export default function WhySection() {
  return (
    <section className="why-section page-section">
      <div className="page-section__inner">
        <SectionTitle title="为什么要做\n棚智未来？" subtitle="大棚管理，很多时候不是不会种，而是信息太散。" note={<>种得好，<br />也需要被看见和记录。</>} />
        <div className="problem-chain">
          {cards.map((card, index) => (
            <article className="problem-card" key={card.title}>
              <div className={`problem-card__image problem-card__image--${index + 1}`}><img src={card.image} alt="" /></div>
              <strong>{card.title}</strong>
              <p>{card.desc}</p>
              {index < cards.length - 1 && <span className="problem-arrow">›</span>}
            </article>
          ))}
        </div>
        <blockquote>“我们希望做的，就是把这些分散的信息，变成一个真正能辅助种植的工作台。”</blockquote>
      </div>
    </section>
  )
}
