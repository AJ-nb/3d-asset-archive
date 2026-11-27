"""Validate the DualSense handoff and render one named camera to a new PNG."""

import argparse
import os
from pathlib import Path
import re
import struct
import sys
from tempfile import TemporaryDirectory

import bpy
from mathutils import Matrix


SCENES = {"dualsense-white": "DualSense White", "white-clay": "White Clay"}
SIZE = (3840, 2160)
SOURCE_COLLECTION = "Controller | Original FBX geometry"
CLAY_COLLECTION = "Controller | Linked white clay"
PNG_HEADER = b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def verify_project():
    source = tuple(bpy.data.collections[SOURCE_COLLECTION].objects)
    clay = tuple(bpy.data.collections[CLAY_COLLECTION].objects)
    require(len(source) == len(clay) == 12, "Expected twelve controller parts in each scene.")
    require({obj.data for obj in source} == {obj.data for obj in clay},
            "The clay scene must share the original controller meshes.")
    require(sum(len(obj.data.vertices) for obj in source) == 480763
            and sum(len(obj.data.polygons) for obj in source) == 452132,
            "Controller mesh counts changed from the approved source.")
    require(all(slot.link == "OBJECT" and slot.material is not None
                and slot.material.name.startswith("Clay |")
                for obj in clay for slot in obj.material_slots),
            "Clay materials must be object overrides.")
    require(bpy.data.images["grip-symbol-height.png"].packed_file is not None,
            "The grip height map must be packed.")

    indexed_scenes = {}
    identity = Matrix.Identity(4)
    for scene_key, scene_name in SCENES.items():
        scene = bpy.data.scenes[scene_name]
        bpy.context.window.scene = scene
        render = scene.render
        image = render.image_settings
        require(render.engine == "CYCLES", f"{scene_name}: expected Cycles.")
        require((render.resolution_x, render.resolution_y) == SIZE
                and render.resolution_percentage == 100,
                f"{scene_name}: expected native UHD settings.")
        require((image.file_format, image.color_mode, image.color_depth) == ("PNG", "RGB", "16"),
                f"{scene_name}: expected 16-bit RGB PNG.")

        stage = scene.objects["Cyclorama | continuous slate floor"]
        faces = stage.data.polygons
        floor_face = min(faces, key=lambda face: face.center.z)
        wall_face = max(faces, key=lambda face: face.center.z)
        require(floor_face.normal.z > 0.99 and wall_face.normal.dot(-wall_face.center) > 0,
                f"{scene_name}: cyclorama normals must face the stage interior.")

        shots = {}
        frames = set()
        parts = source if scene_key == "dualsense-white" else clay
        for marker in sorted(scene.timeline_markers, key=lambda item: item.frame):
            camera = marker.camera
            require(camera is not None, f"{scene_name}: no camera on marker {marker.name}.")
            shot, delimiter, _ = camera.name.partition(" | ")
            require(delimiter and re.fullmatch(r"[0-9]{2}-[a-z0-9]+(?:-[a-z0-9]+)*", shot),
                    f"{scene_name}: invalid camera name {camera.name}.")
            require(shot not in shots and marker.frame not in frames,
                    f"{scene_name}: repeated camera slug or marker frame {shot}.")
            scene.frame_set(marker.frame)
            require(scene.camera == camera, f"{scene_name}: wrong camera at frame {marker.frame}.")
            graph = bpy.context.evaluated_depsgraph_get()
            for obj in parts:
                require(scene.objects.get(obj.name) == obj
                        and obj.animation_data is None
                        and obj.evaluated_get(graph).matrix_world == identity,
                        f"{scene_name}, {shot}: baked transform changed on {obj.name}.")
            shots[shot] = marker
            frames.add(marker.frame)
        require(len(shots) >= 6, f"{scene_name}: expected at least six named camera markers.")
        indexed_scenes[scene_key] = (scene, shots)
    return indexed_scenes


def render_shot(scene, marker, target, preview, device):
    if target.exists():
        raise FileExistsError(f"Output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)

    bpy.context.window.scene = scene
    scene.frame_set(marker.frame)
    require(scene.camera == marker.camera, f"Camera binding changed at frame {marker.frame}.")
    scene.cycles.device = "CPU"
    if device == "optix":
        preferences = bpy.context.preferences.addons["cycles"].preferences
        preferences.compute_device_type = "OPTIX"
        preferences.refresh_devices()
        for entry in preferences.devices:
            entry.use = entry.type == "OPTIX"
        require(any(entry.use for entry in preferences.devices), "No OptiX device found.")
        scene.cycles.device = "GPU"

    size = SIZE
    if preview:
        scene.render.resolution_percentage = 50
        scene.cycles.samples = min(scene.cycles.samples, 64)
        size = (SIZE[0] // 2, SIZE[1] // 2)

    print(f"RENDER {scene.name} / {scene.camera.name} / frame {scene.frame_current}", flush=True)
    with TemporaryDirectory(prefix=".dualsense-", dir=target.parent) as work:
        image = Path(work) / target.name
        scene.render.filepath = str(image)
        scene.render.use_file_extension = True
        require(bpy.ops.render.render(write_still=True) == {"FINISHED"}, "Blender render failed.")
        with image.open("rb") as stream:
            require(stream.read(len(PNG_HEADER)) == PNG_HEADER, "Invalid render PNG header.")
            width, height, depth, color_type = struct.unpack(">IIBB", stream.read(10))
        require((width, height) == size and (depth, color_type) == (16, 2),
                f"Unexpected PNG format: {width}x{height}, depth {depth}, type {color_type}.")
        # Publish only the complete image. Both operations fail if another render won the path.
        if os.name == "nt":
            os.rename(image, target)
        else:
            os.link(image, target)
    print(f"PASS {width}x{height} RGB16 {target}", flush=True)


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Validate the project and list cameras.")
    mode.add_argument("--shot", help="Camera slug from --check, for example 06-grip.")
    parser.add_argument("--scene", choices=SCENES, default="dualsense-white")
    parser.add_argument("--output-dir", type=Path, help="Directory for the new PNG.")
    parser.add_argument("--preview", action="store_true", help="Use 1920x1080 and up to 64 samples.")
    parser.add_argument("--device", choices=("cpu", "optix"), default="cpu")
    options = parser.parse_args(args)
    if options.shot and options.output_dir is None:
        parser.error("--output-dir is required when rendering a shot.")

    indexed_scenes = verify_project()
    if options.check:
        for scene_key, (_, shots) in indexed_scenes.items():
            listing = ", ".join(f"{shot} ({marker.frame})" for shot, marker in shots.items())
            print(f"PASS {scene_key}: {listing}")
        return

    scene, shots = indexed_scenes[options.scene]
    if options.shot not in shots:
        parser.error(f"Unknown shot {options.shot!r} in {options.scene}. Use --check to list cameras.")
    suffix = "-preview" if options.preview else ""
    target = options.output_dir.resolve() / f"{options.scene}-{options.shot}{suffix}.png"
    render_shot(scene, shots[options.shot], target, options.preview, options.device)


if __name__ == "__main__":
    main()
