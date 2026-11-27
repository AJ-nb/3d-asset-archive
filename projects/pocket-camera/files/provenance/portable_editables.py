"""Create distinctly named portable companions, preserve original snapshots, then re-open and compare."""
from pathlib import Path
from array import array
import hashlib
import json
import os
import struct
import sys
import tempfile
import bpy

P=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path.insert(0,str(P))
from audit_editables import BASE, FOLDER, inspect, sha

REG=P/"editable-projects.json"
info=json.loads(REG.read_text(encoding="utf8"))
v7=FOLDER/"dji-osmo-pocket-4p-v7"
media={}
portable=[]
def payload_signature():
    """Stored vertex coordinates, polygon vertex order, parentage, local transforms and animation curves."""
    h=hashlib.sha256()
    def feed(x): h.update(str(x).encode("utf8"));h.update(b"\0")
    for obj in sorted(bpy.data.objects,key=lambda o:o.name):
        feed((obj.name,obj.type,obj.parent.name if obj.parent else None,obj.data.name if obj.data else None))
        feed(tuple(round(a,7) for row in obj.matrix_local for a in row))
        for m in obj.material_slots: feed(m.material.name if m.material else "")
    for mesh in sorted(bpy.data.meshes,key=lambda m:m.name):
        feed(mesh.name)
        for coll,field,code,size in [(mesh.vertices,"co","f",3),(mesh.loops,"vertex_index","i",1),(mesh.polygons,"loop_total","i",1)]:
            buf=array(code,[0])*(len(coll)*size);coll.foreach_get(field,buf);h.update(buf.tobytes())
    count_keys=0
    for action in sorted(bpy.data.actions,key=lambda a:a.name):
        feed(action.name)
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        feed((curve.data_path,curve.array_index))
                        for pt in curve.keyframe_points:
                            count_keys+=1;feed((tuple(pt.co),tuple(pt.handle_left),tuple(pt.handle_right),pt.interpolation))
    return dict(mesh_animation_transform_sha256=h.hexdigest(),objects=len(bpy.data.objects),meshes=len(bpy.data.meshes),actions=len(bpy.data.actions),keyframe_points=count_keys)

def mix_audio(tmp):
    outfile=str(Path(tmp)/"mix.wav")
    bpy.ops.sound.mixdown(filepath=outfile,check_existing=False,container="WAV",codec="PCM",format="F32",mixrate=48000,channels="STEREO")
    raw=Path(outfile).read_bytes()
    i=12
    while i+8<=len(raw):
        tag=raw[i:i+4];n=struct.unpack_from("<I",raw,i+4)[0]
        if tag==b"data": return dict(samples_per_channel=n//8,pcm_f32_sha256=hashlib.sha256(raw[i+8:i+8+n]).hexdigest())
        i+=8+n+(n%2)
    raise ValueError("No PCM data")

def update_score(target):
    strips=bpy.context.scene.sequence_editor.strips
    old=next(s for s in strips if s.type=="SOUND")
    assert len(strips)==1 and old.left_handle==1 and old.right_handle==451
    sound=old.sound
    fields=("select","select_left_handle","select_right_handle","mute","lock","blend_type","blend_alpha","effect_fader","use_default_fade","color_tag","show_retiming_keys","volume","pan","sound_offset","show_waveform","pitch_correction","content_trim_start","content_trim_end")
    settings={name:getattr(old,name) for name in fields}
    name,channel=old.name,old.channel
    wav=target.parent/"production/Pulse-score.wav"
    assert sha(wav)==hashlib.sha256(sound.packed_file.data).hexdigest()
    new=strips.new_sound("portable_score_source",str(wav),old.channel+1,int(old.content_start))
    temp_sound=new.sound
    new.sound=sound
    strips.remove(old)
    new.channel=channel
    new.name=name
    for name,value in settings.items(): setattr(new,name,value)
    if temp_sound!=sound and temp_sound.users==0: bpy.data.sounds.remove(temp_sound)
    assert new.left_handle==1 and new.right_handle==451 and new.sound==sound
    # Convert the sequencer's separate native retained source path to //production/...
    bpy.ops.file.make_paths_relative()
    sound.filepath="//production/Pulse-score.wav"

def emit_packed_images(target):
    for img in bpy.data.images:
        if not img.packed_file: continue
        names={"DJI | sample gallery, official screen artwork":"display-artwork.png","V7 | yaw deck tangent normal":"yaw-deck-normal.png"}
        dest=v7/"portable-media"/names[img.name]
        dest.parent.mkdir(parents=True,exist_ok=True)
        blob=img.packed_file.data
        if dest.exists() and dest.read_bytes()!=blob: raise ValueError(f"Packed collision: {dest}")
        if not dest.exists(): dest.write_bytes(blob)
        img.filepath="//"+Path(os.path.relpath(dest,target.parent)).as_posix()
        media[dest.name]=dict(file=dest.relative_to(BASE).as_posix(),sha256=sha(dest),bytes=len(blob),source="已从工程内嵌图像字节提取",credit=("DJI 商店屏内风景裁图" if "display" in dest.name else "自建模型云台支臂切线法线图"))

for row in info["files"]:
    if row["kind"]!="editable_source": continue
    source=BASE/row["archive_path"]
    dest=source.with_name("Portable-"+source.name)
    assert dest.parent.is_relative_to(FOLDER) and dest!=source
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
    before=payload_signature()
    audio_before=None
    if row["version"]=="CG15":
        with tempfile.TemporaryDirectory() as tmp: audio_before=mix_audio(tmp)
        update_score(dest)
    emit_packed_images(dest)
    for sc in bpy.data.scenes:
        if row["version"]=="CG15": name="Pulse-"
        else: name="render-"
        sc.render.filepath="//portable-renders/"+name
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(dest),copy=True,relative_remap=False,compress=True)
    data=inspect(row,dest.relative_to(BASE).as_posix())
    after=payload_signature()
    if before!=after: raise ValueError(f"Geometry/animation changed: {dest.name} {before} {after}")
    data["source_original_sha256"]=row["sha256"]
    data["source_original"]=row["archive_path"]
    data["mesh_transform_animation_parity"]=after
    data["bytes"]=dest.stat().st_size
    assert not any(r["status"] in {"missing","outside_archive"} for r in data["resources"])
    # Blender's sequencer can keep another filename besides the packed audio datablock.
    for raw in data["unpacked_paths_via_blender"]:
        dst=Path(bpy.path.abspath(raw)).resolve()
        assert raw.startswith("//") and dst.is_relative_to(FOLDER) and dst.is_file(),(raw,dst)
    if audio_before:
        with tempfile.TemporaryDirectory() as tmp: audio_after=mix_audio(tmp)
        if audio_before!=audio_after: raise ValueError(f"Edited film mix differs: {audio_before}, {audio_after}")
        data["film_audio_pcm_parity"]=audio_after
    if sha(source)!=row["sha256"]: raise ValueError("Original snapshot changed")
    portable.append(data)
info["portable_copies"]=portable
info["extracted_packed_images"]=list(media.values())
info["portability"]="原件按哈希复制；Portable 前缀副本保存相对输出与输入位置。CG 的旧音频条另存相同名称/时序/混音参数后重读，原工程序列和可携版全长浮点 PCM 逐字节相同。已在本机 Blender 5.2.3 核对，不含其他操作系统实测。"
REG.write_text(json.dumps(info,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
print("Portable models verified:",len(portable),"extracted images:",len(media))
