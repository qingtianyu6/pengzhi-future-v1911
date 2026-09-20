# 棚智未来 v1.9.4 网站交付说明

本版本把“核心功能”页按用户确认的第一张参考图重新落实到真实网站代码，而不是生成一张静态图片。

## 核心改动
- 桌面导航栏改为约 80px，高度、Logo、导航间距、搜索/游客/登录/注册按钮重新对齐参考图。
- 核心功能 Hero 固定为约 556px，首屏可以自然露出下一节“环境监测”。
- 背景采用 1920 / 2560 / 3360 WebP 响应式高清图，照片不做 scale 动画，避免浏览器重采样发糊。
- 左侧渐变宽度、标题字号、文案宽度、五项功能和 CTA 尺寸重新按 1680×936 参考图校准。
- 右侧 DashboardMockup 保留为真实 React DOM，并补齐：顶部品牌区、设备在线状态、三项指标、环境趋势网格/图例/坐标、六项侧栏和底部入口。
- Dashboard 不再持续浮动，确保像素稳定和截图一致性。
- 原有后续功能（环境监测、病害识别、农事管理、智能决策、数据沉淀）保持可交互。

## 高清素材
`frontend/src/assets/pure-scenes/` 中：
- greenhouse-wide-1920.webp
- greenhouse-wide-2560.webp
- greenhouse-wide-3360.webp

React `<picture>` 会根据显示器宽度自动选图。

## 参考图
`visual_qa/v19_4/core_reference_1680x936.png`

## 本地运行
```powershell
cd frontend
npm install
npm run dev
```

后端：
```powershell
cd backend
pip install -r requirements.txt
python run.py
```
