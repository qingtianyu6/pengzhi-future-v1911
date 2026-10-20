# 棚智未来整体 UI 升级

本次在现有 V2-development 本地代码上增量修改，未覆盖既有未提交功能，无数据库/API变更，未提交或推送 Git。

## 功能分区

- 生产工作区：生产总览、监测与预警、农事执行、三维大棚。
- 智能农艺：棚智探因、病害诊断（含时间机）、AI研究台。
- 知识社区：农业知识库、棚智农讯、棚友论坛。
- 平台管理：数据与管理、AI能力与运行。

保持现有地址及业务权限，重组导航入口。新增可搜索功能导航（Ctrl/Command+K），可按名称、说明和分区搜索，跳转保留大棚及游客状态，支持无结果提示和Escape关闭。

## 视觉与布局

采用深绿侧栏、米白工作画布、浅绿信息区域与统一卡片，统一文字、边框、状态、表单和弹层主题。卡片状态仍来自原业务API，未增加虚构统计或图表。

总览突出棚况、待处理事项、环境指标和任务；研究台恢复宽屏双栏，探因初始问题与照片入口并排，窄屏上下排列；社区筛选器和知识/资讯卡片统一外观。兼顾官网导航、登录注册表单的品牌一致性。保留原三维场景及棚小智模型/动画。1600px起显示协作侧栏，常规屏宽保留独立数字人，避免挤压主工作区。

## 文件

- frontend/src/theme.ts：全平台 Ant Design 主题。
- frontend/src/layouts/workspaceNavigation.tsx：四个分区、菜单及检索说明的统一配置。
- frontend/src/layouts/platform-visual.css：品牌、工作区、各模块及移动端样式，使用pz-ui作用域承接旧样式，不改数字人网格/动画。
- frontend/src/layouts/AppLayout.tsx：导航、搜索面板、当前分区、响应式布局。
- frontend/src/main.tsx：统一主题入口。
- frontend/src/pages/Investigate/InvestigatePage.tsx：问题与图片入口布局。
- frontend/scripts/check-platform-visual.py：真实浏览器布局及导航检查，无API拦截、不写正式数据。

## 启动与检查

沿用运行中的5173前端、8000后端；没有重复启动服务。浏览器打开 http://127.0.0.1:5173/platform?mode=guest&greenhouse_id=101 可体验。

实际检查输出保留 .run/ui-refresh/build.log、lint.log、frontend-exit.txt、browser.log、browser-results.json 和各页面桌面/手机截图。详细通过数在全部验收结束后补录。

此轮为UI与导航升级，不改变模型精度、监测数据或业务权限。现有构建包体积提示仍需后续优化；不将所有页面可打开等同于所有业务流程已重新验收。

## 最终验收结果

- TypeScript/Vite构建与ESLint实际执行，退出码均为0；保留原有大包体积提示。
- 布局与导航检查最终44项通过，JavaScript运行错误0条：13个工作台页面×桌面/390px手机共26项；搜索跳转、空结果/Escape、手机菜单、超宽屏原数字人共4项；官网5页及登录/注册×2种屏宽共14项。
- 原始结果browser-results.json为42通过、2项首页选择器失败；首页实际使用brush-title div而非h1，改用可见hero内容定位后两项补测通过，最终合并记录browser-final-results.json，保留原始日志，不抹除首轮结果。
- 旧探因完整浏览器脚本本轮在游客步骤后，正式页面上传输入框等待超时，未标记通过；后续恢复隔离测试服务的命令被自动审批策略拦截（返回blocked by policy，未给更细原因），没有绕过或向正式库注入测试数据。本轮44项仅验证UI/导航，不宣称所有正式账号业务流程重新验收通过。该项日志为investigation-regression.log。
- 最后确认5173页面与8000健康端点均返回200；自动启动用户浏览器的命令同样被策略拦截，提供可点击本地链接打开。
- 未新增依赖、未调整业务API/数据库、未执行Git提交或推送。测试产物和运行日志位于.run/ui-refresh，主要桌面预览overview-1440.png、research-1440.png、investigate-1440.png，手机预览为对应390.png。
