import SectionTitle from '../components/SectionTitle'
import { Icon } from '../components/Icons'

const flow = [
  { icon: 'leaf' as const, title: '感知', desc: '多源数据实时采集' },
  { icon: 'chart' as const, title: '分析', desc: '数据融合与智能分析' },
  { icon: 'alert' as const, title: '提醒', desc: '异常情况及时预警' },
  { icon: 'decision' as const, title: '决策', desc: '给出种植管理建议' },
  { icon: 'plane' as const, title: '执行', desc: '农事操作落地' },
  { icon: 'database' as const, title: '记录', desc: '形成可追溯数据' },
]

export default function FlowSection() {
  return (
    <section className="flow-section page-section">
      <div className="page-section__inner">
        <SectionTitle title="从数据到行动" subtitle="让每一条数据，都真正服务于农业生产。" note={<>数据连接空间，<br />让经验成为可复制的生产力。</>} />
        <div className="flow-track">
          <svg viewBox="0 0 1200 120" preserveAspectRatio="none" aria-hidden="true"><path d="M65,65 C145,8 205,112 285,62 S435,20 520,64 S680,104 770,60 S930,20 1015,62 S1110,96 1160,55" /></svg>
          <div className="flow-nodes">
            {flow.map((f) => <div className="flow-node" key={f.title}><span><Icon name={f.icon} /></span><strong>{f.title}</strong><small>{f.desc}</small></div>)}
          </div>
        </div>
      </div>
    </section>
  )
}
