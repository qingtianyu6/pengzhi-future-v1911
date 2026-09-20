import { Button, Result } from 'antd'
import { useNavigate } from 'react-router-dom'

export default function NotFoundPage() {
  const navigate = useNavigate()
  return <Result status="404" title="页面不存在" subTitle="请检查访问地址或返回种植总览。" extra={<Button type="primary" onClick={() => navigate('/')}>返回种植总览</Button>} />
}
