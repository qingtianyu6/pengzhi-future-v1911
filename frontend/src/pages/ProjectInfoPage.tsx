import { CheckCircleFilled, CloudOutlined, DatabaseOutlined, FileSearchOutlined, LineChartOutlined, MedicineBoxOutlined, RobotOutlined, SafetyCertificateOutlined, ScheduleOutlined } from '@ant-design/icons'
import { Button } from 'antd'
import { Link, useLocation } from 'react-router-dom'

const capabilityCards = [
  [<DatabaseOutlined />, '统一数据接入', '集中管理大棚档案、种植批次与环境数据，支持 CSV / Excel 导入和传感器 HTTP 接入。'],
  [<LineChartOutlined />, '环境智能研判', '从历史趋势、数据健康度到未来 1—6 小时预测，及时发现环境风险。'],
  [<MedicineBoxOutlined />, '病害辅助识别', '上传番茄叶片图片，输出六分类识别结果、Top-3 候选与人工复核建议。'],
  [<ScheduleOutlined />, '农事任务闭环', '将预警与建议转化为可追踪任务，记录执行反馈，沉淀生产证据链。'],
  [<RobotOutlined />, '棚小智 AI 助手', '结合大棚业务数据和本地农业知识，为管理人员提供可解释的辅助分析。'],
]

const configs: Record<string, { kicker: string; title: string; lead: string; body?: string }> = {
  '/introduction': { kicker: 'PLATFORM INTRODUCTION', title: '让数据成为种植管理的生产力', lead: '棚智未来面向设施农业生产现场，把依赖经验的分散管理转化为可观察、可分析、可执行、可追溯的数字化流程。', body: '传统大棚管理常常面临环境数据分散、异常发现滞后、病害判断依赖经验、农事记录不连续等问题。平台通过统一的数据底座与业务工作台，让每一次数据变化都有机会转化为更及时的管理动作。' },
  '/features': { kicker: 'CORE CAPABILITIES', title: '五大工作台，连接真实生产流程', lead: '不是概念展示，而是覆盖数据接入、智能研判、病害辅助识别与任务执行的真实业务系统。' },
  '/highlights': { kicker: 'TECHNOLOGY HIGHLIGHTS', title: '从“看见数据”到“理解与行动”', lead: '平台的价值不只在于呈现图表，而在于帮助使用者理解数据、发现问题、形成任务，并提供有边界的智能辅助。' },
  '/scenarios': { kicker: 'APPLICATION SCENARIOS', title: '为不同农业管理现场而设计', lead: '无论是单一经营主体、合作社还是示范园区，棚智未来都能以统一的数字化语言连接种植过程。' },
} as const

export default function ProjectInfoPage() {
  const { pathname } = useLocation()
  const config = configs[pathname] ?? configs['/introduction']
  const is = (path: string) => pathname === path
  return <>
    <section className="site-page-hero"><p>{config.kicker}</p><h1>{config.title}</h1><span>{config.lead}</span><Link to="/platform"><Button type="primary" size="large">进入真实管理平台</Button></Link></section>
    {is('/introduction') && <section className="site-page-content"><div className="narrative-grid"><article><b>为什么做？</b><h2>让管理不再只靠经验</h2><p>{config.body}</p></article><article><b>怎么解决？</b><h2>构建统一智慧大棚平台</h2><p>以大棚和种植批次为业务主线，连接环境记录、预测预警、病害图片、决策建议与农事任务。</p></article><article><b>形成什么？</b><h2>一个持续运转的业务闭环</h2><p>数据采集 → 环境分析 → 异常发现 → 病害识别 → 农事任务 → AI 辅助决策。</p></article></div></section>}
    {is('/features') && <section className="site-page-content"><div className="feature-grid page-feature-grid">{capabilityCards.map(([icon, title, text], index) => <article className="feature-card" key={title as string}><div className="feature-icon">{icon}</div><b>0{index + 1}</b><h3>{title}</h3><p>{text}</p></article>)}</div></section>}
    {is('/highlights') && <section className="site-page-content"><div className="detail-list">{[['多源数据融合', '环境数据、作物信息、病害图片和农事记录进入统一业务体系。'], ['智能病害识别', '基于图像模型给出叶片病害辅助判断，低置信结果进入人工复核。'], ['数据驱动决策', '由环境异常和分析结果进一步形成建议与处置路径。'], ['农事闭环追溯', '任务创建、执行反馈与决策证据形成可回溯的生产过程。']].map(([title, text], index) => <article key={title}><b>0{index + 1}</b><div><h2>{title}</h2><p>{text}</p></div><CheckCircleFilled /></article>)}</div></section>}
    {is('/scenarios') && <section className="site-page-content"><div className="scenario-grid"><article><CloudOutlined /><h3>家庭农场</h3><p>帮助经营者管理多个棚区，减少重复巡查与经验盲区。</p></article><article><SafetyCertificateOutlined /><h3>农业合作社</h3><p>统一查看基地环境、作物状态与农事执行进度。</p></article><article><FileSearchOutlined /><h3>智慧农业示范园</h3><p>集中掌握环境、病害和农事信息，沉淀数字化管理样板。</p></article></div></section>}
  </>
}
