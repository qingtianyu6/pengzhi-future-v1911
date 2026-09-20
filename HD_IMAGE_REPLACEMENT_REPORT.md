# 棚智未来：高清图片替换审计

本轮只针对“图片发糊、被放大后清晰度不足”的视觉问题进行处理，不改动页面信息架构和业务逻辑。

## 处理策略

1. **大面积关键视觉直接替换高清母版**
   - 项目成果 Hero：替换为重新生成的高清温室成果场景。
   - 平台介绍「平台能做什么」：替换为高清温室 + 传感器 + 种植人员 + 管理屏场景。
   - 应用场景中的蔬菜 / 草莓 / 花卉 / 育苗照片：替换为清晰的新场景图。

2. **中小型照片统一高清化**
   - 原始裁图宽度不足时统一进行 2–4.5× 高质量重采样。
   - 使用 Lanczos 重采样、轻度局部对比度增强、锐化和 Unsharp Mask。
   - 保持原始宽高比与前端 `object-fit` 逻辑，不拉伸图片。

3. **关键设备与平台界面重做高清素材**
   - 传感器设备、温室管理大屏、项目成果应用温室等替换为高清裁图。

4. **去除重复 UI**
   - 「平台能做什么」新的高清场景图已经带有清晰的功能标注，因此关闭了该区域重复的 DOM 浮层卡片，避免出现双重文字和二次模糊。

## 重点替换文件

- `frontend/src/assets/results-design/hero-results.png`
- `frontend/src/assets/results-design/overview-tablet.png`
- `frontend/src/assets/results-design/tech-sensor.png`
- `frontend/src/assets/results-design/tech-dashboard.png`
- `frontend/src/assets/results-design/application-greenhouse.png`
- `frontend/src/assets/platform-intro/.../section_refs/03_平台能做什么_温室场景构图参考.png`
- `frontend/src/assets/scenarios-design/vegetable-tomato.png`
- `frontend/src/assets/scenarios-design/fruit-strawberry.png`
- `frontend/src/assets/scenarios-design/flower-greenhouse.png`
- `frontend/src/assets/scenarios-design/seedling-nursery.png`
- `frontend/src/assets/highlights-design/edge-greenhouse.png`
- `frontend/src/assets/highlights-design/knowledge-greenhouse.png`

除此之外，代码包内其余低分辨率生产素材也已统一提高分辨率。

## 分辨率底线

本轮处理完成后，除设计参考原图外，实际页面使用的 PNG 素材长边均不低于约 900 px；大面积视觉素材普遍提升到 1600–2800 px 级别。

## 注意

设计稿/reference 文件保留原样，仅作为视觉比对基准，不参与正式页面显示。
