import { useCallback, useEffect, useState } from 'react'
import { ApiOutlined, ArrowRightOutlined, DatabaseOutlined, PlusOutlined } from '@ant-design/icons'
import { Alert, Button, Drawer, Empty, Form, Input, Popconfirm, Select, Space, Spin, Tag, message } from 'antd'
import { bindGreenhouseDevice, getGreenhouseDevices, unbindGreenhouseDevice } from '../../api/greenhouseApi'
import { getSensorIngestStatus } from '../../api/sensorApi'
import { getApiErrorMessage } from '../../api/client'
import { isGuestMode } from '../../api/guestMode'
import { EnvironmentDataImport } from '../../components/EnvironmentDataImport'
import { downloadEnvironmentTemplate } from '../../components/EnvironmentDataImport/template'
import type { DeviceBinding, Greenhouse, GreenhouseDevice } from '../../types/greenhouse'
import type { SensorIngestStatus } from '../../types/sensor'
import { canManage } from '../../utils/permissions'

const kinds = [{ value: 'environment', label: '温湿度 / 环境' }, { value: 'soil', label: '土壤传感器' }, { value: 'light', label: '光照传感器' }, { value: 'co2', label: 'CO₂传感器' }, { value: 'other', label: '其他采集设备' }]

export default function GreenhouseConnections({ greenhouse, initialPanel, openRequest, onPanelClose, onChange }: {
  greenhouse: Greenhouse; initialPanel?: 'data' | 'devices'; openRequest?: {panel: 'data' | 'devices'}; onPanelClose: () => void; onChange: () => void
}) {
  const [panel, setPanel] = useState<'data' | 'devices' | null>(initialPanel ?? null)
  const [devices, setDevices] = useState<GreenhouseDevice[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [ingest, setIngest] = useState<SensorIngestStatus | null>(null)
  const [form] = Form.useForm<DeviceBinding>()
  const [notice, context] = message.useMessage()
  const load = useCallback(async () => {
    setLoading(true); setError('')
    try { setDevices(await getGreenhouseDevices(greenhouse.id)) }
    catch (e) { setError(getApiErrorMessage(e)) }
    finally { setLoading(false) }
  }, [greenhouse.id])
  useEffect(() => { void load() }, [load])
  useEffect(() => { if (initialPanel) setPanel(initialPanel) }, [initialPanel])
  useEffect(() => { if (openRequest) setPanel(openRequest.panel) }, [openRequest])
  useEffect(() => {
    if (panel) void getSensorIngestStatus().then(setIngest).catch(() => setIngest(null))
  }, [panel])
  const save = async (values: DeviceBinding) => {
    setSaving(true)
    try {
      await bindGreenhouseDevice(greenhouse.id, values)
      notice.success(isGuestMode() ? '已保存到当前浏览器会话' : '设备已登记，等待首次上报')
      form.resetFields(); await load(); onChange()
    } catch (e) { notice.error(getApiErrorMessage(e)) }
    finally { setSaving(false) }
  }
  const remove = async (deviceId: string) => {
    try { await unbindGreenhouseDevice(greenhouse.id, deviceId); await load(); onChange(); notice.success('已移除登记，保留历史上报记录') }
    catch (e) { notice.error(getApiErrorMessage(e)) }
  }
  const copy = async (text: string) => {
    try { await navigator.clipboard.writeText(text); notice.success('已复制') }
    catch { notice.error('复制失败，请手动复制') }
  }
  const sample = JSON.stringify({ items: [{ greenhouse_code: greenhouse.code, device_id: devices[0]?.device_id ?? 'SENSOR-001', recorded_at: new Date().toISOString(), temperature: 25 }] }, null, 2)
  const source = !greenhouse.last_recorded_at ? '尚未接入数据' : loading ? '正在读取来源…' : error ? '来源待确认' : devices.some(d => d.last_seen) ? '传感器 / 已接入数据' : '已导入环境数据'

  return <>
    {context}
    <div className="gh-access-strip" id={`gh-access-${greenhouse.id}`}>
      <strong className="gh-access-label">接入管理</strong>
      <div className="gh-access-source"><span>数据来源</span><p><DatabaseOutlined />{source}<i className={`gh-state-dot ${greenhouse.data_status === 'current' ? 'is-current' : ''}`} /></p><Button type="link" onClick={() => setPanel('data')}>配置数据 <ArrowRightOutlined /></Button></div>
      <div className="gh-access-devices"><span>已接入设备</span><p><ApiOutlined />{error ? '暂时无法读取' : loading ? '正在读取…' : devices.length ? `${devices.length} 台设备 · ${devices.filter(d => d.online).length} 台近期上报` : '暂无绑定设备'}</p><Button type="link" onClick={() => setPanel('devices')}>管理设备 <ArrowRightOutlined /></Button></div>
    </div>
    <Drawer title={`${greenhouse.name} · ${panel === 'devices' ? '设备接入' : '数据接入'}`} open={panel !== null} onClose={() => { setPanel(null); onPanelClose() }} width={560} className="gh-connection-drawer">
      {panel === 'data' ? <>
        <section className="gh-drawer-section"><h3>导入已有数据</h3><p>将历史环境记录导入当前大棚，上传后先校验再确认。</p><Space wrap><Button type="primary" disabled={!canManage()} onClick={() => setImportOpen(true)}>选择文件导入</Button><Button onClick={downloadEnvironmentTemplate}>下载导入模板</Button></Space><small>CSV、XLSX、XLSM · 最大 10MB</small></section>
        <section className="gh-drawer-section"><h3>接入实时设备</h3><p>通过现有采集接口上报，数据归属到当前大棚。登记设备后，还需在采集端配置接口与认证。</p><Button icon={<PlusOutlined />} onClick={() => setPanel('devices')}>绑定与配置设备</Button></section>
      </> : <>
        {isGuestMode() && <p className="gh-drawer-note">当前为示例设备，登记仅保存在本次浏览器会话。</p>}
        <p className="gh-drawer-note">在线依据：最近 2 小时收到采集记录。登记成功不代表设备已连接。</p>
        {error ? <Alert type="error" message="设备读取失败" description={error} action={<Button onClick={() => void load()}>重试</Button>} /> : <Spin spinning={loading}><div className="gh-device-list">{devices.map(device => <div className="gh-device-row" key={device.device_id}><div><strong>{device.name}</strong><code>{device.device_id}</code><small>{device.last_seen ? `最近上报 ${new Date(device.last_seen).toLocaleString('zh-CN')}` : '尚无上报记录'}</small></div><div><Tag color={device.online ? 'green' : 'default'}>{device.online ? '近期在线' : device.last_seen ? '离线 / 待同步' : '待上报'}</Tag>{device.registered && <Popconfirm title="移除设备登记？历史数据将保留。" onConfirm={() => void remove(device.device_id)}><Button type="text" danger size="small" disabled={!canManage()}>移除登记</Button></Popconfirm>}</div></div>)}{!loading && !devices.length && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="还没有设备，先登记设备编号" />}</div></Spin>}
        <section className="gh-drawer-section"><h3>绑定设备</h3><Form name={`gh-device-${greenhouse.id}`} form={form} layout="vertical" onFinish={values => void save(values)} initialValues={{ kind: 'environment' }} disabled={!canManage()}>
          <Form.Item name="device_id" label="设备编号" rules={[{ required: true, message: '请输入设备编号' }, { pattern: /^[A-Za-z0-9_.:-]{1,80}$/, message: '使用字母、数字、下划线、点、冒号或短横线，最多80位' }]}><Input placeholder="SENSOR-001" /></Form.Item>
          <Form.Item name="name" label="设备名称" rules={[{ required: true, whitespace: true, message: '请输入设备名称' }, { max: 80 }]}><Input placeholder="东侧温湿度传感器" /></Form.Item>
          <Form.Item name="kind" label="设备类型"><Select options={kinds} /></Form.Item><Button type="primary" htmlType="submit" loading={saving}>保存设备登记</Button>
        </Form></section>
      </>}
      <details className="gh-ingest-details"><summary>采集接口与配置示例</summary><p>目标大棚编码 <code>{greenhouse.code}</code></p><p><code>POST {ingest?.endpoint ?? '/api/v1/ingest/sensor-data'}</code></p><p>认证：所属组织的 Bearer Token；单组织部署可由管理员配置 X-Sensor-Key。此处不展示密钥。</p><pre>{sample}</pre><Space wrap><Button onClick={() => void copy(sample)}>复制上报示例</Button><Button onClick={() => void copy(greenhouse.code)}>复制大棚编码</Button></Space><p>示例仅用于配置说明，不会自动发送测量数据。</p></details>
    </Drawer>
    <EnvironmentDataImport open={importOpen} defaultGreenhouseId={greenhouse.id} onClose={() => setImportOpen(false)} onImported={() => { onChange(); window.dispatchEvent(new Event('greenhouses-changed')) }} />
  </>
}
