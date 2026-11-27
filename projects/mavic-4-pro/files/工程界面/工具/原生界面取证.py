"""Run in a new, visible Blender window on the appropriate original .blend.

blender -M file.blend -P this_script.py -- layout
The optional keys first, clay, mesh, rig and node select the other views.
Nothing in any source .blend is saved. The output is Blender's own window buffer.
"""
import hashlib
import json
import os
import struct
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

here = Path(__file__).resolve().parent.parent
keys = sys.argv[sys.argv.index("--")+1:]
stems = dict(layout="01-预演体块", first="02-首轮装配", clay="03-正式白模",
             mesh="04-后肩编辑网格", rig="05-折叠机构与动作", node="06-机壳材质节点")
notes = dict(
    layout="真实预演工程中的十个体块。包含四个机臂轮廓、四个旋翼占位、一处机身、一处云台。",
    first="首轮装配存档中的机体、旋翼和光学总成。工程视口按各对象材质的基础色显示。",
    clay="最新完整装配，使用统一浅灰视口着色观察外壳、云台、桥接和展开轮廓。",
    mesh="左后机臂根部的真实多对象编辑模式，周围壳体和臂梁保持可见以便辨认装配位置。",
    rig="正式工程第52帧的折叠中间态，选中左右后臂折叠骨骼，下方可见工程内实际的关键帧。",
    node="机壳的真实着色器树。上方为使用材质基础色的实物造型视口，下方显示原来相连的材质节点。临时整理节点显示位置，连接、参数与源文件一致。")

win = bpy.context.window_manager.windows[0]
scene = win.scene
prefs = bpy.context.preferences
prefs.view.use_save_prompt = False
prefs.view.show_splash = False
source = Path(bpy.data.filepath)
with source.open("rb") as fh:
    source_hash = hashlib.file_digest(fh,"sha256").hexdigest()
root = next(o for o in scene.objects if o.name.startswith("AIRCRAFT  |"))
body = next((o for o in scene.objects if o.name.startswith("Fuselage | sculpted composite")), None)
main = max((a for a in win.screen.areas if a.type == "VIEW_3D"), key=lambda a:a.width*a.height)
side = next(a for a in win.screen.areas if a.type == "OUTLINER")
props = next(a for a in win.screen.areas if a.type == "PROPERTIES")
bottom = next(a for a in win.screen.areas if a.type == "DOPESHEET_EDITOR")
index = 0
phase = 0
active = None
points = None
bounds = None
has_detail_panel = False

def region(area):
    return next(r for r in area.regions if r.type=="WINDOW")

def override(area):
    return bpy.context.temp_override(window=win,area=area,region=region(area))

def redraw():
    for area in win.screen.areas:
        area.tag_redraw()

def split_view():
    with override(main):
        assert bpy.ops.screen.area_split(direction="HORIZONTAL",factor=.42)=={"FINISHED"}

def assign_detail_panel():
    global main,bottom,has_detail_panel
    editors=sorted((area for area in win.screen.areas if area.type=="VIEW_3D"),
                   key=lambda area:area.y)
    assert len(editors)==2
    bottom,main=editors
    has_detail_panel=True

def choose(objects):
    for o in win.view_layer.objects:
        if o.select_get():
            o.select_set(False)
    for o in objects:
        o.select_set(True)
    win.view_layer.objects.active = objects[0]

def cloud(objects):
    graph = bpy.context.evaluated_depsgraph_get()
    parts = []
    for ob in objects:
        ev = ob.evaluated_get(graph)
        m = ev.to_mesh()
        co = np.empty(len(m.vertices)*3,dtype=np.float32)
        m.vertices.foreach_get("co",co)
        transform = np.array(ev.matrix_world)
        parts.append(co.reshape(-1,3)@transform[:3,:3].T+transform[:3,3])
        ev.to_mesh_clear()
    return np.concatenate(parts)

def align(center, direction, distance):
    rv = main.spaces.active.region_3d
    rv.view_perspective = "ORTHO"
    rv.view_rotation = Vector(direction).to_track_quat("Z","Y")
    rv.view_distance = distance
    rv.view_location = Vector(center)

def get_screen_box():
    pr = np.asarray(main.spaces.active.region_3d.perspective_matrix)
    v = points@pr[:3,:3].T + pr[:3,3]
    w = points@pr[3,:3]+pr[3,3]
    coords = v[:,:2]/w[:,None]
    return np.array((coords.min(0),coords.max(0)))

def fit_to_view(key):
    rv = main.spaces.active.region_3d
    box = get_screen_box()
    c = box.mean(axis=0)
    pr = np.asarray(rv.perspective_matrix)
    right, up = [rv.view_rotation@Vector(axis) for axis in ((1,0,0),(0,1,0))]
    rv.view_location += right*(c[0]/(pr[0,:3]@right)) + up*(c[1]/(pr[1,:3]@up))
    target = (.84,.76) if key not in ("rig","node") else (.80,.77)
    rv.view_distance *= max(np.ptp(box,axis=0)/2/target)
    redraw()

def set_prop(mode):
    try:
        with override(props):
            props.spaces.active.context=mode
    except TypeError:
        pass

def setup(key):
    global active, points
    view = main.spaces.active
    with override(main):
        if win.view_layer.objects.active and win.view_layer.objects.active.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    for c in scene.collection.children_recursive:
        if c.name.startswith(("05  /","06  /","07  /","08  /","09  /")):
            c.hide_viewport = True
    for o in scene.objects:
        if o.type in ("CAMERA","LIGHT") or o.name.startswith("Photo / "):
            o.hide_set(True)
        if o.type=="ARMATURE":
            o.hide_set(key!="rig")
    scene.frame_set(52 if key=="rig" else 32 if key in ("first","layout") else 1)
    win.view_layer.update()
    view.show_region_ui=False
    view.show_region_toolbar=False
    view.show_gizmo=False
    view.clip_start=.0001
    view.clip_end=1000
    view.shading.type="SOLID"
    view.shading.light="STUDIO"
    view.shading.color_type="MATERIAL" if key in ("first","rig","node") else "SINGLE"
    view.shading.single_color=(.83,.84,.86)
    view.shading.show_cavity=True
    view.shading.cavity_type="BOTH"
    view.shading.curvature_ridge_factor=.7
    view.shading.curvature_valley_factor=.8
    view.shading.cavity_ridge_factor=.75
    view.shading.cavity_valley_factor=.8
    view.shading.show_shadows=False
    view.shading.background_type="VIEWPORT"
    view.shading.background_color=(.061,.071,.085)
    ovr = view.overlay
    ovr.show_overlays=True
    ovr.show_floor=False
    ovr.show_axis_x=False
    ovr.show_axis_y=False
    ovr.show_extras=False
    ovr.show_bones=True
    ovr.show_cursor=False
    ovr.show_relationship_lines=False
    ovr.show_outline_selected=False
    ovr.show_stats=True
    ovr.show_text=True
    parts=[o for o in root.children_recursive if o.type in ("MESH","FONT","CURVE") and not o.hide_render]
    if key=="layout":
        active=scene.objects["Blockout shell"]
        parts=[o for o in scene.objects if o.name.startswith(("Blockout ","Arm guide","Rotor bounds"))]
        assert len(parts)==10
    elif key=="first":
        active=body
    else:
        active=body
    choose([active])
    set_prop("OBJECT")
    if key=="mesh":
        active=scene.objects["Rear.L | rounded shoulder boot"]
        nearby=[active,scene.objects["Rear.L | rear socket lip"],scene.objects["Rear.L | shoulder retaining cap"]]
        points=cloud(nearby)
        choose(nearby)
        with override(main):
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_mode(type="EDGE")
            bpy.ops.mesh.select_all(action="DESELECT")
        align((-.055,.01,.075),(-.9,.48,.9),.14)
        set_prop("DATA")
    else:
        points=cloud(parts)
        center=(points.min(0)+points.max(0))/2
        look=(.49,-1,.64)
        if key=="layout":
            look=(.48,-1,.76)
        if key=="rig":
            look=(.13,-.38,1.0)
            active=scene.objects["Mavic 4 Pro | Mechanical FK"]
            choose([active])
            active.show_in_front=True
            active.data.display_type="OCTAHEDRAL"
            with override(main):
                bpy.ops.object.mode_set(mode="POSE")
                bpy.ops.pose.select_all(action="DESELECT")
                for name in ("Rear.L / arm fold","Rear.R / arm fold"):
                    active.pose.bones[name].select=True
                active.data.bones.active=active.data.bones["Rear.L / arm fold"]
            bottom.ui_type="DOPESHEET"
            bottom.spaces.active.mode="DOPESHEET"
            bottom.spaces.active.show_region_ui=False
            bottom.spaces.active.dopesheet.show_only_selected=True
            set_prop("BONE")
        if key=="node":
            active=body
            choose([active])
            mat=next(m for m in active.data.materials if m.name.startswith("Airframe"))
            active.active_material_index=next(i for i,m in enumerate(active.data.materials) if m==mat)
            bottom.ui_type="ShaderNodeTree"
            nsp=bottom.spaces.active
            nsp.shader_type="OBJECT"
            nsp.show_region_ui=False
            nsp.show_region_toolbar=False
            loc={"TEX_COORD":(-750,120),"TEX_NOISE":(-528,120),"MAP_RANGE":(-280,135),"BUMP":(-280,-106),
                 "BSDF_PRINCIPLED":(6,110),"OUTPUT_MATERIAL":(335,110)}
            for n in mat.node_tree.nodes:
                n.location=loc[n.type]
                n.select=True
                n.width=188 if n.type=="BSDF_PRINCIPLED" else 154
                for socket in n.inputs:
                    socket.hide=not socket.is_linked and socket.name not in ("Color","Base Color","Roughness","Strength","Distance","Scale")
                for socket in n.outputs:
                    socket.hide=not socket.is_linked
            set_prop("MATERIAL")
        align(center,look,.72)
    redraw()

def contextual(key):
    with override(side):
        try:
            if bpy.ops.outliner.show_active.poll():
                bpy.ops.outliner.show_active()
        except RuntimeError:
            pass
    if key=="rig":
        with override(bottom):
            for step in range(4):
                if bpy.ops.anim.channels_expand.poll():
                    bpy.ops.anim.channels_expand(all=True)
            bpy.ops.action.view_all()
    if key=="node":
        with override(bottom):
            bpy.ops.node.view_all()
    if key=="mesh":
        # Set a close but contextual crop using the seven-millimetre-wide shaft as a scale.
        rv=main.spaces.active.region_3d
        rv.view_location=root.matrix_world@Vector(( -55,8,72))
        rv.view_distance=.132
    else:
        fit_to_view(key)
    redraw()

def save(key):
    path=here/(stems[key]+".png")
    with bpy.context.temp_override(window=win):
        result=bpy.ops.screen.screenshot(filepath=str(path))
    assert result=={"FINISHED"} and path.is_file()
    data=path.read_bytes()
    w,h=struct.unpack(">II",data[16:24])
    assert w>=1300 and h>=720
    r=region(main)
    rec=dict(id=key,file=path.name,sha256=hashlib.sha256(data).hexdigest(),
             screen_px=[w,h],captured_utc=datetime.now(timezone.utc).isoformat(),
             method="bpy.ops.screen.screenshot (full Blender application window, uncropped)",
             blender=bpy.app.version_string,source=str(source),source_sha256=source_hash,
             scene=scene.name,frame=scene.frame_current,description=notes[key],
             mode=active.mode,active=active.name,viewport_px=[r.width,r.height],
             viewport_subject_NDC_bounds=get_screen_box().tolist(),
             editors=[dict(type=a.type,ui_type=a.ui_type,x=a.x,y=a.y,w=a.width,h=a.height) for a in win.screen.areas])
    if key=="node":
        tree=active.active_material.node_tree
        rec["shader_material"]=active.active_material.name
        rec["shader_links"]=[(l.from_node.type,l.from_socket.name,l.to_node.type,l.to_socket.name) for l in tree.links]
    if key=="rig":
        rec["bones_selected"]=[b.name for b in active.pose.bones if b.select]
        rec["keyed_action"]=active.animation_data.action.name
    cache=here/"工具"/"记录"
    cache.mkdir(exist_ok=True)
    (cache/(key+".json")).write_text(json.dumps(rec,ensure_ascii=False,indent=2),"utf8")
    print("SAVED",repr(path),w,h,rec["viewport_subject_NDC_bounds"],flush=True)

def tick():
    global phase,index
    try:
        if index>=len(keys):
            os._exit(0)
        key=keys[index]
        if phase==0:
            if key in ("rig","node") and not has_detail_panel:
                split_view()
                phase=-1
                return 1.1
            phase=-2
        if phase==-1:
            assign_detail_panel()
            phase=-2
        if phase==-2:
            setup(key)
            phase=1
            return 1.7
        if phase==1:
            contextual(key)
            phase=2
            return 2.2
        save(key)
        index+=1
        phase=0
        return .4
    except BaseException:
        traceback.print_exc()
        sys.stderr.flush()
        os._exit(2)

bpy.app.timers.register(tick,first_interval=2.2)
