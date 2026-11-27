"""Build a small editable hinge and a skinned tube to exercise the audit."""

import argparse
import math
import sys
from pathlib import Path

import bpy


SEGMENTS = 12


def ring(x, y, z, r, axis="Z"):
    points = []
    for i in range(SEGMENTS):
        angle = 2 * math.pi * i / SEGMENTS
        a, b = r * math.cos(angle), r * math.sin(angle)
        points.append((x + a, y + b, z) if axis == "Z" else (x + a, y, z - b))
    return points


def strip(first, second):
    faces = []
    for i in range(SEGMENTS):
        j = (i + 1) % SEGMENTS
        faces.append((first + i, first + j, second + j, second + i))
    return faces


def mesh(name, points, faces):
    data = bpy.data.meshes.new(name)
    data.from_pydata(points, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    return obj


def eye(name, bottom, top, offset):
    layers = [ring(0, 0, bottom, 1.05), ring(offset, 0, bottom, 4),
              ring(0, 0, top, 1.05), ring(offset, 0, top, 4)]
    faces = []
    for a, b in [(0, 1), (1, 3), (3, 2), (2, 0)]:
        faces.extend(strip(a * SEGMENTS, b * SEGMENTS))
    return mesh(name, sum(layers, []), faces)


def armature(fault):
    bpy.ops.object.select_all(action="DESELECT")
    data = bpy.data.armatures.new("FixtureSkeleton")
    obj = bpy.data.objects.new("FixtureRig", data)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    x = 1 if fault == "pivot" else 0
    swing = data.edit_bones.new("Swing")
    swing.head, swing.tail = (x, 0, 0), (x, 3, 0)
    root = data.edit_bones.new("SleeveRoot")
    root.head, root.tail = (14, 0, 0), (14, 6, 0)
    tip = data.edit_bones.new("SleeveTip")
    tip.head, tip.tail = (14, 6, 0), (14, 12, 0)
    tip.parent = root
    tip.use_connect = True
    bpy.ops.object.mode_set(mode="OBJECT")
    for name, amplitudes in [("Swing", [0, 45, -40, 0]), ("SleeveTip", [0, -30, 35, 0])]:
        bone = obj.pose.bones[name]
        bone.rotation_mode = "XYZ"
        for frame, degrees in zip([1, 6, 12, 18], amplitudes):
            bone.rotation_euler.z = math.radians(degrees)
            bone.keyframe_insert(data_path="rotation_euler", frame=frame)
    return obj


def bind(obj, arm):
    mod = obj.modifiers.new("Skin", "ARMATURE")
    mod.object = arm
    mod.use_vertex_groups = True


def sleeve(arm, fault):
    levels = list(range(0, 13, 2))
    points = sum([ring(14, y, 0, 1.0, "Y") for y in levels], [])
    faces = [tuple(reversed(range(SEGMENTS)))]
    for i in range(len(levels) - 1):
        faces.extend(strip(i * SEGMENTS, (i + 1) * SEGMENTS))
    faces.append(tuple(range(len(points) - SEGMENTS, len(points))))
    obj = mesh("Sleeve", points, faces)
    root = obj.vertex_groups.new(name="SleeveRoot")
    tip = obj.vertex_groups.new(name="SleeveTip")
    for i, y in enumerate(levels):
        ids = list(range(i * SEGMENTS, (i + 1) * SEGMENTS))
        w = min(1, max(0, (y - 4) / 4))
        if w < 1:
            root.add(ids, 1 - w, "REPLACE")
        if w > 0:
            tip.add(ids, w, "REPLACE")
    if fault == "weight":
        root.remove([0])
        obj.vertex_groups.new(name="Swing").add([0], 1, "REPLACE")
    bind(obj, arm)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fault", choices=["none", "pivot", "weight", "flex", "oversize_pin"],
                        default="none")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    if args.out.exists() or args.out.suffix.lower() != ".blend":
        raise ValueError("Use a new .blend output path")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 0.001
    scene.frame_end = 18
    eye("FixedEye", 0, 4, -2)
    moving = eye("SwingEye", 4.1, 8.1, 2)
    pin_radius = 1.2 if args.fault == "oversize_pin" else 1.0
    bpy.ops.mesh.primitive_cylinder_add(vertices=SEGMENTS, radius=pin_radius, depth=8.6,
                                       location=(0, 0, 4.05))
    bpy.context.object.name = "Pin"
    arm = armature(args.fault)
    group = moving.vertex_groups.new(name="Swing")
    group.add(list(range(len(moving.data.vertices))), 1.0, "REPLACE")
    if args.fault == "flex":
        group.remove([13])
        moving.vertex_groups.new(name="SleeveRoot").add([13], 1, "REPLACE")
    bind(moving, arm)
    sleeve(arm, args.fault)
    scene.frame_set(1)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.out.resolve()))


if __name__ == "__main__":
    main()
