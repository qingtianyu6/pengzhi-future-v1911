# 棚智未来 v1.8.0 · 产品化终验与业务闭环

本轮按“真实运行终验 → 统一视觉 → 业务闭环 → 系统状态 → 上线检查”的优先级推进。

## 已完成

1. 大棚管理与农事任务继续沿用 v1.7 视觉目标；环境分析、病害检测加入 v1.8 统一视觉层，统一圆角、Surface、留白、信息密度和响应式规则。
2. 环境分析的活动预警支持直接生成农事任务草稿，并自动跳转任务中心打开对应任务。
3. 病害识别结果增加“人工复核 / 派发农事任务”闭环；仅人工确认或修正后的病害记录可以创建任务，保持后端安全规则。
4. AI 农事建议面板的“采纳建议”不再只是视觉按钮：若关联任务仍是草稿，会直接人工提交进入待执行状态并打开任务详情。
5. 任务完成后的事件、反馈与跨模块 trace 继续由后端任务服务记录，可在 AgriTrace 中追溯。
6. 修正病害检测与大棚详情中的旧版 `/production`、`/environment` 路由，统一到 `/platform/*`。
7. 新增 ProductStates 组件：Skeleton / Error / Permission / Sync Meta，可用于后续所有页面的一致状态呈现。
8. 版本提升至 1.8.0。

## QA / 构建说明

- 后端使用 `python -m compileall` 检查。
- 前端使用 TypeScript `transpileModule` 对全部 TS/TSX 做语法级检查。
- 当前运行容器访问 npm Registry 超时，未把“npm install/build 未完成”伪装成通过；本机联网后执行 `npm ci && npm run build` 即可完成最终依赖级构建检查。
- 参考截图与既有 visual_qa 文件均保留在包内，方便继续进行 actual / overlay / difference 校准。
