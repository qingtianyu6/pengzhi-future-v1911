import { useEffect, useState } from 'react'
import { Alert, Button, Drawer, Form, Input, Modal, Select, Space, Switch, Table, Tabs, message } from 'antd'
import { apiClient, getApiErrorMessage } from '../api/client'
import { changePassword, getStoredUser, type AuthUser } from '../api/authApi'
import type { ApiResponse } from '../types/api'

const roles = [{ value: 'admin', label: '管理员' }, { value: 'agronomist', label: '农技人员' }, { value: 'executor', label: '执行人员' }, { value: 'observer', label: '观察员' }]
export default function AccountSettings({ open, onClose }: { open: boolean; onClose: () => void }) {
  const user = getStoredUser(), [members, setMembers] = useState<AuthUser[]>([])
  const [busy, setBusy] = useState(false), [reset, setReset] = useState<AuthUser | null>(null)
  const [password, setPassword] = useState(''), [error, setError] = useState<string | null>(null)
  const [msg, holder] = message.useMessage(), [form] = Form.useForm()
  const load = async () => {
    try { const response = await apiClient.get<ApiResponse<AuthUser[]>>('/auth/members'); setMembers(response.data.data); setError(null) }
    catch (e) { setError(getApiErrorMessage(e)) }
  }
  useEffect(() => { if (open && user?.role === 'admin') void apiClient.get<ApiResponse<AuthUser[]>>('/auth/members').then(r => setMembers(r.data.data)).catch(e => setError(getApiErrorMessage(e))) }, [open, user?.role])
  const update = async (member: AuthUser, patch: Record<string, unknown>) => {
    setBusy(true)
    try { await apiClient.patch(`/auth/members/${member.id}`, patch); msg.success('成员设置已更新'); await load() }
    catch (e) { msg.error(getApiErrorMessage(e)) } finally { setBusy(false) }
  }
  return <Drawer title="账户与团队" width="min(820px, 100vw)" open={open} onClose={onClose} destroyOnHidden>
    {holder}
    <Tabs items={[
      { key: 'password', label: '修改密码', children: <Form layout="vertical" onFinish={async values => {
        setBusy(true)
        try { await changePassword(values.current_password, values.new_password); msg.success('密码已更新，其他登录会话已退出'); onClose() }
        catch (e) { msg.error(getApiErrorMessage(e)) } finally { setBusy(false) }
      }}>
        <Alert type="info" showIcon message="修改密码后，其他设备的登录会话会失效。" style={{ marginBottom: 20 }} />
        <Form.Item name="current_password" label="当前密码" rules={[{ required: true }]}><Input.Password autoComplete="current-password" /></Form.Item>
        <Form.Item name="new_password" label="新密码" rules={[{ required: true }, { min: 8 }, { max: 72 }]}><Input.Password autoComplete="new-password" /></Form.Item>
        <Form.Item name="confirm" label="确认新密码" dependencies={['new_password']} rules={[{ required: true }, ({ getFieldValue }) => ({ validator(_, value) { return value === getFieldValue('new_password') ? Promise.resolve() : Promise.reject(new Error('两次密码不一致')) } })]}><Input.Password autoComplete="new-password" /></Form.Item>
        <Button type="primary" htmlType="submit" loading={busy}>更新密码</Button>
      </Form> },
      ...(user?.role === 'admin' ? [{ key: 'members', label: '团队成员', children: <>
        {error && <Alert type="error" message={error} />}
        <Table rowKey="id" dataSource={members} pagination={false} scroll={{ x: 640 }} columns={[
          { title: '姓名', dataIndex: 'display_name' }, { title: '手机号', dataIndex: 'phone' },
          { title: '角色', render: (_, row) => <Select value={row.role} options={roles} disabled={busy || row.id === user.id} style={{ width: 115 }} onChange={role => void update(row, { role })} /> },
          { title: '启用', render: (_, row) => <Switch checked={row.is_active !== false} disabled={busy || row.id === user.id} onChange={is_active => void update(row, { is_active })} /> },
          { title: '操作', render: (_, row) => <Button disabled={row.id === user.id} onClick={() => { setReset(row); setPassword('') }}>重置密码</Button> },
        ]} />
        <h3 style={{ marginTop: 28 }}>添加团队成员</h3>
        <Form form={form} layout="vertical" onFinish={async values => {
          setBusy(true)
          try { await apiClient.post('/auth/members', values); msg.success('成员已添加'); form.resetFields(); await load() }
          catch (e) { msg.error(getApiErrorMessage(e)) } finally { setBusy(false) }
        }} initialValues={{ role: 'observer' }}>
          <Form.Item name="display_name" label="姓名" rules={[{ required: true }, { min: 2 }]}><Input /></Form.Item>
          <Form.Item name="phone" label="手机号" rules={[{ required: true }, { pattern: /^1\d{10}$/, message: '请输入11位手机号' }]}><Input maxLength={11} /></Form.Item>
          <Form.Item name="password" label="初始密码" rules={[{ required: true }, { min: 8 }, { max: 72 }]}><Input.Password autoComplete="new-password" /></Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true }]}><Select options={roles} /></Form.Item>
          <Space><Button type="primary" htmlType="submit" loading={busy}>添加成员</Button><Button onClick={() => void load()}>刷新成员</Button></Space>
        </Form>
      </> }] : []),
    ]} />
    <Modal title={`重置${reset?.display_name || ''}的密码`} open={Boolean(reset)} onCancel={() => setReset(null)} okButtonProps={{ disabled: password.length < 8 || password.length > 72 }} onOk={async () => { if (reset) { await update(reset, { new_password: password }); setReset(null) } }}>
      <p>核实成员身份后设置新密码，原登录会话将失效。</p><Input.Password value={password} onChange={e => setPassword(e.target.value)} autoComplete="new-password" placeholder="至少8位" />
    </Modal>
  </Drawer>
}
