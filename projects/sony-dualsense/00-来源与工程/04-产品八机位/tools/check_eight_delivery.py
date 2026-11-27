"""Reopen the source and delivery, compare meshes and poses, then validate the eight PNGs."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

import bpy
import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_geometry import mesh_fingerprint

PARTS = "Controller | Original FBX geometry"
HOUSING = "Housing | shell, touchpad, controls and ports"
ORIGINAL = Path(r"D:\dji-dualsense-4k-render-studio\sony-dualsense\DualSense-4K-Studio.blend")
SHOT_IDS = [f"{i:02d}" for i in range(1, 9)]
SIZE = (3072, 3840)
TOLERANCE = 0.00001


def check(condition, message):
    if not condition:
        raise ValueError(message)


def packed_images():
    images = {}
    for image in bpy.data.images:
        if image.source not in {"FILE", "TILED", "SEQUENCE", "MOVIE"}:
            continue
        check(image.packed_files, f"Unpacked external image: {image.name}")
        images[image.name] = [
            hashlib.sha256(tile.packed_file.data).hexdigest() for tile in image.packed_files
        ]
    return images


def indexes(mesh):
    data = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get("material_index", data)
    return data


def scalar_settings(block):
    """Serialize RNA settings relevant to these rigs, skipping pointers and collections."""
    values = {}
    for prop in block.bl_rna.properties:
        if prop.is_readonly or prop.type not in {"FLOAT", "INT", "BOOLEAN", "ENUM", "STRING"}:
            continue
        key = prop.identifier
        value = getattr(block, key)
        if getattr(prop, "is_array", False):
            value = np.array(value).tolist()
        elif isinstance(value, set):
            value = sorted(value)
        values[key] = value
    return values


def shader_state(tree):
    nodes = []
    for node in sorted(tree.nodes, key=lambda n: n.name):
        values = [[s.identifier, scalar_settings(s).get("default_value")] for s in node.inputs
                  if hasattr(s, "default_value")]
        images = [node.image.name] if getattr(node, "image", None) else []
        ramp = getattr(node, "color_ramp", None)
        stops = [(p.position, list(p.color)) for p in ramp.elements] if ramp else []
        nodes.append([node.bl_idname, scalar_settings(node), values, images, stops])
    links = sorted([l.from_node.name, l.from_socket.identifier, l.to_node.name,
                    l.to_socket.identifier] for l in tree.links)
    return [nodes, links]


def render_rigs(path, numbers):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    rigs = {}
    material_cache = {}
    for scene in bpy.data.scenes:
        if scene.name[:2] not in numbers:
            continue
        bpy.context.window.scene = scene
        scene.frame_set(1)
        camera = scene.camera
        assets = []
        for inst in bpy.context.evaluated_depsgraph_get().object_instances:
            obj = inst.object.original
            if obj.type not in {"MESH", "LIGHT"}:
                continue
            item = {"object": obj.name, "pose": np.array(inst.matrix_world).tolist(),
                    "hide_render": obj.hide_render, "visible_camera": obj.visible_camera}
            if obj.type == "LIGHT":
                item["light"] = scalar_settings(obj.data)
            else:
                item["materials"] = [slot.material.name for slot in obj.material_slots if slot.material]
                for slot in item["materials"]:
                    if slot not in material_cache:
                        mat = bpy.data.materials[slot]
                        material_cache[slot] = hashlib.sha256(json.dumps(
                            shader_state(mat.node_tree), sort_keys=True).encode()).hexdigest()
            assets.append(item)
        used = sorted({name for obj in assets for name in obj.get("materials", [])})
        rigs[scene.name] = {
            "camera": [camera.name, np.array(camera.matrix_world).tolist(), scalar_settings(camera.data),
                       scalar_settings(camera.data.dof)],
            "rig": sorted(assets, key=lambda obj: obj["object"]),
            "materials": {name: material_cache[name] for name in used}, "world": shader_state(scene.world.node_tree),
            "color": scalar_settings(scene.view_settings), "cycles": scalar_settings(scene.cycles),
            "output": [scene.render.engine, scene.render.resolution_x, scene.render.resolution_y,
                       scene.render.resolution_percentage, scalar_settings(scene.render.image_settings)],
        }
    return rigs


def read_reference(path):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    bpy.context.window.scene = bpy.data.scenes["DualSense White"]
    bpy.context.scene.frame_set(1)
    parts = {}
    for obj in bpy.data.collections[PARTS].objects:
        check(not obj.modifiers, f"Reference has modifiers on {obj.name}")
        parts[obj.name] = {
            "hash": mesh_fingerprint(obj.data), "world": np.array(obj.matrix_world),
            "vertices": len(obj.data.vertices), "polygons": len(obj.data.polygons),
        }
    shell = bpy.data.objects[HOUSING].data
    return parts, indexes(shell), [mat.name for mat in shell.materials], packed_images()


def check_png(path, expected_size=SIZE):
    """Verify the PNG envelope, every CRC and the decompressed RGB16 scanline length."""
    digest = hashlib.sha256()
    decoder = zlib.decompressobj()
    inflated = 0
    with path.open("rb") as stream:
        sig = stream.read(8)
        check(sig == b"\x89PNG\r\n\x1a\n", f"Invalid signature: {path}")
        digest.update(sig)
        first = True
        while True:
            header = stream.read(8)
            check(len(header) == 8, f"Truncated chunk: {path}")
            length, kind = struct.unpack(">I4s", header)
            payload = stream.read(length)
            crc = stream.read(4)
            check(len(payload) == length and len(crc) == 4, f"Truncated PNG: {path}")
            check(crc == struct.pack(">I", zlib.crc32(payload, zlib.crc32(kind))),
                  f"Damaged {kind!r}: {path}")
            digest.update(header)
            digest.update(payload)
            digest.update(crc)
            if first:
                check(kind == b"IHDR", f"Missing IHDR: {path}")
                width, height, depth, color, compression, filtering, interlace = struct.unpack(
                    ">IIBBBBB", payload)
                check((width, height) == expected_size and (depth, color) == (16, 2),
                      f"Wrong resolution or bit depth: {path}")
                check((compression, filtering, interlace) == (0, 0, 0), f"Unexpected PNG encoding: {path}")
                first = False
            if kind == b"IDAT":
                inflated += len(decoder.decompress(payload))
            if kind == b"IEND":
                check(length == 0 and not stream.read(1), f"Invalid end of file: {path}")
                break
    inflated += len(decoder.flush())
    check(decoder.eof and not decoder.unused_data and inflated == height * (1 + width * 6),
          f"Incomplete pixel data: {path}")
    return {"name": path.name, "width": width, "height": height, "channels": "RGB",
            "bits_per_channel": depth, "sha256": digest.hexdigest(), "bytes": path.stat().st_size}


def inspect_scene(scene, parts, fingerprints, map_by_hash, reference_indexes, material_names):
    bpy.context.window.scene = scene
    scene.frame_set(1)
    graph = bpy.context.evaluated_depsgraph_get()
    camera = scene.camera
    check(camera and any(m.frame == 1 and m.camera == camera for m in scene.timeline_markers),
          f"Missing frame 1 camera binding in {scene.name}")
    check(camera.name in scene.objects and not camera.hide_render, f"Unusable camera in {scene.name}")
    render = scene.render
    fmt = render.image_settings
    check(render.engine == "CYCLES" and (render.resolution_x, render.resolution_y) == SIZE
          and render.resolution_percentage == 100 and (fmt.file_format, fmt.color_mode, fmt.color_depth)
          == ("PNG", "RGB", "16"), f"Unexpected final render settings in {scene.name}")
    output = Path(bpy.path.abspath(render.filepath)).resolve()
    check(render.filepath.startswith("//") and output.name.startswith(scene.name[:2] + "-")
          and output.suffix.lower() == ".png", f"Invalid render target {render.filepath}")
    check(output.is_relative_to(Path(bpy.data.filepath).parent),
          f"Nonportable output path {render.filepath}")
    found, concept_faces = {}, 0
    for instance in graph.object_instances:
        obj = instance.object.original
        if obj.type != "MESH" or obj.hide_render:
            continue
        mesh = obj.data
        ptr = mesh.as_pointer()
        if ptr not in fingerprints:
            fingerprints[ptr] = mesh_fingerprint(mesh)
        part = map_by_hash.get(fingerprints[ptr])
        if not part:
            continue
        check(part not in found, f"Duplicate {part} in {scene.name}")
        check(not obj.modifiers and not obj.data.shape_keys, f"Deformed mesh in {scene.name}: {part}")
        check(obj.visible_camera, f"Product hidden from camera in {scene.name}: {part}")
        found[part] = np.array(instance.matrix_world) @ np.linalg.inv(parts[part]["world"])
        if part == HOUSING:
            current_indexes = indexes(mesh)
            if scene.name.startswith("03 "):
                changed = current_indexes != reference_indexes
                concept_faces = int(np.count_nonzero(changed))
                slots = [mat.name for mat in mesh.materials]
                used = {slots[i] for i in np.unique(current_indexes[changed])}
                original_used = {material_names[i] for i in np.unique(reference_indexes[changed])}
                check(concept_faces > 0 and used == {"Shell concept | Smoked ice polymer"}
                      and original_used == {"Shell | frost-white satin polymer"}
                      and slots[:len(material_names)] == material_names, "Unexpected concept-shell assignment")
            else:
                check(np.array_equal(current_indexes, reference_indexes),
                      f"Original shell material assignments changed in {scene.name}")
    check(set(found) == set(parts), f"Missing source meshes in {scene.name}: {set(parts) - set(found)}")
    anchor = found[HOUSING]
    error = max(float(np.max(np.abs(matrix - anchor))) for matrix in found.values())
    rotation = anchor[:3, :3]
    check(error < TOLERANCE and np.allclose(rotation.T @ rotation, np.eye(3), atol=TOLERANCE)
          and abs(np.linalg.det(rotation) - 1) < TOLERANCE,
          f"Product dimensions or relative transforms changed in {scene.name}, error {error}")
    camera_world = np.array(camera.evaluated_get(graph).matrix_world)
    return {"scene": scene.name, "camera": camera.name, "camera_world": camera_world.round(7).tolist(),
            "lens_mm": round(camera.data.lens, 5), "parts": len(found),
            "assembly_matrix": anchor.round(7).tolist(), "max_relative_matrix_error": error,
            "concept_shell_faces": concept_faces, "output": render.filepath}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=ORIGINAL)
    parser.add_argument("--image-dir", type=Path)
    parser.add_argument("--scene-only", action="store_true")
    parser.add_argument("--prior-render-project", type=Path, help="Blend file used to render the selected shots")
    parser.add_argument("--prior-shots", nargs="+", choices=SHOT_IDS,
                        help="Scene numbers rendered from the specified earlier project")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if bool(args.prior_shots) != bool(args.prior_render_project):
        parser.error("Use --prior-shots and --prior-render-project together")
    if args.prior_shots and len(set(args.prior_shots)) != len(args.prior_shots):
        parser.error("List each prior shot only once")
    delivery = Path(bpy.data.filepath).resolve()
    check(delivery.is_file() and delivery != args.reference.resolve(), "Open the delivery .blend first")
    image_dir = args.image_dir.resolve() if args.image_dir else delivery.parent / "renders"
    qa = delivery.parent / "qa"
    qa.mkdir(exist_ok=True)
    target = qa / ("scene-check.json" if args.scene_only else "delivery-check.json")
    if args.prior_render_project:
        subset = "-".join(sorted(args.prior_shots))
        target = qa / f"rigs-{subset}-vs-{args.prior_render_project.stem}.json"
    report = {"delivery": str(delivery), "reference": str(args.reference), "blender": bpy.app.version_string,
              "mode": "scene-only" if args.scene_only else "scene-and-images", "scenes": [], "passed": False}
    try:
        with delivery.open("rb") as stream:
            report["delivery_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
        parts, reference_indexes, material_names, original_maps = read_reference(args.reference.resolve())
        bpy.ops.wm.open_mainfile(filepath=str(delivery))
        maps = packed_images()
        check(all(maps.get(name) == hashes for name, hashes in original_maps.items()),
              "Source texture payload missing or changed")
        check(not bpy.data.libraries, "External linked blend library required")
        report["packed_textures"] = maps
        report["original_geometry"] = {k: {p: v for p, v in data.items() if p != "world"}
                                       for k, data in sorted(parts.items())}
        map_by_hash = {data["hash"]: name for name, data in parts.items()}
        check(len(map_by_hash) == len(parts), "Source geometry fingerprints are ambiguous")
        fingerprints = {}
        originals = bpy.data.collections[PARTS].objects
        check({obj.name for obj in originals} == set(parts), "Original product collection changed")
        for obj in originals:
            key = obj.data.as_pointer()
            fingerprints[key] = mesh_fingerprint(obj.data)
            check(fingerprints[key] == parts[obj.name]["hash"], f"Changed source geometry: {obj.name}")
        shots = sorted((s for s in bpy.data.scenes if s.name[:2] in SHOT_IDS and s.name[2:3] == " "),
                       key=lambda s: s.name)
        check([s.name[:2] for s in shots] == SHOT_IDS, "One scene per number 01 through 08 required")
        for scene in shots:
            report["scenes"].append(inspect_scene(scene, parts, fingerprints, map_by_hash,
                                                  reference_indexes, material_names))
        cameras = {s["camera"] for s in report["scenes"]}
        poses = {json.dumps(s["camera_world"]) for s in report["scenes"]}
        check(len(cameras) == 8 and len(poses) == 8, "Duplicate camera/pose in still series")
        if args.prior_render_project:
            numbers = set(args.prior_shots)
            prior = render_rigs(args.prior_render_project.resolve(), numbers)
            final = render_rigs(delivery, numbers)
            check(set(prior) == set(final) and {name[:2] for name in final} == numbers
                  and len(final) == len(numbers), "Missing or ambiguous rigs for comparison")
            differences = {name: [field for field in rig if rig[field] != final[name][field]]
                           for name, rig in prior.items()}
            report["prior_project"] = str(args.prior_render_project.resolve())
            with args.prior_render_project.open("rb") as stream:
                report["prior_project_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
            report["prior_shots"] = sorted(numbers)
            report["rig_differences"] = differences
            check(not any(differences.values()), f"Rigs changed: {differences}")
        if not args.scene_only:
            names = {Path(bpy.path.abspath(shot["output"])).name for shot in report["scenes"]}
            files = sorted(image_dir.glob("*.png"))
            check({path.name for path in files} == names, f"Check number and names of PNGs in {image_dir}")
            report["images"] = [check_png(path) for path in files]
            check(len({im["sha256"] for im in report["images"]}) == 8, "Duplicate encoded images")
        report["passed"] = True
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{'PASS' if report['passed'] else 'FAIL'} {target}", flush=True)


if __name__ == "__main__":
    main()
