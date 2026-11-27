"""Blender-side worker. Invoke through render_batch.py."""

from array import array
import hashlib
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


def connected_assets(outputs):
    """Walk links feeding the selected output, including the used sockets of groups."""
    pending = [(socket, ()) for node in outputs for socket in node.inputs if socket.is_linked]
    visited = set()
    while pending:
        socket, groups = pending.pop()
        state = (socket, groups)
        if state in visited:
            continue
        visited.add(state)
        for link in socket.links:
            if not link.is_valid or link.is_muted:
                continue
            node, output = link.from_node, link.from_socket
            if node.mute:
                pending.extend((item.from_socket, groups) for item in node.internal_links if item.to_socket == output)
            elif node.type == "GROUP" and node.node_tree:
                yield node.node_tree
                for inner in node.node_tree.nodes:
                    if inner.type == "GROUP_OUTPUT" and inner.is_active_output:
                        pending.extend((pin, groups + (node,)) for pin in inner.inputs if pin.identifier == output.identifier)
            elif node.type == "GROUP_INPUT" and groups:
                pending.extend((pin, groups[:-1]) for pin in groups[-1].inputs if pin.identifier == output.identifier)
            else:
                if getattr(node, "image", None):
                    yield node.image
                pending.extend((pin, groups) for pin in node.inputs if pin.is_linked)


def render_members(layer_collection, instances=None):
    """Include render-enabled collection instances and honor per-layer exclusions."""
    collection = instances or layer_collection.collection
    if collection.hide_render or (instances is None and layer_collection.exclude):
        return
    yield collection
    for obj in collection.objects:
        if not obj.hide_render:
            yield obj
            if obj.instance_type == "COLLECTION" and obj.instance_collection:
                yield from render_members(None, obj.instance_collection)
    if instances is None:
        for child in layer_collection.children:
            yield from render_members(child)
    else:
        for child in collection.children:
            yield from render_members(None, child)


def assigned_materials(obj):
    slots = obj.material_slots
    if obj.type == "MESH" and len(slots) > 1 and not any(mod.show_render for mod in obj.modifiers):
        indices = array("i", [0]) * len(obj.data.polygons)
        obj.data.polygons.foreach_get("material_index", indices)
        return {slots[index].material for index in set(indices) if index < len(slots) and slots[index].material}
    return {slot.material for slot in slots if slot.material}


def shot_assets(scene):
    """Find file-backed IDs on supported material, light, world and compositor paths."""
    owners = set()
    for layer in scene.view_layers:
        if not layer.use:
            continue
        world = getattr(layer, "world_override", None) or scene.world
        if world:
            owners.add(world)
        for obj in set(render_members(layer.layer_collection)):
            yield obj
            if not isinstance(obj, bpy.types.Object):
                continue
            if obj.data:
                yield obj.data
            if obj.type == "LIGHT":
                owners.add(obj.data)
            if layer.material_override and obj.material_slots:
                owners.add(layer.material_override)
            else:
                owners.update(assigned_materials(obj))
    target = {"CYCLES": "CYCLES", "BLENDER_EEVEE": "EEVEE", "BLENDER_EEVEE_NEXT": "EEVEE"}.get(scene.render.engine, "ALL")
    for owner in owners:
        yield owner
        tree = owner.node_tree
        if tree and getattr(owner, "use_nodes", True):
            output = tree.get_output_node(target)
            if output:
                yield from connected_assets([output])
    tree = getattr(scene, "compositing_node_group", None) or getattr(scene, "node_tree", None)
    if tree and scene.render.use_compositing and getattr(scene, "use_nodes", True):
        outputs = [node for node in tree.nodes if node.type in {"COMPOSITE", "GROUP_OUTPUT"}
                   and getattr(node, "is_active_output", True)]
        yield from connected_assets(outputs)


class Dependencies:
    def __init__(self):
        self.files = {}
        self.stamps = {}

    def add(self, path, reference, frame):
        path = Path(path).resolve()
        entry = self.files.get(path)
        if entry is None:
            entry = {"path": str(path), "used_by": [], "first_frame": frame}
            self.files[path] = entry
            try:
                stat = path.stat()
                self.stamps[path] = (stat.st_size, stat.st_mtime_ns)
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                entry.update(status="available", sha256=digest.hexdigest())
            except OSError as exc:
                entry.update(status="unavailable", reason=str(exc))
        if reference not in entry["used_by"]:
            entry["used_by"].append(reference)

    def scan(self, scene, frame):
        for asset in set(shot_assets(scene)):
            if isinstance(asset, bpy.types.Image) and asset.source == "FILE" and not asset.packed_files:
                if asset.filepath:
                    self.add(bpy.path.abspath(asset.filepath, library=asset.library), f"Image {asset.name}", frame)
            lib = asset.library
            while lib:
                if not getattr(lib, "packed_file", None):
                    self.add(bpy.path.abspath(lib.filepath, library=lib.parent), f"Library {lib.name}", frame)
                lib = lib.parent

    def problems(self):
        for path, stamp in self.stamps.items():
            entry = self.files[path]
            if entry["status"] == "available":
                try:
                    stat = path.stat()
                    if (stat.st_size, stat.st_mtime_ns) != stamp:
                        entry.update(status="changed", reason="File changed during this job")
                except OSError as exc:
                    entry.update(status="unavailable", reason=str(exc))
        return [str(path) for path, entry in self.files.items() if entry["status"] != "available"]


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
    dependencies = Dependencies()
    for path in job.get("required_files", []):
        dependencies.add(path, "required_files", first)
    render = request["mode"] == "render"
    images = work / "images"
    if render:
        images.mkdir()
    for frame in range(first, last + 1):
        scene.frame_set(frame)
        scene.camera = camera
        dependencies.scan(scene, frame)
        if dependencies.problems():
            break
        if not render:
            continue
        name = "still.png" if "frame" in job else f"frame_{frame:06d}.png"
        path = images / name
        settings.filepath = str(path)
        result = bpy.ops.render.render(write_still=True, scene=scene.name)
        if "FINISHED" not in result:
            raise RuntimeError(f"Render did not finish on frame {frame}: {result}")
        check_png(path, pixels)
    problems = dependencies.problems()
    details["dependencies"] = sorted(dependencies.files.values(), key=lambda item: item["path"])
    for entry in details["dependencies"]:
        entry["used_by"].sort()
    if problems:
        details.update(ok=False, status="needs_review", error="Required render dependencies need review: " + ", ".join(problems))
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
