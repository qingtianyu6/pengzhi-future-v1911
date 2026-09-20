import SectionHeader from '../components/SectionHeader'
import HandNote from '../components/HandNote'
import { RecordGlyph } from '../components/Icons'

const cards = [
  ['water', '浇水记录'], ['fertilize', '施肥记录'], ['spray', '打药记录'], ['patrol', '巡棚记录'], ['custom', '自定义事项']
]
const records = [
  ['2025-06-12 09:30', '浇水', '1号棚', '张三'],
  ['2025-06-11 15:20', '施肥', '2号棚', '李四'],
  ['2025-06-10 10:00', '巡棚', '1号棚', '王五'],
  ['2025-06-08 14:10', '打药', '3号棚', '张三'],
]

export default function FarmSection() {
  return (
    <section id="farm" className="feature-section">
      <SectionHeader number="03" title="农事管理" subtitle="记录日常，规范生产" />
      <p className="section-desc">支持种植过程中的浇水、施肥、打药、巡棚等农事操作记录，<br/>形成完整的生产档案，方便后续查看和复盘。</p>
      <HandNote className="section-note note-three">让每一次付出都有痕迹</HandNote>
      <div className="farm-grid">
        <div className="record-cards">
          {cards.map(([kind, name]) => (
            <button key={name} className="record-card"><span><RecordGlyph kind={kind}/></span><b>{name}</b></button>
          ))}
        </div>
        <div className="farm-table-card">
          <div className="farm-table-card__head"><span className="calendar-dot">✿</span><b>农事记录</b></div>
          <div className="farm-table">
            {records.map((r, i) => (
              <div className="farm-row" key={r[0]}><span className="tiny-doc">▣</span><span>{r[0]}</span><span>{r[1]}</span><span>{r[2]}</span><span>{r[3]}</span><i className={`mini-field mini-field-${i+1}`} /></div>
            ))}
          </div>
          <button className="add-record">＋ 新增记录</button>
        </div>
      </div>
    </section>
  )
}
