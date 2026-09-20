# 棚智未来 v1.9.2 核心功能整屏 Hero 改造说明

## 本轮目标
将“核心功能”页面首屏改为：**整屏高清温室摄影背景 + 左侧文字叠加 + 右侧真实 React DashboardMockup**。

## 已完成

- 首屏高度改为桌面端 `calc(100svh - 96px)`，即导航栏以下纵向铺满屏幕。
- 温室照片改为绝对定位整屏背景，采用 `object-fit: cover`，不再是右侧局部图片卡片。
- 新增左强右弱的白色渐变遮罩，保证左侧标题可读，同时保留右侧温室实景。
- 原有 DashboardMockup 保持 React DOM 渲染，悬浮在右侧，不把 UI 烘焙进图片。
- 五大功能改成无卡片横向信息条，减少“卡片堆积感”。
- CTA 改为“立即体验”。
- Dashboard 允许轻微浮动，但**背景照片完全不缩放、不漂移、不滤镜**，避免浏览器反复重采样导致发糊。
- 新增 SCROLL 提示，环境监测区增加锚点。

## 高清素材策略

运行时提供 WebP 多尺寸：

- `greenhouse-wide-1920.webp`
- `greenhouse-wide-2560.webp`
- `greenhouse-wide-3360.webp`

通过 `<picture> + srcSet + sizes="100vw"` 让浏览器按屏幕宽度选择合适资源。
原始 PNG 保留为 fallback。

> 说明：1920/2560/3360 版本基于当前清晰实景母图以 Lanczos + 极轻锐化生成，用于减少浏览器二次放大带来的软化；背景照片不再施加 CSS scale 动画。

## 响应式

- 桌面：左右 46/54 视觉结构，整屏背景。
- 900px 以下：仍保持摄影背景，但改为纵向内容；左侧遮罩改为上强下弱。
- 手机端：功能点横向滚动；Dashboard 放在文案下方；背景图依旧 cover。
- `prefers-reduced-motion` 下关闭 Dashboard 浮动。

## QA

`visual_qa/v19_2/` 中包含 1672×941 的视觉预览。
