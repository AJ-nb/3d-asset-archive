"""Run in a new headless Blender process, started on the final V7 file."""
import datetime
import hashlib
import json
from pathlib import Path
import sys
import time

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


archive = Path(__file__).resolve().parent.parent
target = archive / "05_同机位补拍/V7终版对照"
target.mkdir(parents=True, exist_ok=True)
temp = Path(sys.argv[sys.argv.index("--") + 1])
temp.mkdir(parents=True, exist_ok=True)
src = Path(bpy.data.filepath)
assert src.name == "DJI-Osmo-Pocket-4P-V7-Final.blend"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def product_objects():
    def walk(collection):
        if collection.hide_render:
            return
        yield from collection.objects
        for child in collection.children:
            yield from walk(child)
    root = bpy.data.collections["DJI Osmo Pocket 4P • exterior"]
    return sorted({ob for ob in walk(root) if not ob.hide_render and ob.type in {"MESH", "CURVE", "FONT", "SURFACE"}},
                  key=lambda ob: ob.name)


def select_plate():
    sys.path.insert(0, str(src.parent / "studio"))
    import art_direction
    scene = art_direction.select("01-Hero")
    art_direction.configure_gpu(scene)
    scene.cycles.samples = 152
    scene.render.resolution_x, scene.render.resolution_y = 2160, 3840
    scene.render.resolution_percentage = 100
    assert scene.camera.data.sensor_fit == "VERTICAL" and scene.frame_current == 62
    return scene


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def render(scene, filename, method):
    path = target / filename
    scene.render.filepath = str(path)
    started = utc()
    instant = time.monotonic()
    print("RESHOOT START", filename, flush=True)
    bpy.ops.render.render(write_still=True)
    record = {"file": str(path.relative_to(archive)), "sha256": sha(path), "bytes": path.stat().st_size,
              "engine": scene.render.engine, "started_utc": started, "finished_utc": utc(),
              "elapsed_seconds": round(time.monotonic() - instant, 2), "method": method}
    print("RESHOOT COMPLETE", filename, flush=True)
    return record


if __name__ == "__main__":
    scene = select_plate()
    cam = scene.camera
    products = product_objects()
    scene.view_layers[0].use_pass_cryptomatte_object = False
    scene.view_layers[0].use_pass_normal = False
    scene.view_layers[0].use_pass_diffuse_color = False
    scene.view_layers[0].use_pass_z = False
    camera = {"object": cam.name, "lens_mm": cam.data.lens, "sensor_fit": cam.data.sensor_fit,
              "sensor_height_mm": cam.data.sensor_height, "sensor_width_mm": cam.data.sensor_width,
              "type": cam.data.type, "shift_xy": [cam.data.shift_x, cam.data.shift_y],
              "pixel_aspect_xy": [scene.render.pixel_aspect_x, scene.render.pixel_aspect_y],
              "matrix_world": [list(row) for row in cam.matrix_world], "dof": cam.data.dof.use_dof}
    anchors = {}
    for z in (.016, .052, .085, .115, .138, .150):
        co = Vector((0, 0, z))
        ndc = world_to_camera_view(scene, cam, co)
        anchors[str(z)] = [round(ndc.x * 2160, 4), round((1 - ndc.y) * 3840, 4)]
    meta = {"source_file": str(src), "source_sha256": sha(src), "blender": bpy.app.version_string,
            "frame": scene.frame_current, "native_resolution": [2160, 3840],
            "scene": scene.name, "camera": camera, "test_points_xyz_m": "x=y=0, z as key",
            "projected_test_points_pixels": anchors, "active_product_objects": len(products),
            "renderer": {"engine": scene.render.engine, "device": scene.cycles.device,
                         "device_names": [d.name for d in bpy.context.preferences.addons["cycles"].preferences.devices if d.use],
                         "samples": scene.cycles.samples, "adaptive_threshold": scene.cycles.adaptive_threshold,
                         "denoise": scene.cycles.use_denoising, "transform": scene.view_settings.view_transform,
                         "look": scene.view_settings.look, "exposure": scene.view_settings.exposure,
                         "gamma": scene.view_settings.gamma, "color_encoding": "16-bit RGB PNG"},
            "active_studio_lights": {o.name: {"energy": o.data.energy, "color": list(o.data.color)}
                                     for o in scene.objects if o.type == "LIGHT" and not o.hide_render},
            "plates": []}
    meta["plates"].append(render(scene, "03_整机成品.png", "V7 Final materials, original hero camera and light recipe."))
    (temp / "beauty-meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    material = bpy.data.materials.new("Neutral photographic clay")
    material.use_nodes = True
    shader = next(n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    shader.inputs["Base Color"].default_value = (.63, .65, .66, 1)
    shader.inputs["Roughness"].default_value = .60
    for ob in products:
        if not ob.material_slots:
            ob.data.materials.append(material)
        else:
            for slot in ob.material_slots:
                slot.link = "OBJECT"
                slot.material = material
    meta["plates"].append(render(scene, "01_整机白模.png",
                                "All renderable product material slots overridden with a single neutral clay; original studio sweep, lights, camera, rig and pose."))
    meta["clay_linear_rgb"] = [.63, .65, .66]
    meta["clay_roughness"] = .60
    assert sha(src) == meta["source_sha256"]
    (temp / "render-meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
