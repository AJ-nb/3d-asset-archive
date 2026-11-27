"""Reopen the archived Blender projects and count the data that loads."""
import json
from pathlib import Path

import bpy


root = Path(__file__).resolve().parents[1]
records = []
for path in sorted((root / "源工程与记录").rglob("*.blend")):
    bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False, use_scripts=False)
    missing = []
    for image in bpy.data.images:
        if image.source != "FILE" or image.packed_file or not image.filepath:
            continue
        if not Path(bpy.path.abspath(image.filepath)).is_file():
            missing.append(image.name)
    records.append({
        "归档路径": path.relative_to(root).as_posix(),
        "场景": [scene.name for scene in bpy.data.scenes],
        "网格对象": sum(obj.type == "MESH" for obj in bpy.data.objects),
        "相机": len(bpy.data.cameras),
        "动作": len(bpy.data.actions),
        "缺失的外部静态图片": missing,
    })
    print(records[-1], flush=True)

(root / "源工程与记录" / "工程打开复验.json").write_text(
    json.dumps({"Blender": bpy.app.version_string, "工程": records}, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
