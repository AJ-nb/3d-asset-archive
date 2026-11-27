"""Verify the nine portable files from a new root on a second volume with detached source paths."""
from pathlib import Path
import hashlib
import json
import shutil
import tempfile
import bpy

P=Path(__file__).resolve().parent
BASE=P.parent
SRC=BASE/"06_自建工程与成片"
REG=P/"editable-projects.json"
notes=json.loads(REG.read_text(encoding="utf8"))
out=[]
with tempfile.TemporaryDirectory(prefix="pocket-portability-") as name:
    test=Path(name).resolve()
    if test.drive.casefold()==SRC.drive.casefold(): raise RuntimeError("Expected an isolated test on another volume.")
    parts=[BASE/c["path"] for c in notes["portable_copies"]]
    media=[BASE/c["file"] for c in notes["extracted_packed_images"]]
    media+=[SRC/"dji-osmo-pocket-4p-cg15/production/Pulse-score.wav"]
    for src in parts+media:
        target=test/src.relative_to(SRC)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,target)
    for c,src in zip(notes["portable_copies"],parts):
        target=test/src.relative_to(SRC)
        bpy.ops.wm.open_mainfile(filepath=str(target),load_ui=False,use_scripts=False)
        raw_paths=set(bpy.utils.blend_paths(absolute=False,packed=True,local=False))
        checks=[]
        for raw in sorted(raw_paths):
            p=Path(bpy.path.abspath(raw)).resolve()
            if not (raw.startswith("//") and p.is_relative_to(test) and p.is_file()):
                raise ValueError((target,raw,p))
            checks.append({"path":raw,"resolved_under_relocated_package":True})
        assert all(sc.render.filepath.startswith("//") and Path(bpy.path.abspath(sc.render.filepath)).resolve().is_relative_to(test) for sc in bpy.data.scenes)
        for im in bpy.data.images:
            if im.packed_file and im.source=="FILE":
                assert all(n>0 for n in im.size)
                pixels=tuple(im.pixels[:4]); assert len(pixels)==4
        out.append(dict(portable=c["path"],sha256=c["sha256"],relative_input_paths=checks,relative_output_verified=True))
    notes["relocation_test"]=dict(source_volume=SRC.drive,destination_volume=test.drive,blender=bpy.app.version_string,
        method="只将九份可携版和两张贴图、一段音轨移至另一磁盘的临时根目录逐一复开；所有 Blender 输入和输出路径均转入临时包内。",reports=out)
REG.write_text(json.dumps(notes,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
print("Verified relocated files:",len(out))
