# 农业知识库主题配图

全部为主题示意，非参考文献原图、真实现场凭证或诊断样本。资料标题、内容与来源链接保持独立，不因选图而改变。

- light、ventilation、winter、irrigation、inspection：2026-10-20 使用内置 imagegen 生成；完整提示词见 generation-prompts.json。巡查图只表现健康叶片观察，不用生成病斑冒充病害证据。
- seedling：复用 src/assets/pure-scenes/seedling-wide.png。
- tomato：复用 public/homepage-v11/scene-tomato.jpg。
- muskmelon：复用 public/images/greenhouse-management/muskmelon.png。
- environment：复用 src/assets/pure-scenes/sensor-clean-1920.webp。
- greenhouse：复用 public/images/greenhouse-management/hero.png。

WebP 使用浏览器 Canvas 编码为 640px 宽，保持完整构图，不裁剪、不修图；单图约 42–85KB。AI生成原始文件保留于生成目录，浏览器仅加载轻量版本。

匹配逻辑集中在 src/pages/Community/knowledgeIllustrations.ts，优先标题主题，其次类别，最后使用设施场景回退。相同文章不随排序、分页、刷新随机换图；同一主题可复用配图，不给每篇摘要伪造独立现场照片。
