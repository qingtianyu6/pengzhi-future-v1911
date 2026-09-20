# 棚智未来官网设计还原说明

本版在原有前后端源码基础上补充并实现了官网展示页：

- 首页 `/home`
- 平台介绍 `/introduction`
- 核心功能 `/features`
- 技术亮点 `/highlights`
- 应用场景 `/scenarios`
- 项目成果 `/results`

## 视觉实现

- 统一复用官网导航栏与品牌 Logo。
- 按提供的 6 张设计图组织页面层级、留白、图片、数据卡、手写注记与页尾大图。
- 已加入滚动淡入、数字递增、首屏轻微呼吸、卡片悬浮、图表动画等克制型动态效果。
- 平台介绍、核心功能页中的 UI 类设计元素优先使用真实 HTML/CSS/ECharts 实现，而不是把整张设计稿直接贴为网页。
- 提供桌面端与移动端响应式布局。

## 本地启动

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

默认：
- 前端开发服务器：Vite 输出的本地地址（通常为 `http://127.0.0.1:5173`）
- 后端：`http://127.0.0.1:8000`
- 健康检查：`http://127.0.0.1:8000/api/health`

## 本次校验

- 后端 Python 源码已通过 `compileall` 语法检查。
- 后端服务已在本地启动并通过 `/` 和 `/api/health` 检查。
- 前端所有相对 import 路径已检查，未发现缺失文件。
- 当前执行环境无法解析 `registry.npmjs.org`，因此无法在此容器中重新下载 npm 依赖并完成最终 Vite 浏览器构建；源码包保留完整 `package.json` / `package-lock.json`，在正常联网环境执行 `npm install` 即可运行。
