"""Screenshot the opened native Blender window. All changes are unsaved inspection settings."""
from pathlib import Path
import hashlib, json, math, sys, traceback
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/"04_Blender工程实拍"
WORK=Path(__file__).resolve().parent
MODE=sys.argv[sys.argv.index("--")+1]
SOURCE=Path(bpy.data.filepath)
W=bpy.context.window_manager.windows[0]
SC=W.scene
STEPS={"early":["early"],"final":["clay","wire","joints","shader"],"film":["film"]}
FILES={"early":"01_V1_早期分件与装配","clay":"02_V7_整机白模",
       "wire":"03_V7_镜头面板与线框","joints":"04_V7_云台传动支承",
       "shader":"05_V7_支臂材质节点","film":"06_CG_转屏与动画时间线"}
CAPTIONS={"early":"打开现存第一版完整工程，以零件颜色观察早期外观装配。界面分色由 Blender 对象显示生成。",
          "clay":"打开 V7 Final，用视口单色工作室照明观察整机。该图是对最终几何的白模复查。",
          "wire":"V7 Final 镜头正面。白色实体与原生拓扑边同屏，展示保护窗、镜圈与倒角排线。",
          "joints":"V7 Final 云台后侧，隔离偏航、横滚、俯仰相关的实际零件。隔离仅用于显示内部支撑关系。",
          "shader":"V7 Final 偏航支臂着色树。显示工程内的切线空间法线贴图、法线节点与 Principled 材质。",
          "film":"打开成片源工程，查看转屏过程与原生控制器的关键帧、切镜时间标记。画面为实体视图。"}
DEST.mkdir(exist_ok=True,parents=True)
STEPS["studio"]=["studio"]
FILES["studio"]="07_V7_棚灯机位与主视觉"
CAPTIONS["studio"]="V7 Final 棚拍。左侧显示 V7 摄影集合的六盏实际面光、主视相机和模型。右侧图像编辑器打开工程原存的 4K 主视觉，属性面板显示主灯的功率与尺寸。"
seen=[]
step=0
def status(x):
    print(x,flush=True)
    with (WORK/(MODE+".txt")).open("a",encoding="utf8") as f:f.write(str(x)+"\n")
def screen():return W.screen
def area_of(typ):
    return max((a for a in screen().areas if a.type==typ),key=lambda a:a.width*a.height)
def override(area):
    return bpy.context.temp_override(window=W,area=area,region=next(r for r in area.regions if r.type=="WINDOW"))
def refresh():
    for area in screen().areas:area.tag_redraw()
def select(ob):
    for o in bpy.context.selected_objects:o.select_set(False)
    if ob:
        ob.select_set(True)
        bpy.context.view_layer.objects.active=ob
def fold_outliner(active=None):
    ar=area_of("OUTLINER")
    with override(ar):
        for i in range(6):
            bpy.ops.outliner.show_one_level(open=False)
        bpy.ops.outliner.show_one_level(open=True)
        bpy.ops.outliner.show_one_level(open=True)
        if active:
            bpy.ops.outliner.show_active()
def visible_parts():
    col=bpy.data.collections.get("DJI Osmo Pocket 4P • exterior")
    if col: return {o for o in col.all_objects if o.type in {"MESH","FONT","CURVE"} and not o.hide_render}
    return {o for o in SC.objects if o.type in {"MESH","FONT","CURVE"} and not o.hide_render and not any(w in o.name.lower() for w in ("floor","stage","sweep","plane"))}
PARTS=visible_parts()
ORIG={o.name:o.hide_get() for o in SC.objects}
def configure(typ):
    global subject
    if typ!="early": SC.frame_set(95 if typ=="film" else 62)
    for o in SC.objects:
        o.hide_set(ORIG[o.name])
        if o.type in {"MESH","FONT","CURVE"}:
            o.show_wire=False
            if o not in PARTS:o.hide_set(True)
    ar=area_of("VIEW_3D");sp=ar.spaces.active
    sp.clip_start=.00025;sp.clip_end=5;sp.lens=48
    sp.show_region_ui=False;sp.show_region_toolbar=False
    sp.show_gizmo=True
    ov=sp.overlay;ov.show_overlays=True;ov.show_floor=False;ov.show_ortho_grid=False;ov.show_axis_x=False;ov.show_axis_y=False
    ov.show_cursor=False;ov.show_extras=False;ov.show_relationship_lines=False;ov.show_bones=False;ov.show_text=True
    ov.show_stats=False;ov.show_outline_selected=False
    sh=sp.shading;sh.type="SOLID";sh.light="STUDIO";sh.studio_light="paint.sl"
    sh.studiolight_rotate_z=.45;sh.color_type="SINGLE";sh.single_color=(.74,.76,.77)
    sh.show_cavity=True;sh.cavity_type="WORLD";sh.cavity_ridge_factor=.54;sh.cavity_valley_factor=.52
    sh.show_shadows=False;sh.show_object_outline=False;sh.show_specular_highlight=True
    sh.background_type="VIEWPORT";sh.background_color=(.055,.067,.080)
    SC.display.matcap_ssao_distance=.002
    direction=(.57,-1,.22); center=(0,0,.080); distance=.235
    subject=None
    prop=area_of("PROPERTIES");prop.spaces.active.context="SCENE"
    if typ=="early":
        sh.color_type="RANDOM"
        subject=next((o for o in PARTS if "housing" in o.name.lower() and "camera" in o.name.lower()),None)
    if typ=="clay":
        subject=bpy.data.objects.get("04P | Dual camera rear housing")
    if typ=="wire":
        direction=(.20,-1,.13);center=(0,-.006,.134);distance=.094
        for o in PARTS:
            if any(w in o.name.lower() for w in ("milled dual-pocket optical face","protector metal edge","satin collar","outer barrel lip","flat removable glass","rear housing","end cap")):
                o.show_wire=True
        subject=bpy.data.objects.get("04P | Milled dual-pocket optical face")
        prop.spaces.active.context="MODIFIER"
    if typ=="joints" or typ=="shader":
        direction=(-.95,1,.43);center=(0,.003,.128);distance=.095
        terms=("pan motor rotating collar","pan bearing journal","pan fixed flanged bushing","offset rising pan arm","roll motor stator","roll motor rotor flange","roll bearing spindle","rear roll bridge","tilt bearing spindle","tilt fixed flanged bushing","tilt support web","roll fixed flanged bushing","tilt motor end cap","roll motor face")
        for o in PARTS:
            if typ=="joints" and not any(term in o.name.lower() for term in terms):o.hide_set(True)
        subject=bpy.data.objects.get("04P | Offset rising pan arm")
        if typ=="joints":sh.color_type="RANDOM";prop.spaces.active.context="OBJECT"
    if typ=="film":
        subject=next(o for o in SC.objects if o.type=="ARMATURE")
        subject.hide_set(False)
        direction=(.25,-1,.1);center=(0,0,.092);distance=.235
    if typ=="studio":
        direction=(1,.42,.90);center=(.04,-.11,.132);distance=.65
        ov.show_extras=True;ov.show_floor=False;ov.show_object_origins=False
        sh.background_color=(.32,.345,.36)
        for o in SC.objects:
            if o.type in {"LIGHT","CAMERA","EMPTY","ARMATURE"}:
                on=(o.type=="LIGHT" and o.name.startswith("Studio V7 | ")) or o==SC.camera
                o.hide_set(not on)
                if on:
                    o.show_name=True
                    if o.type=="CAMERA":o.data.display_size=.045
        subject=SC.objects["Studio V7 | Key"]
        prop.spaces.active.context="DATA"
    select(subject)
    rv=sp.region_3d;rv.view_rotation=(-Vector(direction)).to_track_quat("-Z","Y")
    rv.view_location=Vector(center);rv.view_distance=distance;rv.view_perspective="ORTHO"
    fold_outliner(subject)
    if typ=="studio":
        SC.camera.select_set(True)
        with override(ar):bpy.ops.screen.area_split(direction="VERTICAL",factor=.62)
    if typ in ("shader","film"):
        # Use temporary splits, leaving the .blend and saved workspaces untouched.
        original={a.as_pointer() for a in screen().areas}
        with override(ar):bpy.ops.screen.area_split(direction="VERTICAL" if typ=="shader" else "HORIZONTAL",
                                                    factor=.48 if typ=="shader" else .33)
        candidates=[a for a in screen().areas if a.type=="VIEW_3D"]
        if typ=="shader":
            new=max(candidates,key=lambda x:x.x)
            new.type="NODE_EDITOR";new.ui_type="ShaderNodeTree"
            new.spaces.active.shader_type="OBJECT";new.spaces.active.show_region_ui=False
            new.spaces.active.show_region_toolbar=False
            prop.spaces.active.context="MATERIAL"
            layout={"UVMAP":(-710,110),"TEX_COORD":(-710,110),"TEX_IMAGE":(-460,110),
                    "NORMAL_MAP":(-190,110),"BSDF_PRINCIPLED":(65,250),"OUTPUT_MATERIAL":(365,250)}
            for n in subject.active_material.node_tree.nodes:
                if n.type in layout: n.location=layout[n.type]
        else:
            new=min(candidates,key=lambda x:x.y)
            new.type="DOPESHEET_EDITOR";new.ui_type="DOPESHEET"
            new.spaces.active.show_region_ui=False;new.spaces.active.show_markers=True
            new.spaces.active.mode="ACTION"
            new.spaces.active.dopesheet.show_only_selected=False
            if subject.animation_data and subject.animation_data.action:
                if hasattr(new.spaces.active,"action"):new.spaces.active.action=subject.animation_data.action
                status("TRACK "+repr((subject.name,subject.animation_data.action.name,subject.animation_data.action_slot)))
            for b in subject.data.bones:
                if hasattr(b,"select"):b.select=True
            prop.spaces.active.context="DATA"
    refresh()
def extra(typ):
    if typ=="studio":
        candidates=[a for a in screen().areas if a.type=="VIEW_3D"]
        img=max(candidates,key=lambda a:a.x)
        img.type="IMAGE_EDITOR"
        hero=SOURCE.parent/"renders/01-Hero.png"
        img.spaces.active.image=bpy.data.images.load(str(hero))
        img.spaces.active.show_region_ui=False
        img.spaces.active.show_region_toolbar=False
        def fit_native_image():
            with override(img):bpy.ops.image.view_all(fit_view=True)
            return None
        bpy.app.timers.register(fit_native_image,first_interval=.4)
    if typ=="shader":
        ar=area_of("NODE_EDITOR")
        with override(ar):bpy.ops.node.view_all()
    if typ=="film":
        ar=max([a for a in screen().areas if a.type=="DOPESHEET_EDITOR"], key=lambda a:a.height)
        with override(ar):
            for i in range(3):
                bpy.ops.anim.channels_expand(all=True)
            bpy.ops.action.view_all()
        a=area_of("VIEW_3D")
        a.spaces.active.region_3d.view_perspective="CAMERA"
        a.spaces.active.region_3d.view_camera_zoom=24
        SC.camera.data.show_passepartout=True
        SC.camera.data.passepartout_alpha=.88
    refresh()
def snap(typ):
    path=DEST/(FILES[typ]+".png")
    with bpy.context.temp_override(window=W):
        bpy.ops.screen.screenshot(filepath=str(path),check_existing=False)
    shot={"id":typ,"file":str(path.relative_to(ROOT)),"caption":CAPTIONS[typ],"frame":SC.frame_current,
          "source":str(SOURCE),"source_sha256":hashlib.sha256(SOURCE.read_bytes()).hexdigest(),"recaptured":True,
          "window_pixels":[W.width,W.height],"screenshot_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
          "scene":SC.name,"workspace":W.workspace.name,"app_version":bpy.app.version_string,
          "source_saved_during_capture":False,"capture_method":"bpy.ops.screen.screenshot (native window framebuffer; full Blender client area)",
          "active_object":subject.name if subject else None,"native_areas":[a.type for a in screen().areas]}
    seen.append(shot)
    if typ=="studio":
        image_path=SOURCE.parent/"renders/01-Hero.png"
        shot["paired_original_render"]=str(image_path)
        shot["paired_render_sha256"]=hashlib.sha256(image_path.read_bytes()).hexdigest()
        shot["photography_collection_objects"]={o.name:{"world_position_m":list(o.matrix_world.translation),
            "power_w":o.data.energy,"size_m":[o.data.size,o.data.size_y],"shape":o.data.shape} for o in SC.objects if o.type=="LIGHT" and o.name.startswith("Studio V7 | ")}
        shot["camera"]={"name":SC.camera.name,"world_position_m":list(SC.camera.matrix_world.translation),
                        "focal_length_mm":SC.camera.data.lens,"type":SC.camera.data.type,"ortho_scale_m":SC.camera.data.ortho_scale}
    (WORK/(MODE+".json")).write_text(json.dumps(seen,ensure_ascii=False,indent=2),encoding="utf8")
    status("OK "+path.name)
def tick():
    global step
    try:
        shots=STEPS[MODE]
        i=step//3;phase=step%3
        if i>=len(shots):
            bpy.ops.wm.quit_blender();return None
        typ=shots[i]
        if phase==0:
            status("configure "+typ)
            configure(typ)
        elif phase==1:extra(typ)
        else:snap(typ)
        step+=1
        return 2.1 if phase<2 else .45
    except Exception:
        status(traceback.format_exc())
        bpy.ops.wm.quit_blender()
        return None
status("OPEN "+str(SOURCE)+" "+str([(a.type,a.width,a.height) for a in screen().areas]))
bpy.app.timers.register(tick,first_interval=2)

