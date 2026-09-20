import SectionHeader from '../components/SectionHeader'

const items = [
  ['↻', '历史数据查询', '随时回溯'],
  ['▤', '农业档案管理', '分类存储'],
  ['▥', '数据可视化', '图表展示'],
  ['▣', '支持导出', '便于使用'],
]

export default function ArchiveSection() {
  return (
    <section id="archive" className="feature-section feature-section--archive">
      <SectionHeader number="05" title="数据沉淀" subtitle="持续积累，助力成长" />
      <p className="section-desc">所有监测数据、识别结果和农事记录都会自动保存，形成可追溯的种植档案，<br/>为后续分析、优化管理和规模化应用提供数据支持。</p>
      <div className="archive-cards">
        {items.map(([icon, title, desc]) => <div className="archive-card" key={title}><span>{icon}</span><div><b>{title}</b><small>{desc}</small></div></div>)}
      </div>
    </section>
  )
}
