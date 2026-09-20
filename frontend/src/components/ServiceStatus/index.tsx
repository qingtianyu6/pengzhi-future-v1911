import { Badge, Button, Tooltip } from 'antd'
import { useSystemStore } from '../../store/system'

const statusConfig = {
  checking: { status: 'processing' as const, text: '正在检查服务' },
  online: { status: 'success' as const, text: '系统正常' },
  offline: { status: 'error' as const, text: '后端服务未连接' },
}

export function ServiceStatus() {
  const { status, version, checkHealth } = useSystemStore()
  const config = statusConfig[status]

  return (
    <Tooltip title={version ? `后端版本 v${version}` : '单击重新检查连接'}>
      <Button className="service-status" type="text" onClick={() => void checkHealth()}>
        <Badge status={config.status} text={config.text} />
      </Button>
    </Tooltip>
  )
}
