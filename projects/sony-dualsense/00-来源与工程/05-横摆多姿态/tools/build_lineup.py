"""Build a single-camera study of three DualSense assemblies on a common floor."""

import argparse
from math import radians
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Euler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_studio import (
    PARTS, camera_rig, collection, floor_stage, set_area, setup_scene, shot_scene,
    studio_world,
)

SIZE = (4800, 1540)
TITLE = "Horizontal | Three resting poses"


def assembly_points(product):
    clouds = []
    for part in product.all_objects:
        if part.type == "MESH":
            coords = np.empty(len(part.data.vertices) * 3, dtype=np.float32)
            part.data.vertices.foreach_get("co", coords)
            matrix = np.array(part.matrix_world)
            clouds.append(coords.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3])
    return np.concatenate(clouds) - np.array(product.instance_offset)


def rest_pose(poses, product, points, name, pitch, yaw, x):
    instance = bpy.data.objects.new(name, None)
    poses.objects.link(instance)
    instance.instance_type = "COLLECTION"
    instance.instance_collection = product
    instance.empty_display_type = "PLAIN_AXES"
    instance.empty_display_size = .24
    instance.rotation_euler = Euler((radians(pitch), 0, radians(yaw)), "XYZ")
    transformed = points @ np.array(instance.rotation_euler.to_matrix()).T
    lo, hi = transformed.min(axis=0), transformed.max(axis=0)
    instance.location = (
        x - .5 * (lo[0] + hi[0]), -.5 * (lo[1] + hi[1]), -.0003 - lo[2],
    )
    instance["Placement"] = "Lowest mesh vertex on common cyclorama surface"
    print(f"POSE {name} | {pitch:.3f} / {yaw:.1f} deg | "
          f"{np.round(hi-lo, 4)} | ground Z {lo[2] + instance.location.z:.6f}")


def create(source):
    product = bpy.data.collections[PARTS]
    scene = shot_scene(source, TITLE, product, "DualSense-Horizontal-Lineup", SIZE)
    scene.collection.children.unlink(product)
    scene.compositing_node_group = None
    scene.world = studio_world(source)
    scene.world.name = "Lineup | Ambient graphite studio"
    world = next(node for node in scene.world.node_tree.nodes if node.type == "BACKGROUND")
    world.inputs["Color"].default_value = (.62, .69, .78, 1)
    world.inputs["Strength"].default_value = .14
    scene.view_settings.exposure = .04
    floor_stage(source, scene, "Lineup | Blue graphite seamless", (.025, .034, .044), .53)
    poses = collection(scene, "Lineup | Three editable placements")
    points = assembly_points(product)
    # Pitch comes from the common tangent joining two support regions in the
    # original assembly's longitudinal section. Yaw leaves these contacts intact.
    rest_pose(poses, product, points, "A | Face-up, control surface", -96.719, -19, -3.93)
    rest_pose(poses, product, points, "B | Shoulder and charging port", -96.719, 153, 0)
    rest_pose(poses, product, points, "C | Turned over, underside", 48.058, 154, 3.93)
    camera, _ = camera_rig(scene, "Lineup | Parallel studio camera",
                           (0, 0, .72), 0, 36, 14, 90)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 12.57
    camera.data.clip_end = 100
    lights = collection(scene, "Lineup | Silks and reflection cards")
    for specs in (
        ("Lineup | Main overhead silk", (-5.5, -4.5, 6.5), (-.6, .12, .2),
         940, 6.0, 3.2, (1, .968, .917)),
        ("Lineup | Broad camera bounce", (1.35, -6.1, 3.2), (0, -.05, .6),
         177, 6.2, 2.9, (.85, .93, 1)),
        ("Lineup | Silhouette horizon strip", (4.15, 3.85, 3.1), (1.15, .1, .4),
         390, 3.8, .76, (.76, .895, 1)),
        ("Lineup | Grip contour silk", (6.3, -.65, 4.3), (3.6, .2, .65),
         208, 1.3, 3.1, (.99, .94, .84)),
        ("Lineup | Lens-side keycap card", (-5.8, -2.1, 3.0), (-3.65, -.2, .72),
         78, .46, 2.5, (.945, .97, 1)),
        ("Lineup | Backdrop gradient", (-6.5, 4.7, 2.15), (-4.6, 4.35, .05),
         100, 2.8, 1.25, (.57, .77, 1)),
    ):
        set_area(lights, *specs)
    setup_scene(scene, 192)
    scene.cycles.adaptive_threshold = .010
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "16"
    scene.render.image_settings.compression = 40
    scene.render.filepath = "//DualSense-Horizontal-Lineup.png"
    bpy.context.window.scene = scene
    for screen in bpy.data.screens:
        for viewport in (area for area in screen.areas if area.type == "VIEW_3D"):
            viewport.spaces.active.region_3d.view_perspective = "CAMERA"
            viewport.spaces.active.region_3d.view_camera_zoom = 0
    return scene


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blend", type=Path)
    parser.add_argument("--render", type=Path)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--optix", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    for target in (args.blend, args.render):
        if target:
            if target.exists():
                raise FileExistsError(target)
            target.parent.mkdir(parents=True, exist_ok=True)
    scene = bpy.data.scenes.get(TITLE) or create(bpy.data.scenes["DualSense White"])
    bpy.context.window.scene = scene
    if args.blend:
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=str(args.blend.resolve()), relative_remap=False)
    if args.render:
        if args.optix:
            prefs = bpy.context.preferences.addons["cycles"].preferences
            prefs.compute_device_type = "OPTIX"
            prefs.refresh_devices()
            for device in prefs.devices:
                device.use = device.type == "OPTIX"
            if not any(device.use for device in prefs.devices):
                raise RuntimeError("No usable OptiX device")
            scene.cycles.device = "GPU"
        if args.preview:
            scene.render.resolution_percentage = 29
            scene.cycles.adaptive_min_samples = 8
            scene.cycles.adaptive_threshold = .045
            scene.cycles.samples = 36
        scene.render.filepath = str(args.render.resolve())
        if bpy.ops.render.render(write_still=True) != {"FINISHED"}:
            raise RuntimeError("Blender render failed")


if __name__ == "__main__":
    main()
