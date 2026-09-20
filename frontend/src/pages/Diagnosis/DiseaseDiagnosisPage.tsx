import { useCallback, useEffect, useState } from 'react'
import { CheckCircleOutlined, CloudUploadOutlined, ExclamationCircleOutlined, ReloadOutlined, SafetyCertificateOutlined } from '@ant-design/icons'
import { Alert, Button, Form, Input, Modal, Progress, Select, Space, Table, Tag, Typography, Upload, message } from 'antd'
import type { UploadProps } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getCropBatches } from '../../api/cropBatchApi'
import { getApiErrorMessage } from '../../api/client'
import { getDiseaseModelStatus, getDiseaseRecords, identifyDisease, reviewDiseaseRecord } from '../../api/diseaseApi'
import { getGreenhouses } from '../../api/greenhouseApi'
import { createTaskFromDisease } from '../../api/taskApi'
import type { CropBatch } from '../../types/cropBatch'
import type { DiseaseIdentification, DiseaseModelStatus, DiseaseRecord, DiseaseReviewInput, ReviewStatus } from '../../types/disease'
import type { Greenhouse } from '../../types/greenhouse'
import { SaasEmptyState, SectionHeading } from '../../components/SaasUI'
import { ProductSkeleton } from '../../components/ProductStates'

const { Dragger } = Upload
const reviewLabels: Record<ReviewStatus, { label: string; color: string }> = {
  unreviewed: { label: '待复核', color: 'gold' }, confirmed: { label: '已确认', color: 'green' },
  corrected: { label: '已修正', color: 'blue' }, rejected: { label: '已拒绝', color: 'default' },
}
type ReviewFormValues = DiseaseReviewInput

export default function DiseaseDiagnosisPage() {
  const navigate = useNavigate(); const [searchParams] = useSearchParams()
  const [status, setStatus] = useState<DiseaseModelStatus | null>(null)
  const [greenhouses, setGreenhouses] = useState<Greenhouse[]>([])
  const [greenhouseId, setGreenhouseId] = useState<number | null>(null)
  const [batches, setBatches] = useState<CropBatch[]>([])
  const [batchId, setBatchId] = useState<number | null>(null)
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [result, setResult] = useState<DiseaseIdentification | null>(null)
  const [records, setRecords] = useState<DiseaseRecord[]>([])
  const [total, setTotal] = useState(0); const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true); const [identifying, setIdentifying] = useState(false)
  const [error, setError] = useState<string | null>(null); const [reviewing, setReviewing] = useState<DiseaseRecord | null>(null)
  const [savingReview, setSavingReview] = useState(false)
  const [form] = Form.useForm<ReviewFormValues>(); const [messageApi, messageContext] = message.useMessage()

  const loadRecords = useCallback(async (selectedPage = page, selectedGreenhouse = greenhouseId ?? undefined) => {
    const data = await getDiseaseRecords(selectedPage, 10, selectedGreenhouse); setRecords(data.items); setTotal(data.total)
  }, [greenhouseId, page])

  const initialize = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [model, greenhousePage] = await Promise.all([getDiseaseModelStatus(), getGreenhouses({ page: 1, page_size: 100, status: 'active' })])
      setStatus(model); setGreenhouses(greenhousePage.items)
      const fromUrl = Number(searchParams.get('greenhouse_id')) || null
      const selected = fromUrl && greenhousePage.items.some((item) => item.id === fromUrl) ? fromUrl : greenhousePage.items.find((item) => item.active_batch?.crop_type === 'tomato')?.id ?? greenhousePage.items[0]?.id ?? null
      setGreenhouseId(selected)
      if (selected) {
        const allBatches = await getCropBatches(selected); const tomato = allBatches.filter((item) => item.crop_type === 'tomato' && item.status === 'growing')
        setBatches(tomato); setBatchId(tomato[0]?.id ?? null)
        const history = await getDiseaseRecords(1, 10, selected); setRecords(history.items); setTotal(history.total)
      }
    } catch (requestError) { setError(getApiErrorMessage(requestError)) } finally { setLoading(false) }
  }, [searchParams])
  useEffect(() => { void initialize() }, [initialize])
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl) }, [previewUrl])

  const changeGreenhouse = async (id: number) => {
    setGreenhouseId(id); setBatchId(null); setPage(1); setResult(null)
    try {
      const all = await getCropBatches(id); const tomato = all.filter((item) => item.crop_type === 'tomato' && item.status === 'growing')
      setBatches(tomato); setBatchId(tomato[0]?.id ?? null); await loadRecords(1, id)
    } catch (requestError) { messageApi.error(getApiErrorMessage(requestError)) }
  }
  const beforeUpload: UploadProps['beforeUpload'] = (file) => {
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) { messageApi.error('仅支持 JPG、JPEG、PNG 和 WEBP'); return Upload.LIST_IGNORE }
    if (file.size > 10 * 1024 * 1024) { messageApi.error('图片大小不能超过10MB'); return Upload.LIST_IGNORE }
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    setImageFile(file); setPreviewUrl(URL.createObjectURL(file)); setResult(null); return false
  }
  const identify = async () => {
    if (!greenhouseId || !batchId || !imageFile) return
    setIdentifying(true)
    try { const response = await identifyDisease(greenhouseId, batchId, imageFile); setResult(response); messageApi.success('识别记录已保存'); await loadRecords(1, greenhouseId); setPage(1) }
    catch (requestError) { messageApi.error(getApiErrorMessage(requestError)) } finally { setIdentifying(false) }
  }
  const openReview = (record: DiseaseRecord, initial: 'confirmed' | 'corrected' | 'rejected') => {
    setReviewing(record); form.setFieldsValue({ review_status: initial, reviewed_class: initial === 'confirmed' ? record.predicted_class ?? undefined : undefined, review_note: '' })
  }
  const saveReview = async (values: ReviewFormValues) => {
    if (!reviewing) return; setSavingReview(true)
    try { await reviewDiseaseRecord(reviewing.id, values); messageApi.success('人工审核已保存'); setReviewing(null); await loadRecords() }
    catch (requestError) { messageApi.error(getApiErrorMessage(requestError)) } finally { setSavingReview(false) }
  }
  const createFieldTask = async (record: DiseaseRecord) => {
    try {
      const task = await createTaskFromDisease(record.id, '管理员')
      messageApi.success('已创建现场复核任务草稿')
      navigate(`/platform/production?tab=tasks&greenhouse_id=${record.greenhouse_id}&batch_id=${record.crop_batch_id}&task_id=${task.id}`)
    } catch (requestError) { messageApi.error(getApiErrorMessage(requestError)) }
  }

  const selectedGreenhouse = greenhouses.find((item) => item.id === greenhouseId); const topCandidate = result?.top3_predictions[0]
  const columns: ColumnsType<DiseaseRecord> = [
    { title: '时间 / 文件', key: 'file', width: 190, render: (_, row) => <div className="table-primary"><strong>{new Date(row.created_at).toLocaleString()}</strong><span>{row.original_filename}</span></div> },
    { title: '模型候选结果', key: 'result', render: (_, row) => ['recognized', 'review_required'].includes(row.recognition_status) ? <Space direction="vertical" size={2}><strong>{row.predicted_class_name}</strong><Typography.Text type="secondary">置信度 {((row.confidence ?? 0) * 100).toFixed(1)}% · 等待人工复核</Typography.Text></Space> : <Tag color={row.recognition_status === 'low_confidence' ? 'orange' : 'red'}>{row.recognition_status === 'low_confidence' ? '低置信度，未形成确定候选' : '模型不可用'}</Tag> },
    { title: '模型状态', key: 'model', width: 180, render: (_, row) => <Space direction="vertical" size={2}><span>{row.model_version}</span></Space> },
    { title: '人工复核状态', key: 'review', width: 280, render: (_, row) => <Space wrap><Tag color={reviewLabels[row.review_status].color}>{reviewLabels[row.review_status].label}</Tag>{row.review_status === 'unreviewed' && <>{['recognized', 'review_required'].includes(row.recognition_status) && <Button size="small" type="link" onClick={() => openReview(row, 'confirmed')}>确认候选</Button>}<Button size="small" type="link" onClick={() => openReview(row, 'corrected')}>修正</Button><Button size="small" type="link" danger onClick={() => openReview(row, 'rejected')}>拒绝</Button></>}{['confirmed', 'corrected'].includes(row.review_status) && <Button size="small" type="link" onClick={() => void createFieldTask(row)}>创建现场任务</Button>}</Space> },
  ]

  if (loading) return <div className="v18-disease-page"><ProductSkeleton rows={7} /></div>
  return <div className="business-page disease-page commercial-disease-page v18-disease-page">{messageContext}
    <div className="page-intro commercial-page-intro">
      <div>
        <span className="eyebrow">AI DISEASE ASSISTANT</span>
        <h1>病害辅助识别</h1>
        <p>上传叶片照片，AI 给出候选结果，再由人工复核后进入现场任务闭环。</p>
      </div>
      <Space wrap><Tag color={status?.model_status === 'ready' ? 'green' : 'orange'}>{status?.model_status === 'under_evaluation' ? '辅助识别模式' : status?.model_status === 'ready' ? '模型已就绪' : '模型状态异常'}</Tag></Space>
    </div>

    <div className="disease-safety-note"><SafetyCertificateOutlined /><span><strong>辅助判断，不替代人工确认</strong><small>识别结果需要结合叶片症状、种植环境和现场情况进行复核。</small></span></div>
    {error && <Alert className="page-alert" type="error" showIcon message="页面数据加载失败" description={error} action={<Button icon={<ReloadOutlined />} onClick={() => void initialize()}>重试</Button>} />}

    <section className="disease-ai-workspace surface-card surface-card-major">
      <div className="disease-upload-column">
        <SectionHeading title="上传叶片照片" description="支持 JPG / PNG / WEBP，建议在自然光下对焦叶片主体" />
        <div className="disease-selectors commercial-disease-selectors">
          <div><span>大棚</span><Select value={greenhouseId} onChange={(value) => void changeGreenhouse(value)} options={greenhouses.map((item) => ({ value: item.id, label: `${item.name}（${item.active_batch?.crop_type === 'tomato' ? '番茄' : '非番茄/无批次'}）` }))} /></div>
          <div><span>番茄生长中批次</span><Select value={batchId} onChange={setBatchId} placeholder="暂无可用番茄批次" options={batches.map((item) => ({ value: item.id, label: `${item.batch_code} · ${item.variety}` }))} /></div>
        </div>
        {selectedGreenhouse?.active_batch?.crop_type !== 'tomato' && <Alert type="info" showIcon message="请选择具有生长中番茄批次的大棚；甜瓜和未知作物不会调用番茄模型。" />}

        {previewUrl ? <div className={`disease-image-stage ${identifying ? 'is-scanning' : ''}`}>
          <img src={previewUrl} alt="待识别叶片预览" />
          <div className="disease-scan-line" />
          <div className="disease-image-meta"><strong>{imageFile?.name}</strong><span>{imageFile ? `${(imageFile.size / 1024 / 1024).toFixed(2)} MB` : ''}</span></div>
        </div> : <Dragger accept=".jpg,.jpeg,.png,.webp" multiple={false} showUploadList={false} beforeUpload={beforeUpload} className="disease-uploader commercial-disease-uploader"><p className="ant-upload-drag-icon"><CloudUploadOutlined /></p><p className="ant-upload-text">拖拽叶片照片到这里</p><p className="ant-upload-hint">或点击选择文件 · 最大 10MB</p></Dragger>}

        <div className="disease-upload-actions">
          {previewUrl && <Upload accept=".jpg,.jpeg,.png,.webp" multiple={false} showUploadList={false} beforeUpload={beforeUpload}><Button>更换图片</Button></Upload>}
          <Button type="primary" size="large" loading={identifying} disabled={!imageFile || !batchId} onClick={() => void identify()}>{identifying ? '正在分析叶片特征…' : '开始识别'}</Button>
        </div>
      </div>

      <div className={`disease-result-column ${result ? 'has-result' : ''}`}>
        <SectionHeading title="AI 识别结果" description="候选类别、置信度与人工复核入口" />
        {!result ? <SaasEmptyState title="等待识别结果" description="上传合法叶片图片并选择番茄批次后，AI 会在这里展示候选类别和置信度。" /> : result.recognition_status === 'model_unavailable' ? <Alert type="error" showIcon message="模型当前不可用" description="记录已保存，但没有生成分类结果。请检查模型产物后重试。" /> : <div className="disease-result-content">
          {result.recognition_status === 'low_confidence' ? <div className="disease-confidence-warning"><ExclamationCircleOutlined /><div><strong>低置信度，不输出确定候选</strong><p>最高候选为“{topCandidate?.class_name ?? '未知'}”，建议重新拍摄或交由专业人员复核。</p></div></div> : <>
            <div className="disease-result-hero">
              <div><span>模型候选结果</span><strong>{result.predicted_class_name}</strong><small>需要人工确认后才可转为农事任务来源</small></div>
              <div className="confidence-number"><strong>{Math.round((result.confidence ?? 0) * 100)}%</strong><span>置信度</span></div>
            </div>
            <Progress percent={Math.round((result.confidence ?? 0) * 100)} showInfo={false} strokeColor="#13815f" trailColor="#e7eeea" />
          </>}

          <div className="disease-top3">
            <span className="result-label">Top-3 候选</span>
            {result.top3_predictions.map((item, index) => <div key={item.class_key} className={index === 0 ? 'is-top' : ''}><b>0{index + 1}</b><span>{item.class_name}</span><strong>{(item.confidence * 100).toFixed(1)}%</strong></div>)}
          </div>
          <div className="disease-result-meta"><Tag>{result.model_version}</Tag><Tag color="blue">番茄六分类</Tag>{result.duplicate_image && <Tag color="purple">检测到重复图片</Tag>}</div>
          <div className="disease-human-review"><CheckCircleOutlined /><span><strong>下一步：人工复核</strong><small>高置信度也需要人工确认，再决定是否创建现场任务。</small></span></div>
          <div className="v18-disease-actions-bridge">
            <Button onClick={() => { const current = records.find((item) => item.id === result.record_id); if (current) openReview(current, 'confirmed'); else messageApi.info('识别记录正在同步，请稍后在历史记录中复核。') }}>人工复核</Button>
            <Button type="primary" onClick={() => { const current = records.find((item) => item.id === result.record_id); if (current && ['confirmed', 'corrected'].includes(current.review_status)) void createFieldTask(current); else messageApi.info('请先完成人工复核，确认后即可一键派发现场任务。') }}>派发农事任务</Button>
          </div>
        </div>}
      </div>
    </section>

    <section className="disease-history-section surface-card">
      <SectionHeading title="识别历史与人工纠正" description="保留模型候选、人工复核与任务来源，方便持续改进模型" action={<Button icon={<ReloadOutlined />} onClick={() => void loadRecords()}>刷新</Button>} />
      <Table<DiseaseRecord> rowKey="id" columns={columns} dataSource={records} scroll={{ x: 900 }} locale={{ emptyText: <SaasEmptyState title="暂无识别记录" description="完成第一次病害辅助识别后，记录会出现在这里。" /> }} pagination={{ current: page, pageSize: 10, total, showSizeChanger: false, onChange: (next) => { setPage(next); void loadRecords(next) } }} />
    </section>

    <Modal title="人工复核识别记录" open={Boolean(reviewing)} confirmLoading={savingReview} onCancel={() => setReviewing(null)} onOk={() => form.submit()} destroyOnHidden><Form form={form} layout="vertical" onFinish={(values) => void saveReview(values)}>
      <Form.Item name="review_status" label="审核结论" rules={[{ required: true }]}><Select options={[{ value: 'confirmed', label: '确认模型结果' }, { value: 'corrected', label: '修正类别' }, { value: 'rejected', label: '拒绝此识别记录' }]} /></Form.Item>
      <Form.Item noStyle shouldUpdate={(previous, current) => previous.review_status !== current.review_status}>{({ getFieldValue }) => getFieldValue('review_status') === 'corrected' ? <Form.Item name="reviewed_class" label="修正为" rules={[{ required: true, message: '请选择修正类别' }]}><Select options={status?.supported_classes.map((item) => ({ value: item.key, label: item.name }))} /></Form.Item> : null}</Form.Item>
      <Form.Item name="review_note" label="复核备注" rules={[{ max: 1000 }]}><Input.TextArea rows={4} placeholder="记录可观察症状或复核依据；不要在此自动生成用药剂量。" /></Form.Item>
    </Form></Modal>
  </div>
}
