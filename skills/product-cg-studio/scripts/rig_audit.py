"""Evaluate named assembly and skin checks on the saved Blender scene."""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Expected a finite number, received {value!r}")
    return float(value)


def sample_frames(values):
    if not isinstance(values, list) or not values:
        raise ValueError("frames must be a nonempty list of scene frame numbers")
    return list(dict.fromkeys(number(value) for value in values))


def vertex_index(index, count):
    if type(index) is not int or not 0 <= index < count:
        raise ValueError(f"Vertex index {index!r} outside mesh of size {count}")
    return index


def metric_tolerance(spec, key):
    value = number(spec[key])
    if value < 0:
        raise ValueError(f"Negative {key}")
    return value


class Sample:
    def __init__(self, scene, frame, mm):
        integer = math.floor(frame)
        scene.frame_set(integer, subframe=frame - integer)
        self.graph = bpy.context.evaluated_depsgraph_get()
        self.scene = scene
        self.mm = mm

    def obj(self, name):
        return self.scene.objects[name].evaluated_get(self.graph)

    def mesh(self, name):
        obj = self.obj(name)
        if obj.type != "MESH":
            raise ValueError(f"{name} must be a mesh")
        return obj

    def point(self, anchor):
        obj = self.obj(anchor["object"])
        if ("vertex" in anchor) == ("point" in anchor):
            raise ValueError("Each anchor needs exactly one local point or evaluated vertex")
        if "vertex" in anchor:
            vertices = self.mesh(anchor["object"]).data.vertices
            local = vertices[vertex_index(anchor["vertex"], len(vertices))].co
        else:
            coordinates = anchor["point"]
            if len(coordinates) != 3:
                raise ValueError("A local point needs three coordinates in Blender units")
            local = Vector([number(v) for v in coordinates])
        return (obj.matrix_world @ local) * self.mm

    def body_coordinates(self, spec):
        obj = self.mesh(spec["object"])
        points = [(obj.matrix_world @ vertex.co) * self.mm for vertex in obj.data.vertices]
        a, b, c = [points[vertex_index(i, len(points))] for i in spec["basis_vertices"]]
        ab, ac = b - a, c - a
        normal = ab.cross(ac)
        if min(ab.length, ac.length) == 0 or normal.length <= 1e-6 * ab.length * ac.length:
            raise ValueError("Rigid basis vertices must be distinct and noncollinear")
        x, z = ab.normalized(), normal.normalized()
        y = z.cross(x)
        return [Vector((v.dot(x), v.dot(y), v.dot(z))) for v in (p - a for p in points)]

    def direction(self, axis):
        components = axis["direction"]
        if len(components) != 3:
            raise ValueError("Axis direction requires three components")
        local = Vector([number(value) for value in components])
        world = self.obj(axis["object"]).matrix_world.to_3x3() @ local
        if world.length == 0:
            raise ValueError("Axis has zero world-space length")
        return world.normalized()

    def surface_hit_mm(self, name, origin, direction):
        obj = self.mesh(name)
        inverse = obj.matrix_world.inverted()
        local_direction = (inverse.to_3x3() @ direction).normalized()
        hit, location, _, _ = obj.ray_cast(inverse @ origin, local_direction)
        if not hit:
            raise ValueError(f"Ray missed {name}; inspect alignment and probe depth")
        return (obj.matrix_world @ location - origin).dot(direction) * self.mm

    def inspect_shell(self, name):
        obj = self.mesh(name)
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            transform = obj.matrix_world.copy()
            transform.translation = Vector((0, 0, 0))
            bm.transform(transform)
            bm.normal_update()
            bad_edges = sum(not e.is_manifold for e in bm.edges)
            bad_winding = sum(e.is_manifold and not e.is_contiguous for e in bm.edges)
            bad_vertices = sum(not v.is_manifold for v in bm.verts)
            unseen = set(bm.faces)
            components = 0
            while unseen:
                pending = [unseen.pop()]
                components += 1
                while pending:
                    for edge in pending.pop().edges:
                        for face in edge.link_faces:
                            if face in unseen:
                                unseen.remove(face)
                                pending.append(face)
            volume = bm.calc_volume(signed=True) * self.mm ** 3
            if not math.isfinite(volume):
                raise ValueError("Nonfinite signed volume")
            passed = components == 1 and not (bad_edges or bad_winding or bad_vertices) and volume > 0
            return {"pass": passed, "faces": len(bm.faces), "edges": len(bm.edges),
                    "nonmanifold_edges": bad_edges, "nonmanifold_vertices": bad_vertices,
                    "inconsistent_edges": bad_winding, "connected_shells": components,
                    "signed_volume_mm3": volume}
        finally:
            bm.free()


def check_skin(scene, spec):
    obj, arm = scene.objects[spec["object"]], scene.objects[spec["armature"]]
    if obj.type != "MESH" or arm.type != "ARMATURE" or not obj.data.vertices:
        raise ValueError("Skin check needs a nonempty mesh and an armature")
    modifiers = [m for m in obj.modifiers if m.type == "ARMATURE" and m.object == arm]
    enabled = any(m.show_viewport and m.show_render and m.use_vertex_groups for m in modifiers)
    deform = {b.name for b in arm.data.bones if b.use_deform}
    tolerance = metric_tolerance(spec, "weight_sum_tolerance")
    max_influences = spec.get("max_influences")
    if max_influences is not None and (type(max_influences) is not int or max_influences < 1):
        raise ValueError("max_influences must be a positive integer")
    regions = []
    for region in spec.get("regions", []):
        allowed = set(region["allowed_bones"])
        if not allowed or not allowed <= deform or not region["vertices"]:
            raise ValueError("Skin region must name deform bones and vertices")
        indices = {vertex_index(v, len(obj.data.vertices)) for v in region["vertices"]}
        regions.append((indices, allowed))
    bad_count = 0
    examples = []
    for v in obj.data.vertices:
        weights = {obj.vertex_groups[g.group].name: g.weight for g in v.groups
                   if g.weight > 0 and obj.vertex_groups[g.group].name in deform}
        reasons = []
        if not weights or abs(sum(weights.values()) - 1) > tolerance:
            reasons.append("weight_sum")
        if max_influences is not None and len(weights) > max_influences:
            reasons.append("influence_count")
        if any(v.index in indices and weights.keys() - allowed for indices, allowed in regions):
            reasons.append("outside_region")
        if reasons:
            bad_count += 1
            if len(examples) < 20:
                examples.append({"vertex": v.index, "weights": weights, "reasons": reasons})
    return {"pass": enabled and not bad_count, "modifier_enabled": enabled,
            "bad_vertices": bad_count, "vertices": len(obj.data.vertices), "examples": examples}


def run_check(scene, mm, rest, frames, spec):
    kind = spec["type"]
    if kind == "skin":
        return check_skin(scene, spec)
    if kind == "closed_single_shell":
        rows = [{"frame": f, **Sample(scene, f, mm).inspect_shell(spec["object"])}
                for f in sample_frames(spec.get("frames", frames))]
        return {"pass": all(row["pass"] for row in rows), "samples": rows}
    if kind not in {"distance", "axis_gap", "ray_gap", "rigid"}:
        raise ValueError(f"Unknown check type {kind}")
    if kind == "rigid":
        base = Sample(scene, rest, mm).body_coordinates(spec)
        limit = metric_tolerance(spec, "max_error_mm")
    else:
        low, high = number(spec["min_mm"]), number(spec["max_mm"])
        if low > high or (kind == "distance" and low < 0):
            raise ValueError("Invalid interval for distance or signed axial separation")
    results = []
    for frame in sample_frames(spec.get("frames", frames)):
        state = Sample(scene, frame, mm)
        if kind == "ray_gap":
            origin = state.point(spec["origin"]) / state.mm
            direction = state.direction(spec["axis"])
            outer = state.surface_hit_mm(spec["outer_surface"], origin, direction)
            inner = state.surface_hit_mm(spec["inner_surface"], origin, direction)
            gap = outer - inner
            if not math.isfinite(gap) or min(outer, inner) <= 0:
                raise ValueError("Ray needs two positive finite intersections")
            row = {"outer_hit_mm": outer, "inner_hit_mm": inner, "signed_gap_mm": gap,
                   "pass": low <= gap <= high}
        elif kind in {"distance", "axis_gap"}:
            delta = state.point(spec["a"]) - state.point(spec["b"])
            value = delta.length if kind == "distance" else delta.dot(state.direction(spec["axis"]))
            if not math.isfinite(value):
                raise ValueError("Nonfinite anchor distance")
            field = "distance_mm" if kind == "distance" else "signed_gap_mm"
            row = {field: value, "pass": low <= value <= high}
        else:
            points = state.body_coordinates(spec)
            if len(points) != len(base):
                row = {"pass": False, "reason": "vertex_count_changed"}
            else:
                errors = [(p - q).length for p, q in zip(points, base)]
                if any(not math.isfinite(error) for error in errors):
                    raise ValueError("Nonfinite vertex position")
                index = max(range(len(errors)), key=errors.__getitem__)
                row = {"max_error_mm": errors[index], "vertex": index, "pass": errors[index] <= limit}
        results.append({"frame": frame, **row})
    return {"pass": all(r["pass"] for r in results), "samples": results}


def digest(path):
    with path.open("rb") as stream:
        value = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
        return value.hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--manifest", type=Path, required=True)
    cli.add_argument("--out", type=Path, required=True)
    args = cli.parse_args(sys.argv[sys.argv.index("--") + 1:])
    spec = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    source = Path(bpy.data.filepath)
    if not source.is_file():
        raise ValueError("Open a saved .blend before running the audit")
    scene = bpy.data.scenes[spec["scene"]]
    bpy.context.window.scene = scene
    rest = number(spec["rest_frame"])
    frames = sample_frames(spec["frames"])
    if scene.unit_settings.system == "NONE" and "mm_per_blender_unit" not in spec:
        raise ValueError("Unitless scene requires calibrated mm_per_blender_unit in manifest")
    mm = number(spec.get("mm_per_blender_unit", scene.unit_settings.scale_length * 1000))
    if mm <= 0:
        raise ValueError("mm_per_blender_unit must be positive")
    checks = spec["checks"]
    if not checks or any(not isinstance(c["id"], str) or not c["id"].strip() for c in checks):
        raise ValueError("Manifest needs named checks")
    if len({c["id"] for c in checks}) != len(checks):
        raise ValueError("Duplicate check IDs")
    results = []
    for check in checks:
        try:
            result = run_check(scene, mm, rest, frames, check)
        except (KeyError, ValueError, TypeError, IndexError, RuntimeError) as exc:
            result = {"pass": False, "error": str(exc)}
        results.append({"id": check["id"], "type": check.get("type"), **result})
    report = {"pass": all(r["pass"] for r in results), "scene": scene.name,
              "asset": source.name, "blend_sha256": digest(source),
              "manifest_sha256": digest(args.manifest), "blender": bpy.app.version_string,
              "mm_per_blender_unit": mm, "rest_frame": rest, "checks": results}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    if not report["pass"]:
        raise RuntimeError("Rig audit failed: " + ", ".join(r["id"] for r in results if not r["pass"]))
    print(f"Rig audit passed {len(results)} checks; report saved to {args.out}")


if __name__ == "__main__":
    main()
