# Sony DualSense · 从高模到成片

从接收第三方 FBX 高模开始记录 Blender 制作流程，包括模型导入与检查、白模、颜色与材料表现、灯光，以及产品原片和尺度概念。原片以实际输出尺寸归档。

[浏览全部文件](FILES.md) · [10 个 Blender 工程](FILES.md#blender-工程) · [下载 V3 产品摄影工程 · 35.8 MB](https://github.com/AJ-nb/3d-asset-archive/raw/refs/heads/main/projects/sony-dualsense/00-来源与工程/08-V3产品与概念/DualSense-Product-Photography.blend) · [下载同机位四步工程 · 22.1 MB](https://github.com/AJ-nb/3d-asset-archive/raw/refs/heads/main/projects/sony-dualsense/03-同机位流程/DualSense-同机位渲染流程.blend)

![九张小红书发布图总览](小红书图组总览.jpg)

| 目录 | 内容 |
| --- | --- |
| [00　来源与工程](00-来源与工程/) | 源 FBX、首次导入工程、9 个历史 Blender 工程，以及搭建脚本、渲染日志和校验记录 |
| [01　历史原图](01-历史原图/) | 51 幅历史画面，含 37 张长边 3840 像素的独立渲染、原生白模、4800 像素宽的横摆组合和 V3 成片。透明通道 EXR 另存 |
| [02　工程界面](02-工程界面/) | 5 张历史原截、8 张本次实截及 2 张历史预览 |
| [03　同机位流程](03-同机位流程/) | 结构分色、哑光白模、CMF 单主灯与归档终稿。前三张为阶段复现，第四张为 V3 原图。附可编辑工程 |
| [04　小红书图组](04-小红书图组/) | 9 张按发布顺序命名的 1440 × 1920 PNG |

[制作流程与证据索引](制作流程与证据索引.md) · [原图索引](01-历史原图/原图索引.csv) · [发布图逐图溯源](小红书逐图溯源.csv) · [原版 4K 评审板](01-历史原图/08-初版评审板/dualsense-4k-review.jpg)

[下载九张发布图 ZIP](https://github.com/AJ-nb/3d-asset-archive/raw/refs/heads/main/projects/sony-dualsense/DualSense-Xiaohongshu.zip) · [小红书发布文案](小红书发布文案.md)

## 下载原图与工程

在浏览器中打开[完整文件目录](FILES.md)，可以逐项查看历史原图、下载任一版 Blender 工程、源素材和制作记录。[制作起点与素材来源](00-来源与工程/先读.md)记录了第三方高模的来源和已知授权情况。

如需保留目录结构并离线浏览，安装 Git LFS 后运行以下命令。下载完成后，双击项目目录下的 `打开看图.html` 可按发布图回查原件。在该目录运行 `sha256sum --check 全包文件校验.sha256` 可核对归档文件。

```sh
git lfs install
git clone https://github.com/AJ-nb/3d-asset-archive.git
cd 3d-asset-archive
git lfs pull
```

需要单个完整归档时，可在下载后将 `projects/sony-dualsense` 整个目录压缩为 ZIP。

截图索引中的三处本机会话路径用文字标记，保留同期记录的行号、截图与日志。归档流程从导入已有高模开始，产品作者从草图到网格的原始建模过程未随模型交付。
