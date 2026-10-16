import { useSearchParams } from 'react-router-dom'
import { canManage } from '../utils/permissions'
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
import { Button, Modal, message } from 'antd'
import { EnvironmentDataImport } from '../components/EnvironmentDataImport'
import { downloadEnvironmentTemplate } from '../components/EnvironmentDataImport/template'
import GreenhouseManagementPage from './Greenhouses/GreenhouseManagementPage'
import { getSensorIngestStatus } from '../api/sensorApi'
import type { SensorIngestStatus } from '../types/sensor'
import './PlatformV17.css'
import './data-center-refresh.css'

export default function DataCenterPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const activeTab = searchParams.get('tab') === 'connection' ? 'connection' : 'assets'
  const [importOpen, setImportOpen] = useState(false)
  const [guideOpen, setGuideOpen] = useState(false)
  const [status, setStatus] = useState<SensorIngestStatus | null>(null)
  const [messageApi, contextHolder] = message.useMessage()

  useEffect(() => {
    void getSensorIngestStatus().then(setStatus).catch(() => setStatus(null))
  }, [])

  const copy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value)
      messageApi.success('已复制')
    } catch {
      messageApi.error('复制失败，请手动选取内容')
    }
  }

  const endpoint = status?.endpoint ?? '/api/v1/ingest/sensor-data'
  const authLabel = status?.auth_required ? 'Bearer Token / X-Sensor-Key' : '无需认证'
  const batchSize = status?.max_batch_size ?? 1000
  const apiOrigin = import.meta.env.DEV
    ? (import.meta.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000')
    : new URL(import.meta.env.VITE_API_BASE_URL || '/api', window.location.origin).origin
  const docsUrl = new URL('/docs', apiOrigin).href

  return <div className="business-page v17-page v17-data-page" data-tab={activeTab}>
    {contextHolder}

    <section className="v17-hero-line v17-data-hero">
      <div>
        <span className="v17-kicker">大棚管理</span>
        <h1>数据与管理</h1>
        <p>管理大棚与种植批次，维护设备连接和环境数据。</p>
      </div>
      <div className="v17-hero-script">让每一座大棚<br />都有数据的力量</div>
    </section>

    <nav className="wb-section-tabs" aria-label="数据管理功能">{[{ key: 'assets', label: '大棚档案与批次' }, { key: 'connection', label: '设备与数据接入' }].map(tab => <button type="button" key={tab.key} aria-current={activeTab === tab.key ? 'page' : undefined} onClick={() => { const next = new URLSearchParams(searchParams); next.set('tab', tab.key); setSearchParams(next, { replace: true }) }}>{tab.label}</button>)}</nav>
    <section className="v17-connect-grid">
      <article className="v17-connect-card v17-file-card">
        <div className="v17-connect-title-row">
          <span className="v17-connect-icon"><FileTextOutlined /></span>
          <div><h2>文件导入</h2><p>适合已有历史数据，通过 Excel 等文件快速导入。</p></div>
          <span className="v17-soft-badge">历史数据</span>
        </div>

        <div className="v17-file-card-body">
          <button className="v17-dropzone" type="button" disabled={!canManage()} onClick={() => setImportOpen(true)}>
            <CloudUploadOutlined />
            <strong>点击选择数据文件</strong>
            <span>支持 CSV、XLSX、XLSM，单个文件不超过 10MB</span>
          </button>
          <ul className="v17-check-list">
            <li><CheckCircleFilled /> 自动识别温度、湿度、光照等字段</li>
            <li><CheckCircleFilled /> 单文件最多 5000 行，读取首个工作表</li>
            <li><CheckCircleFilled /> 数据校验与异常提示</li>
            <li><CheckCircleFilled /> 导入后自动生成可视化图表</li>
          </ul>
        </div>
        <div className="v17-card-actions">
          <Button type="primary" size="large" icon={<CloudUploadOutlined />} disabled={!canManage()} onClick={() => setImportOpen(true)}>选择文件导入 <ArrowRightOutlined /></Button>
          <Button type="link" icon={<FileTextOutlined />} onClick={downloadEnvironmentTemplate}>下载导入模板</Button>
        </div>
      </article>

      <article className="v17-connect-card v17-sensor-card">
        <div className="v17-connect-title-row">
          <span className="v17-connect-icon"><ApiOutlined /></span>
          <div><h2>实时设备接入</h2><p>通过物联网设备实时采集数据，不错过任何环境变化。</p></div>
          <span className="v17-soft-badge">实时数据</span>
          <span className={`v17-api-ok${status ? '' : ' is-unknown'}`}><i /> {status ? '服务已响应' : '状态未知'}</span>
        </div>

        <div className="v17-device-flow" aria-label="实时设备接入流程">
          <div><span><NodeIndexOutlined /></span><b>传感器</b><small>温湿度 / 光照 / CO₂</small></div><ArrowRightOutlined />
          <div><span><CloudServerOutlined /></span><b>API Gateway</b><small>数据接入网关</small></div><ArrowRightOutlined />
          <div><span><HomeOutlined /></span><b>棚智未来</b><small>数据处理与存储</small></div><ArrowRightOutlined />
          <div><span><DatabaseOutlined /></span><b>实时数据</b><small>监测与预警</small></div>
        </div>

        <div className="v17-api-metrics">
          <div><span>接口地址</span><strong>POST {endpoint}</strong><button type="button" onClick={() => void copy(endpoint)}><CopyOutlined /></button></div>
          <div><span>认证方式</span><strong>{status ? authLabel : '待确认'}</strong><button type="button" aria-label="复制认证方式" disabled={!status} onClick={() => void copy(authLabel)}><CopyOutlined /></button></div>
          <div><span>单次上限限制</span><strong>{batchSize} 条/批</strong></div>
        </div>
        <div className="v17-api-links"><Button type="link" href={docsUrl} target="_blank" rel="noopener noreferrer">查看 API 文档</Button><Button type="link" onClick={() => setGuideOpen(true)}>接入指引</Button></div>
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

    <EnvironmentDataImport onImported={() => window.dispatchEvent(new Event('greenhouses-changed'))} open={importOpen} onClose={() => setImportOpen(false)} />
    <Modal title="设备接入指引" open={guideOpen} onCancel={() => setGuideOpen(false)} footer={<Button onClick={() => setGuideOpen(false)}>关闭</Button>}>
      <ol className="v17-ingest-guide">
        <li>在大棚管理中确认目标大棚的编码。</li>
        <li>由管理员获取 Bearer Token；单组织部署也可在服务端配置 X-Sensor-Key。</li>
        <li>向 <code>POST {endpoint}</code> 发送 JSON：<code>{'{"items":[{"greenhouse_code":"大棚编码","device_id":"设备编号","recorded_at":"2026-01-01T12:00:00+08:00","temperature":25}]}'}</code></li>
        <li>每批最多 {batchSize} 条，时间采用 ISO 8601 格式，至少提供一个环境指标。接入后可在环境分析查看数据。</li>
      </ol>
    </Modal>
  </div>
}
