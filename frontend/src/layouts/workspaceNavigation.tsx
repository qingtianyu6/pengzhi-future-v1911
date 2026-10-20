import type { ReactNode } from 'react'
import { AppstoreOutlined, HomeOutlined, LineChartOutlined, CheckCircleOutlined,
  FileSearchOutlined, ExperimentOutlined, ReadOutlined, CommentOutlined, DatabaseOutlined,
  DashboardOutlined, SettingOutlined, BankOutlined, BuildOutlined } from '@ant-design/icons'

export interface WorkspaceItem { key: string; label: string; icon: ReactNode; description: string }
export interface WorkspaceGroup {
  id: string; label: string; subtitle: string; icon: ReactNode; items: WorkspaceItem[]
}

// One route belongs to one workspace. Existing URLs and business records stay intact.
export const workspaceGroups: WorkspaceGroup[] = [
  { id: 'overview', label: '生产工作台', subtitle: '看清今日棚况，抓住需要处理的事', icon: <HomeOutlined />, items: [
    { key: '/platform', label: '生产总览', icon: <HomeOutlined />, description: '环境指标、重点预警与今日待办' },
  ] },
  { id: 'greenhouse', label: '大棚管理', subtitle: '把大棚、种植批次与设备数据放在一起管理', icon: <BankOutlined />, items: [
    { key: '/platform/data', label: '大棚管理', icon: <DatabaseOutlined />, description: '创建大棚、管理种植批次、数据与设备接入' },
  ] },
  { id: 'digital-twin', label: '三维大棚', subtitle: '查看空间布局与大棚状态', icon: <BuildOutlined />, items: [
    { key: '/platform/3d', label: '三维大棚', icon: <AppstoreOutlined />, description: '查看空间布局、大棚状态与设备交互' },
  ] },
  { id: 'environment', label: '环境监测', subtitle: '从实时变化到预警处置，持续关注生长环境', icon: <LineChartOutlined />, items: [
    { key: '/platform/environment', label: '环境监测', icon: <LineChartOutlined />, description: '实时监测、历史趋势、未来预测与预警处置' },
  ] },
  { id: 'diagnosis', label: '棚智探因', subtitle: '问题、叶片、证据与动态排查', icon: <FileSearchOutlined />, items: [
    { key: '/platform/investigate', label: '棚智探因', icon: <FileSearchOutlined />, description: '异常描述、叶片识别、自主排查与调查记录' },
  ] },
  { id: 'production', label: '生产管理', subtitle: '把处理建议落到任务，让生产经验持续积累', icon: <CheckCircleOutlined />, items: [
    { key: '/platform/production', label: '农事执行', icon: <CheckCircleOutlined />, description: '管理建议、农事任务与执行记录' },
    { key: '/platform/autonomy', label: '棚智自治', icon: <ExperimentOutlined />, description: '温室模拟调控、策略比较与设备适配' },
    { key: '/platform/research', label: 'AI 研究台', icon: <ExperimentOutlined />, description: '作物观察、生产研究、农艺技能与目标编排' },
  ] },
  { id: 'knowledge', label: '知识社区', subtitle: '查可靠资料，读农业资讯，与棚友交流经验', icon: <ReadOutlined />, items: [
    { key: '/platform/knowledge', label: '农业知识库', icon: <ReadOutlined />, description: '文档导入、知识检索与来源追溯' },
    { key: '/platform/news', label: '棚智农讯', icon: <DashboardOutlined />, description: '农业资讯、关注主题与每日简报' },
    { key: '/platform/forum', label: '棚友论坛', icon: <CommentOutlined />, description: '种植求助、农事经验与研究讨论' },
  ] },
]

export const managementGroup: WorkspaceGroup = {
  id: 'management', label: '系统设置', subtitle: '了解平台 AI 的调用表现与运行状态', icon: <SettingOutlined />, items: [
    { key: '/platform/ai-quality', label: 'AI 能力与运行', icon: <ExperimentOutlined />, description: '调用追踪、工具执行与能力评测' },
  ],
}
export const allWorkspaceGroups = [...workspaceGroups, managementGroup]
export const navigationItems = allWorkspaceGroups.flatMap(group => group.items)

export function resolveWorkspace(pathname: string, search: string) {
  const path = pathname.replace(/\/$/, '')
  const view = new URLSearchParams(search).get('view')
  const matches = navigationItems.filter(item => item.key.split('?')[0] === path)
  const item = matches.find(item => item.key.includes('?') && new URLSearchParams(item.key.split('?')[1]).get('view') === view)
    ?? matches.find(item => !item.key.includes('?'))
  return { item, group: allWorkspaceGroups.find(group => item && group.items.includes(item)) }
}

/** Carry only shared context; route-specific tabs/filters must not leak to another page. */
export function workspaceHref(target: string, search: string) {
  const [path, query] = target.split('?')
  const source = new URLSearchParams(search)
  const params = new URLSearchParams(query)
  for (const key of ['greenhouse_id', 'mode']) {
    const value = source.get(key)
    if (value && !params.has(key)) params.set(key, value)
  }
  if (path === '/platform/research' && source.get('batch_id')) params.set('batch_id', source.get('batch_id')!)
  return `${path}${params.size ? `?${params}` : ''}`
}
