"""Blender -b --factory-startup --disable-autoexec --python-exit-code 1 -P audit_editables.py

Open each archived original, enumerate file inputs, distinguish embedded media from file dependencies,
and record saved output destinations separately. No .blend or source project is saved.
"""
from pathlib import Path
import hashlib
import json
import bpy

BASE=Path(__file__).resolve().parent.parent
PROV=BASE/"provenance"
FOLDER=BASE/"06_自建工程与成片"
def sha(file):
    with file.open("rb") as f: return hashlib.file_digest(f,"sha256").hexdigest()
def get_path(raw,owner):
    try: return str(Path(bpy.path.abspath(raw,library=getattr(owner,"library",None))).resolve()) if raw else ""
    except (TypeError,ValueError,OSError): return ""
def packed_files(item):
    many=getattr(item,"packed_files",None)
    if many and len(many):
        return [getattr(f,"packed_file",f) for f in many]
    one=getattr(item,"packed_file",None)
    return [one] if one else []
def packed_info(items):
    return [{"bytes":f.size,"sha256":hashlib.sha256(f.data).hexdigest()} for f in items if f]
def inspect(row,alternate=None):
    target=BASE/(alternate or row["archive_path"])
    bpy.ops.wm.open_mainfile(filepath=str(target),load_ui=False,use_scripts=False)
    if Path(bpy.data.filepath).resolve()!=target.resolve(): raise RuntimeError(str(target))
    live_sha=sha(target)
    if not alternate and row["sha256"]!=live_sha: raise ValueError(target)
    resources=[]
    for dbtype in ("images","fonts","sounds","libraries","movieclips","cache_files","volumes","texts","pointclouds","hair_curves","lightprobes"):
        for item in getattr(bpy.data,dbtype,()):
            raw=getattr(item,"filepath","") or ""
            packed=packed_info(packed_files(item))
            subtype=getattr(item,"source","") or getattr(item,"type","")
            if dbtype=="images" and subtype in {"GENERATED","VIEWER"}:
                status="generated_or_render_buffer"
            elif packed:
                status="embedded"
            elif dbtype=="fonts" and (raw=="<builtin>" or (item.name=="Bfont" and not raw)):
                status="blender_builtin"
            elif raw:
                resolved=get_path(raw,item)
                inside=Path(resolved).is_relative_to(FOLDER) if resolved else False
                status=("present_in_archive" if inside else "outside_archive") if resolved and Path(resolved).is_file() else "missing"
            else:
                status="in_blend_datablock"
            result=dict(type=dbtype,name=item.name,source_kind=subtype,users=item.users,stored_path=raw,status=status)
            if raw and raw!="<builtin>": result["resolved_path"]=get_path(raw,item)
            if packed: result["packed_files"]=packed
            if dbtype=="images" and subtype not in {"VIEWER","GENERATED"}:
                result["dimensions"]=list(item.size)
            if dbtype=="libraries" and item.parent: result["parent_library"]=item.parent.name
            resources.append(result)
    # An image/sound strip can hold an external path even if no separate ID exists for it.
    for scene in bpy.data.scenes:
        sequence=scene.sequence_editor
        if sequence:
            strips=getattr(sequence,"strips_all",())
            for strip in strips:
                if strip.type in {"IMAGE","MOVIE"}:
                    paths=[getattr(strip,"filepath","")] if strip.type=="MOVIE" else [
                        str(getattr(strip,"directory",""))+s.filename for s in strip.elements]
                    for raw in filter(None,paths):
                        resolved=get_path(raw,scene)
                        inside=Path(resolved).is_relative_to(FOLDER)
                        exists=Path(resolved).is_file()
                        resources.append(dict(type="sequence."+strip.type,name=strip.name,stored_path=raw,
                          resolved_path=resolved,status=("present_in_archive" if inside else "outside_archive") if exists else "missing"))
    output_settings=[]
    for scene in bpy.data.scenes:
        output_settings.append(dict(scene=scene.name,render_filepath=scene.render.filepath))
        for node in (scene.compositing_node_group.nodes if scene.compositing_node_group else []):
            if node.type=="OUTPUT_FILE": output_settings[-1].setdefault("compositor_output",[]).append(getattr(node,"directory",getattr(node,"base_path","")))
    allpaths=sorted(set(str(s) for s in bpy.utils.blend_paths(absolute=False,packed=False,local=False) if s))
    return dict(path=target.relative_to(BASE).as_posix(),sha256=live_sha,
                blender=bpy.app.version_string,scene_names=[s.name for s in bpy.data.scenes],
                active_scene=bpy.context.scene.name,frame_range=[bpy.context.scene.frame_start,bpy.context.scene.frame_end],
                cameras=len(bpy.data.cameras),objects=len(bpy.data.objects),materials=len(bpy.data.materials),
                resources=resources,unpacked_paths_via_blender=allpaths,output_settings=output_settings)
if __name__=="__main__":
    files=json.loads((PROV/"editable-inputs.json").read_text(encoding="utf8"))
    checks=[inspect(row) for row in files if row["kind"]=="editable_source"]
    for check in checks:
        print("@@AUDIT",Path(check["path"]).name,"outside or missing",[(r["name"],r["status"]) for r in check["resources"] if r["status"] in {"outside_archive","missing"}],"filepaths",check["unpacked_paths_via_blender"])
    notes=dict(scope="V1–V6 主模型、V7 基线及 Final、CG15 工程与成片",blender=bpy.app.version_string,files=files,model_checks=checks)
    (PROV/"editable-projects.json").write_text(json.dumps(notes,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
