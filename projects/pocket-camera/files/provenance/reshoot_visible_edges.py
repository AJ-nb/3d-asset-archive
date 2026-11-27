"""Project evaluated polygon edges and retain only segments visible from the V7 camera."""
import json
import math
from pathlib import Path
import sys
import time

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reshoot_v7 import product_objects, select_plate, temp

start = time.monotonic()
scene = select_plate()
graph = bpy.context.evaluated_depsgraph_get()
cam = scene.camera
width, height = scene.render.resolution_x, scene.render.resolution_y
camera_mm = cam.matrix_world.translation * 1000.
matrix = np.array(cam.calc_matrix_camera(graph, x=width, y=height) @ cam.matrix_world.inverted())
world = []
faces = []
groups = []
for original in product_objects():
    ob = original.evaluated_get(graph)
    mesh = ob.to_mesh()
    if not mesh or not mesh.vertices:
        ob.to_mesh_clear()
        continue
    points = [ob.matrix_world @ v.co for v in mesh.vertices]
    arr = np.array(points, dtype=np.float64)
    clip = arr @ matrix[:, :3].T + matrix[:, 3]
    screen = clip[:, :2] / clip[:, 3:4]
    screen = np.column_stack(((screen[:, 0] + 1) * (width / 2), (1 - screen[:, 1]) * (height / 2)))
    mesh.calc_loop_triangles()
    offset = len(world)
    tris = [tuple(offset + i for i in tri.vertices) for tri in mesh.loop_triangles]
    faces.extend(tris)
    vertex_mm = [p * 1000. for p in points]
    world.extend(vertex_mm)
    edges = [(e.vertices[0], e.vertices[1]) for e in mesh.edges]
    normal = [None] * len(edges)
    hard = np.zeros(len(edges), dtype=np.uint8)
    for face in mesh.polygons:
        n = face.normal
        for loop in face.loop_indices:
            edge_index = mesh.loops[loop].edge_index
            first = normal[edge_index]
            if first is None:
                normal[edge_index] = n.copy()
            elif first.dot(n) < .94:
                hard[edge_index] = 1
    groups.append((original.name, vertex_mm, screen, clip[:, 3], edges, hard))
    ob.to_mesh_clear()

print("OCCLUSION INDEX", len(world), len(faces), "triangles", flush=True)
tree = BVHTree.FromPolygons(world, faces, all_triangles=True)
visible = [[], []]
tested = 0
samples = 0
group_counts = {}
for name, vertices, screen, w, edges, hard in groups:
    count = 0
    for i, (a, b) in enumerate(edges):
        pa, pb = screen[a], screen[b]
        dx, dy = pb - pa
        projected_length = math.hypot(dx, dy)
        if projected_length < .55 or w[a] <= 0 or w[b] <= 0:
            continue
        tested += 1
        steps = max(1, math.ceil(projected_length / 2.5))
        start_t = None
        edge = vertices[b] - vertices[a]
        # Parameter t is in 3D. Use perspective division for each segment end.
        def projected(t):
            ratio = t * w[b] / ((1. - t) * w[a] + t * w[b])
            return pa[0] + dx * ratio, pa[1] + dy * ratio
        for k in range(steps + 1):
            if k < steps:
                v = vertices[a] + edge * ((k + .5) / steps)
                direction = camera_mm - v
                distance = direction.length
                direction.normalize()
                # Two micrometers move the test ray off its originating mesh edge.
                hit = tree.ray_cast(v + direction * .002, direction, distance)[0] is None
                samples += 1
            else:
                hit = False
            if hit and start_t is None:
                start_t = k / steps
            elif not hit and start_t is not None:
                visible[hard[i]].append((*projected(start_t), *projected(k / steps)))
                count += 1
                start_t = None
    if count:
        group_counts[name] = count
print("VISIBLE", list(map(len,visible)), "ray tests", samples, flush=True)
np.savez_compressed(temp / "visible.npz", smooth=np.array(visible[0], dtype=np.float32),
                    sharp=np.array(visible[1], dtype=np.float32))
report = {"eligible_evaluated_edges": tested, "triangle_occluders": len(faces), "vertex_count": len(world),
          "ray_tests": samples, "ray_sample_projected_max_step_px": 2.5, "ray_bias_mm": .002,
          "visible_segment_count_by_object": group_counts, "visible_smooth_segments": len(visible[0]),
          "visible_sharp_segments": len(visible[1]), "sharp_threshold_face_normal_dot": .94,
          "elapsed_seconds": round(time.monotonic() - start, 2), "camera_world_to_clip": matrix.tolist()}
(temp / "visible-meta.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
