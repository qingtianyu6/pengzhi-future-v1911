# 棚智未来 v1.9.6 · 四页统一参考图 Hero 高清版

## 本轮目标
以核心功能页最终确认的“第一参考图”作为统一视觉基准，将平台介绍、技术亮点、应用场景、项目成果四个营销页的首屏 Hero 统一为同一套构图。

## 统一规则
- 桌面端 Hero 固定 556px，高度与核心功能页一致，首屏自然露出下一节。
- 高清实景图全宽铺满 Hero，object-fit: cover；禁止照片 scale / breath / filter 动画。
- 左侧统一白色到透明渐变遮罩，文字直接压在照片上。
- 左侧内容基线：700px copy 区、57px 左右主标题、585px 正文宽度。
- 右侧只放真实 DOM / SVG / 数据卡，不把 UI 烘焙进照片。
- 平台介绍：Dashboard + 手机界面。
- 技术亮点：多源数据卡 + 分层技术架构。
- 应用场景：2×2 场景状态卡 + 场景说明条。
- 项目成果：2×2 成果数字卡。

## 高清素材
- greenhouse-wide：1920 / 2560 / 3360 WebP 响应式 Hero。
- sensor-clean：新增 1920 / 2560 / 3360 WebP 响应式 Hero。
- 首页 Hero 同样接入 1920 / 2560 / 3360 WebP。
- 站内主要摄影 PNG 统一提升到约 2200px 宽；头像类提升到 1600px 宽。
- 移除营销页图片 filter / scale 等可能触发浏览器额外重采样的效果。

## 代码改动
- `LandingPage.tsx/css`
- `PlatformIntroductionPage.css`
- `TechHighlightsPage.tsx/css`
- `ApplicationScenariosPage.tsx/css`
- `ProjectResultsPage.tsx/css`
- `MarketingShared.css`

## 版本
Frontend: 1.9.6
