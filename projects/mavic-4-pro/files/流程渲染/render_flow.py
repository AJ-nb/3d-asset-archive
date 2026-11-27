"""Re-render the archived blockout and the final model at one orthographic gate."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/"复现脚本"))
import studio

SOURCES={
    "layout":(
        "mavic-4-pro/review/layout.blend",
        "源工程与记录/01-预演/layout.blend",
        "26061777349f0df24000f8933e90ea4e29fca412691277c7f39cc859e6346168",
    ),
    "final":(
        "mavic-4-pro-fit-work/rear-shoulder/Mavic-4-Pro-Rear-Fit-Final.blend",
        "源工程与记录/05-后肩修订/Mavic-4-Pro-Rear-Fit-Final.blend",
        "57b641958dae8172326e534ede99674fdff11af6f9df332058352f71fc6e3463",
    ),
}

def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()

parser=argparse.ArgumentParser()
parser.add_argument("phase", choices=("layout","final"))
parser.add_argument("--manifest-only", action="store_true", help="Audit camera and hash images previously rendered by this script")
option=parser.parse_args(sys.argv[sys.argv.index("--")+1:])
scene=bpy.context.scene
native=Path(bpy.data.filepath)
source_path,archive_path,expected_hash=SOURCES[option.phase]
source_hash=sha(native)
if source_hash != expected_hash:
    raise ValueError(f"Wrong Blender source for {option.phase}: {native}")
root=bpy.data.objects[studio.ROOT]
frame=32 if option.phase=="layout" else 1
if option.phase=="final":
    studio.configure("06-motion")
else:
    for o in bpy.data.objects:
        if o.type=="FONT":
            o.hide_render=True
    for c in bpy.data.collections:
        if c.name.startswith("07  /"):
            c.hide_render=True

try:
    studio.device()
except (RuntimeError, TypeError):
    scene.cycles.device="CPU"
scene.frame_set(frame)
camera=bpy.data.objects.new("Flow orthographic",bpy.data.cameras.new("Flow orthographic"))
scene.collection.objects.link(camera)
target=(0,-8,64)
offset=(355,-690,386)
camera.location=root.matrix_world @ (Vector(target)+Vector(offset))
studio.lookat(camera,root.matrix_world @ Vector(target))
camera.data.type="ORTHO"
camera.data.ortho_scale=.699
camera.data.clip_start=.001
camera.data.clip_end=20
scene.camera=camera
scene.render.engine="CYCLES"
scene.render.use_sequencer=False
scene.render.use_persistent_data=True
scene.render.use_compositing=False
scene.render.film_transparent=False
scene.render.image_settings.media_type="IMAGE"
scene.render.image_settings.file_format="PNG"
scene.render.image_settings.color_mode="RGB"
scene.render.image_settings.color_depth="8"
scene.render.resolution_x,scene.render.resolution_y=3840,2160
scene.render.resolution_percentage=100
scene.cycles.use_denoising=True
scene.cycles.samples=112
scene.cycles.adaptive_threshold=.018

def product_bounds():
    bpy.context.view_layer.update()
    graph=bpy.context.evaluated_depsgraph_get()
    inv=np.array(camera.matrix_world.inverted())
    frame_shape=np.array(camera.data.view_frame(scene=scene))[:,:2]
    span=np.ptp(frame_shape,axis=0)
    points=[]
    for piece in root.children_recursive:
        if piece.type not in {"MESH","FONT","CURVE","SURFACE"} or piece.hide_render:
            continue
        obj=piece.evaluated_get(graph)
        mesh=obj.to_mesh()
        vertices=np.empty(len(mesh.vertices)*3,dtype="f")
        mesh.vertices.foreach_get("co",vertices)
        transform=inv @ np.array(obj.matrix_world)
        xy=(vertices.reshape(-1,3) @ transform[:2,:3].T + transform[:2,3])/span+.5
        if len(xy):
            points += [xy.min(axis=0),xy.max(axis=0)]
        obj.to_mesh_clear()
    points=np.array(points)
    lo,hi=points.min(axis=0),points.max(axis=0)
    assert ((lo>.03)&(hi<.97)).all(),(lo,hi)
    return [float(x) for x in (*lo,*hi)]

def white_material():
    clay=bpy.data.materials.new("Flow | interchangeable satin clay")
    clay.use_nodes=True
    surface=clay.node_tree.nodes.get("Principled BSDF")
    surface.inputs["Base Color"].default_value=(.71,.72,.73,1)
    surface.inputs["Roughness"].default_value=.49
    surface.inputs["Specular IOR Level"].default_value=.27
    for piece in root.children_recursive:
        if piece.type not in {"MESH","FONT","CURVE","SURFACE"} or piece.hide_render:
            continue
        if not piece.material_slots:
            piece.data.materials.append(clay)
        for slot in piece.material_slots:
            slot.link="OBJECT"
            slot.material=clay

bounds=product_bounds()
meta={
    "source_path":source_path,
    "archive_path":archive_path,
    "source_sha256":source_hash,
    "camera_orbit_vector_mm":offset,
    "camera_target_mm":target,
    "world_camera_matrix":[list(row) for row in camera.matrix_world],
    "ortho_span_mm":camera.data.ortho_scale*1000,
    "resolution":[3840,2160],
    "frame":frame,
    "scene":scene.name,
    "blender_version":bpy.app.version_string,
    "bounds_normalized_lower_upper_xy":bounds,
    "engine":scene.render.engine,
    "device":scene.cycles.device,
    "sample_limit":scene.cycles.samples,
    "outputs":{}
}
def record(stem,method):
    path=HERE/(stem+".png")
    if not option.manifest_only:
        scene.render.filepath=str(path)
        bpy.ops.render.render(write_still=True)
    meta["outputs"][path.name]={"sha256":sha(path),"method":method}

if option.phase=="layout":
    record("01-基础体块-补绘","Re-rendered archived layout.blend blockout. Archived materials and lighting.")
else:
    record("03-材质灯光-4K补渲","Cycles product render from the final assembly with native materials and studio lighting.")
    white_material()
    record("02-白模-补绘","The same final assembly, camera and lighting with a uniform clay material.")
(HERE/(option.phase+"-source.json")).write_text(json.dumps(meta,ensure_ascii=False,indent=2),"utf8")
