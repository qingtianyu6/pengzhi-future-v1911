import { Button, Result } from 'antd'
import { useNavigate } from 'react-router-dom'
export default function RouteError() {
  const navigate = useNavigate()
  return <Result status="warning" title="页面暂时无法显示" subTitle="请重新加载；如果仍有问题，可返回工作台继续使用其他模块。" extra={<><Button type="primary" onClick={() => window.location.reload()}>重新加载</Button><Button onClick={() => navigate('/platform')}>返回工作台</Button><Button onClick={() => navigate('/home')}>返回首页</Button></>} />
}
