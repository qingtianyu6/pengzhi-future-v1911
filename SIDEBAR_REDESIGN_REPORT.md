# 棚智未来后台侧栏重构说明（v1.5）

本轮只针对管理后台的左侧导航与工作区上下文进行商业化重构，没有改变业务页面的数据逻辑。

## 已完成

- 展开宽度由 248px 调整为 240px，收起宽度由 76px 调整为 72px。
- 品牌区高度压缩到 74px，Logo 36px，弱化英文副标题，降低顶部视觉重量。
- 当前大棚从静态信息卡升级为 Workspace Switcher：
  - 点击可切换已存在的大棚；
  - 切换后会把 `greenhouse_id` 写入当前 URL；
  - 末尾提供“管理大棚”入口；
  - 收起状态显示大棚首字并提供 Tooltip。
- 导航信息架构由“概览 / 生产”调整为“工作台 / 生产管理”。
- Active 状态重做为 3px 品牌绿左侧指示线 + 低透明浅绿底，不再使用厚重实色块。
- 普通菜单文字与图标降低视觉权重；Hover 与 Active 使用不同层级反馈。
- 侧栏底部重构为工具区：系统状态、返回官网、帮助中心、系统设置、账户摘要。
- 折叠状态针对品牌、工作区、菜单、底部工具分别做了专门样式，不再只是机械缩窄。
- 新增 Workspace Dropdown 样式，列表显示大棚名称、编号、品种/位置。
- 侧栏背景从单一深绿改为非常轻的纵向深绿渐变，减少“黑绿色整块”的压迫感。

## 主要设计参数

- Sidebar: `#0B3B2E → #0A342A`
- Active: `rgba(61,214,156,.085)`
- Active indicator: `#3DD69C`
- Expanded width: `240px`
- Collapsed width: `72px`
- Menu row: `42px`
- Logo: `36px`
- Workspace radius: `12px`
- Menu radius: `9px`

## 涉及文件

- `frontend/src/layouts/AppLayout.tsx`
- `frontend/src/styles.css`

## 验证说明

当前容器没有项目完整 `node_modules`，因此不能声称执行了完整 Vite build。已使用全局 TypeScript 解析修改文件；输出仅出现缺失第三方依赖类型的错误，没有出现本轮修改引入的 TS 语法错误。
