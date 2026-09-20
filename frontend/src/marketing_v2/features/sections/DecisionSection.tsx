import SectionHeader from '../components/SectionHeader'
import greenhouse from '../assets/images/greenhouse-wide.png'
import HandNote from '../components/HandNote'

const advice = [
  ['green', '当前棚内湿度偏高', '建议加强通风'],
  ['blue', '未来24小时有降雨', '建议提前做好排水准备'],
  ['orange', '土壤湿度偏低', '建议今日傍晚适量灌溉'],
  ['red', '近期灰霉病风险上升', '建议加强巡查'],
]

export default function DecisionSection() {
  return (
    <section id="decision" className="feature-section">
      <SectionHeader number="04" title="智能决策" subtitle="数据分析，辅助管理" />
      <p className="section-desc">基于历史数据和实时监测结果，结合作物生长规律，提供通俗易懂的管理建议，<br/>帮助种植户科学决策，降低经验依赖。</p>
      <div className="decision-grid">
        <div className="advice-panel">
          <div className="advice-title">▣&nbsp; 智能建议</div>
          <div className="advice-items">
            {advice.map(([tone, title, desc]) => <div className="advice-item" key={title}><i className={`status-dot ${tone}`}/><div><b>{title}</b><span>{desc}</span></div></div>)}
          </div>
        </div>
        <div className="decision-photo">
          <img src={greenhouse} alt="智慧温室"/>
          <HandNote className="decision-note">基于数据的建议<br/>让种植更有把握</HandNote>
        </div>
      </div>
    </section>
  )
}
