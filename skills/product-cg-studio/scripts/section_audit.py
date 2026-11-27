"""Slice evaluated Blender meshes in a registered coordinate system. See references/sections.md."""
import argparse
import csv
import gzip
import hashlib
import html
import json
import math
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET

import bpy
from mathutils import Matrix
from mathutils.bvhtree import BVHTree
import numpy as np


AXES = "XYZ"
UV = {"X": (1, 2), "Y": (0, 2), "Z": (0, 1)}
FIELDS = ("part", "axis", "station_mm", "status", "current_segments", "reference_segments",
          "sample_max_mm", "worst_direction", "worst_u_mm", "worst_v_mm", "nearest_u_mm",
          "nearest_v_mm", "svg")
RADIUS_FIELDS = ("feature", "part", "axis", "station_mm", "box_uv_mm", "current_fit",
                 "current_R_mm", "current_rms_mm", "current_span_deg", "current_vertices",
                 "reference_fit", "reference_R_mm", "reference_rms_mm", "reference_span_deg",
                 "reference_vertices", "delta_R_mm")


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--parts", nargs="+", help="Exact mesh object names")
    group.add_argument("--collection", help="Mesh objects in a collection and its children")
    parser.add_argument("--allow-absent-parts", action="store_true",
                        help="Record absent named parts in a baseline for a later union comparison")
    parser.add_argument("--out", required=True, type=Path, help="New output directory")
    parser.add_argument("--reference", type=Path, help="Prior section_audit output directory")
    parser.add_argument("--pose", required=True, help="Assembly state shared by both inputs")
    parser.add_argument("--scene", help="Exact scene in a multi-scene .blend (default: saved active scene)")
    parser.add_argument("--frame", type=int, default=1)
    parser.add_argument("--datum", help="Rigid unscaled datum object; default is world axes")
    parser.add_argument("--axes", default="XYZ", help="Any combination of X, Y, Z")
    parser.add_argument("--step-mm", type=float, default=1)
    parser.add_argument("--range-mm", type=float, nargs=2, metavar=("MIN", "MAX"))
    parser.add_argument("--probe-mm", type=float, default=0.25, help="Maximum in-plane probe spacing")
    parser.add_argument("--mm-per-unit", type=float, help="Explicit calibrated physical scale")
    parser.add_argument("--fits", type=Path, help="Registered arc-window definitions (JSON)")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    args.axes = args.axes.upper()
    if not args.axes or set(args.axes) - set(AXES) or len(set(args.axes)) != len(args.axes):
        parser.error("--axes must contain distinct letters from XYZ")
    args.axes = "".join(axis for axis in AXES if axis in args.axes)
    for value in (args.step_mm, args.probe_mm, args.mm_per_unit):
        if value is not None and (not math.isfinite(value) or value <= 0):
            parser.error("Unit scale and spacing must be finite and positive")
    if args.range_mm and (not all(map(math.isfinite, args.range_mm)) or args.range_mm[1] < args.range_mm[0]):
        parser.error("--range-mm must be a finite ascending interval")
    if not args.pose.strip() or (args.parts and len(args.parts) != len(set(args.parts))):
        parser.error("Provide a pose label and distinct part names")
    if args.allow_absent_parts and (not args.parts or args.reference):
        parser.error("--allow-absent-parts is for a named-parts baseline before comparison")
    return args


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def datum_transform(scene, name, deps):
    if not name:
        return Matrix.Identity(4)
    obj = scene.objects.get(name)
    if not obj:
        raise ValueError(f"Missing datum object: {name}")
    matrix = obj.evaluated_get(deps).matrix_world.copy()
    orientation = np.array(matrix.to_3x3(), dtype=float)
    if not np.allclose(orientation.T @ orientation, np.eye(3), atol=1e-5) or np.linalg.det(orientation) <= 0:
        raise ValueError("Datum must have unit scale, perpendicular axes and positive handedness")
    return matrix


def triangles(obj, deps, world_to_datum, scale):
    evaluated = obj.evaluated_get(deps)
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        coordinates = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", coordinates)
        matrix = world_to_datum @ np.asarray(evaluated.matrix_world, dtype=float)
        xyz = (coordinates.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3]) * scale
        if not np.isfinite(xyz).all():
            raise ValueError(f"Nonfinite vertices in {obj.name}")
        indices = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
        mesh.loop_triangles.foreach_get("vertices", indices)
        return xyz[indices.reshape(-1, 3)]
    finally:
        evaluated.to_mesh_clear()


def cut_axis(tris, axis, step, limits):
    if not len(tris):
        return {}
    normal = AXES.index(axis)
    levels = tris[:, :, normal]
    # Integer station indices avoid accumulated step drift; normalize near-grid float noise.
    grid = np.rint(levels / step) * step
    levels = np.where(abs(levels - grid) <= min(1e-6, step * 1e-5), grid, levels)
    lo, hi = levels.min(axis=1), levels.max(axis=1)
    start, stop = limits or (lo.min(), hi.max())
    result = {}
    for index in range(math.ceil(start / step - 1e-10), math.floor(stop / step + 1e-10) + 1):
        plane = index * step
        crossing = (lo <= plane) & (hi > plane)
        selected, heights = tris[crossing], levels[crossing]
        pts = np.empty((len(selected), 2, 2))
        count = np.zeros(len(selected), dtype=int)
        for a, b in ((0, 1), (1, 2), (2, 0)):
            rows = np.flatnonzero((heights[:, a] > plane) != (heights[:, b] > plane))
            fraction = (plane - heights[rows, a]) / (heights[rows, b] - heights[rows, a])
            p = selected[rows, a] + fraction[:, None] * (selected[rows, b] - selected[rows, a])
            pts[rows, count[rows]] = p[:, UV[axis]]
            count[rows] += 1
        # Keep raw segments, weld endpoints only to 10^-6 mm, independent of display scale.
        segments = set()
        for a, b in np.round(pts[count == 2], 6):
            p, q = tuple(a), tuple(b)
            if p != q:
                segments.add((p, q) if p < q else (q, p))
        result[str(index)] = sorted(segments)
    return result


def greatest_distance(source, target, spacing):
    # Extrude the 2D segments above/below the plane. On z=0 their BVH nearest point
    # is the nearest point on a target segment, including its endpoints.
    vertices, faces = [], []
    for (u, v), (x, y) in target:
        i = len(vertices)
        vertices.extend(((u, v, -1), (x, y, -1), (x, y, 1), (u, v, 1)))
        faces.append((i, i + 1, i + 2, i + 3))
    tree = BVHTree.FromPolygons(vertices, faces)
    best = (-1.0, (), ())
    for (u, v), (x, y) in source:
        count = max(1, math.ceil(math.hypot(x - u, y - v) / spacing))
        for i in range(count + 1):
            t = i / count
            point = (u + (x - u) * t, v + (y - v) * t, 0)
            closest, _, _, distance = tree.find_nearest(point)
            if distance > best[0]:
                best = (distance, point[:2], tuple(closest[:2]))
    return best


def differences(current, reference, compare, probe):
    if not compare:
        return {"status": "model_only" if current else "empty"}
    if not current or not reference:
        status = "current_only" if current else ("reference_only" if reference else "empty")
        return {"status": status}
    # Exactly identical saved segment sets give exact zero even when BVH float precision differs.
    if np.array_equal(current, reference):
        point = current[0][0]
        best, direction = (0, point, point), "both"
    else:
        forward = greatest_distance(current, reference, probe)
        reverse = greatest_distance(reference, current, probe)
        best, direction = (forward, "current_to_reference") if forward[0] >= reverse[0] else (reverse, "reference_to_current")
    distance, p, q = best
    return dict(status="compared", sample_max_mm=round(distance, 6), worst_direction=direction,
                worst_u_mm=round(p[0], 6), worst_v_mm=round(p[1], 6),
                nearest_u_mm=round(q[0], 6), nearest_v_mm=round(q[1], 6))


def fit_arc(segments, box):
    """Use one connected open contour in the registered window, discarding collinear split vertices."""
    from collections import defaultdict

    adjacent = defaultdict(set)
    u0, v0, u1, v1 = box
    for a, b in segments:
        if all(u0 <= u <= u1 and v0 <= v <= v1 for u, v in (a, b)):
            p, q = tuple(a), tuple(b)
            adjacent[p].add(q)
            adjacent[q].add(p)
    ends = [p for p, nb in adjacent.items() if len(nb) == 1]
    if len(ends) != 2 or any(len(nb) > 2 for nb in adjacent.values()):
        return {"fit": "window_needs_one_open_arc"}
    path, previous, point = [], None, ends[0]
    while point is not None:
        path.append(point)
        nxt = next((p for p in adjacent[point] if p != previous), None)
        previous, point = point, nxt
    if len(path) != len(adjacent):
        return {"fit": "multiple_contours"}
    pts = np.array(path)
    vectors = np.diff(pts, axis=0)
    directions = np.unwrap(np.arctan2(vectors[:, 1], vectors[:, 0]))
    turns = np.diff(directions)
    pts = pts[np.r_[True, np.abs(turns) > math.radians(0.25), True]]
    result = {"fit": "insufficient_arc", "vertices": len(pts)}
    if len(pts) < 5:
        return result
    origin = pts.mean(axis=0)
    xy = pts - origin
    system = np.column_stack((2 * xy, np.ones(len(xy))))
    center, _, rank, _ = np.linalg.lstsq(system, (xy * xy).sum(axis=1), rcond=None)
    if rank != 3:
        return result
    radii = np.linalg.norm(xy - center[:2], axis=1)
    radius = radii.mean()
    angles = np.unwrap(np.arctan2(xy[:, 1] - center[1], xy[:, 0] - center[0]))
    span = abs(math.degrees(angles[-1] - angles[0]))
    rms = float(np.sqrt(np.mean((radii - radius) ** 2)))
    result.update(rms_mm=round(rms, 6), span_deg=round(span, 3))
    delta = np.diff(angles)
    if 30 <= span <= 180.01 and (np.all(delta > 0) or np.all(delta < 0)) and 0 < radius and rms <= 0.01 * radius:
        result.update(fit="supported", R_mm=round(radius, 6))
    return result


def svg(path, cur, ref, metric):
    pts = np.asarray(list(cur) + list(ref), dtype=float).reshape(-1, 2)
    low, high = pts.min(axis=0), pts.max(axis=0)
    width, height = high - low
    pad = max(width, height, 0.01) * 0.06
    box = f"{low[0]-pad:g} {-high[1]-pad:g} {width+2*pad:g} {height+2*pad:g}"
    layers = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{box}"><g transform="scale(1,-1)" fill="none">']
    for segments, color, extra in ((cur, "#cf5620", ''), (ref, "#1274a9", 'stroke-dasharray="4 3"')):
        d = " ".join(f"M{u:.6f},{v:.6f}L{x:.6f},{y:.6f}" for (u, v), (x, y) in segments)
        layers.append(f'<path d="{d}" stroke="{color}" stroke-width="1.7" {extra} vector-effect="non-scaling-stroke"/>')
    if metric.get("sample_max_mm", 0) > 0:
        x, y = metric["worst_u_mm"], metric["worst_v_mm"]
        u, v = metric["nearest_u_mm"], metric["nearest_v_mm"]
        layers.append(f'<line x1="{x}" y1="{y}" x2="{u}" y2="{v}" stroke="#101010" stroke-width="3" vector-effect="non-scaling-stroke"/>')
    layers.append("</g></svg>")
    path.write_text("".join(layers), encoding="utf-8")
    return (low[0] - pad, -high[1] - pad, low[0] + width + pad, -low[1] + pad)


def write_assembly_views(out, layers, listing, step):
    listing.insert(3, '<p><a href="#assembly">整套装配逐站叠图</a></p>')
    listing.append('<h2 id="assembly">整套装配</h2>')
    for axis in AXES:
        keys = sorted((key for key in layers if key[0] == axis), key=lambda key: key[1])
        if not keys:
            continue
        links = []
        for _, index in keys:
            parts = layers[axis, index]
            bounds = np.array([box for _, _, box in parts])
            left, top = bounds[:, :2].min(axis=0)
            right, bottom = bounds[:, 2:].max(axis=0)
            path = f"svg/assembly-{axis}-{index}.svg"
            root = ET.Element("svg", xmlns="http://www.w3.org/2000/svg",
                              viewBox=f"{left:g} {top:g} {right-left:g} {bottom-top:g}")
            for name, file, _ in parts:
                group = ET.SubElement(root, "g")
                ET.SubElement(group, "title").text = name
                # Reuse the exact registered SVG paths. Strip their parsed namespace so the
                # assembly can declare a single default SVG namespace at the root.
                for layer in ET.parse(out / file).getroot():
                    for node in layer.iter():
                        node.tag = node.tag.rsplit("}", 1)[-1]
                    group.append(layer)
            ET.ElementTree(root).write(out / path, encoding="utf-8")
            links.append(f'<a href="{path}">{index * step:g}</a>')
        listing.append(f"<details><summary>{axis} · {len(links)} 层</summary><p>" + " · ".join(links) + "</p></details>")


def read_windows(args, parts):
    windows = json.loads(args.fits.read_text(encoding="utf-8-sig")) if args.fits else []
    for window in windows:
        part, axis, station, box = (window[k] for k in ("part", "axis", "station_mm", "box_uv_mm"))
        if (not window["feature"] or part not in parts or axis not in list(args.axes)
                or not math.isfinite(station) or abs(station / args.step_mm - round(station / args.step_mm)) > 1e-7
                or (args.range_mm and not args.range_mm[0] <= station <= args.range_mm[1])
                or len(box) != 4 or not all(map(math.isfinite, box)) or box[0] >= box[2] or box[1] >= box[3]):
            raise ValueError(f"Invalid part/axis/station/window: {window}")
    return windows


def write_audit(args, out):
    if args.scene is not None:
        bpy.context.window.scene = bpy.data.scenes[args.scene]
    scene = bpy.context.scene
    scene.frame_set(args.frame)
    deps = bpy.context.evaluated_depsgraph_get()
    datum = datum_transform(scene, args.datum, deps)
    world_to_datum = np.linalg.inv(np.asarray(datum, dtype=float))
    if not args.mm_per_unit and scene.unit_settings.system == "NONE":
        raise ValueError("A unitless scene needs an independently calibrated --mm-per-unit")
    scale = args.mm_per_unit or float(f"{scene.unit_settings.scale_length * 1000:.7g}")
    if not bpy.data.filepath:
        raise ValueError("Open a saved source .blend file")
    source = Path(bpy.data.filepath)
    selector = {"parts": sorted(args.parts)} if args.parts else {"collection": args.collection}
    contract = dict(format=1, pose=args.pose, frame=args.frame, datum=args.datum, axes=args.axes,
                    step_mm=args.step_mm, range_mm=args.range_mm, selector=selector)
    reference = {}
    if args.reference:
        reference = json.loads((args.reference / "manifest.json").read_text(encoding="utf-8"))
        if reference["contract"] != contract:
            raise ValueError(f"Reference and current settings differ: {reference['contract']} / {contract}")
    if args.parts:
        selected = {name for name in args.parts if name in scene.objects}
        parts = set(args.parts)
    else:
        collection = bpy.data.collections.get(args.collection)
        if not collection:
            raise ValueError(f"Missing collection: {args.collection}")
        selected = {obj.name for obj in collection.all_objects if obj.type == "MESH" and obj.name in scene.objects}
        parts = set(selected)
        if reference and reference.get("collection") == args.collection:
            parts.update(reference["parts"])
    if not parts:
        raise ValueError("No mesh parts selected")
    windows = read_windows(args, parts)
    (out / "profiles").mkdir()
    (out / "svg").mkdir()
    manifest = dict(contract=contract, blend=source.name, blend_sha256=file_hash(source),
                    blender=bpy.app.version_string, scene=scene.name, mm_per_unit=scale,
                    datum_world_BU=np.asarray(datum).tolist(), probe_mm=args.probe_mm, parts={},
                    present_parts=sorted(selected), collection=args.collection,
                    reference_sha256=reference.get("blend_sha256"))
    listing = ['<!doctype html><html lang="zh"><meta charset="utf-8"><title>逐站截面</title>',
               '<h1>逐站截面</h1><p>橙色实线为当前版，蓝色虚线为参考版，黑线标出已采样的最大轮廓距离。坐标与距离均为 mm。</p>',
               '<p><a href="sections.csv">逐站数据</a> · <a href="coverage.csv">逐件覆盖</a> · <a href="manifest.json">坐标与版本</a></p>']
    if windows:
        listing.append('<p><a href="radii.csv">局部等效圆角</a></p>')
    coverage = []
    assembly = {}
    with (out / "sections.csv").open("w", encoding="utf-8-sig", newline="") as records, \
            (out / "radii.csv").open("w", encoding="utf-8-sig", newline="") as radius_file:
        writer = csv.DictWriter(records, FIELDS)
        arc_writer = csv.DictWriter(radius_file, RADIUS_FIELDS)
        writer.writeheader()
        arc_writer.writeheader()
        for number, part in enumerate(sorted(parts)):
            obj = scene.objects.get(part) if part in selected else None
            ref_file = reference.get("parts", {}).get(part)
            reference_has_part = part in reference.get("present_parts", reference.get("parts", {}))
            if (obj and obj.type != "MESH") or (not obj and not reference_has_part and not args.allow_absent_parts):
                raise ValueError(f"Missing mesh or incorrect name: {part}")
            old = {}
            if ref_file:
                with gzip.open(args.reference / ref_file, "rt", encoding="utf-8") as stream:
                    old = json.load(stream)
            tris = triangles(obj, deps, world_to_datum, scale) if obj else []
            profile = {axis: cut_axis(tris, axis, args.step_mm, args.range_mm) for axis in args.axes}
            relpath = f"profiles/{number:04d}.json.gz"
            with gzip.open(out / relpath, "wt", encoding="utf-8") as stream:
                json.dump(profile, stream, separators=(",", ":"), allow_nan=False)
            manifest["parts"][part] = relpath
            listing.append(f"<h2>{html.escape(part)}</h2>")
            for axis in args.axes:
                prior = old.get(axis, {})
                current = profile[axis]
                links = []
                for key in sorted(current.keys() | prior.keys(), key=int):
                    cur, ref = current.get(key, []), prior.get(key, [])
                    station = int(key) * args.step_mm
                    result = differences(cur, ref, bool(reference), args.probe_mm)
                    link = ""
                    if cur or ref:
                        link = f"svg/{number:04d}-{axis}-{key}.svg"
                        bounds = svg(out / link, cur, ref, result)
                        if len(parts) > 1:
                            assembly.setdefault((axis, int(key)), []).append((part, link, bounds))
                        links.append(f'<a href="{link}">{station:g}</a>')
                    writer.writerow(dict(part=part, axis=axis, station_mm=station, current_segments=len(cur),
                                         reference_segments=len(ref) if reference else "", svg=link, **result))
                listing.append(f"<details><summary>{axis} · {len(links)} 层</summary><p>" + " · ".join(links) + "</p></details>")
            part_windows = [w for w in windows if w["part"] == part]
            supported = 0
            for w in part_windows:
                axis, key, box = w["axis"], str(round(w["station_mm"] / args.step_mm)), w["box_uv_mm"]
                row = {k: w[k] for k in ("part", "axis", "feature", "station_mm", "box_uv_mm")}
                for label, profiles in (("current", profile), ("reference", old)):
                    if label == "reference" and not reference:
                        continue
                    fit = fit_arc(profiles.get(axis, {}).get(key, []), box)
                    row.update({label + "_" + k: v for k, v in fit.items()})
                if row.get("current_fit") == row.get("reference_fit") == "supported":
                    row["delta_R_mm"] = round(row["current_R_mm"] - row["reference_R_mm"], 6)
                arc_writer.writerow(row)
                supported += row.get("current_fit") == "supported"
            count = sum(bool(segs) for stations in profile.values() for segs in stations.values())
            coverage.append((part, bool(obj), len(tris), count, len(part_windows), supported))
    with (out / "coverage.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        table = csv.writer(stream)
        table.writerow(("part", "present_in_scene", "triangles", "nonempty_stations", "arc_windows", "supported_arc_windows"))
        table.writerows(coverage)
    manifest["fit_windows"] = windows
    if assembly:
        write_assembly_views(out, assembly, listing, args.step_mm)
    (out / "index.html").write_text("\n".join(listing) + "</html>", encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    args = arguments()
    target = args.out.resolve()
    if target.exists():
        raise FileExistsError(f"Use a new output directory: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".section-audit-", dir=target.parent) as temp:
        stage = Path(temp) / "report"
        stage.mkdir()
        write_audit(args, stage)
        stage.rename(target)
    print(f"Section audit: {target}")


if __name__ == "__main__":
    main()
