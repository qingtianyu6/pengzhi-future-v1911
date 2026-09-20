import { useEffect, useState } from 'react'
import {
  ApiOutlined,
  ExperimentOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { Alert, Card, Col, Drawer, Empty, Progress, Row, Skeleton, Space, Statistic, Tag } from 'antd'
import { getApiErrorMessage } from '../../api/client'
import { getModelOverview } from '../../api/modelApi'
import type { ModelOverview } from '../../types/model'

interface ModelCenterProps {
  open: boolean
  onClose: () => void
}

function percent(value: number | null): string {
  return value === null ? '—' : `${(value * 100).toFixed(1)}%`
}

function metric(value: number | null, digits = 2): string {
  return value === null ? '—' : value.toFixed(digits)
}

export function ModelCenter({ open, onClose }: ModelCenterProps) {
  const [data, setData] = useState<ModelOverview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    setError(null)
    void getModelOverview()
      .then(setData)
      .catch((requestError) => setError(getApiErrorMessage(requestError)))
      .finally(() => setLoading(false))
  }, [open])

  return <Drawer
    className="model-center-drawer"
    title="AI 模型中心"
    width="min(1040px, 96vw)"
    open={open}
    onClose={onClose}
    destroyOnHidden
  >
    {loading && !data ? <Skeleton active paragraph={{ rows: 10 }} /> : error ? <Alert type="error" showIcon message="模型信息读取失败" description={error} /> : data ? <div className="model-center-grid">
      <Card className="model-overview-card env-model-card" bordered={false}>
        <div className="model-card-head">
          <div className="model-icon"><ThunderboltOutlined /></div>
          <div>
            <span>环境预测引擎</span>
            <h3>{data.environment.name}</h3>
          </div>
          <Tag color="green">服务正常</Tag>
        </div>
        <p className="model-description">根据最近环境时序数据输出未来 1～{data.environment.prediction_window_hours} 小时温湿度趋势，并按验证结果选择不同预测方法。</p>
        <Space size={[6, 6]} wrap className="model-chip-list">
          {data.environment.algorithms.map((item) => <Tag key={item}>{item}</Tag>)}
        </Space>
        <Row gutter={[12, 12]} className="model-metric-grid">
          <Col xs={24} sm={12}>
            <div className="model-metric-box">
              <span>1h 温度 MAE</span>
              <strong>{metric(data.environment.temperature_h1.mae)} ℃</strong>
              <small>相对周期基线改善 {metric(data.environment.temperature_h1.improvement_pct, 1)}%</small>
            </div>
          </Col>
          <Col xs={24} sm={12}>
            <div className="model-metric-box">
              <span>1h 湿度 MAE</span>
              <strong>{metric(data.environment.humidity_h1.mae)} %RH</strong>
              <small>相对周期基线改善 {metric(data.environment.humidity_h1.improvement_pct, 1)}%</small>
            </div>
          </Col>
        </Row>
        <div className="model-footnote"><ApiOutlined /> 当前服务版本 {data.environment.version}</div>
      </Card>

      <Card className="model-overview-card disease-model-card" bordered={false}>
        <div className="model-card-head">
          <div className="model-icon"><ExperimentOutlined /></div>
          <div>
            <span>病害辅助识别</span>
            <h3>{data.disease.architecture}</h3>
          </div>
          <Tag color="gold">辅助识别模式</Tag>
        </div>
        <p className="model-description">对番茄叶片图片输出 Top-3 候选结果；低置信结果进入人工复核，不直接生成生产处置结论。</p>
        <Row gutter={[12, 12]} className="model-metric-grid">
          <Col xs={12}><Statistic title="识别类别" value={data.disease.class_count} suffix="类" /></Col>
          <Col xs={12}><Statistic title="置信阈值" value={data.disease.confidence_threshold ?? 0} precision={2} /></Col>
          <Col xs={12}><Statistic title="内部 Accuracy" value={data.disease.internal_accuracy ? data.disease.internal_accuracy * 100 : 0} suffix="%" precision={1} /></Col>
          <Col xs={12}><Statistic title="内部 Macro-F1" value={data.disease.internal_macro_f1 ? data.disease.internal_macro_f1 * 100 : 0} suffix="%" precision={1} /></Col>
        </Row>
        <div className="confidence-gate">
          <div><SafetyCertificateOutlined /><span>高置信结果准确率</span><strong>{percent(data.disease.accepted_accuracy)}</strong></div>
          <Progress percent={data.disease.accepted_accuracy ? Math.round(data.disease.accepted_accuracy * 100) : 0} showInfo={false} strokeColor="#168464" />
          <small>外部数据表现仍作为模型迭代依据，因此当前保持辅助识别和人工复核机制。</small>
        </div>
        <div className="model-footnote"><ApiOutlined /> 当前服务版本 {data.disease.version}</div>
      </Card>
    </div> : <Empty description="暂无模型信息" />}
  </Drawer>
}
