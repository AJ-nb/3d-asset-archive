# 批量渲染已准备好的 Blender 场景

执行器按清单打开源文件，选中场景和相机，为每个任务生成一张 PNG 或一段连续的 PNG 序列。产品几何、材质、灯光、摆放和动画都从源场景读取。一次摆放可用多台相机拍摄。不同摆放可保存为不同场景或动画帧。

## 用附带的旋钮控制器跑通流程

需要 Python 3 和带后台渲染能力的 Blender。以下命令从技能根目录执行。先准备一个空的工作目录，将示例清单复制到那里，然后生成同目录的模型。下面的命令适用于 Windows PowerShell。

```powershell
New-Item -ItemType Directory -Path ./cg-demo
Copy-Item ./examples/batch.json ./cg-demo/batch.json
blender -b --factory-startup --python-exit-code 1 -P ./examples/make_demo.py -- ./cg-demo/demo.blend
python ./scripts/render_batch.py check ./cg-demo/batch.json
python ./scripts/render_batch.py render ./cg-demo/batch.json --out ./cg-demo/proof-01
```

macOS / Linux 的前两行可用 `mkdir cg-demo` 和 `cp examples/batch.json cg-demo/`。Blender 未加入 PATH 时，把第 3 行的可执行文件替换为实际路径，并为第 4、5 行追加 `--blender "/path/to/blender"`。也可设置环境变量 `BLENDER_BIN` 供批处理器读取。PowerShell 中带空格的可执行路径用 `& "…/blender.exe"` 调用。示例使用 Cycles CPU，只需本机渲染。打开下列输出确认旋钮顶面的刻线在细节镜头中连续转动。

| 示例输出 | 内容 |
| --- | --- |
| `proof-01/shots/hero/still.png` | 384 × 256 的整体效果图 |
| `proof-01/shots/turn/frame_000001.png` 至 `frame_000004.png` | 256 × 192 的旋钮近景 |
| `proof-01/report.json` | 每项状态、主工程和已识别关键外链文件的 SHA-256、实际像素、场景和相机、引擎、Blender 版本、色彩变换、帧范围和帧率 |

## 准备自己的清单

从 [batch.json](../examples/batch.json) 复制一份。顶层为 `{"version": 1, "jobs": [...]}`。每个任务支持下表中的字段。

| 字段 | 取值 |
| --- | --- |
| `id` | 唯一输出目录名，1–64 个小写英文字母、数字、连字符或下划线，首字符为字母或数字。避开 Windows 设备名如 `con`。 |
| `blend` | 相对清单所在目录的源文件路径，如 `../models/dial.blend`。跨平台分享时用 `/`。 |
| `scene`、`camera` | 场景及其相机对象的准确名称，区分大小写。相机名称取自 Outliner 中的对象。 |
| `frame` 或 `range` | 静帧使用单个整数。序列使用起止均含的整数对，如 `[101, 148]`。二选一。支持 0 至 1048574。 |
| 可选 `resolution` | `[宽, 高]`，单位为像素，每边 4 至 65536，按 100% 渲染。省略时沿用场景分辨率和百分比。 |
| 可选 `required_files` | 本镜头必须读取的外部文件，按清单所在目录填相对路径，如 `["sim/frame_001.vdb", "textures/body.1001.exr"]`。每个所需缓存帧、UDIM 图块或链接库分别列出实际文件。 |

`check` 和 `render` 均会启动 Blender，逐帧检查选定场景中启用渲染的视图层、集合实例、对象材质、灯光、世界与主合成输出。沿输出节点连线和实际接通的节点组端口查找普通单文件贴图，登记所遇到的链接库。打包贴图随所在的工程或链接库定版。未接入输出、属于其他场景或禁用集合的贴图丢失时，可以在 `missing_source_warnings` 中看到提示。

报告的 `dependencies` 列出识别出的外链文件及清单声明的依赖，记录路径、引用者、首次检出帧、状态和可读文件的 SHA-256。`source_sha256` 对应主工程。指定预检的 `--out` 可保留首批摘要，正式交付时与渲染报告逐项比对。关键文件缺失、读不到或本次检查期间发生了可检测的大小／时间戳变化时，镜头标为 `needs_review`，整批返回非零状态，问题镜头留在工作区。恢复或重连文件后用 `--only` 重新检查、渲染。

依赖检查按场景和节点连接关系取样。画外物体仍可能投影或参与反射；带渲染修改器的网格会保守检查所有已分配材质槽。混合节点权重、插件运行时读取、几何节点生成的材质、模拟缓存、UDIM 和序列文件仍需按项目核对。把已知关键文件列入 `required_files`，再渲染对应帧的小图复查材质与效果。可用 `python examples/check_render_dependencies.py --blender "/path/to/blender"` 在临时目录复现关键贴图缺失、闲置贴图缺失和恢复后的结果。

每个任务在独立 Blender 进程中执行，保留源场景的引擎、灯光、曝光和材质。在内存中选定相机、禁用时间线相机切换、VSE 覆盖、立体多视图、渲染区域裁切及合成器文件输出节点。主合成结果仍用于 PNG。源文件不会被保存。若短片依赖剪辑台或多机位切换，请按镜头拆到清单中后再剪辑。涉及脚本驱动或自定义渲染插件的场景，要先确认在工厂启动且关闭自动执行脚本的命令行环境中可以正确渲染，或为该项目另配兼容的执行环境。

## 检查结果和局部重试

- 每次运行给 `--out` 指定一个尚未存在的目录。运行期间查看 `report.json` 与 `logs/<id>.log`。同一批中的其他任务会在单项失败后继续。清单结构错误、任务失败、输出目录冲突均返回非零状态。
- 通过检查的完整镜头才进入 `shots/<id>/`。图像检查核对 PNG 签名、尺寸和结束标记。失败或中断的中间帧留在 `work/<id>/`。打开最终图和抽帧检查穿模、失焦、材质和运动时序。
- 修正失败镜头后，仅选择有关 ID 写入新目录。例如 `python scripts/render_batch.py render ./cg-demo/batch.json --only hero --out ./cg-demo/retry-hero-01`。同一个任务的全部帧会一起重渲，便于核对源文件和参数是否一致。

需要 MP4 时，先检查帧范围和 `report.json` 的实际帧率。已安装 FFmpeg 的环境可用以下命令编码示例的四帧。

```sh
ffmpeg -n -framerate 24 -start_number 1 -i "cg-demo/proof-01/shots/turn/frame_%06d.png" -frames:v 4 -c:v libx264 -pix_fmt yuv420p "cg-demo/dial-proof.mp4"
```

替换成自己的起始帧、帧数及帧率。如果项目采用 23.976 fps，可按原设置写 `24000/1001`。使用 `yuv420p` 时宽高需为偶数。动画交付另行验证实际解码尺寸、帧率、时长和首尾帧。
