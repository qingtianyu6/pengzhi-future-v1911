import { Link } from 'react-router-dom'
import { Badge } from 'antd'
import type { WorkspaceGroup, WorkspaceItem } from './workspaceNavigation'
import { workspaceHref } from './workspaceNavigation'

export function WorkspaceSectionNav({ group, current, search, newsUnread }: {
  group: WorkspaceGroup; current?: WorkspaceItem; search: string; newsUnread: number
}) {
  if (group.items.length < 2 || group.id==='knowledge') return null
  return <section className="pz-section-nav pz-section-nav-compact" aria-label={`${group.label}工作区`}>
    <nav className="pz-section-links" aria-label={`${group.label}子功能`}>
      {group.items.map(item => <Link key={item.key} to={workspaceHref(item.key, search)} aria-label={item.label} aria-current={item.key === current?.key ? 'page' : undefined}>
        {item.icon}<span>{item.label}</span>{item.key === '/platform/news' && newsUnread > 0 && <Badge count={newsUnread} size="small" />}
      </Link>)}
    </nav>
  </section>
}
