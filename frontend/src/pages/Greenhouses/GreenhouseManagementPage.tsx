import { canManage } from '../../utils/permissions'
import { getStoredUser } from '../../api/authApi'
import { useCallback, useEffect, useState } from 'react'
import { DownOutlined, UpOutlined, MoreOutlined, PlusOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Col, Descriptions, Drawer, Dropdown, Empty, Form, Input, InputNumber, Modal, Pagination, Row, Select, Space, Spin, Tag, message } from 'antd'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { createCropBatch } from '../../api/cropBatchApi'
import { getApiErrorMessage } from '../../api/client'
import { createGreenhouse, deleteGreenhouse, getGreenhouse, getGreenhouses, getManagementSummary, updateGreenhouse } from '../../api/greenhouseApi'
import type { CropBatchInput, CropType } from '../../types/cropBatch'
import type { Greenhouse, GreenhouseInput, GreenhouseManagementSummary, GreenhouseStatus } from '../../types/greenhouse'

import GreenhouseConnections from './GreenhouseConnections'
import tomatoImage from '../../marketing_v2/scenarios/assets/images/scene-tomato.png'
import seedlingImage from '../../assets/pure-scenes/seedling-wide.png'
import greenhouseImage from '../../assets/pure-scenes/greenhouse-wide.webp'
import './greenhouse-management.css'


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

export default function GreenhouseManagementPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedGreenhouse = Number(searchParams.get('greenhouse_id')) || null
  const requestedConnection = searchParams.get('tab') === 'connection'
  const [expanded, setExpanded] = useState<number | null | undefined>(undefined)
  const [directPanel, setDirectPanel] = useState<{id: number; panel: 'data' | 'devices'} | null>(null)
  const [summary, setSummary] = useState<GreenhouseManagementSummary | null>(null)
  const [summaryError, setSummaryError] = useState(false)
  const [items, setItems] = useState<Greenhouse[]>([])
  const [total, setTotal] = useState(0)
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
      const list = await getGreenhouses({ page, page_size: 4, status: statusFilter, keyword: keyword || undefined })
      setItems(list.items)
      setTotal(list.total)
      setExpanded(current => current === undefined ? (list.items.find(g => g.id === requestedGreenhouse)?.id ?? list.items[0]?.id ?? null) : current)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError))
    } finally {
      setLoading(false)
    }
  }, [keyword, page, statusFilter, requestedGreenhouse])

  useEffect(() => { void loadData() }, [loadData])
  const loadSummary = useCallback(async () => {
    try { setSummary(await getManagementSummary()); setSummaryError(false) }
    catch { setSummaryError(true) }
  }, [])
  useEffect(() => { void loadSummary() }, [loadSummary])
  useEffect(() => {
    const refresh = () => { void loadData(); void loadSummary() }
    window.addEventListener('greenhouses-changed', refresh)
    return () => window.removeEventListener('greenhouses-changed', refresh)
  }, [loadData, loadSummary])
  const refreshConnections = () => { void loadData(); void loadSummary() }
  const closeConnection = () => {
    setDirectPanel(null)
    if (requestedConnection) {
      const next = new URLSearchParams(searchParams); next.delete('tab'); setSearchParams(next, {replace:true})
    }
  }
  const openConnection = (record: Greenhouse, panel: 'data' | 'devices') => {
    setExpanded(record.id); setDirectPanel({id: record.id, panel})
  }

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ status: 'active', code: `ORG${getStoredUser()?.organization_id ?? 'GUEST'}-${Date.now().toString().slice(-8)}` })
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
        messageApi.success('大棚档案已更新'); window.dispatchEvent(new Event('greenhouses-changed'))
      } else {
        await createGreenhouse(values)
        messageApi.success('大棚创建成功'); window.dispatchEvent(new Event('greenhouses-changed'))
      }
      setFormOpen(false)
      await loadData(); window.dispatchEvent(new Event('greenhouses-changed'))
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
      await loadData(); window.dispatchEvent(new Event('greenhouses-changed'))
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
          messageApi.success('大棚删除成功'); window.dispatchEvent(new Event('greenhouses-changed'))
          await loadData(); window.dispatchEvent(new Event('greenhouses-changed'))
        } catch (requestError) {
          messageApi.error(getApiErrorMessage(requestError))
          throw requestError
        }
      },
    })
  }

  return <div className="gh-management-page">
    {messageContext}{modalContext}
    <section className="gh-management-hero" aria-label="大棚管理概况">
      <div className="gh-hero-copy"><span className="gh-hero-eyebrow">GREENHOUSE MANAGEMENT</span><h1>每一座大棚，管理有序</h1><p>创建大棚、接入数据、绑定设备，一处完成。</p>
        <dl className="gh-hero-metrics"><div><dt>大棚总数</dt><dd>{summaryError ? '—' : summary?.total ?? '—'}</dd></div><div><dt>已接入数据</dt><dd>{summaryError ? '—' : summary?.connected ?? '—'}</dd></div><div title="最近2小时有采集记录的设备；按大棚与设备编号统计"><dt>在线设备</dt><dd>{summaryError ? '—' : summary?.online_devices ?? '—'}</dd></div></dl>
      </div><Button className="gh-create-button" type="primary" icon={<PlusOutlined />} disabled={!canManage()} onClick={openCreate}>创建大棚</Button>
    </section>
    {summaryError && <Alert type="warning" message="接入概况暂时无法读取" action={<Button size="small" onClick={() => void loadSummary()}>重试</Button>} />}
    <section className="gh-inventory" aria-labelledby="gh-inventory-heading">
      <div className="gh-list-heading"><div><h2 id="gh-inventory-heading">我的大棚</h2><span>{keyword || statusFilter ? `筛选结果 ${total} 座` : `共 ${total} 座`}{summary && !summaryError ? ` · ${summary.total - summary.connected} 座待接入` : ''}</span></div><div className="gh-list-tools"><Input.Search aria-label="搜索大棚" prefix={<SearchOutlined />} allowClear placeholder="搜索大棚" onSearch={value => { setPage(1); setKeyword(value.trim()) }} /><Select<GreenhouseStatus> aria-label="筛选大棚状态" allowClear placeholder="全部状态" value={statusFilter} onChange={value => { setPage(1); setStatusFilter(value) }} options={Object.entries(statusMeta).map(([value, meta]) => ({value:value as GreenhouseStatus,label:meta.label}))} /><Button type="text" aria-label="刷新大棚" icon={<ReloadOutlined />} onClick={refreshConnections} /></div></div>
      {error ? <Alert type="error" showIcon message="大棚数据加载失败" description={error} action={<Button onClick={() => void loadData()}>重试</Button>} /> : <Spin spinning={loading}><div className="gh-inventory-list">{items.map(record => {
        const opened = expanded === record.id
        const crop = record.active_batch?.crop_type
        const stage = record.active_batch?.growth_stage
        const image = stage === '苗期' ? seedlingImage : crop === 'tomato' ? tomatoImage : crop === 'muskmelon' ? '/images/greenhouse-management/muskmelon.png' : greenhouseImage
        const connected = Boolean(record.last_recorded_at)
        const dataState = record.data_status === 'current' ? '数据已接入' : record.data_status === 'historical' ? '已接入 · 待同步' : record.data_status === 'suspect' ? '已接入 · 需复查' : '尚未接入数据'
        return <article className="gh-inventory-item" key={record.id}>
          <div className="gh-inventory-row"><img className="gh-crop-photo" src={image} alt="作物场景示意" loading="lazy" /><div className="gh-row-copy"><div className="gh-row-title"><h3>{record.name}</h3><Tag color={record.status === 'active' && !connected ? 'default' : statusMeta[record.status].color}>{record.status === 'active' && !connected ? '待接入' : statusMeta[record.status].label}</Tag></div><p className="gh-crop-meta">{record.active_batch ? `${cropMeta[record.active_batch.crop_type].label} · ${record.active_batch.growth_stage}` : '暂未创建种植批次'}<span>·</span>{Number(record.area_mu).toLocaleString('zh-CN')} 亩</p><div className="gh-data-meta"><span><i className={`gh-state-dot ${record.data_status === 'current' ? 'is-current' : ''}`} />{dataState}</span><span>{record.device_count ? `${record.online_device_count ?? 0} / ${record.device_count} 台设备在线` : '暂无绑定设备'}</span><time>{record.last_recorded_at ? `最近上报 ${new Date(record.last_recorded_at).toLocaleString('zh-CN', {month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})}` : record.code}</time></div></div><div className="gh-row-actions"><Button onClick={() => void openDetail(record)}>查看大棚</Button>{connected ? <Button aria-expanded={opened} aria-controls={`gh-access-${record.id}`} onClick={() => {setDirectPanel(null);setExpanded(opened ? null : record.id)}}>管理接入 {opened ? <UpOutlined /> : <DownOutlined />}</Button> : <><Button type="primary" onClick={() => openConnection(record,'data')}>接入数据</Button><Button onClick={() => openConnection(record,'devices')}>绑定设备</Button></>}<Dropdown trigger={['click']} menu={{items:[{key:'edit',label:'编辑大棚',disabled:!canManage()},{key:'batch',label:'创建种植批次',disabled:!canManage() || Boolean(record.active_batch) || record.status==='closed'},{key:'delete',label:'删除大棚',danger:true,disabled:!canManage()}],onClick:({key})=>{if(key==='edit')openEdit(record);if(key==='batch')openBatch(record);if(key==='delete')removeGreenhouse(record)}}}><Button type="text" aria-label={`更多操作：${record.name}`} icon={<MoreOutlined />} /></Dropdown></div></div>
          {opened && <GreenhouseConnections greenhouse={record} onPanelClose={closeConnection} onChange={refreshConnections} openRequest={directPanel?.id === record.id ? directPanel : undefined} initialPanel={requestedConnection && record.id === requestedGreenhouse ? 'data' : undefined} />}
        </article>
      })}{!loading && !items.length && <Empty description={keyword || statusFilter ? '没有符合条件的大棚，请调整筛选' : '还没有大棚，从创建第一座开始'}>{!keyword && !statusFilter && <Button type="primary" disabled={!canManage()} onClick={openCreate}>创建大棚</Button>}</Empty>}</div></Spin>}
      <div className="gh-list-footer"><Pagination current={page} pageSize={4} total={total} hideOnSinglePage={false} showSizeChanger={false} onChange={setPage} showTotal={count=>`共 ${count} 座`} /><small>场景配图为示意 · 在线按最近2小时上报统计</small></div>
    </section>

    <Modal title={editing ? '编辑大棚' : '创建大棚'} open={formOpen} confirmLoading={saving} onCancel={() => setFormOpen(false)} onOk={() => form.submit()} destroyOnHidden>
      <Form name="gh-profile" form={form} layout="vertical" onFinish={(values) => void submitGreenhouse(values)}>
        <Row gutter={12}><Col span={12}><Form.Item name="code" label="全局大棚编码" rules={[{ required: true, message: '请输入大棚编号' }, { max: 32 }]}><Input placeholder="GH-001" /></Form.Item></Col><Col span={12}><Form.Item name="name" label="大棚名称" rules={[{ required: true, message: '请输入大棚名称' }, { max: 80 }]}><Input /></Form.Item></Col></Row>
        <Form.Item name="location" label="位置" rules={[{ required: true, message: '请输入位置' }, { max: 160 }]}><Input /></Form.Item>
        <Row gutter={12}><Col span={12}><Form.Item name="area_mu" label="面积（亩）" rules={[{ required: true, message: '请输入面积' }]}><InputNumber min={0.01} precision={2} className="full-width" /></Form.Item></Col><Col span={12}><Form.Item name="status" label="状态" rules={[{ required: true }]}><Select options={Object.entries(statusMeta).map(([value, meta]) => ({ value, label: meta.label }))} /></Form.Item></Col></Row>
        <Form.Item name="manager_name" label="负责人" rules={[{ max: 40 }]}><Input /></Form.Item>
      </Form>
    </Modal>

    <Modal title={`为${batchGreenhouse?.name || ''}创建种植批次`} open={Boolean(batchGreenhouse)} confirmLoading={saving} onCancel={() => setBatchGreenhouse(null)} onOk={() => batchForm.submit()} destroyOnHidden>
      <Alert className="form-note" type="info" showIcon message="生育期按作物和定植日期计算，并支持人工修正。" />
      <Form name="gh-batch" form={batchForm} layout="vertical" onFinish={(values) => void submitBatch(values)}>
        <Form.Item name="batch_code" label="批次编号" rules={[{ required: true, message: '请输入批次编号' }, { max: 40 }]}><Input placeholder="TOMATO-2026-001" /></Form.Item>
        <Form.Item name="crop_type" label="作物类型" rules={[{ required: true, message: '请选择作物类型' }]}><Select options={Object.entries(cropMeta).map(([value, meta]) => ({ value, label: meta.label }))} /></Form.Item>
        <Form.Item name="variety" label="品种" rules={[{ required: true, message: '请输入品种' }, { max: 80 }]}><Input placeholder="请输入作物品种" /></Form.Item>
        <Row gutter={12}><Col span={12}><Form.Item name="planted_at" label="定植日期" rules={[{ required: true, message: '请选择定植日期' }]}><Input type="date" /></Form.Item></Col><Col span={12}><Form.Item name="expected_harvest_at" label="预计采收日期" rules={[{ required: true, message: '请选择预计采收日期' }]}><Input type="date" /></Form.Item></Col></Row>
        <Form.Item name="status" label="批次状态" rules={[{ required: true }]}><Select options={[{ value: 'growing', label: '生长中' }, { value: 'harvested', label: '已采收' }, { value: 'closed', label: '已关闭' }]} /></Form.Item>
      </Form>
    </Modal>

    <Drawer title="大棚详情" width={520} open={Boolean(detail)} onClose={() => setDetail(null)} extra={detail && canManage() && !detail.active_batch && detail.status !== 'closed' ? <Button type="primary" onClick={() => openBatch(detail)}>创建批次</Button> : null}>
      <Spin spinning={detailLoading}>{detail && <><Descriptions column={1} bordered size="small" items={[
        { key: 'code', label: '编号', children: detail.code }, { key: 'name', label: '名称', children: detail.name }, { key: 'location', label: '位置', children: detail.location }, { key: 'area', label: '面积', children: `${detail.area_mu} 亩` }, { key: 'manager', label: '负责人', children: detail.manager_name || '未设置' }, { key: 'status', label: '状态', children: <Tag color={statusMeta[detail.status].color}>{statusMeta[detail.status].label}</Tag> },
      ]} /><Space className="detail-nav" wrap><Button onClick={() => navigate(`/platform/environment?greenhouse_id=${detail.id}&batch_id=${detail.active_batch?.id ?? ''}`)}>环境研判</Button><Button onClick={() => navigate(`/platform/production?greenhouse_id=${detail.id}&batch_id=${detail.active_batch?.id ?? ''}`)}>生产决策</Button></Space><Card className="detail-batch-card" size="small" title="当前种植批次">{detail.active_batch ? <Descriptions column={1} size="small" items={[
        { key: 'crop', label: '作物类型', children: <Tag color={cropMeta[detail.active_batch.crop_type].color}>{cropMeta[detail.active_batch.crop_type].label}</Tag> }, { key: 'variety', label: '品种', children: detail.active_batch.variety }, { key: 'code', label: '批次编号', children: detail.active_batch.batch_code }, { key: 'stage', label: '当前生育期', children: <Tag color="green">{detail.active_batch.growth_stage}</Tag> }, { key: 'rules', label: '适用规则', children: cropMeta[detail.active_batch.crop_type].rules }, { key: 'day', label: '生长天数', children: `第 ${detail.active_batch.growth_day} 天` }, { key: 'harvest', label: '预计采收', children: detail.active_batch.expected_harvest_at || '未设置' },
      ]} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无生长中批次" />}</Card></>}</Spin>
    </Drawer>
  </div>
}
