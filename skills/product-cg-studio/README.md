# 产品 CG 工作室 · Product CG Studio

给 AI 制作搭档一句概念、一张草图、实拍参考或已有工程，按项目交付可编辑的 Blender 场景、效果图和展示动画。方向未定时，先访谈、找真实先例、做白模选型。方向确定后逐件复核几何、连接与动作，修正源模型，再用定稿的模型出整套图。包内脚本可生成工单、检查网格、对比每毫米截面、测试绑定和批量渲染。

| DJI 口袋云台相机研究 · V7 成品 | 同机位白模 | 双镜头局部 |
| --- | --- | --- |
| ![DJI 口袋云台相机研究，V7 着色成品](examples/dji/pocket-v7-hero.jpg) | ![V7 同一机位白模，用于核对机身与云台的轮廓](examples/dji/pocket-v7-clay.jpg) | ![V7 镜头模组斜前方特写](examples/dji/pocket-v7-optics.jpg) |

前两张出自同一版 Blender 工程，归档时固定在第 62 帧、使用同一台 88 mm 相机补渲。先看白模中云台与机身的轮廓，再对照着色图中的高光、反射与材质分界；右图单独看镜头模组。配图来自本项目的 DJI 产品 CG 研究。[图片来源与版本](examples/dji/sources.md)

## 安装与调用

要让支持 MCP 的 AI 客户端直接运行 Blender 检查、提交后台渲染并查收文件，请按[本地 MCP 安装与 DJI 试跑](mcp/README.md)配置。分享包同时包含 Skill、MCP 服务与命令行脚本。

下载分享包并解压，把完整的 `product-cg-studio` 文件夹复制到 Codex 的技能目录。默认位置为 Windows 的 `%USERPROFILE%\.codex\skills\` 或 macOS／Linux 的 `~/.codex/skills/`。设置过 `CODEX_HOME` 时放进它下面的 `skills/`。安装后应能看到 `skills/product-cg-studio/SKILL.md`。新开一个对话，附上素材或指定工作目录，发送下面任何一种请求。同事使用其他支持本地文件和 Blender 的 AI 工具时，也可以直接指定它阅读 [SKILL.md](SKILL.md) 并执行。

> 使用 $product-cg-studio 接手这个手柄工程，保留原始外形和按钮布局。做一张按键朝上横放的桌面主视觉，另做一张手机竖图，能看清握把的细纹。交付两张原图和可重开的工程。

> 使用 $product-cg-studio 根据这些照片制作带铰链的台灯。先用侧视白模验证连接位置，再做一个展示开合的 6 秒短片。请注明哪些尺寸来自测量、哪些只按照片估计。

> 使用 $product-cg-studio 接手这个装配工程和对应的设计 CAD。按部件检查所有连接、倒角、壁厚和间隙，用相同装配基准每 1 mm 比截面。把差异修回模型，测试默认、常用、极限及组合动作，再从修后工程重渲官网主图和铰链特写。交付逐项实测、待证项和可编辑工程。

> 使用 $product-cg-studio 处理 products.json 里的每款产品。逐款完成建模或修复、出样、精修和交付，汇总可打开的工程、成品、已验项目和缺件。

> 使用 $product-cg-studio。我想做一台口袋云台相机，只有大致的机身和屏幕轮廓。先找几个 DJI 案例，帮我比较手持走拍和桌面口播各需要怎样的握持、支撑和取景，再选方向做白模。

## 从概念到第一版白模

1. 把手头的草图交给 AI，或者直接说出想做的东西。它会复述能看懂的部分，针对会改变设计或交付的取舍，实际向你提出至少 10 个问题。可以分轮回答，也可以指定哪些由它代拟。[客户访谈与按品类换题](references/concept-intake.md)
2. 打开相似案例，对照图中的结构、材料与使用状态。比如想单手边走边拍，就让设计师在白模上同时画出手指握区、屏幕的视线和云台转动的空间。[查找与筛选先例](references/design-precedents.md) · [DJI 官方产品参考板](examples/concept/dji-references.md)
3. 核对交回的设计简报。假设已确定拍桌面口播，接下来要比较的是同一桌面上外接底座和机内折脚各要做哪些动作、收起来占多少空间、充电线能否插拔。再选取一个最重要的使用任务，在白模、样机或目标画幅中验证，并保留客户仍需确认的事项。[DJI 参考与同场景方案交接示例](examples/concept/handoff.md)

批量处理创意项目时，复制[概念工单示例](examples/concept/products.json)，从技能目录运行下列命令。脚本准备访谈和记录文件。把生成的工单交给启用了本技能的 AI，由它打开草图、实际访谈、上网检索并开展后续制作。

```sh
python scripts/prepare_queue.py examples/concept/products.json --out work/concept-01
```

想看另一位执行者实际怎样用现有素材接单，可以打开[桌面拍讲课视频的独立试用记录](https://github.com/AJ-nb/3d-asset-archive/tree/main/projects/pocket-camera/desk-support-trial)。工单使用档案中的 DJI 相机，访谈角色由 AI 模拟，记录区分了数字模型可验的项目和需要真人、样机才能验证的项目。

## 怎样从「看起来不对」查到具体部件

| 情况 | 操作与交付 |
| --- | --- |
| 有 CAD、校准扫描或带尺寸的数字参考 | 核对单位和零位，按零件在 X/Y/Z 每 1 mm 剖切。打开离线叠图，用逐站 CSV 定位偏差，给孔口、棱边等特征单列测量窗。[截面比较与圆角拟合](references/sections.md) |
| 只有照片或文字简报 | 照片核对可见轮廓、孔位和比例，留一组独立视角复查。原创设计使用本单明确设定的尺寸。两种情况都能检查模型自身的结构；没有真实尺寸依据的部位在复核表列为待证。[逐件核对表与网格工具](references/model-review.md) |
| 折叠、转动、滑动或柔性变形 | 建真实基础绑定，按配合面测净隙、支承和行程；硬件复核保形，柔性部位同时查权重、变形及固定端。以故障样件验证检查能定位错误，再对修后件复跑。[装配与动作测试](references/assembly-and-rig.md) |
| 修完需要用于网页、展板或作品集 | 冻结工程与依赖版本，按画面用途分镜。重出受影响的整机、局部和状态图，看成套联系表、原像素局部和实际版位。[渲染、CMF 与渠道验收](references/cmf-stills.md) |

### 用同一侧视角检查云台支承

| V3 · 正右视 | V4 · 正右视 |
| --- | --- |
| ![DJI 口袋云台相机 V3，侧视镜头支承轮廓](examples/dji/pocket-v3-gimbal-side.png) | ![V4 对应侧视，比较横桥和斜臂的轮廓](examples/dji/pocket-v4-gimbal-side.png) |

沿两张图从机身顶部往镜头看，比较横桥向后伸了多远、斜臂在哪里接上。这个视角可以定位轮廓变化。要量销孔配合、倒角半径或运动间隙，还需要在工程里选择相应的零件和基准面。[图源与迭代记录](examples/dji/sources.md) · [装配与动作复验](references/assembly-and-rig.md)

### 用标准试件复验每毫米截面

同一块 12 × 10 × 8 mm 数字试件，初稿误用了 R2 圆角。独立保存的设计参考为 R1。沿 Z = 0 mm 的中部截面，测得两者轮廓的最大采样距离约 0.4142 mm，局部圆弧拟合出的半径正好差 1 mm。重开初稿修改倒角后，三轴共 30 个非空截面全部与数字参考重合。同一灯光和机位重新渲染后，修正版与参考图的 RGB 像素也一致。这里的 1 mm 是采样站距，实物还原精度取决于参考、配准和测量误差。

随包的[试件工程与测量数据](examples/verification-data.zip)含逐站 CSV、原始轮廓、可重开的工程和绑定测试。需要查看当时的叠图时，下载[完整原始验证档案](https://raw.githubusercontent.com/AJ-nb/3d-asset-archive/main/downloads/product-cg-verification-evidence.zip)，解压后打开 `sections/qa/draft/index.html`。也可用[截面说明](references/sections.md)中的命令离线重建报告，再从相同机位复拍试件。

```sh
blender -b --disable-autoexec section-gauge-run/corrected.blend --python-exit-code 1 -P examples/section-gauge/render_gauge.py -- work/gauge-corrected.png
```

铰链示例还能区分「轴心对了」与「销能装进去」。正常件通过 18 项检查。孔径保持 2.10 mm，销径从 2.00 mm 变成 2.40 mm 时，两实体表面的单侧径向净隙从 +0.050 mm 变成 −0.150 mm。另三个故障工程分别展示枢轴偏移、权重归一但绑错骨骼、硬件在运动中发生形变。所有检查均可从工程重跑。

## 批量怎么跑

准备阶段只需 Python 3。渲染阶段还需要能在本地后台运行的 Blender。此包在 Windows、Blender 5.2.2 LTS、Cycles CPU 下实测。命令中的 `python`、`blender` 可替换为本机程序路径。生成 MP4 时另用 FFmpeg。

| 手里的材料 | 从哪里开始 | 运行后得到什么 |
| --- | --- | --- |
| 多款产品的文字简报、参考图或旧工程 | 复制 [products.json](examples/products.json)，按款改输入、画幅和验收要求。生成工单后，执行人按实际进度更新每款的 `delivery.json`。 | 用 `order_status.py` 汇总当前阶段、阻塞、改版后需重出的镜头和已签收版本。[工单字段与续做](references/production-queue.md) |
| 可渲染的 Blender 工程和命名机位 | 复制 [batch.json](examples/batch.json)，替换工程、场景、相机和帧段，先检查再渲染。 | 分镜头的静帧／PNG 序列和运行报告；可选择失败镜头单独重跑。[批渲染、重试和视频编码](references/batch.md) |

从本技能目录试跑，以下输出目录应使用新名字。

```sh
python scripts/prepare_queue.py examples/products.json --out work/orders-01
python scripts/order_status.py work/orders-01
python scripts/render_batch.py check examples/batch.json
python scripts/render_batch.py render examples/batch.json --out work/render-01
```

[原创旋钮控制器场景](examples/demo.blend) 随包提供。示例会输出一张整体图和四帧旋钮转动近景。打开 `work/render-01/shots/hero/still.png` 看整体，逐帧看 `shots/turn/` 中的指示线。要从空场景重建，可运行[示例生成脚本](examples/make_demo.py)，用法见批渲染说明。

试做材质与构图精修时，打开 [volume-controller.blend](examples/finished/volume-controller.blend)。这个版本为金属旋钮建立了侧面凹槽与盘面细纹，保留了分件、材质节点和两台相机。下面的命令直接重渲 1280 × 640 的整机横幅和 800 × 1000 的旋钮竖幅。

```sh
python scripts/render_batch.py render examples/finished/shots.json --out work/finished-01
```

要重做精修过程，在新的工作目录生成基础场景，再运行[材质与机位修改脚本](examples/finished/finish.py)。以下命令从技能目录运行，输出 `work/remake/volume-controller.blend` 和该次运行的白模小样。可以把 `examples/finished/shots.json` 复制到新工程旁再渲染。

```sh
blender -b --factory-startup --python-exit-code 1 -P examples/make_demo.py -- work/remake/blockout.blend
blender -b --factory-startup --disable-autoexec work/remake/blockout.blend --python-exit-code 1 -P examples/finished/finish.py
```

## 产品动画示例

同一台控制器还拍了一支 3 秒的双镜头短片。首镜从较低的位置升起，交代整机和底座。第 33 帧切到旋钮特写，机身保持固定，指针跟随旋钮旋转。在 Blender 打开动画工程即可查看摄影机、剪点与产品各自的关键帧。[播放或下载 MP4](examples/film/volume-control.mp4) · [动画工程](examples/film/motion.blend) · [逐镜重渲与编码说明](examples/film/README.md)

## 怎样验收一次试跑

- 工单报告应列出两个可制作的原创简报。可以在清单副本中给其中一款添加不存在的参考图，检查报告是否点名缺件，并继续生成另一款的工单。
- 在渲染清单副本中把一个相机改成不存在的名字。报告应给出那一项的错误及可选机位，另一项仍应出片。修正相机名后，用 `--only` 和新的输出目录复跑该项。
- 在临时场景中移走产品表面的贴图，再恢复原文件。比较 `needs_review`、成品目录和依赖摘要。随包的[缺图回归样例](examples/check_render_dependencies.py)也会检查动画中途首次用图和闲置贴图两种情况。
- 打开控制器试跑输出的横幅和竖图，分别检查底脚与桌面的接触、旋钮侧槽和盘面细纹。用同一工程与相机重渲可疑部位，核对画幅和材质效果。

## 三个项目怎样改变了流程

[完整案例复盘](references/iteration-lessons.md)按反馈、可区分成因的检查、源工程修正与复验结果整理了下列项目，还包括热端拆解、相机转屏联动和后补制作过程图的实际返工经验。

| 项目经验 | 复用到下一单的决定 |
| --- | --- |
| DualSense 的已有模型需要修复。桌面横图和手机竖图承担不同的信息，放大后还有肩键印字等细节限制。 | 接单先确定模型来源，保留基准。分别安排产品姿态、拍摄机位和画幅，按最终使用尺寸检查文字、轮廓和贴地阴影。[静帧与 CMF](references/cmf-stills.md) |
| 口袋云台相机历版通过同机位图、装配检查和运动抽帧反复修正；最终竖片有独立的镜头表、工程及成片检查。 | 拍参考与模型的配准图。把产品转动、相机运动和剪点写在同一张分镜表里，分别复核场景中的动作和编码后看到的画面。[建模与动画](references/model-and-motion.md) |
| 折叠无人机的外轮廓、关节的安装方式以及收纳时的运动包络，需要不同证据才能确认。 | 用模型坐标、支承、极限帧和独立视角定位问题。记录照片估计和模型内测量的适用范围，几何修改后重出受影响的镜头。[结构复核](references/model-and-motion.md) |

分享包使用原创示例，运行无需联网下载商业产品模型、字体、HDRI 或插件。
