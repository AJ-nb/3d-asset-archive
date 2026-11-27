# Product CG Studio MCP

把现有的 Blender 工程交给支持 MCP 的 AI 客户端，按清单复查装配、比较截面和圆角，再把选中的镜头渲染到本地。设计访谈、参考选择、改模和视觉验收继续按 [Product CG Studio 工作流](../SKILL.md)进行。服务通过标准输入输出（stdio）连接，由客户端启动；运行渲染的电脑需要安装 Blender。

## 接入客户端

取得完整的 `product-cg-studio` 文件夹。服务会调用相邻 `scripts/` 下的 Blender 脚本。[下载 Skill 和 MCP 的完整包](https://github.com/AJ-nb/3d-asset-archive/raw/refs/heads/main/downloads/product-cg-studio.zip)

以下示例使用 Python 3.12。在 Windows PowerShell 中进入解压后的 `product-cg-studio` 目录，把 `$project` 和 `$blenderExe` 换成本机已有目录和程序路径。

~~~powershell
$venv = Join-Path $env:LOCALAPPDATA "product-cg-studio/venv"
py -3.12 -m venv $venv
$pythonExe = Join-Path $venv "Scripts/python.exe"
$serverFile = (Resolve-Path "./mcp/server.py").Path
& $pythonExe -m pip install -r ./mcp/requirements.txt
$project = "D:/CG/desk-support-trial"
$blenderExe = "D:/blender/blender.exe"
codex mcp add product-cg-studio -- $pythonExe $serverFile --workspace $project --blender $blenderExe --external-render-worker
& $pythonExe ./mcp/render_jobs.py serve --workspace $project --blender $blenderExe
~~~

最后一行启动独立渲染进程。保持这个终端运行，可以关闭或重开 AI 客户端。Windows 上有些客户端会在断开时终止其启动的整个进程树，独立工作进程能继续处理已提交的镜头。

macOS／Linux 可以用下列命令，从同一个技能目录执行。把项目目录和 Blender 程序换成实际路径；macOS 的 Blender 通常位于 `/Applications/Blender.app/Contents/MacOS/Blender`。

~~~sh
python3.12 -m venv "$HOME/.venvs/product-cg-studio"
py="$HOME/.venvs/product-cg-studio/bin/python"
"$py" -m pip install -r mcp/requirements.txt
project="/path/to/project"
blender="/path/to/blender"
codex mcp add product-cg-studio -- "$py" "$PWD/mcp/server.py" --workspace "$project" --blender "$blender" --external-render-worker
"$py" mcp/render_jobs.py serve --workspace "$project" --blender "$blender"
~~~

在 Codex 中运行 `codex mcp get product-cg-studio` 核对启动命令，再新开对话。其他采用 `mcpServers` 配置的 stdio 客户端可使用如下 JSON，替换为本机绝对路径并重连。Blender 已在 PATH 中时可省略 `--blender`，也可通过 `BLENDER_BIN` 指定。

~~~json
{
  "mcpServers": {
    "product-cg-studio": {
      "command": "C:/Users/you/AppData/Local/product-cg-studio/venv/Scripts/python.exe",
      "args": [
        "D:/tools/product-cg-studio/mcp/server.py",
        "--workspace", "D:/CG/desk-support-trial",
        "--blender", "D:/blender/blender.exe",
        "--external-render-worker"
      ]
    }
  }
}
~~~

`--workspace` 应指向包含客户工程、清单和已归档依赖的项目目录。客户端与独立工作进程应指向同一工作区和 Blender。传给工具的文件名相对于工作区，镜头清单内的路径相对于清单所在目录。每轮输出位于 `.product-cg-mcp/`。请在能运行该项目的受信任环境中打开工程；Blender 仍以启动账户权限读取工程引用的外链。

只在当前对话内做短任务时，可省略 `--external-render-worker` 和启动独立进程的命令，由服务自行启动每次渲染。使用这种模式时请保持客户端连接到任务结束。装配、截面和镜头预检可在两种模式下直接运行。对大型工程，请按实际检查耗时调整客户端的工具调用超时。

## 五个工具

| 客户想知道什么 | 调用 | 应核对的结果 |
| --- | --- | --- |
| 折脚收拢时哪一帧相撞，或哪条刚性、间隙、蒙皮约束越界？ | `audit_assembly(blend, manifest)` | 在 JSON 清单中指定场景、帧／子帧、对象对或测点和容差。查看逐项报告里的失败对象与采样结果。[清单与测量方式](../references/assembly-and-rig.md) |
| 改模后哪些站位和哪些圆角偏离对照？ | `compare_sections(blend, parts, pose, reference_blend, bevel_windows)`（按名传参） | 命名部件按默认 X/Y/Z 每 1 mm 取截面。两版需要同一尺度、部件名、姿态和装配基准。可指定场景、局部基准物、轴、帧和范围。圆角拟合另给同一处的测量窗。只有一个工程时可留存其截面，实物偏差仍未知。[配准、圆角窗口与叠图](../references/sections.md) |
| 机位可用、关键贴图都能读取吗？ | `preflight_render(manifest, shot_ids)` | 省略镜头列表以预检全批。检查每个镜头的状态、依赖和源工程指纹；`needs_review` 时按报告补齐资料。[镜头清单示例](../examples/batch.json) |
| 能否单独重出改过的镜头？ | `submit_render(manifest, shot_ids)` | 返回新的 `job_id`。传一个或多个镜头 ID 可单独重渲，每次提交都有独立目录。 |
| 关闭对话后如何找回结果？ | `render_status(job_id)` | 在同一工作区按原 ID 查看各镜头、报告和可用输出。已完成的 PNG 存在本机，可逐张打开。[渲染输出与适用范围](../references/batch.md) |

装配返回 `passed`、`failed` 或 `incomplete`。后者表示有检查无法求值，例如对象被改名；同时查看其余已测项目的失败样本。截面对比返回 `needs_review`，并给出候选件／参考件覆盖、最差已比站位与圆角拟合值，根据本单容差判断能否签收。

使用独立工作进程时，`queued` 且 `worker_online: false` 表示任务已经写入磁盘。启动同一工作区的工作进程后会开始消费队列。`running` 表示正在执行，`completed` 时可在 `shots` 中取得成图。若工作进程在渲染中被终止，`interrupted` 会标出未完成的镜头；用这些镜头的 ID 重新提交，新旧报告各自保留。

## 用 DJI 桌面支架试跑

把仓库中 [DJI 桌面支架项目](https://github.com/AJ-nb/3d-asset-archive/tree/main/projects/pocket-camera/desk-support-trial) 的 `desk-study.blend`、`fold-checks.json` 和 `shots.json` 放在同一目录，设为工作区。将以下指令发给已接入的客户端。

> 用 product-cg-studio 的 audit_assembly 打开 desk-study.blend，清单是 fold-checks.json。告诉我折脚收拢时测了哪些帧、有无表面相交，并给出报告。再用 shots.json 预检 bundle 镜头，预检通过后只渲染 bundle。保存任务 ID，查询到结束，给我成图的位置。

这份清单覆盖三条支脚之间的 12 个网格配对和第 94–110 帧的 17 个整数帧。原始试用在较早设计上找到四条相交记录，修正版可用此清单重查。结果适用于指定网格和采样时刻；判断最小装配间隙或两帧之间的擦碰，需要相应的距离测量和加密取样。[早期相交记录](https://github.com/AJ-nb/3d-asset-archive/blob/main/projects/pocket-camera/desk-support-trial/intersections-before.json)

## 用已知偏差校验截面测量

将技能自带的 [verification-data.zip](../examples/verification-data.zip) 解压到工作区，保留 `sections/` 子目录。调用 `compare_sections` 时传入以下参数。

~~~json
{
  "blend": "sections/draft.blend",
  "reference_blend": "sections/reference.blend",
  "parts": ["Gauge"],
  "pose": "neutral",
  "axes": "Z",
  "range_mm": [0, 0],
  "bevel_windows": "sections/fits.json"
}
~~~

Z=0 站的预期轮廓偏差约为 0.4142 mm，圆角拟合为初稿约 R2、参考约 R1。把 `blend` 改为 `sections/corrected.blend` 再运行，检查相同站位和同一圆角窗。这里的 1 mm 指相邻截面的间距；对实物还原精度的判断还取决于测量参考、配准误差和网格质量。

要从独立客户端复验安装，可在技能目录运行下面的命令。它使用包内的已知正常和故障工程，并把结果保留在指定的新目录。

~~~powershell
& $pythonExe ./mcp/tests/smoke_stdio.py --blender $blenderExe --output ./mcp-test-01
~~~
