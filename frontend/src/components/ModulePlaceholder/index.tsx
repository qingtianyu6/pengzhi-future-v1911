import { ArrowRightOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { Card, Tag } from 'antd'

interface ModulePlaceholderProps {
  eyebrow: string
  title: string
  description: string
  day: string
  capabilities: string[]
}

export function ModulePlaceholder({
  eyebrow,
  title,
  description,
  day,
  capabilities,
}: ModulePlaceholderProps) {
  return (
    <div className="module-page">
      <section className="page-intro">
        <div>
          <span className="eyebrow">{eyebrow}</span>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        <Tag className="roadmap-tag">计划于{day}接入业务数据</Tag>
      </section>

      <Card className="module-placeholder" bordered={false}>
        <div className="placeholder-mark">{title.slice(0, 1)}</div>
        <div>
          <h2>模块骨架已就绪</h2>
          <p>当前为第一天工程版本。页面路由、布局和数据承载区域已经建立，暂不展示虚构业务结果。</p>
          <div className="capability-list">
            {capabilities.map((capability) => (
              <span key={capability}>
                <CheckCircleOutlined /> {capability}
              </span>
            ))}
          </div>
          <div className="next-step">
            下一步 <ArrowRightOutlined /> 接入真实后端接口与业务状态
          </div>
        </div>
      </Card>
    </div>
  )
}
