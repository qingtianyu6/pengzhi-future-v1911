import { useEffect, useState } from 'react'
import {
  ApiOutlined,
  ArrowRightOutlined,
  CheckCircleFilled,
  CloudServerOutlined,
  CloudUploadOutlined,
  CopyOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  HomeOutlined,
  NodeIndexOutlined,
} from '@ant-design/icons'
import { Button, message } from 'antd'
import { EnvironmentDataImport } from '../components/EnvironmentDataImport'
import GreenhouseManagementPage from './Greenhouses/GreenhouseManagementPage'
import { getSensorIngestStatus } from '../api/sensorApi'
import type { SensorIngestStatus } from '../types/sensor'
import './PlatformV17.css'

export default function DataCenterPage() {
  const [importOpen, setImportOpen] = useState(false)
  const [status, setStatus] = useState<SensorIngestStatus | null>(null)
  const [messageApi, contextHolder] = message.useMessage()

  useEffect(() => {
    void getSensorIngestStatus().then(setStatus).catch(() => setStatus(null))
  }, [])

  const copy = async (value: string) => {
    await navigator.clipboard.writeText(value)
    messageApi.success('已复制')
  }

  const endpoint = status?.endpoint ?? '/api/v1/ingest/sensor-data'
  const authLabel = status?.auth_required ? 'Token' : '可配置 Token'
  const batchSize = status?.max_batch_size ?? 1000

  return <div className="business-page v17-page v17-data-page">
    {contextHolder}

    <section className="v17-hero-line v17-data-hero">
      <div>
        <span className="v17-kicker">大棚管理</span>
        <h1>连接你的大棚</h1>
        <p>用两条清晰的路径把历史数据和实时设备接入同一个农业工作台，让数据驱动更好的种植决策。</p>
      </div>
      <div className="v17-hero-script">让每一座大棚<br />都有数据的力量</div>
    </section>

    <section className="v17-connect-grid">
      <article className="v17-connect-card v17-file-card">
        <div className="v17-connect-title-row">
          <span className="v17-connect-icon"><FileTextOutlined /></span>
          <div><h2>文件导入</h2><p>适合已有历史数据，通过 Excel 等文件快速导入。</p></div>
          <span className="v17-soft-badge">历史数据</span>
        </div>

        <div className="v17-file-card-body">
          <button className="v17-dropzone" type="button" onClick={() => setImportOpen(true)}>
            <CloudUploadOutlined />
            <strong>点击或拖拽文件到此处上传</strong>
            <span>支持 CSV、XLSX 格式，单个文件不超过 50MB</span>
          </button>
          <ul className="v17-check-list">
            <li><CheckCircleFilled /> 自动识别温度、湿度、光照等字段</li>
            <li><CheckCircleFilled /> 支持多工作表、批量导入</li>
            <li><CheckCircleFilled /> 数据校验与异常提示</li>
            <li><CheckCircleFilled /> 导入后自动生成可视化图表</li>
          </ul>
        </div>
        <div className="v17-card-actions">
          <Button type="primary" size="large" icon={<CloudUploadOutlined />} onClick={() => setImportOpen(true)}>选择文件导入 <ArrowRightOutlined /></Button>
          <Button type="link" icon={<FileTextOutlined />}>查看导入示例</Button>
        </div>
      </article>

      <article className="v17-connect-card v17-sensor-card">
        <div className="v17-connect-title-row">
          <span className="v17-connect-icon"><ApiOutlined /></span>
          <div><h2>实时设备接入</h2><p>通过物联网设备实时采集数据，不错过任何环境变化。</p></div>
          <span className="v17-soft-badge">实时数据</span>
          <span className="v17-api-ok"><i /> API 正常</span>
        </div>

        <div className="v17-device-flow" aria-label="实时设备接入流程">
          <div><span><NodeIndexOutlined /></span><b>传感器</b><small>温湿度 / 光照 / CO₂</small></div><ArrowRightOutlined />
          <div><span><CloudServerOutlined /></span><b>API Gateway</b><small>数据接入网关</small></div><ArrowRightOutlined />
          <div><span><HomeOutlined /></span><b>棚智未来</b><small>数据处理与存储</small></div><ArrowRightOutlined />
          <div><span><DatabaseOutlined /></span><b>实时数据</b><small>监测与预警</small></div>
        </div>

        <div className="v17-api-metrics">
          <div><span>接口地址</span><strong>POST {endpoint}</strong><button type="button" onClick={() => void copy(endpoint)}><CopyOutlined /></button></div>
          <div><span>认证方式</span><strong>{authLabel}</strong><button type="button" onClick={() => void copy(authLabel)}><CopyOutlined /></button></div>
          <div><span>单次上限限制</span><strong>{batchSize} 条/批</strong></div>
        </div>
        <div className="v17-api-links"><Button type="link">查看 API 文档</Button><Button type="link">接入指引</Button></div>
      </article>
    </section>

    <section className="v17-step-strip" aria-label="数据接入步骤">
      <div className="is-active"><i>1</i><span><b>连接数据源</b><small>选择文件导入或接入设备</small></span></div><em />
      <div><i>2</i><span><b>校验数据质量</b><small>系统自动校验并提示异常</small></span></div><em />
      <div><i>3</i><span><b>进入日常管理</b><small>在大棚看板查看实时数据与分析</small></span></div>
    </section>

    <section className="v17-asset-shell">
      <GreenhouseManagementPage embedded />
    </section>

    <EnvironmentDataImport open={importOpen} onClose={() => setImportOpen(false)} />
  </div>
}
