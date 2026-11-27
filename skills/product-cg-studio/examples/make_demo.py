"""Build an original tabletop dial for a self-contained batch rendering test."""

import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def material(name, color, metal=0.0, roughness=0.4):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Metallic"].default_value = metal
    shader.inputs["Roughness"].default_value = roughness
    return mat


def finish(name, mat, radius):
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    bevel = obj.modifiers.new("Edge highlights", "BEVEL")
    bevel.width = radius
    bevel.segments = 4
    obj.modifiers.new("Face normals", "WEIGHTED_NORMAL")
    return obj


def box(name, location, size, mat, radius):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    bpy.context.object.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(name, mat, radius)


def disc(name, location, radius, height, mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=radius, depth=height, location=location)
    return finish(name, mat, 0.025)


def aim(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()


def area(name, location, power, size, tint):
    bpy.ops.object.light_add(type="AREA", location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.energy = power
    obj.data.shape = "DISK"
    obj.data.size = size
    obj.data.color = tint
    aim(obj, (0, 0, 0.2))


def camera(name, location, point, scale):
    bpy.ops.object.camera_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.type = "ORTHO"
    obj.data.ortho_scale = scale
    aim(obj, point)
    return obj


def build(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "Studio"
    shell = material("Midnight satin", (0.035, 0.075, 0.09), 0.32)
    graphite = material("Graphite", (0.019, 0.021, 0.022))
    bronze = material("Brushed brass", (0.56, 0.31, 0.103), 0.8, 0.29)
    porcelain = material("Warm ivory", (0.87, 0.83, 0.68))
    surface = material("Warm grey", (0.31, 0.30, 0.29))
    box("Foot", (0, 0, 0.055), (2.84, 1.70, 0.11), graphite, 0.045)
    box("Enclosure", (0, 0, 0.24), (3.12, 1.96, 0.40), shell, 0.12)
    disc("Bearing ring", (-0.64, 0, 0.46), 0.59, 0.08, graphite)
    knob = disc("Dial", (-0.64, 0, 0.605), 0.53, 0.24, bronze)
    tick = box("Dial index", (0, 0, 0), (0.048, 0.20, 0.012), porcelain, 0.005)
    tick.parent = knob
    tick.location = (0, 0.35, 0.122)
    for frame, degrees in ((1, -70), (4, 65)):
        knob.rotation_euler.z = math.radians(degrees)
        knob.keyframe_insert(data_path="rotation_euler", frame=frame)
    for i, y in enumerate((-0.33, 0, 0.33)):
        box(f"Key {i + 1}", (0.72, y, 0.478), (0.75, 0.20, 0.078), porcelain, 0.037)
    bpy.ops.mesh.primitive_plane_add(size=200)
    bpy.context.object.name = "Table"
    bpy.context.object.data.materials.append(surface)
    area("Left softbox", (-3, -4, 6), 580, 4, (1.0, 0.89, 0.77))
    area("Right fill", (4, 1, 4), 380, 4, (0.74, 0.85, 1.0))
    area("Rear strip", (-1, 4, 3), 280, 2.4, (1.0, 0.92, 0.82))
    hero = camera("Hero", (3.2, -4.8, 4.0), (0, 0, 0.25), 4.6)
    camera("Detail", (-2, -3.9, 4.4), (-0.57, 0, 0.51), 2.6)
    scene.camera = hero
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 8
    scene.cycles.seed = 5
    scene.render.resolution_x = 384
    scene.render.resolution_y = 256
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.frame_end = 4
    scene.frame_set(1)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(path))


if __name__ == "__main__":
    target = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
    if target.exists() or target.suffix.lower() != ".blend":
        raise ValueError("Supply a new .blend file path after --")
    build(target)
