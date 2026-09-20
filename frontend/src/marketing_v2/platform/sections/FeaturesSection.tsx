import SectionTitle from '../components/SectionTitle'
import { Icon } from '../components/Icons'

const features = [
  { no: '01', icon: 'layers' as const, title: '数据不用到处找', desc: '棚里的环境信息集中在一个地方。' },
  { no: '02', icon: 'bell' as const, title: '异常不用一直盯', desc: '重要变化及时提醒，不用24小时守着。' },
  { no: '03', icon: 'sprout' as const, title: '有问题不用只靠猜', desc: '拍一张作物照片，系统帮助分析。' },
  { no: '04', icon: 'document' as const, title: '做过什么不会忘', desc: '农事操作持续记录，方便之后复盘。' },
]

export default function FeaturesSection() {
  return (
    <section className="features-section page-section">
      <div className="page-section__inner">
        <SectionTitle title="我们的特色" subtitle="我们更在意，它到底好不好用。" />
        <div className="feature-grid">
          {features.map((f) => <article className="feature-item" key={f.no}><div className="feature-item__icon"><Icon name={f.icon} /></div><div className="feature-item__no">{f.no}</div><strong>{f.title}</strong><p>{f.desc}</p></article>)}
        </div>
      </div>
    </section>
  )
}
