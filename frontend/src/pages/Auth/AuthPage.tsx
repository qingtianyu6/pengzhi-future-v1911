import { useState } from 'react'
import {
  ArrowLeftOutlined, CheckCircleFilled, EyeInvisibleOutlined, EyeTwoTone,
  LockOutlined, PhoneOutlined, SafetyCertificateOutlined, TeamOutlined, UserOutlined,
} from '@ant-design/icons'
import { Button, Checkbox, Form, Input, Typography, message } from 'antd'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { getApiErrorMessage } from '../../api/client'
import { loginAccount, registerAccount } from '../../api/authApi'
import './AuthPage.css'

type LoginValues = { phone: string; password: string; remember_me?: boolean }
type RegisterValues = LoginValues & {
  display_name: string
  organization?: string
  confirm_password: string
  agreement: boolean
}

function BrandMark() {
  return <svg viewBox="0 0 72 72" aria-hidden="true"><path d="M11 54V27L36 10l25 17v27"/><path d="M7 60c14-2 25-6 34-13 8-6 13-13 18-23"/><path d="M15 54c3-18 16-29 38-31-2 18-13 29-31 31-3 0-5 0-7 0Z"/><path d="M16 55c9-11 19-18 31-24"/></svg>
}

export default function AuthPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const [messageApi, contextHolder] = message.useMessage()
  const [submitting, setSubmitting] = useState(false)
  const isRegister = location.pathname === '/register'

  const submitLogin = async (values: LoginValues) => {
    setSubmitting(true)
    try {
      await loginAccount({ ...values, remember_me: Boolean(values.remember_me) })
      messageApi.success('登录成功，正在进入管理平台')
      navigate('/platform', { replace: true })
    } catch (error) {
      messageApi.error(getApiErrorMessage(error))
    } finally { setSubmitting(false) }
  }

  const submitRegister = async (values: RegisterValues) => {
    setSubmitting(true)
    try {
      await registerAccount({
        display_name: values.display_name,
        phone: values.phone,
        organization: values.organization,
        password: values.password,
      })
      messageApi.success('注册成功，欢迎加入棚智未来')
      navigate('/platform', { replace: true })
    } catch (error) {
      messageApi.error(getApiErrorMessage(error))
    } finally { setSubmitting(false) }
  }

  return <main className="auth-page">
    {contextHolder}
    <section className="auth-scene" aria-label="智慧温室场景">
      <div className="auth-scene-overlay" />
      <Link className="auth-brand" to="/home"><BrandMark/><span><strong>棚智未来</strong><small>让农业更有未来</small></span></Link>
      <div className="auth-scene-copy">
        <span className="auth-kicker">SMART GREENHOUSE PLATFORM</span>
        <h1>让每一座大棚<br/>拥有智慧生长力</h1>
        <p>连接环境数据、智能研判与农事执行，让生产管理更清晰、更及时、更可追溯。</p>
        <div className="auth-scene-points">
          <span><CheckCircleFilled/>多源数据统一感知</span>
          <span><CheckCircleFilled/>风险与病害辅助研判</span>
          <span><CheckCircleFilled/>农事任务闭环追踪</span>
        </div>
      </div>
      <div className="auth-scene-status"><i/><span>系统服务正常</span><b>数据持续同步</b></div>
    </section>

    <section className="auth-form-area">
      <Link className="auth-back" to="/home"><ArrowLeftOutlined/>返回首页</Link>
      <div className="auth-form-wrap">
        <div className="auth-form-heading">
          <span>{isRegister ? 'CREATE ACCOUNT' : 'WELCOME BACK'}</span>
          <h2>{isRegister ? '创建您的账号' : '登录管理平台'}</h2>
          <p>{isRegister ? '填写基本信息，开始管理您的智慧大棚。' : '使用已注册手机号继续访问您的工作台。'}</p>
        </div>

        {isRegister ? <Form<RegisterValues> layout="vertical" requiredMark={false} onFinish={(values) => void submitRegister(values)}>
          <div className="auth-two-columns">
            <Form.Item name="display_name" label="姓名" rules={[{ required: true, message: '请输入姓名' }, { min: 2, max: 40 }]}>
              <Input size="large" prefix={<UserOutlined/>} placeholder="请输入姓名" autoComplete="name" />
            </Form.Item>
            <Form.Item name="phone" label="手机号" rules={[{ required: true, message: '请输入手机号' }, { pattern: /^1\d{10}$/, message: '请输入正确的11位手机号' }]}>
              <Input size="large" prefix={<PhoneOutlined/>} placeholder="用于登录平台" autoComplete="tel" maxLength={11} />
            </Form.Item>
          </div>
          <Form.Item name="organization" label="合作社或园区（选填）" rules={[{ max: 120 }]}>
            <Input size="large" prefix={<TeamOutlined/>} placeholder="例如：莘县现代农业示范园" />
          </Form.Item>
          <div className="auth-two-columns">
            <Form.Item name="password" label="设置密码" rules={[{ required: true, message: '请设置密码' }, { min: 8, message: '密码至少8位' }]}>
              <Input.Password size="large" prefix={<LockOutlined/>} placeholder="至少8位字符" autoComplete="new-password" iconRender={(visible) => visible ? <EyeTwoTone/> : <EyeInvisibleOutlined/>} />
            </Form.Item>
            <Form.Item name="confirm_password" label="确认密码" dependencies={['password']} rules={[{ required: true, message: '请再次输入密码' }, ({ getFieldValue }) => ({ validator(_, value) { return !value || getFieldValue('password') === value ? Promise.resolve() : Promise.reject(new Error('两次输入的密码不一致')) } })]}>
              <Input.Password size="large" prefix={<SafetyCertificateOutlined/>} placeholder="再次输入密码" autoComplete="new-password" />
            </Form.Item>
          </div>
          <Form.Item name="agreement" valuePropName="checked" rules={[{ validator: (_, checked) => checked ? Promise.resolve() : Promise.reject(new Error('请先阅读并同意服务协议')) }]}>
            <Checkbox>我已阅读并同意<a href="#service">《服务协议》</a>和<a href="#privacy">《隐私政策》</a></Checkbox>
          </Form.Item>
          <Button className="auth-submit" type="primary" htmlType="submit" size="large" loading={submitting}>注册并进入平台</Button>
          <p className="auth-switch">已有账号？<Link to="/login">立即登录</Link></p>
        </Form> : <Form<LoginValues> layout="vertical" requiredMark={false} initialValues={{ remember_me: true }} onFinish={(values) => void submitLogin(values)}>
          <Form.Item name="phone" label="手机号" rules={[{ required: true, message: '请输入手机号' }, { pattern: /^1\d{10}$/, message: '请输入正确的11位手机号' }]}>
            <Input size="large" prefix={<PhoneOutlined/>} placeholder="请输入注册手机号" autoComplete="tel" maxLength={11} />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password size="large" prefix={<LockOutlined/>} placeholder="请输入密码" autoComplete="current-password" iconRender={(visible) => visible ? <EyeTwoTone/> : <EyeInvisibleOutlined/>} />
          </Form.Item>
          <div className="auth-options"><Form.Item name="remember_me" valuePropName="checked" noStyle><Checkbox>保持登录状态</Checkbox></Form.Item><Typography.Link onClick={() => messageApi.info('请联系平台管理员重置密码')}>忘记密码？</Typography.Link></div>
          <Button className="auth-submit" type="primary" htmlType="submit" size="large" loading={submitting}>登录管理平台</Button>
          <button className="auth-guest" type="button" onClick={() => navigate('/platform?mode=guest')}>暂不登录，以游客身份体验</button>
          <p className="auth-switch">还没有账号？<Link to="/register">免费注册</Link></p>
        </Form>}
      </div>
      <p className="auth-copyright">© 2026 棚智未来 · 设施农业智能监测与决策平台</p>
    </section>
  </main>
}
