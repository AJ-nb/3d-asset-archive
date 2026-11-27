"""Create the readable index without modifying historical scripts or original files."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil

BASE=Path(__file__).resolve().parent.parent
PROV=BASE/"provenance/editable-projects.json"
ROOT=BASE/"06_自建工程与成片"
data=json.loads(PROV.read_text(encoding="utf8"))
cg=ROOT/"dji-osmo-pocket-4p-cg15"
v7=ROOT/"dji-osmo-pocket-4p-v7"
original=Path("D:/oc/output/dji-osmo-pocket-4p-v7/review/镜头与云台线框素模-Final.jpg")
local=v7/"review"/original.name
local.parent.mkdir(parents=True,exist_ok=True)
def sha(path):
    with path.open("rb") as handle: return hashlib.file_digest(handle,"sha256").hexdigest()
if local.exists() and sha(local)!=sha(original): raise ValueError("Conflicting comparison sheet")
if not local.exists(): shutil.copy2(original,local)
assert sha(original)==sha(local)
script_text=(cg/"15秒CG分镜脚本.md").read_text(encoding="utf8")
script_text=script_text.replace("../dji-osmo-pocket-4p-v7/renders/","../../02_历版效果图/V7_终版/")
readable=cg/"15秒CG分镜脚本-归档阅读版.md"
readable.write_text(script_text,encoding="utf8")
for doc in [readable,cg/"15秒执行分镜.md"]:
    for link in re.findall(r'\]\(([^)]+)\)',doc.read_text(encoding="utf8")):
        assert (cg/link).is_file(),(doc,link)
def rel(path): return Path(os.path.relpath(BASE/path,ROOT)).as_posix()
def url(label,path): return f"[{label}]({rel(path)})"
rows=[]
for n,(orig,portable) in enumerate(zip(data["model_checks"],data["portable_copies"])):
    label=["V1 初版","V2 壳体与装配","V3 截面修形","V4 云台连接","V5 镜头表面","V6 轴承与干涉","V7 基线","V7 Final 成品","CG15 成片工程"][n]
    rows.append(f"| {label} | {url('可携工程',portable['path'])} | {url('原始快照',orig['path'])} |")
text="""# 自建工程与 15 秒成片

继续编辑成品，请打开 **V7 Final 可携工程**。编辑运镜或播放时间线，请打开 **CG15 可携工程**。直接播放可用[15 秒竖屏成片](dji-osmo-pocket-4p-cg15/Pulse-15s.mp4)。保持整个目录的层次，新的渲染将写入工程旁的 portable-renders 文件夹。

| 阶段 | 跨路径编辑 | 当时归档的源文件 |
| --- | --- | --- |
"""+'\n'.join(rows)+"""

九个原始快照逐字节复制并核对 SHA-256。V1–V4 原件保存着旧 D 盘的渲染输出目录；CG15 原件中有内嵌声音，序列另记了一次旧的绝对 WAV 路径。可携版把输出和媒体路径改为相对位置。为便于替换或编辑，另附[原声 WAV](dji-osmo-pocket-4p-cg15/production/Pulse-score.wav)、[屏幕图片](dji-osmo-pocket-4p-v7/portable-media/display-artwork.png)和[支臂法线贴图](dji-osmo-pocket-4p-v7/portable-media/yaw-deck-normal.png)。屏内示例风景来自 DJI 商店，详见[来源记录](../provenance/同期依据/V7/studio/display-source.json)。

在同一台 Windows 机器上用 Blender 5.2.3 LTS 复开了九份原件和九份可携版，比较网格顶点、面索引、局部变换、父级、对象材质槽及动作关键帧。可携版随后移至 C 盘临时目录再次逐个打开，检查到的读写路径都落在移动后的包内。CG15 的可携版与原件导出的完整双声道 PCM 数据逐字节相同。macOS、Linux 及其他 Blender 版本未经实机验证。[完整路径、哈希与复开清单](../provenance/editable-projects.json)

15 秒短片附[分镜方案](dji-osmo-pocket-4p-cg15/15秒CG分镜脚本-归档阅读版.md)、[执行分镜](dji-osmo-pocket-4p-cg15/15秒执行分镜.md)、[剪辑表](dji-osmo-pocket-4p-cg15/分镜剪辑表.csv)、[相机数据](dji-osmo-pocket-4p-cg15/镜头数据.csv)及[全片联系表](dji-osmo-pocket-4p-cg15/Pulse-contact.jpg)。分镜方案阅读版仅调整图片链接，原始文稿保留在同一文件夹。
"""
index=ROOT/"工程索引.md"
index.write_text(text,encoding="utf8")
for link in re.findall(r'\]\(([^)]+)\)',text):
    assert (ROOT/link).is_file(),link
data["additional_documents"]=[dict(path=local.relative_to(BASE).as_posix(),source_path=str(original),source_sha256=sha(original),sha256=sha(local)),dict(path=readable.relative_to(BASE).as_posix(),source_path="归档原始分镜文稿，修改图片相对链接",sha256=sha(readable)),dict(path=index.relative_to(BASE).as_posix(),sha256=sha(index))]
PROV.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
print(len(rows),"stages indexed")
