"""Blender -b --factory-startup --python-exit-code 1 -P replay_v1.py

Replay the unmodified V1 construction functions from their verified archival copy.
No existing Blender project is opened. Writes only under this archive.
"""
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import bpy
from mathutils import Vector

PROVENANCE = Path(__file__).resolve().parent
ARCHIVE = PROVENANCE.parent
OUT = ARCHIVE / "05_同机位补拍" / "V1起模复演"
SOURCE = PROVENANCE / "同期依据" / "V1" / "build_pocket.py"
SOURCE_SHA = "a9441a6ffd0dcc405d522a7784ed8ba34f5448c26d77949f90aeb870e1f24105"
RECEIPT = PROVENANCE / "replay-v1.json"
state = SimpleNamespace(model=None, guides=None)
stages = []
CAMERA_OFFSET = (0.145, -0.29, 0.105)
TARGET = (0, 0, 0.051)
SCALE = 0.143


def sha(file):
    with file.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def guides_and_camera(scene):
    guide = bpy.data.collections.new("Replay presentation | 10 mm coordinate grid")
    scene.collection.children.link(guide)
    def curves(name, lines, radius, color):
        data = bpy.data.curves.new(name, "CURVE")
        data.dimensions = "3D"
        data.bevel_depth = radius
        data.resolution_u = 1
        data.bevel_resolution = 1
        for start, end in lines:
            spline = data.splines.new("POLY")
            spline.points.add(1)
            spline.points[0].co = (*start, 1)
            spline.points[1].co = (*end, 1)
        obj = bpy.data.objects.new(name, data)
        obj.color = (*color, 1)
        guide.objects.link(obj)
    half = 0.095
    lines = []
    for n in range(-9,10):
        if n:
            t = n * 0.01
            lines.extend([((t,-half,-0.0003),(t,half,-0.0003)),((-half,t,-0.0003),(half,t,-0.0003))])
    curves("10 mm floor grid", lines, 0.000075, (0.12,0.16,0.20))
    curves("X", [((-half,0,-.0002),(half,0,-.0002))], .00014, (.42,.18,.13))
    curves("Y", [((0,-half,-.0002),(0,half,-.0002))], .00014, (.13,.34,.24))
    curves("Z", [((0,0,0),(0,0,.104))], .00014, (.15,.31,.51))
    ticks = [((-.0013,0,n*.01),(.0013,0,n*.01)) for n in range(1,11)]
    curves("10 mm height graduation", ticks, .00012, (.22,.37,.52))
    cam_data = bpy.data.cameras.new("Replay orthographic")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = SCALE
    cam_data.clip_start = .001
    cam_data.clip_end = 3
    camera = bpy.data.objects.new("Replay orthographic",cam_data)
    guide.objects.link(camera)
    camera.location = Vector(TARGET) + Vector(CAMERA_OFFSET)
    camera.rotation_euler = (-Vector(CAMERA_OFFSET)).to_track_quat("-Z","Y").to_euler()
    scene.camera = camera
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.film_transparent = False
    scene.display.render_aa = "32"
    shade = scene.display.shading
    shade.light = "STUDIO"
    shade.studio_light = "paint.sl"
    shade.color_type = "OBJECT"
    shade.background_type = "VIEWPORT"
    shade.background_color = (.048,.063,.079)
    world = bpy.data.worlds.new("Replay backdrop")
    world.color = (.048,.063,.079)
    scene.world = world
    shade.show_shadows = True
    shade.show_cavity = True
    shade.cavity_type = 'WORLD'
    shade.cavity_ridge_factor = .75
    shade.cavity_valley_factor = .8
    scene.view_settings.view_transform = "Standard"
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 1500
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    state.guides = guide


def capture(key, title, source_line):
    scene = bpy.context.scene
    product = [] if state.model is None else [obj for obj in state.model.all_objects
        if obj.type in {"MESH","CURVE","FONT"} and not obj.hide_render
        and not any(c.hide_render for c in obj.users_collection)]
    product.sort(key=lambda x:x.name)
    shell_color = (.52,.55,.59,1)
    for obj in product:
        color = shell_color
        if "OLED active" in obj.name: color = (.27,.32,.37,1)
        elif "cover" in obj.name and obj.name.startswith("Display"): color = (.40,.44,.49,1)
        elif "gasket" in obj.name: color = (.34,.37,.40,1)
        obj.color = color
    bpy.context.view_layer.update()
    dep = bpy.context.evaluated_depsgraph_get()
    n_tris = 0
    samples = []
    for obj in product:
        evaluated = obj.evaluated_get(dep)
        geo = evaluated.to_mesh()
        if geo:
            geo.calc_loop_triangles()
            n_tris += len(geo.loop_triangles)
            samples.extend(evaluated.matrix_world @ v.co for v in geo.vertices)
            evaluated.to_mesh_clear()
    bounds = [[round(f(v[i] for v in samples)*1000,4) for i in range(3)] for f in (min,max)] if samples else []
    target = OUT / (key + ".png")
    scene.render.filepath = str(target)
    bpy.ops.render.render(write_still=True)
    stages.append(dict(stage=key, title=title, file=target.relative_to(ARCHIVE).as_posix(),
        sha256=sha(target), pixels=[1200,1500], source_line=source_line, visible_parts=len(product),
        evaluated_triangles=n_tris, world_bounds_min_max_mm=bounds, part_names=[o.name for o in product]))


def main():
    if sha(SOURCE) != SOURCE_SHA:
        raise RuntimeError("The archived V1 source differs from the verified original.")
    OUT.mkdir(parents=True,exist_ok=True)
    tree = ast.parse(SOURCE.read_bytes(), filename=str(SOURCE))
    native = {"__file__":str(SOURCE),"__name__":"readonly_archived_v1"}
    exec(compile(tree,str(SOURCE),"exec"),native)
    original_main = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="main")
    reset = next(i for i,n in enumerate(original_main.body) if "read_factory_settings" in ast.unparse(n))
    stop = next(i for i,n in enumerate(original_main.body) if isinstance(n,ast.Assign) and isinstance(n.value,ast.Call) and getattr(n.value.func,"id",None)=="build_body")
    # Execute exactly the original reset, then capture the before-product state.
    def run(statements):
        exec(compile(ast.Module(body=statements,type_ignores=[]),str(SOURCE),"exec"), native)
    run([original_main.body[reset]])
    empty_objects = len(bpy.data.objects)
    if empty_objects != 0: raise ValueError("Expected the original factory-empty state")
    guides_and_camera(bpy.context.scene)
    capture("01_空场景", "空场景与世界坐标", original_main.body[reset].lineno)
    run(original_main.body[reset+1:stop])
    state.model = native["model"]
    loft = native["loft"]
    # Capture the returned result of the genuine V1 loft, before any booleans or plates.
    def capture_loft(name, *args, **kwargs):
        obj = loft(name,*args,**kwargs)
        if name == "Handle • molded upper shell":
            capture("02_握把主壳放样", "握把主壳完成首次放样", source_lines["shell"])
        return obj
    native["loft"] = capture_loft
    run([original_main.body[stop]])
    capture("03_机身与横屏组件", "机身、操控件及横屏完成，云台尚未生成", source_lines["body"])
    counts = [p["visible_parts"] for p in stages]
    if len(stages)!=3 or counts[:2]!=[0,1] or counts[2]<10: raise RuntimeError(f"Unexpected stages {counts}")
    if not any("OLED active" in s for s in stages[2]["part_names"]): raise RuntimeError("Missing screen stage")
    receipt=dict(type="本次依 V1 原脚本复演",created_for_archive=True, historical_screenshot=False,
        source_file=SOURCE.relative_to(ARCHIVE).as_posix(),source_sha256=SOURCE_SHA,
        original_source="D:/oc/output/dji-osmo-pocket-4p/build_pocket.py",
        blender=bpy.app.version_string,factory_empty_object_count=empty_objects,
        process="原文件哈希锁定。仅执行 main 的空场景初始化及 build_body，拦截首次主壳放样返回时的场景；不载入已有 .blend，不调用原脚本的写出、渲染及保存分支。",
        methods=dict(presentation="本次增加固定的 Workbench 正交相机、10 mm 坐标网与中性显示色。坐标线及相机从产品零件统计排除。",orthographic_scale_m=SCALE,camera_offset_m=CAMERA_OFFSET,aim_point_m=TARGET),
        script=Path(__file__).relative_to(ARCHIVE).as_posix(), stages=stages)
    RECEIPT.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf8")


source_text = SOURCE.read_text(encoding="utf8").splitlines()
source_lines = {
    "shell": next(i for i,v in enumerate(source_text,1) if 'main = loft("Handle • molded upper shell"' in v),
    "body": next(i for i,v in enumerate(source_text,1) if "body = build_body(root,model,cutters)" in v)}
main()
