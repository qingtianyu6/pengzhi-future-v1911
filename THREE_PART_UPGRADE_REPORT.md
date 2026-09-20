# 棚智未来｜三项深化升级完成说明

本版本围绕三个目标完成：

1. **纯图片与 UI 完全分离**
2. **全站字体与间距统一**
3. **把核心交互真正做起来**

## 1. 纯图片与 UI 完全分离

### 已完成
- 首页 Hero 改为高清纯温室照片，光照 / 温度 / 湿度数据卡改为前端 DOM 组件。
- 平台介绍 Hero 改为纯温室照片 + CSS/React 电脑端与手机端界面 Mockup。
- “平台能做什么”区域改为纯温室照片背景，4 个功能热点由 DOM/CSS 渲染。
- 核心功能 Hero 改为纯温室照片 + React Dashboard Mockup。
- 技术亮点 Hero 改为纯传感器照片，数据卡改为 DOM；数据分层、算法趋势图改为 CSS/SVG/React 组件。
- 应用场景 Hero、区域基地、页尾全部使用纯场景照片，功能与收益仍由 DOM 卡片渲染。
- 项目成果 Hero 改为纯温室照片，12 / 850 / 320+ / 18.6% 数据卡由真实 DOM 动画渲染；成果总览里的平台界面改为 Dashboard Mockup；荣誉区改为 DOM 证书组件。
- 所有官网页 Footer 口号均由 HTML/CSS 渲染，不再烘焙在图片里。
- 删除已不再使用的“带文字 / UI 的旧运行素材”，保留设计参考图用于对照。

### 新增核心组件
- `src/components/MarketingVisuals.tsx`
- `src/components/MarketingVisuals.css`

包括：
- `DashboardMockup`
- `PhoneMockup`
- `DataCard`
- `MiniLayerStack`
- `TrendMiniChart`
- `CertificateStrip`

## 2. 全站字体与间距统一

### 新增统一视觉 Token
位于 `src/styles.css`：
- `--font-sans`
- `--font-display`
- `--site-green`
- `--site-deep`
- `--site-ink`
- `--site-muted`
- `--site-line`
- `--site-radius`
- `--site-container`
- `--site-pad`
- `--space-xs/sm/md/lg/xl/section`

### 统一策略
- 导航、正文、数据、按钮：统一现代中文无衬线字体栈。
- 品牌大标题 / 少量手写感标题：统一 `--font-display`。
- 页面左右留白统一通过 `--site-pad` 控制。
- Marketing 页面共同使用统一色彩、卡片、阴影、Hover 与 section 密度。
- Ant Design 全局字体同步到统一字体栈。

## 3. 核心交互已真正实现

### 全站
- 顶部搜索按钮已可点击。
- 打开站内搜索浮层。
- 支持实时过滤“首页 / 平台介绍 / 核心功能 / 技术亮点 / 应用场景 / 项目成果”。
- 点击结果跳转并自动关闭；Esc 关闭。

### 核心功能页
#### 环境监测
- 温度 / 湿度 / 光照三个指标可点击切换。
- ECharts 曲线会跟随指标更新。
- Tooltip、纵轴范围、颜色会同步切换。

#### 病害识别
- 支持点击上传真实本地图片。
- 上传后本地即时预览。
- 有“正在识别”状态。
- 完成后更新识别名称、置信度与管理建议。

#### 农事管理
- “新建记录”按钮可展开表单。
- 可填写农事名称、时间、区域。
- 保存后立即加入农事记录。
- 支持导出 CSV。

#### 智能决策
- “重新分析当前大棚”按钮可重新生成一组建议。

#### 数据沉淀
- “导出当前记录”可直接下载 CSV。

## 高清纯素材
新增 `src/assets/pure-scenes/`，运行素材全部可正常解码，无截断 PNG。
主要素材分辨率：
- greenhouse-wide：2400×1200
- sensor-clean：1400×1100
- disease-gallery：1600×850
- disease-phone：1200×900
- strawberry / flower / seedling：1800×1000
- regional-base-clean：1800×900

## 校验
- `tsc -p tsconfig.json --noEmit`：通过（0 错误）
- 后端 `python -m compileall`：通过
- 运行图片完整性扫描：0 张损坏 / 截断图片
- 页面代码中不再引用旧的 Hero / Footer / UI 烘焙素材

## 本地运行
前端：
```bash
cd frontend
npm install
npm run dev
```

后端：
```bash
cd backend
pip install -r requirements.txt
python run.py
```

> 当前交付包不包含 `node_modules`，避免携带残缺依赖；请在正常联网环境中执行 `npm install`。
