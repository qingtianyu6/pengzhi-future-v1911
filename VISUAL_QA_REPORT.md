# 棚智未来官网｜六页面深度精修与视觉 QA 报告

本轮按照“统一字体 → 统一字号 → 统一 Section 密度 → 清除素材自带文字/UI 与代码层重复 → 逐页视觉比对”的顺序继续深化。

## 1. 本轮处理范围

已继续精修六个官网页面：

- 首页
- 平台介绍
- 核心功能
- 技术亮点
- 应用场景
- 项目成果

公共导航栏继续复用同一套 `SiteLayout`，不为各页面重复造导航组件。

## 2. 统一视觉规则

### 字体
正文、导航、卡片统一优先使用：

`Noto Sans CJK SC / HarmonyOS Sans SC / PingFang SC / Microsoft YaHei UI / Microsoft YaHei`

主视觉中需要书写感的标题优先使用系统楷体栈，不打包或分发字体文件：

`STKaiti / KaiTi / Noto Serif CJK SC`

### 页面密度
- 缩短 Marketing Hero 的无效高度。
- 压缩重复的大块留白。
- 统一 Section 上下间距、标题层级和内容最大宽度。
- 卡片阴影进一步减弱，保持农业品牌官网而非 AI 科技大屏的感觉。

### 动效原则
保留滚动淡入、轻微 stagger、hover 上移、图片轻微缩放和真实图表动画；不加入粒子、霓虹、扫描线等会破坏参考设计的效果。

## 3. 分页面深化情况

### 首页
- 延续上一轮精修成果。
- 导航、Logo 比例、主标题、按钮、功能入口及 Hero 过渡保持已校准状态。
- `visual_qa/home_refined_1672x941.png` 为当前桌面检查图。

### 平台介绍
- 统一为更接近参考稿的现代中文无衬线字体。
- 缩短 Hero 与各 Section 的纵向留白。
- “平台能做什么”场景素材本身已包含热点/文字，因此清理代码层重复热点，避免双重 UI。
- 页尾素材本身已有口号，隐藏重复 HTML 口号层。
- 当前离线视觉检查图：`visual_qa/platform_intro_deep_preview.png`。

### 核心功能
- 环境监测继续使用真实 ECharts 结构，离线 QA 截图中用静态 SVG 替代图表运行时，仅用于视觉检查。
- 病害识别重排为“拍照场景 / 识别结果 / 常见病害”三列，减少纵向冗余。
- 农事管理改为五个紧凑操作入口 + 右侧农事记录列表，更接近参考稿密度。
- “数据档案”调整为“数据沉淀”，改成历史查询、档案管理、可视化、导出四个轻量入口。
- 页尾清理重复 HTML 文案，仅保留素材中的视觉口号。
- 当前离线视觉检查图：`visual_qa/core_functions_deep_preview.png`。

### 技术亮点
- Hero 素材本身已有手写说明，清理代码层重复手写文案。
- 五个技术 Section 缩短高度，放大关键标题与视觉元素，减少“文档页”感。
- 页尾素材自带品牌文案，清理重复 HTML 文案。
- 1440px 离线预览总高度约 2242px；参考稿按宽度等比换算约 2160px，页面纵向节奏已较接近。
- 当前检查图：`visual_qa/tech_highlights_deep_preview.png`。

### 应用场景
- 调整场景照片、能力卡和收益区比例，改善此前“页面偏薄、卡片偏小”的问题。
- 清除 Hero 和 Footer 素材中已存在的手写文案与代码层重复。
- 保留蔬菜、水果、花卉、育苗、规模化基地五类场景及地图区域。
- 1440px 离线预览总高度约 2238px；参考稿等比约 2160px。
- 当前检查图：`visual_qa/application_scenarios_deep_preview.png`。

### 项目成果
- 重点修复 Hero “12 / 850 / 320+ / 18.6%”成果卡被素材和 DOM 重复渲染的问题。
- 清理重复 Hero 手写字、荣誉区重复标签和 Footer 重复文案。
- 保留成果总览、技术成果、应用成效、荣誉认可、未来展望五段结构。
- 1440px 离线预览总高度约 2123px；参考稿等比约 2160px，纵向密度已非常接近。
- 当前检查图：`visual_qa/project_results_deep_preview.png`。

> 注意：设计图中的基地数量、服务用户、增产率、奖项/论文等数字可能属于视觉演示数据。上线前应以项目真实材料替换，不建议将未经核实的演示数字作为真实项目成果发布。

## 4. Overlay / Difference 检查

`visual_qa/` 中包含平台介绍、核心功能、技术亮点、应用场景、项目成果的：

- `*_deep_preview.png`：当前离线渲染预览
- `*_overlay_50pct.png`：设计参考与实际预览 50% 叠加
- `*_difference.png`：差异增强图
- `*_reference_vs_actual.png`：左右对照图

首页保留上一轮的：

- `home_actual_1672x941.png`
- `home_overlay_50pct.png`
- `home_difference.png`
- `home_mobile_430.png`

这些图用于继续做位置、字号、图片比例和 Section 高度的人工校准，不应作为网页内容引用。

## 5. 代码完整性检查

已对以下 TSX 执行 TypeScript `transpileModule` 语法诊断，全部通过：

- `PlatformIntroductionPage.tsx`
- `CoreFunctionsPage.tsx`
- `TechHighlightsPage.tsx`
- `ApplicationScenariosPage.tsx`
- `ProjectResultsPage.tsx`
- `SiteLayout.tsx`

后端已执行：

```bash
python -m compileall -q .
```

检查通过。

另外检查了 `frontend/src`：最终页面没有直接 import `design-references/*.png` 作为整页网页背景，参考稿仍只用于 QA/对照。

## 6. 当前环境限制

上传源码包中的 `frontend/node_modules` 并不完整，因此当前容器不能进行可信的完整 `npm run build`。本轮没有把“离线截图能显示”冒充成 Vite 完整构建通过。

在正常开发机上请执行：

```bash
cd frontend
npm install
npm run build
npm run dev
```

后端：

```bash
cd backend
pip install -r requirements.txt
python run.py
```

## 7. 当前仍可继续微调的细节

如果继续追求像素级极限复刻，下一轮优先级建议为：

1. 平台介绍：进一步校准 Hero 字体换行和 Section 总高度。
2. 核心功能：继续压缩约 8%～10% 的纵向高度，重点是环境监测与农事管理区。
3. 技术亮点 / 应用场景：只做 1～3px 级间距和字号微调，不再改结构。
4. 项目成果：结构和密度已经接近参考，主要剩字体抗锯齿和素材裁切细节。
5. 全站最终在真实 Vite/Chromium 环境用参考尺寸再做一轮 Overlay。

本轮目标是“深化已有实现”，没有重新设计页面结构。
