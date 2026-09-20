import type { ReactNode } from 'react'
import { Button, Result, Skeleton } from 'antd'
import { CloudSyncOutlined, LockOutlined, ReloadOutlined } from '@ant-design/icons'

export function ProductSkeleton({ rows = 3 }: { rows?: number }) {
  return <div className="product-state product-skeleton" aria-label="正在加载">
    <div className="product-skeleton-head"><Skeleton.Avatar active size={40} shape="square" /><Skeleton active title paragraph={{ rows: 1 }} /></div>
    <Skeleton active paragraph={{ rows }} />
  </div>
}

export function ProductErrorState({ title = '数据暂时不可用', description, onRetry }: { title?: string; description?: ReactNode; onRetry?: () => void }) {
  return <Result className="product-state product-result" status="warning" title={title} subTitle={description} extra={onRetry ? <Button type="primary" icon={<ReloadOutlined />} onClick={onRetry}>重新加载</Button> : undefined} />
}

export function ProductPermissionState({ description = '当前账号暂无访问权限，请联系管理员。' }: { description?: ReactNode }) {
  return <Result className="product-state product-result" icon={<LockOutlined />} title="暂无访问权限" subTitle={description} />
}

export function ProductSyncMeta({ updatedAt, syncing = false }: { updatedAt?: string | null; syncing?: boolean }) {
  return <span className="product-sync-meta"><CloudSyncOutlined spin={syncing} />{syncing ? '正在同步' : updatedAt ? `更新于 ${updatedAt}` : '等待数据同步'}</span>
}
