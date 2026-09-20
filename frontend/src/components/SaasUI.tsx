import type { ReactNode } from 'react'
import { ArrowRightOutlined, InboxOutlined } from '@ant-design/icons'
import { Button } from 'antd'

export function SaasEmptyState({
  icon,
  title,
  description,
  actionLabel,
  onAction,
  secondaryLabel,
  onSecondary,
}: {
  icon?: ReactNode
  title: string
  description: string
  actionLabel?: string
  onAction?: () => void
  secondaryLabel?: string
  onSecondary?: () => void
}) {
  return <div className="saas-empty-state">
    <div className="saas-empty-icon">{icon ?? <InboxOutlined />}</div>
    <strong>{title}</strong>
    <p>{description}</p>
    {(actionLabel || secondaryLabel) && <div className="saas-empty-actions">
      {actionLabel && <Button type="primary" onClick={onAction}>{actionLabel}</Button>}
      {secondaryLabel && <Button type="link" onClick={onSecondary}>{secondaryLabel}<ArrowRightOutlined /></Button>}
    </div>}
  </div>
}

export function MetricTile({
  label,
  value,
  unit,
  meta,
  tone = 'green',
  icon,
}: {
  label: string
  value: ReactNode
  unit?: string
  meta?: ReactNode
  tone?: 'green' | 'blue' | 'orange' | 'yellow' | 'purple' | 'teal'
  icon?: ReactNode
}) {
  return <div className={`saas-metric-tile saas-tone-${tone}`}>
    <div className="saas-metric-head"><span>{label}</span>{icon && <i>{icon}</i>}</div>
    <div className="saas-metric-value">{value}{unit && <small>{unit}</small>}</div>
    {meta && <div className="saas-metric-meta">{meta}</div>}
    <svg className="saas-metric-spark" viewBox="0 0 120 24" aria-hidden="true">
      <path d="M2 18 C18 15 22 19 38 13 S58 17 70 10 S90 12 118 4" />
    </svg>
  </div>
}

export function InsightPanel({
  eyebrow,
  title,
  children,
  action,
  className = '',
}: {
  eyebrow?: ReactNode
  title: ReactNode
  children: ReactNode
  action?: ReactNode
  className?: string
}) {
  return <section className={`saas-insight-panel ${className}`}>
    <div className="saas-insight-head">
      <div>{eyebrow && <span>{eyebrow}</span>}<h3>{title}</h3></div>
      {action}
    </div>
    <div className="saas-insight-body">{children}</div>
  </section>
}

export function SectionHeading({
  title,
  description,
  action,
}: {
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
}) {
  return <div className="saas-section-heading">
    <div><h2>{title}</h2>{description && <p>{description}</p>}</div>
    {action}
  </div>
}
