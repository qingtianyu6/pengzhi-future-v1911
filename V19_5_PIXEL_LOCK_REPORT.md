# 棚智未来 v1.9.5 · 第一参考图像素锁定继续精修

本轮以 `visual_qa/v19_5/core_reference_1680x936.png` 为核心功能页桌面端唯一视觉基准，继续针对 1680×936 首屏进行几何锁定。

## 本轮实际改动

- 顶部导航继续锁定 80px 高度体系。
- 核心功能 Hero 固定为 556px，高度与参考图首屏分界一致。
- Hero 背景使用 1920 / 2560 / 3360 三档 WebP，不对照片进行 scale 动画或滤镜缩放。
- 文案区锁定为 700px，Dashboard 锁定为 674px，并将 Dashboard 下移 15px 对齐参考稿。
- 主标题强化为无衬线粗体体系，字号、字重与行距重新调整。
- 左侧白色渐变重新锁定过渡区，尽量保留参考图中“左侧清爽、右侧实景”的层次。
- 环境监测第一节固定 1430px 桌面内容宽度，并重新设定 641px + 剩余区的左右布局。
- 环境监测传感器图改为 eager + high priority，避免首屏截图时图片尚未加载。
- 环境趋势由 ECharts 首次异步初始化改为 React 内联 SVG：首帧即可出现、缩放保持矢量锐度，同时保留点击温度/湿度/光照切换数据的交互。

## 清晰度策略

- `greenhouse-wide-1920.webp`
- `greenhouse-wide-2560.webp`
- `greenhouse-wide-3360.webp`
- `sensor-clean.png`

Hero 根据屏幕宽度自动选择图像版本，背景图本身不做 transform/animation/filter 重采样。

## QA 文件

- `core_reference_1680x936.png`：目标参考图
- `core_layout_preview_1680x936.png`：本轮几何布局预览
- `core_reference_vs_preview.png`：左右对照
- `core_layout_preview.html`：静态几何 QA 页面

> 静态 QA 页面用于锁定几何关系，不等同于声称完整 React 运行截图。最终真实运行图仍应在依赖安装后由 Vite 页面生成。
