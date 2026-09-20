import { LeafIcon } from './Icons'

export default function SectionHeader({ number, title, subtitle }: { number: string, title: string, subtitle: string }) {
  return (
    <div className="section-heading">
      <div className="section-heading__title">
        <LeafIcon />
        <span className="section-number">{number}</span>
        <h2>{title}</h2>
        <span className="title-dot">·</span>
        <h3>{subtitle}</h3>
      </div>
    </div>
  )
}
