from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
from PIL import Image

work = Path(__file__).resolve().parent
root = work.parents[1]
display = {
    "early": "Solid / Random object colors / orthographic front three-quarter / Outliner",
    "clay": "Solid / Single color / studio light / world cavity / orthographic front three-quarter",
    "wire": "Solid / Single color / selected optical front and local mesh-wire overlay / modifier properties",
    "joints": "Solid / Random object colors / isolated pan, roll and tilt geometry / rear three-quarter",
    "shader": "Solid / single color + Shader Editor / original nodes temporarily arranged for readability in memory",
    "film": "Solid / active editorial camera and Action Editor / Film | stabilizer and display / markers and selected keyframes",
    "studio": "Solid / six V7 studio area lights and hero camera isolated for display / Image Editor with prior V7 4K master / physical key-light settings",
}
rows = []
for s in ("early", "final", "film", "studio"):
    rows.extend(json.loads((work / (s + ".json")).read_text(encoding="utf-8")))
for row in rows:
    path = root / row["file"]
    source = Path(row["source"])
    assert hashlib.sha256(source.read_bytes()).hexdigest() == row["source_sha256"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == row["screenshot_sha256"]
    with Image.open(path) as im:
        assert list(im.size) == row["window_pixels"] == [2260, 1280]
        im.verify()
    row["file"] = path.relative_to(root).as_posix()
    row["last_written_utc"] = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
    row["view_display_and_editors"] = display[row["id"]]
    row["capture_origin"] = "本次在单独的 Blender 窗口重开对应存档，设置观察方式后截取。"
studio=next(r for r in rows if r["id"]=="studio")
assert hashlib.sha256(Path(studio["paired_original_render"]).read_bytes()).hexdigest()==studio["paired_render_sha256"]
historic_source=Path("C:/Users/Arjen/AppData/Local/Temp/codex-clipboard-79df1bfb-1c05-448f-942e-496bd0f8dde6.png")
historic_copy=root/"04_Blender工程实拍/00_V3_当时反馈原始截图.png"
historic_sha=hashlib.sha256(historic_source.read_bytes()).hexdigest()
assert hashlib.sha256(historic_copy.read_bytes()).hexdigest()==historic_sha
with Image.open(historic_copy) as im:
    dims=list(im.size)
    im.verify()
rows.insert(0,{"id":"historical_v3","file":historic_copy.relative_to(root).as_posix(),
    "caption":"用户反馈镜头与下方连接结构时随消息提交的 V3 Blender 工程桌面截图。",
    "frame":1,"app_version":"5.2.2 LTS (as shown in original title bar)",
    "source":str(historic_source),"source_sha256":historic_sha,"screenshot_sha256":historic_sha,
    "recaptured":False,"window_pixels":dims,"capture_method":"原附件按字节复制",
    "capture_origin":"用户历史消息随附原图。原始 PNG 文件和归档件按字节一致。",
    "source_file_last_written_utc":datetime.fromtimestamp(historic_source.stat().st_mtime,timezone.utc).isoformat(),
    "blend_path_visible_in_original":"D:/oc/output/dji-osmo-pocket-4p-v3/DJI-Osmo-Pocket-4P-Classic-Black-V3.blend"})
assert len(rows) == 8 and len({r["screenshot_sha256"] for r in rows}) == 8
output = {"capture_count": len(rows), "historical_attachment_count":1,"recaptured_count":7,
          "recaptured_app": "Blender 5.2.3 LTS", "recaptured_dimensions": [2260, 1280],
          "publication_context": "00 为历史反馈原附件。01 至 07 为本次打开工程补拍。早期分件来自现存 V1 完整工程，白模为 V7 Final 的单色观察。",
          "source_check": "八张截图均已核对实际像素和 SHA-256；补拍核对三个源工程，与第 07 张配对的 4K 主视觉另有源图哈希。", "captures": rows}
(root / "provenance/ui-captures.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
