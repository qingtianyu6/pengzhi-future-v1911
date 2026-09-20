import { useCallback, useEffect, useState } from 'react'
import { ApartmentOutlined, CheckCircleOutlined, LinkOutlined, PlusOutlined, ReloadOutlined, SearchOutlined, WarningOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Col, Descriptions, Drawer, Empty, Form, Input, InputNumber, Modal, Row, Select, Space, Spin, Table, Tag, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useNavigate } from 'react-router-dom'
import { createCropBatch } from '../../api/cropBatchApi'
import { getApiErrorMessage } from '../../api/client'
import { createGreenhouse, deleteGreenhouse, getGreenhouse, getGreenhouses, updateGreenhouse } from '../../api/greenhouseApi'
import type { CropBatchInput, CropType } from '../../types/cropBatch'
import type { Greenhouse, GreenhouseInput, GreenhouseStatus } from '../../types/greenhouse'

const statusMeta: Record<GreenhouseStatus, { label: string; color: string }> = {
  active: { label: '运行中', color: 'green' },
  paused: { label: '已暂停', color: 'orange' },
  closed: { label: '已关闭', color: 'default' },
}

const cropMeta: Record<CropType, { label: string; color: string; rules: string }> = {
  tomato: { label: '番茄', color: 'green', rules: '番茄生育期规则' },
  muskmelon: { label: '甜瓜', color: 'gold', rules: '暂无适用规则' },
  other: { label: '其他', color: 'default', rules: '暂无适用规则' },
  unknown: { label: '未知', color: 'default', rules: '暂无适用规则' },
}

type GreenhouseFormValues = GreenhouseInput
type BatchFormValues = CropBatchInput

export default function GreenhouseManagementPage({ embedded = false }: { embedded?: boolean } = {}) {
  const navigate = useNavigate()
  const [items, setItems] = useState<Greenhouse[]>([])
  const [total, setTotal] = useState(0)
  const [activeTotal, setActiveTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [statusFilter, setStatusFilter] = useState<GreenhouseStatus | undefined>()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<Greenhouse | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [detail, setDetail] = useState<Greenhouse | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [batchGreenhouse, setBatchGreenhouse] = useState<Greenhouse | null>(null)
  const [form] = Form.useForm<GreenhouseFormValues>()
  const [batchForm] = Form.useForm<BatchFormValues>()
  const [messageApi, messageContext] = message.useMessage()
  const [modalApi, modalContext] = Modal.useModal()

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [list, active] = await Promise.all([
        getGreenhouses({ page, page_size: 10, status: statusFilter, keyword: keyword || undefined }),
        getGreenhouses({ page: 1, page_size: 1, status: 'active' }),
      ])
      setItems(list.items)
      setTotal(list.total)
      setActiveTotal(active.total)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError))
    } finally {
      setLoading(false)
    }
  }, [keyword, page, statusFilter])

  useEffect(() => { void loadData() }, [loadData])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ status: 'active' })
    setFormOpen(true)
  }

  const openEdit = (greenhouse: Greenhouse) => {
    setEditing(greenhouse)
    form.setFieldsValue({
      code: greenhouse.code, name: greenhouse.name, location: greenhouse.location,
      area_mu: Number(greenhouse.area_mu), status: greenhouse.status,
      manager_name: greenhouse.manager_name || undefined,
    })
    setFormOpen(true)
  }

  const submitGreenhouse = async (values: GreenhouseFormValues) => {
    setSaving(true)
    try {
      if (editing) {
        await updateGreenhouse(editing.id, values)
        messageApi.success('大棚档案已更新')
      } else {
        await createGreenhouse(values)
        messageApi.success('大棚创建成功')
      }
      setFormOpen(false)
      await loadData()
    } catch (requestError) {
      messageApi.error(getApiErrorMessage(requestError))
    } finally { setSaving(false) }
  }

  const openDetail = async (greenhouse: Greenhouse) => {
    setDetail(greenhouse)
    setDetailLoading(true)
    try { setDetail(await getGreenhouse(greenhouse.id)) }
    catch (requestError) { messageApi.error(getApiErrorMessage(requestError)) }
    finally { setDetailLoading(false) }
  }

  const openBatch = (greenhouse: Greenhouse) => {
    setBatchGreenhouse(greenhouse)
    batchForm.resetFields()
    batchForm.setFieldsValue({ status: 'growing', crop_type: 'tomato' })
  }

  const submitBatch = async (values: BatchFormValues) => {
    if (!batchGreenhouse) return
    setSaving(true)
    try {
      await createCropBatch(batchGreenhouse.id, values)
      messageApi.success('种植批次创建成功，已按作物类型计算生育期')
      setBatchGreenhouse(null)
      if (detail?.id === batchGreenhouse.id) setDetail(await getGreenhouse(batchGreenhouse.id))
      await loadData()
    } catch (requestError) { messageApi.error(getApiErrorMessage(requestError)) }
    finally { setSaving(false) }
  }

  const removeGreenhouse = (greenhouse: Greenhouse) => {
    modalApi.confirm({
      title: '确认删除大棚？',
      content: '删除后，该大棚关联的环境数据、种植批次、预警、决策、病害检测记录和农事任务将一并删除，此操作不可恢复。',
      okText: '确认删除', cancelText: '取消', okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await deleteGreenhouse(greenhouse.id)
          if (detail?.id === greenhouse.id) setDetail(null)
          messageApi.success('大棚删除成功')
          await loadData()
        } catch (requestError) {
          messageApi.error(getApiErrorMessage(requestError))
          throw requestError
        }
      },
    })
  }

  const columns: ColumnsType<Greenhouse> = [
    { title: '大棚名称', key: 'greenhouse', width: 180, render: (_, record) => <div className="v17-gh-name"><strong>{record.name}</strong><span>{record.code}</span></div> },
    { title: '面积', dataIndex: 'area_mu', width: 90, render: (value: string) => `${value} 亩` },
    { title: '作物类型', key: 'crop', width: 110, render: (_, record) => record.active_batch?.variety ?? '—' },
    { title: '设备状态', dataIndex: 'status', width: 130, render: (value: GreenhouseStatus) => value === 'active' ? <span className="v17-device-status is-online"><i />运行中</span> : <span className="v17-device-status"><i />{statusMeta[value].label}</span> },
    { title: '最近同步', key: 'sync', width: 170, render: (_, record) => <div className="v17-sync-cell"><strong>{record.status === 'active' ? '刚刚' : '暂无数据'}</strong><span>{record.status === 'active' ? '设备持续同步' : '—'}</span></div> },
    { title: '当前批次', key: 'batch', width: 190, render: (_, record) => record.active_batch ? <div className="v17-batch-cell"><strong>{record.active_batch.variety} · {record.active_batch.batch_code}</strong><span>{record.active_batch.growth_stage} · 第 {record.active_batch.growth_day} 天</span></div> : <Typography.Text type="secondary">暂无批次</Typography.Text> },
    { title: '操作', key: 'actions', width: 190, render: (_, record) => <Space size={2}><Button type="link" size="small" onClick={() => void openDetail(record)}>查看</Button><Button type="link" size="small" onClick={() => openEdit(record)}>编辑</Button>{!record.active_batch && record.status !== 'closed' && <Button type="link" size="small" onClick={() => openBatch(record)}>接入设备</Button>}<Button danger type="link" size="small" onClick={() => removeGreenhouse(record)}>删除</Button></Space> },
  ]

  return <div className="business-page">
    {messageContext}
    {modalContext}
    {!embedded && <div className="page-intro"><div><h1>大棚档案</h1><p>管理大棚基础信息与种植批次。</p></div><Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建大棚</Button></div>}
    {embedded && <div className="v17-asset-head"><div><strong>大棚资产与连接状态</strong><span>管理名下所有大棚的设备连接状态、数据同步情况和运行健康度。</span></div><div className="v17-asset-actions"><Input prefix={<SearchOutlined />} allowClear placeholder="搜索大棚名称或设备编号" onPressEnter={(event) => { setPage(1); setKeyword(event.currentTarget.value.trim()) }} /><Button icon={<ReloadOutlined />} onClick={() => void loadData()}>刷新数据</Button><Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建大棚</Button></div></div>}
    <div className="v17-greenhouse-summary">
      <div><span className="v17-summary-icon"><ApartmentOutlined /></span><span><small>大棚总数</small><strong>{total}<em>座</em></strong></span></div>
      <div><span className="v17-summary-icon"><LinkOutlined /></span><span><small>已接设备</small><strong>{activeTotal}<em>座</em></strong></span><i className="v17-mini-progress"><b style={{ width: `${total ? Math.round(activeTotal / total * 100) : 0}%` }} /></i></div>
      <div><span className="v17-summary-icon"><CheckCircleOutlined /></span><span><small>数据正常</small><strong>{activeTotal}<em>座</em></strong></span><i className="v17-mini-progress"><b style={{ width: `${total ? Math.round(activeTotal / total * 100) : 0}%` }} /></i></div>
      <div className="is-warning"><span className="v17-summary-icon"><WarningOutlined /></span><span><small>待处理</small><strong>{Math.max(total - activeTotal, 0)}<em>座</em></strong></span><i className="v17-mini-progress"><b style={{ width: `${total ? Math.round(Math.max(total - activeTotal, 0) / total * 100) : 0}%` }} /></i></div>
    </div>
    <Card className="business-card v17-greenhouse-table-card" bordered={false}>
      {!embedded && <div className="toolbar"><Input.Search allowClear placeholder="搜索编号、名称或位置" onSearch={(value) => { setPage(1); setKeyword(value.trim()) }} /><Select<GreenhouseStatus> allowClear placeholder="全部状态" value={statusFilter} onChange={(value) => { setPage(1); setStatusFilter(value) }} options={Object.entries(statusMeta).map(([value, meta]) => ({ value: value as GreenhouseStatus, label: meta.label }))} /><Button icon={<ReloadOutlined />} onClick={() => void loadData()}>刷新</Button></div>}
      {error ? <Alert type="error" showIcon message="大棚数据加载失败" description={error} action={<Button size="small" onClick={() => void loadData()}>重试</Button>} /> : <Table<Greenhouse> rowKey="id" rowSelection={{ columnWidth: 42 }} columns={columns} dataSource={items} loading={loading} scroll={{ x: 980 }} locale={{ emptyText: <Empty description="暂无大棚，请先创建大棚档案" /> }} pagination={{ current: page, pageSize: 10, total, showSizeChanger: false, onChange: setPage, showTotal: (count) => `共 ${count} 条记录` }} />}
    </Card>

    <Modal title={editing ? '编辑大棚' : '新建大棚'} open={formOpen} confirmLoading={saving} onCancel={() => setFormOpen(false)} onOk={() => form.submit()} destroyOnHidden>
      <Form form={form} layout="vertical" onFinish={(values) => void submitGreenhouse(values)}>
        <Row gutter={12}><Col span={12}><Form.Item name="code" label="大棚编号" rules={[{ required: true, message: '请输入大棚编号' }, { max: 32 }]}><Input placeholder="GH-001" /></Form.Item></Col><Col span={12}><Form.Item name="name" label="大棚名称" rules={[{ required: true, message: '请输入大棚名称' }, { max: 80 }]}><Input /></Form.Item></Col></Row>
        <Form.Item name="location" label="位置" rules={[{ required: true, message: '请输入位置' }, { max: 160 }]}><Input /></Form.Item>
        <Row gutter={12}><Col span={12}><Form.Item name="area_mu" label="面积（亩）" rules={[{ required: true, message: '请输入面积' }]}><InputNumber min={0.01} precision={2} className="full-width" /></Form.Item></Col><Col span={12}><Form.Item name="status" label="状态" rules={[{ required: true }]}><Select options={Object.entries(statusMeta).map(([value, meta]) => ({ value, label: meta.label }))} /></Form.Item></Col></Row>
        <Form.Item name="manager_name" label="负责人" rules={[{ max: 40 }]}><Input /></Form.Item>
      </Form>
    </Modal>

    <Modal title={`为${batchGreenhouse?.name || ''}创建种植批次`} open={Boolean(batchGreenhouse)} confirmLoading={saving} onCancel={() => setBatchGreenhouse(null)} onOk={() => batchForm.submit()} destroyOnHidden>
      <Alert className="form-note" type="info" showIcon message="生育期按作物和定植日期计算，并支持人工修正。" />
      <Form form={batchForm} layout="vertical" onFinish={(values) => void submitBatch(values)}>
        <Form.Item name="batch_code" label="批次编号" rules={[{ required: true, message: '请输入批次编号' }, { max: 40 }]}><Input placeholder="TOMATO-2026-001" /></Form.Item>
        <Form.Item name="crop_type" label="作物类型" rules={[{ required: true, message: '请选择作物类型' }]}><Select options={Object.entries(cropMeta).map(([value, meta]) => ({ value, label: meta.label }))} /></Form.Item>
        <Form.Item name="variety" label="品种" rules={[{ required: true, message: '请输入品种' }, { max: 80 }]}><Input placeholder="请输入作物品种" /></Form.Item>
        <Row gutter={12}><Col span={12}><Form.Item name="planted_at" label="定植日期" rules={[{ required: true, message: '请选择定植日期' }]}><Input type="date" /></Form.Item></Col><Col span={12}><Form.Item name="expected_harvest_at" label="预计采收日期" rules={[{ required: true, message: '请选择预计采收日期' }]}><Input type="date" /></Form.Item></Col></Row>
        <Form.Item name="status" label="批次状态" rules={[{ required: true }]}><Select options={[{ value: 'growing', label: '生长中' }, { value: 'harvested', label: '已采收' }, { value: 'closed', label: '已关闭' }]} /></Form.Item>
      </Form>
    </Modal>

    <Drawer title="大棚详情" width={520} open={Boolean(detail)} onClose={() => setDetail(null)} extra={detail && !detail.active_batch && detail.status !== 'closed' ? <Button type="primary" onClick={() => openBatch(detail)}>创建批次</Button> : null}>
      <Spin spinning={detailLoading}>{detail && <><Descriptions column={1} bordered size="small" items={[
        { key: 'code', label: '编号', children: detail.code }, { key: 'name', label: '名称', children: detail.name }, { key: 'location', label: '位置', children: detail.location }, { key: 'area', label: '面积', children: `${detail.area_mu} 亩` }, { key: 'manager', label: '负责人', children: detail.manager_name || '未设置' }, { key: 'status', label: '状态', children: <Tag color={statusMeta[detail.status].color}>{statusMeta[detail.status].label}</Tag> },
      ]} /><Space className="detail-nav" wrap><Button onClick={() => navigate(`/platform/environment?greenhouse_id=${detail.id}&batch_id=${detail.active_batch?.id ?? ''}`)}>环境研判</Button><Button onClick={() => navigate(`/platform/production?greenhouse_id=${detail.id}&batch_id=${detail.active_batch?.id ?? ''}`)}>生产决策</Button></Space><Card className="detail-batch-card" size="small" title="当前种植批次">{detail.active_batch ? <Descriptions column={1} size="small" items={[
        { key: 'crop', label: '作物类型', children: <Tag color={cropMeta[detail.active_batch.crop_type].color}>{cropMeta[detail.active_batch.crop_type].label}</Tag> }, { key: 'variety', label: '品种', children: detail.active_batch.variety }, { key: 'code', label: '批次编号', children: detail.active_batch.batch_code }, { key: 'stage', label: '当前生育期', children: <Tag color="green">{detail.active_batch.growth_stage}</Tag> }, { key: 'rules', label: '适用规则', children: cropMeta[detail.active_batch.crop_type].rules }, { key: 'day', label: '生长天数', children: `第 ${detail.active_batch.growth_day} 天` }, { key: 'harvest', label: '预计采收', children: detail.active_batch.expected_harvest_at || '未设置' },
      ]} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无生长中批次" />}</Card></>}</Spin>
    </Drawer>
  </div>
}
