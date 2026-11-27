"""Open the finished controller, choreograph two shots, and save a new .blend."""

import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def camera_key(camera, frame, position, target, width):
    camera.location = position
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = width
    camera.keyframe_insert(data_path="location", frame=frame)
    camera.keyframe_insert(data_path="rotation_euler", frame=frame)
    camera.data.keyframe_insert(data_path="ortho_scale", frame=frame)


def build(source, target):
    if source.suffix.lower() != ".blend" or not source.is_file():
        raise ValueError(f"Expected a finished controller .blend: {source}")
    if target.exists() or target.suffix.lower() != ".blend":
        raise ValueError(f"Supply a new .blend output path: {target}")

    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.data.scenes["Studio"]
    bpy.context.window.scene = scene
    scene.name = "Volume control"
    scene.frame_start, scene.frame_end = 1, 72
    scene.render.fps, scene.render.fps_base = 24, 1.0
    scene.render.resolution_x, scene.render.resolution_y = 640, 360
    scene.render.resolution_percentage = 100
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 12
    scene.cycles.seed = 5
    scene.cycles.use_animated_seed = False
    scene.cycles.use_denoising = True
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 8
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "BEZIER"

    reveal = scene.objects["Hero"]
    reveal.name = "Reveal"
    camera_key(reveal, 1, (3.1, -5.6, 2.32), (0, 0, 0.29), 4.80)
    camera_key(reveal, 32, (2.00, -5.35, 3.46), (-0.035, 0, 0.31), 4.44)

    macro = scene.objects["Detail"]
    macro.name = "Dial macro"
    camera_key(macro, 33, (-1.76, -4.43, 4.16), (-0.55, 0, 0.51), 2.65)
    camera_key(macro, 72, (-1.19, -4.40, 4.38), (-0.53, 0.02, 0.53), 2.48)

    dial = scene.objects["Dial"]
    dial.animation_data_clear()
    for frame, degrees in ((1, 95), (35, 95), (69, -71), (72, -71)):
        dial.rotation_euler.z = math.radians(degrees)
        dial.keyframe_insert(data_path="rotation_euler", index=2, frame=frame)

    for marker in list(scene.timeline_markers):
        scene.timeline_markers.remove(marker)
    for frame, camera in ((1, reveal), (33, macro)):
        scene.timeline_markers.new(camera.name, frame=frame).camera = camera
    scene.camera = reveal
    scene.frame_set(1)
    target.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target), compress=True)


if __name__ == "__main__":
    source_path, output_path = sys.argv[sys.argv.index("--") + 1:]
    build(Path(source_path).resolve(), Path(output_path).resolve())
