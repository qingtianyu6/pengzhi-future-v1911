import { useEffect, useMemo, useState } from 'react'
import {
  CheckCircleOutlined,
  CloudUploadOutlined,
  DownloadOutlined,
  FileSearchOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import {
  Alert,
  Button,
  Col,
  Descriptions,
  Form,
  Modal,
  Progress,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Upload,
  message,
} from 'antd'
import type { UploadFile } from 'antd/es/upload/interface'
import { getApiErrorMessage } from '../../api/client'
import { getGreenhouses } from '../../api/greenhouseApi'
import {
  importSensorFile,
  previewSensorFile,
  type EnvironmentImportPreview,
  type ImportPreviewSample,
} from '../../api/sensorApi'
import type { Greenhouse } from '../../types/greenhouse'

interface EnvironmentDataImportProps {
  open: boolean
  defaultGreenhouseId?: number | null
  onClose: () => void
  onImported?: () => void
}

interface ImportFormValues {
  greenhouse_id: number
}

function formatTime(value: string | null): string {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'
}

function scoreColor(score: number): string {
  if (score >= 90) return '#168464'
  if (score >= 75) return '#3c83c5'
  if (score >= 60) return '#d59a20'
  return '#d65745'
}

export function EnvironmentDataImport({ open, defaultGreenhouseId, onClose, onImported }: EnvironmentDataImportProps) {
  const [greenhouses, setGreenhouses] = useState<Greenhouse[]>([])
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [preview, setPreview] = useState<EnvironmentImportPreview | null>(null)
  const [checking, setChecking] = useState(false)
  const [importing, setImporting] = useState(false)
  const [form] = Form.useForm<ImportFormValues>()
  const [messageApi, contextHolder] = message.useMessage()

  useEffect(() => {
    if (!open) return
    setPreview(null)
    setFileList([])
    void getGreenhouses({ page: 1, page_size: 100, status: 'active' }).then((data) => {
      setGreenhouses(data.items)
      const target = defaultGreenhouseId && data.items.some((item) => item.id === defaultGreenhouseId)
        ? defaultGreenhouseId
        : data.items[0]?.id
      if (target) form.setFieldsValue({ greenhouse_id: target })
    }).catch((error) => messageApi.error(getApiErrorMessage(error)))
  }, [defaultGreenhouseId, form, messageApi, open])

  const selectedFile = useMemo(() => fileList[0]?.originFileObj, [fileList])

  const runPreview = async () => {
    if (!selectedFile) {
      messageApi.warning('请选择要导入的数据文件')
      return
    }
    setChecking(true)
    try {
      setPreview(await previewSensorFile(selectedFile))
    } catch (error) {
      setPreview(null)
      messageApi.error(getApiErrorMessage(error))
    } finally {
      setChecking(false)
    }
  }

  const submit = async () => {
    let values: ImportFormValues
    try {
      values = await form.validateFields()
    } catch {
      return
    }
    if (!selectedFile || !preview) {
      messageApi.warning('请先完成数据质量检查')
      return
    }
    if (!preview.import_ready) {
      messageApi.warning('当前文件存在阻断性问题，请修正后重新检查')
      return
    }

    setImporting(true)
    try {
      const result = await importSensorFile(values.greenhouse_id, selectedFile)
      messageApi.success(`导入完成：新增 ${result.success_count} 条，跳过 ${result.skipped_count} 条重复记录`)
      onImported?.()
      onClose()
    } catch (error) {
      messageApi.error(getApiErrorMessage(error))
    } finally {
      setImporting(false)
    }
  }

  const downloadTemplate = () => {
    const csv = 'recorded_at,temperature,air_humidity,soil_moisture,light_intensity,co2_concentration'
    const url = URL.createObjectURL(new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' }))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'environment_data_template.csv'
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const columns = [
    { title: '时间', dataIndex: 'recorded_at', render: (value: string | null) => formatTime(value) },
    { title: '温度', dataIndex: 'temperature', render: (value: number | null) => value ?? '—' },
    { title: '空气湿度', dataIndex: 'air_humidity', render: (value: number | null) => value ?? '—' },
    { title: '土壤湿度', dataIndex: 'soil_moisture', render: (value: number | null) => value ?? '—' },
    { title: '光照', dataIndex: 'light_intensity', render: (value: number | null) => value ?? '—' },
    { title: 'CO₂', dataIndex: 'co2_concentration', render: (value: number | null) => value ?? '—' },
  ]

  return <>
    {contextHolder}
    <Modal
      className="data-import-modal"
      title="导入环境数据"
      width="min(960px, 96vw)"
      open={open}
      onCancel={onClose}
      destroyOnHidden
      footer={[
        <Button key="template" icon={<DownloadOutlined />} onClick={downloadTemplate}>下载模板</Button>,
        <Button key="cancel" onClick={onClose}>取消</Button>,
        <Button key="check" icon={<FileSearchOutlined />} loading={checking} onClick={() => void runPreview()}>检查数据</Button>,
        <Button key="import" type="primary" icon={<CloudUploadOutlined />} disabled={!preview?.import_ready} loading={importing} onClick={() => void submit()}>确认导入</Button>,
      ]}
    >
      <div className="import-layout">
        <div className="import-source-panel">
          <Form form={form} layout="vertical">
            <Form.Item name="greenhouse_id" label="目标大棚" rules={[{ required: true, message: '请选择目标大棚' }]}>
              <Select placeholder="选择大棚" options={greenhouses.map((item) => ({ value: item.id, label: `${item.name} · ${item.code}` }))} />
            </Form.Item>
            <Form.Item label="数据文件" required>
              <Upload
                accept=".csv,.xlsx,.xlsm"
                maxCount={1}
                beforeUpload={() => false}
                fileList={fileList}
                onChange={({ fileList: next }) => {
                  setFileList(next.slice(-1))
                  setPreview(null)
                }}
              >
                <Button icon={<CloudUploadOutlined />}>选择 CSV / Excel</Button>
              </Upload>
            </Form.Item>
          </Form>
          <div className="import-hint">
            <strong>字段可自动识别</strong>
            <span>支持中文或英文列名；时间列必填，环境指标可按现有数据提供。</span>
          </div>
        </div>

        {!preview ? (
          <div className="import-preview-empty">
            <FileSearchOutlined />
            <strong>导入前先做一次数据体检</strong>
            <span>系统会检查时间连续性、字段完整度、越界值和重复时间点。</span>
          </div>
        ) : (
          <div className="import-preview-panel">
            <div className="quality-score-block">
              <Progress type="dashboard" percent={preview.quality_score} strokeColor={scoreColor(preview.quality_score)} size={132} />
              <div>
                <span>数据健康度</span>
                <strong>{preview.quality_level}</strong>
                <Tag color={preview.import_ready ? 'green' : 'red'} icon={preview.import_ready ? <CheckCircleOutlined /> : <WarningOutlined />}>
                  {preview.import_ready ? '可导入' : '需要修正'}
                </Tag>
              </div>
            </div>
            <Row gutter={[12, 12]} className="import-stat-grid">
              <Col span={6}><Statistic title="完整率" value={preview.completeness_rate} suffix="%" precision={1} /></Col>
              <Col span={6}><Statistic title="连续率" value={preview.continuity_rate} suffix="%" precision={1} /></Col>
              <Col span={6}><Statistic title="范围有效率" value={preview.valid_range_rate} suffix="%" precision={1} /></Col>
              <Col span={6}><Statistic title="记录数" value={preview.total_rows} /></Col>
            </Row>
            <Descriptions size="small" column={2} items={[
              { key: 'range', label: '时间范围', children: `${formatTime(preview.time_start)} 至 ${formatTime(preview.time_end)}` },
              { key: 'interval', label: '典型间隔', children: preview.interval_minutes ? `${preview.interval_minutes} 分钟` : '—' },
              { key: 'metrics', label: '识别指标', children: <Space size={[4, 4]} wrap>{preview.available_metrics.map((item) => <Tag key={item}>{item}</Tag>)}</Space> },
              { key: 'duplicates', label: '重复时间点', children: `${preview.duplicate_time_rows} 行` },
            ]} />
            <Alert
              type={preview.import_ready ? 'success' : 'warning'}
              showIcon
              message={preview.import_ready ? '数据检查通过' : '发现需要处理的问题'}
              description={<ul className="compact-issue-list">{preview.issues.map((item) => <li key={item}>{item}</li>)}</ul>}
            />
          </div>
        )}
      </div>

      {preview && preview.sample_rows.length > 0 && (
        <div className="import-sample-table">
          <div className="section-heading"><strong>数据预览</strong><span>前 {preview.sample_rows.length} 条</span></div>
          <Table<ImportPreviewSample> rowKey={(_, index) => String(index)} size="small" pagination={false} dataSource={preview.sample_rows} columns={columns} scroll={{ x: 760 }} />
        </div>
      )}
    </Modal>
  </>
}
