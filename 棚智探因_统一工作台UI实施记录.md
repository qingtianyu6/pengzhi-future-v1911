# 棚智探因统一工作台

日期：2026-10-19。在 `V2-development` 本地现有代码上增量修改，未提交或推送 Git。

## 实际完成

- 将智能诊断的四个子入口整合为“棚智探因”：文字问题、叶片照片、证据分析、候选解释、主动观察与调查进展在一个页面衔接。
- 按确认的设计图调整米白底色、深绿模式切换、左侧问题与图片输入、中部证据和候选原因、贯穿右侧的浅绿自主排查面板；桌面分栏，手机纵向布局。
- 分析区域全部使用实际接口结果。没有调查时显示空状态；不填入示例病害概率、固定候选排名或虚构执行步骤。
- 图片既可单独发起调查，也可加入当前调查。复用本地视觉、原有分类器、可选多模态授权及人工修正接口；图片详情放入抽屉，缩略图留在主页面。
- 候选先显示前三项，其余可展开。保留支持、冲突、缺失特征、引用和完整观察评分。
- 大棚区域示意图支持选择异常区及正常区补测；这是位置标记，不是传感器热力图。修复原有静态 Modal 在当前 React 环境下无法正常弹出的问题。
- 调查记录抽屉保留全部观察、图片、各轮判断、归档、人工核验与经验评测；既有识别记录及其复核/任务入口仍可访问。
- 病害时间机放入环境风险抽屉。旧 `/platform/diagnosis`、`/platform/diagnosis?view=history`、`/platform/disease-time-machine` 自动进入统一页面的对应区域，并保留大棚及体验参数。
- 保留棚小智原有三维模型与动作，本轮不修改模型文件。
- 全平台正文优先使用本地可变字重 Noto Sans SC，统一标题、正文及控件字体；保留官网原有书法展示字。

## 自主排查的实际范围

正式账号在创建调查、提交观察或修正图片后，自动刷新本棚环境历史、活动预警、灌溉/通风任务、病害识别及知识检索，调用已有规则和观察选择器重新分析。只读取现有生产记录，不把查询记录伪装成执行了现场检查。

体验账号调用现有公开规则接口重新计算实际输入，记录保存在浏览器会话，按大棚隔离。不借用正式组织数据，也不向正式业务表写调查。执行记录明确显示哪些数据没有关联。

模式包括自主与引导。自主模式支持暂停/继续；暂停阻止后续补证触发自动更新，当前已经发出的请求仍会返回。需要拍摄、测量等现场证据时停在等待状态。失败有错误提示与重试入口。此功能是页面内证据驱动的自动分析流程，未新增后台无人值守巡检或自动设备控制。

保留原有显式模型解释按钮及图片模型授权，不自动新增付费模型调用。规则支持分不是病害概率。

## 主要文件

| 文件 | 改动 |
| --- | --- |
| `frontend/src/pages/Investigate/InvestigatePage.tsx` | 统一页面、自动更新编排、抽屉及实际结果展示 |
| `frontend/src/pages/Investigate/InvestigationVisionPanel.tsx` | 紧凑上传、独立图片详情、修正历史保留、已完成动作排除 |
| `frontend/src/pages/Investigate/InvestigationSpatialMap.tsx` | 可交互的大棚区域示意 |
| `frontend/src/pages/Investigate/investigation-workspace.css` | 参考图布局、文字层次、响应式 |
| `frontend/src/pages/Diagnosis/DiseaseDiagnosisPage.tsx` | 支持嵌入既有识别记录 |
| `frontend/src/layouts/{AppLayout,workspaceNavigation}.tsx` | 单一诊断入口及页面宽度 |
| `frontend/src/router/index.tsx` | 旧入口兼容跳转 |
| `frontend/src/{theme.ts,typography.css,main.tsx}` | 本地字体与统一文字规范 |
| `frontend/src/layouts/platform-visual.css`、`frontend/index.html` | 字体优先级与预加载 |
| `backend/app/{api/investigation.py,services/investigation_service.py}` | 带权限和版本检查的上下文刷新 |
| `backend/tests/test_investigation_workspace.py` | 刷新、版本、权限、预算和判断保留测试 |
| `frontend/scripts/check-investigation-workspace.py` | 真实浏览器交互验收 |

数据库：复用 `AgronomyRecord`，仅在其 JSON payload 中增加最多保留 20 次的 `autonomy_runs`。未新增表、未删除字段或正式记录。环境上下文变化确实影响支持分时，才增加判断历史；普通重复刷新不伪造新的判断变化。

新增 API：`POST /api/investigate/{record_id}/refresh`，请求 `{ "version": 当前版本 }`，返回现有调查响应结构。跨组织不可访问；版本过期或已归档返回 409；上下文读取不消耗现场检查预算。

## 字体来源

Noto Sans SC 2.004，SIL OFL 1.1。来源：[Google Fonts 官方仓库](https://github.com/google/fonts/tree/main/ofl/notosanssc)。

本地资源：`frontend/public/fonts/pengzhi-ui-sc.woff`，约 2.53 MB；许可证为同目录 `OFL-NotoSansSC.txt`。来源、版本、原始和产物 SHA-256、字形覆盖见 `font-manifest.json`。裁剪覆盖 GB2312 常用汉字、现有前端文案、拉丁及标点，其余字符使用系统字体回退。保留可变字重，避免浏览器合成粗体。

重建脚本 `scripts/build_ui_font.py` 使用本机已有 fontTools，仅是开发工具，不增加应用运行依赖。未添加新的 npm/Python 运行依赖。

## 验证及运行

- 后端：`tests/test_investigation.py`、`test_investigation_v2.py`、`test_investigation_validation.py`、`test_investigation_workspace.py`：**16 passed**。保留 1 条上游 Starlette/AnyIO 弃用提示。
- 浏览器：`python frontend/scripts/check-investigation-workspace.py`：**23 项通过**。覆盖真实规则计算、证据改变优先原因、检查排除、预算、暂停/继续、引导模式、真实图片上传、人工修正、照片历史恢复、旧路由、组织外体验记录隔离、390px 无水平溢出与抽屉、无 JavaScript 运行异常。图片测试使用明确的像素测试夹具，不代表真实病害准确率评估。
- 前端：`npm run build` 通过，保留现有大型 bundle 提示；修改的 TS/TSX 文件 ESLint 通过。
- 输出：`.run/investigation-ui/{backend-tests.log,browser.log,browser-results.json,build.log,eslint.log}`；桌面/手机截图在同目录。完整日志为本轮实际执行结果。

入口：`http://127.0.0.1:5173/platform/investigate?mode=guest&greenhouse_id=101`。

沿用前端 5173、后端 8000；检查端口后复用前端开发服务，重启后端以加载刷新接口。手动启动仍使用项目原有 Vite 与 Uvicorn 命令。

## 保留限制

未新增病害模型训练或可靠病害概率；图片分类质量仍受现有模型约束。未关联的区域测量与现场照片需要用户实际补充。天气、设备实时控制、后台定时巡检不属于本次 UI 升级。可变长度的实际结果允许内容区自然伸展，保留设计图的主要布局关系。
