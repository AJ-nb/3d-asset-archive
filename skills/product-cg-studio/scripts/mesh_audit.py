"""Inspect named evaluated meshes in the active Blender scene. All distances are physical mm."""

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import bpy
from mathutils.bvhtree import BVHTree


def inspect(obj, depsgraph, mm_per_bu, solid, check_intersections):
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    issues = {}

    def record(kind, sample):
        item = issues.setdefault(kind, {"count": 0, "examples": []})
        item["count"] += 1
        if len(item["examples"]) < 8:
            item["examples"].append(sample)

    try:
        world = [evaluated.matrix_world @ v.co for v in mesh.vertices]
        if not world or not mesh.polygons:
            record("empty_surface", obj.name)
        if any(not all(math.isfinite(x) for x in co) for co in world):
            raise ValueError(f"{obj.name}: non-finite evaluated world coordinates")
        coord_counts = Counter(tuple(v) for v in world)
        edge_uses = defaultdict(list)
        for edge in mesh.edges:
            edge_uses[tuple(sorted(edge.vertices))] = []
        used = set()
        faces = {}
        for poly in mesh.polygons:
            ids = tuple(poly.vertices)
            used.update(ids)
            for a, b in zip(ids, ids[1:] + ids[:1]):
                key = (min(a, b), max(a, b))
                edge_uses[key].append((poly.index, a <= b))
            # Normalize the cyclic order and its reversal, preserving polygon connectivity.
            start = ids.index(min(ids))
            seq = ids[start:] + ids[:start]
            key = min(seq, seq[:1] + seq[:0:-1])
            if key in faces:
                record("duplicate_polygon_loop", [faces[key], poly.index])
            else:
                faces[key] = poly.index
        neighbours = defaultdict(list)
        open_or_unoriented = set()
        for key, uses in edge_uses.items():
            if len(uses) != 2 or uses[0][1] == uses[1][1]:
                open_or_unoriented.update(face for face, _ in uses)
            if len(uses) == 0:
                record("loose_edge", key)
            elif len(uses) == 1:
                record("boundary_edge", key)
            elif len(uses) > 2:
                record("edge_with_multiple_sheets", key)
            elif uses[0][1] == uses[1][1]:
                record("inconsistent_winding", key)
            if uses:
                first = uses[0][0]
                for face, _ in uses[1:]:
                    neighbours[first].append(face)
                    neighbours[face].append(first)
        for v in mesh.vertices:
            if v.index not in used:
                record("vertex_outside_faces", v.index)
        mesh.calc_loop_triangles()
        triangles = [tuple(tri.vertices) for tri in mesh.loop_triangles]
        # Compute one signed volume per connected, closed, consistently wound shell.
        # An anchor on the shell avoids subtracting large world-origin tetrahedra.
        component = {}
        shells = []
        for face in mesh.polygons:
            if face.index in component:
                continue
            idx = len(shells)
            pending = [face.index]
            component[face.index] = idx
            shell = {"first_polygon": face.index, "orientable_closed": True, "signed_volume_mm3": 0.0}
            while pending:
                here = pending.pop()
                if here in open_or_unoriented:
                    shell["orientable_closed"] = False
                for other in neighbours[here]:
                    if other not in component:
                        component[other] = idx
                        pending.append(other)
            shells.append(shell)
        anchors = [world[mesh.polygons[s["first_polygon"]].vertices[0]] for s in shells]
        smallest_area = None
        for i, (a, b, c) in enumerate(triangles):
            idx = component[mesh.loop_triangles[i].polygon_index]
            if shells[idx]["orientable_closed"]:
                anchor = anchors[idx]
                tetrahedron = (world[a] - anchor).dot((world[b] - anchor).cross(world[c] - anchor))
                shells[idx]["signed_volume_mm3"] += tetrahedron * mm_per_bu ** 3 / 6
            area = (world[b] - world[a]).cross(world[c] - world[a]).length * mm_per_bu ** 2 / 2
            if area == 0:
                record("zero_area_triangle", i)
            smallest_area = area if smallest_area is None else min(smallest_area, area)
        for shell in shells:
            if not shell["orientable_closed"]:
                shell["signed_volume_mm3"] = None
            elif shell["signed_volume_mm3"] <= 0:
                record("nonpositive_shell_volume_review", shell["first_polygon"])
        if check_intersections and triangles:
            tree = BVHTree.FromPolygons(world, triangles, all_triangles=True)
            for a, b in tree.overlap(tree):
                if a < b and set(triangles[a]).isdisjoint(triangles[b]):
                    record("nonadjacent_triangle_overlap_candidate", [a, b])
        mandatory = {"empty_surface", "duplicate_polygon_loop", "zero_area_triangle", "inconsistent_winding"}
        if solid:
            mandatory.update({"boundary_edge", "edge_with_multiple_sheets", "loose_edge", "vertex_outside_faces"})
            if len(shells) == 1 and evaluated.matrix_world.to_3x3().determinant() > 0:
                mandatory.add("nonpositive_shell_volume_review")
        return {
            "object": obj.name, "closed_solid_expected": solid, "vertices": len(world),
            "polygons": len(mesh.polygons), "triangles": len(triangles),
            "smallest_triangle_mm2": smallest_area,
            "extra_vertices_at_identical_world_coordinates": sum(n - 1 for n in coord_counts.values()),
            "shells": shells, "issues": issues, "failed_checks": sorted(mandatory.intersection(issues)),
        }
    finally:
        evaluated.to_mesh_clear()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--part", action="append", default=[], help="Mesh object name. Repeat for other parts.")
    parser.add_argument("--solid", action="append", default=[], help="Include this part and require closed topology.")
    parser.add_argument("--out", required=True, type=Path, help="New JSON report path")
    parser.add_argument("--self-overlap", action="store_true", help="Report candidate nonadjacent triangle pairs")
    parser.add_argument("--mm-per-unit", "--mm-per-bu", dest="mm_per_bu", type=float,
                        help="Explicit millimetres per Blender unit, e.g. for unitless scenes")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    scene = bpy.context.scene
    mm = args.mm_per_bu
    if mm is None and scene.unit_settings.system != "NONE":
        mm = 1000 * scene.unit_settings.scale_length
    if mm is None or not math.isfinite(mm) or mm <= 0:
        parser.error("set a physical scene unit or pass a verified positive --mm-per-unit")
    names = list(dict.fromkeys(args.part + args.solid))
    if not names:
        parser.error("identify the product meshes with --part or --solid")
    depsgraph = bpy.context.evaluated_depsgraph_get()
    reports = []
    for name in names:
        obj = scene.objects.get(name)
        if obj is None or obj.type != "MESH":
            parser.error(f"mesh object absent from active scene: {name}")
        reports.append(inspect(obj, depsgraph, mm, name in args.solid, args.self_overlap))
    source = Path(bpy.data.filepath)
    source_hash = None
    if source.is_file():
        with source.open("rb") as handle:
            source_hash = hashlib.file_digest(handle, "sha256").hexdigest()
    report = {"asset": source.name, "blend_sha256": source_hash, "blender": bpy.app.version_string,
              "scene": scene.name, "frame": scene.frame_current, "mm_per_bu": mm,
              "self_overlap_checked": args.self_overlap, "parts": reports}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    failed = [r["object"] for r in reports if r["failed_checks"]]
    print(f"Mesh report: {args.out} | {len(reports)} parts | failed: {failed}")
    if failed:
        raise RuntimeError("Mesh audit found defects. See failed_checks and element indices in the report.")


if __name__ == "__main__":
    main()
