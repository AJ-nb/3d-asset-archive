"""Measure the two animated desk supports in the open Blender file.

Run with Blender's --python-exit-code 1 before -P audit.py. By default the
JSON report goes to stdout. Append -- OUTPUT.json to create a new report file.
"""

import argparse
from itertools import combinations, product
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


MM_PER_METRE = 1000
LIFT_HITS = "A_lift_flank_face_intersections"
FOLD_HITS = "B_compaction_between_blades_and_toes"


def named_part(scene, prefix):
    matches = [obj for obj in scene.objects if obj.name.startswith(prefix)]
    if len(matches) != 1:
        raise ValueError(f"{scene.name}: expected one part starting with {prefix!r}, found {len(matches)}")
    return matches[0]


def world_vertices(evaluated):
    transform = evaluated.matrix_world
    return [transform @ vertex.co for vertex in evaluated.data.vertices]


def bounds_mm(objects, depsgraph):
    vertices = []
    for obj in objects:
        vertices.extend(world_vertices(obj.evaluated_get(depsgraph)))
    bounds = []
    for axis in range(3):
        low = min(point[axis] for point in vertices)
        high = max(point[axis] for point in vertices)
        bounds.append((round(low * MM_PER_METRE, 3), round(high * MM_PER_METRE, 3)))
    return bounds


def translation_mm(obj, depsgraph):
    position = obj.evaluated_get(depsgraph).matrix_world.translation
    return [round(value * MM_PER_METRE, 3) for value in position]


def measure_support(scene, label, frames, report):
    bpy.context.window.scene = scene
    parts = [obj for obj in scene.objects if obj.type == "MESH" and obj.name.startswith(f"{label} | ")]
    parts.append(named_part(scene, "Adapter |"))
    for frame in frames:
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        bounds = bounds_mm(parts, depsgraph)
        report[f"{label}{frame}_overall_xy_mm"] = [round(high - low, 2) for low, high in bounds[:2]]
        if label == "A":
            sole = named_part(scene, "A | contact sole")
            report["A_sole_low_z_mm"] = bounds_mm([sole], depsgraph)[2][0]
        else:
            toes = [obj for obj in parts if obj.name.startswith("B | rubber foot")]
            report[f"B{frame}_toe_low_z_mm"] = [bounds_mm([toe], depsgraph)[2][0] for toe in toes]


def world_tree(obj, depsgraph):
    evaluated = obj.evaluated_get(depsgraph)
    faces = [list(face.vertices) for face in evaluated.data.polygons]
    return BVHTree.FromPolygons(world_vertices(evaluated), faces)


def face_intersections(scene, frames, pairs):
    bpy.context.window.scene = scene
    objects = {obj for pair in pairs for obj in pair}
    intersections = []
    for frame in frames:
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        trees = {obj: world_tree(obj, depsgraph) for obj in objects}
        for first, second in pairs:
            hits = trees[first].overlap(trees[second])
            if hits:
                intersections.append([frame, first.name, second.name, len(hits)])
    return intersections


def measure_lift(scene, report):
    shells = [
        scene.objects["Clay | Handle • molded upper shell"],
        scene.objects["Clay | Handle • lower cap and connector carrier"],
    ]
    flanks = [obj for obj in scene.objects if obj.name.startswith(("Seat | lower flank", "Lining | lower flank"))]
    if len(flanks) != 4:
        raise ValueError(f"Expected four guide flanks, found {len(flanks)}")
    report[LIFT_HITS] = face_intersections(scene, range(62, 95), list(product(shells, flanks)))

    grip = named_part(scene, "Lift camera vertically")
    plug = named_part(scene, "Straight USB-C | external")
    for frame in (62, 74, 83, 89, 94):
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        report[f"A_frame_{frame}"] = {
            "grip_root_mm": translation_mm(grip, depsgraph),
            "plug_mould_centre_mm": translation_mm(plug, depsgraph),
            "plug_set_aside": plug.hide_render,
        }


def measure_aim(scene):
    bpy.context.window.scene = scene
    scene.frame_set(62)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    tilt = named_part(scene, "Gimbal pitch").evaluated_get(depsgraph)
    axis = (tilt.matrix_world.to_3x3() @ Vector((0, -1, 0))).normalized()
    glass = named_part(scene, "Clay | 04P | 1-inch wide angle / flat removable glass")
    bounds = bounds_mm([glass], depsgraph)
    origin = Vector([(low + high) / (2 * MM_PER_METRE) for low, high in bounds])
    target = named_part(scene, "Chest-up target").evaluated_get(depsgraph).matrix_world.translation
    distance = (target.y - origin.y) / axis.y
    crossing = origin + axis * distance
    return {
        "axis": [round(value, 5) for value in axis],
        "pitch_deg": round(math.degrees(math.asin(axis.z)), 2),
        "reference_y_mm": round(target.y * MM_PER_METRE, 2),
        "line_z_at_subjectplane_mm": round(crossing.z * MM_PER_METRE, 2),
        "target_z_mm": round(target.z * MM_PER_METRE, 2),
    }


def measure_fold(scene):
    legs = [
        (scene.objects[f"B | fan blade {index}"], scene.objects[f"B | rubber foot {index}"])
        for index in range(1, 4)
    ]
    # The blade and toe on each leg are joined. Only compare different legs.
    pairs = []
    for first_leg, second_leg in combinations(legs, 2):
        pairs.extend(product(first_leg, second_leg))
    return face_intersections(scene, range(94, 111), pairs)


def audit():
    dock = bpy.data.scenes["A - Lift-out desk dock"]
    fan = bpy.data.scenes["B - Detachable fan-foot dock"]
    report = {
        "opened_default": bpy.context.scene.name,
        "reopened_scene_names": [scene.name for scene in bpy.data.scenes],
        "blender": bpy.app.version_string,
        "external_paths": [path for path in bpy.utils.blend_paths(absolute=True) if path and not path.startswith("<")],
        "images": [image.name for image in bpy.data.images],
        "libraries": [library.name for library in bpy.data.libraries],
        "fonts": [font.name for font in bpy.data.fonts],
        "product_meshes": sum(obj.type == "MESH" and obj.name.startswith("Clay | ") for obj in dock.objects),
    }
    bpy.context.window.scene = dock
    dock.frame_set(62)
    desk = named_part(dock, "Writing desk")
    report["table_top_z_mm"] = bounds_mm([desk], bpy.context.evaluated_depsgraph_get())[2][1]
    measure_support(dock, "A", (62,), report)
    measure_support(fan, "B", (62, 102, 110), report)
    measure_lift(dock, report)
    report["aim"] = measure_aim(dock)
    report[FOLD_HITS] = measure_fold(fan)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, help="create a new JSON file")
    arguments = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    output = parser.parse_args(arguments).output
    report = audit()
    document = json.dumps(report, indent=2, ensure_ascii=False)
    if output is None:
        print(document, flush=True)
    else:
        with output.open("x", encoding="utf-8") as stream:
            stream.write(document)
    if report[LIFT_HITS] or report[FOLD_HITS]:
        raise RuntimeError("Surface intersections detected. See the lift and compaction entries in the QA report.")


if __name__ == "__main__":
    main()
