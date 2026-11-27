"""Blender-side worker. Invoke through render_batch.py."""

import json
from pathlib import Path
import struct
import sys

import bpy


def missing_sources():
    def missing(raw, owner):
        return not Path(bpy.path.abspath(raw, library=owner)).is_file()

    warnings = []
    for lib in bpy.data.libraries:
        if not getattr(lib, "packed_file", None) and missing(lib.filepath, lib.parent):
            warnings.append(f"Linked library: {lib.filepath}")
    for img in bpy.data.images:
        if img.users and img.source == "FILE" and img.filepath and not img.packed_files:
            if missing(img.filepath, img.library):
                warnings.append(f"Image {img.name}: {img.filepath}")
    return sorted(warnings)


def prepare_scene(job):
    if Path(bpy.data.filepath).resolve() != Path(job["blend"]):
        raise ValueError("Blender did not open the requested source")
    scene = bpy.data.scenes.get(job["scene"])
    if scene is None:
        raise ValueError(f"Scene {job['scene']!r} missing. Available: {list(bpy.data.scenes.keys())}")
    camera = scene.objects.get(job["camera"])
    if camera is None or camera.type != "CAMERA":
        cameras = [obj.name for obj in scene.objects if obj.type == "CAMERA"]
        raise ValueError(f"Camera {job['camera']!r} missing from scene {scene.name!r}. Available: {cameras}")
    bpy.context.window.scene = scene
    for marker in scene.timeline_markers:
        if marker.camera:
            marker.camera = None
    scene.camera = camera
    settings = scene.render
    settings.use_sequencer = False
    settings.use_multiview = False
    settings.use_border = False
    # Suppress secondary compositor writes; keep the actual composited beauty output.
    trees = list(bpy.data.node_groups)
    for other in bpy.data.scenes:
        old_tree = getattr(other, "node_tree", None)
        if old_tree:
            trees.append(old_tree)
    for tree in trees:
        if tree.bl_idname == "CompositorNodeTree":
            for node in tree.nodes:
                if node.type == "OUTPUT_FILE":
                    node.mute = True
    if "resolution" in job:
        settings.resolution_x, settings.resolution_y = job["resolution"]
        settings.resolution_percentage = 100
    if hasattr(settings.image_settings, "media_type"):
        settings.image_settings.media_type = "IMAGE"
    settings.image_settings.file_format = "PNG"
    settings.use_file_extension = True
    return scene, camera


def check_png(path, pixels):
    with path.open("rb") as stream:
        header = stream.read(24)
        stream.seek(-12, 2)
        last_chunk = stream.read()
    if (header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR"
            or struct.unpack(">II", header[16:24]) != tuple(pixels)
            or last_chunk != b"\x00\x00\x00\x00IEND\xaeB`\x82"):
        raise ValueError(f"Incomplete PNG or unexpected dimensions: {path}")


def process(request, work):
    job = request["job"]
    scene, camera = prepare_scene(job)
    first, last = job.get("range", [job.get("frame")] * 2)
    settings = scene.render
    pixels = [max(1, side * settings.resolution_percentage // 100)
              for side in (settings.resolution_x, settings.resolution_y)]
    details = {
        "ok": True, "blender": bpy.app.version_string, "engine": settings.engine,
        "source": job["blend"], "scene": scene.name, "camera": camera.name,
        "pixels": pixels, "range": [first, last], "frames": last - first + 1,
        "fps": settings.fps / settings.fps_base, "view_transform": scene.view_settings.view_transform,
        "missing_source_warnings": missing_sources(),
    }
    if request["mode"] == "check":
        return details
    images = work / "images"
    images.mkdir()
    for frame in range(first, last + 1):
        scene.frame_set(frame)
        scene.camera = camera
        name = "still.png" if "frame" in job else f"frame_{frame:06d}.png"
        path = images / name
        settings.filepath = str(path)
        result = bpy.ops.render.render(write_still=True, scene=scene.name)
        if "FINISHED" not in result:
            raise RuntimeError(f"Render did not finish on frame {frame}: {result}")
        check_png(path, pixels)
    return details


if __name__ == "__main__":
    request_path = Path(sys.argv[sys.argv.index("--") + 1])
    receipt = request_path.with_name("result.json")
    try:
        details = process(json.loads(request_path.read_text(encoding="utf-8")), request_path.parent)
    except Exception as exc:
        receipt.write_text(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), encoding="utf-8")
        raise
    receipt.write_text(json.dumps(details, ensure_ascii=False), encoding="utf-8")
