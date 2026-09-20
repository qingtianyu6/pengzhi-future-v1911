import type { ReactNode } from 'react'
import { Icon } from './Icons'

type Props = {
  title: string
  subtitle?: string
  note?: ReactNode
  className?: string
}

export default function SectionTitle({ title, subtitle, note, className = '' }: Props) {
  return (
    <div className={`section-title ${className}`}>
      <div className="section-title__copy">
        <div className="section-title__heading"><span className="section-leaf"><Icon name="leaf" /></span><h2>{title}</h2></div>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {note && <div className="section-title__note">{note}<i /></div>}
    </div>
  )
}
