"""Render the two desk-support studies from the archived Pocket V7 Final scene."""

import hashlib
from pathlib import Path
import sys

import bpy
from mathutils import Vector


V7_SHA256 = "136a14ee3a5d632842276f49a599b920a55c24ea7e46b47e3f4f37b9a6471392"
MM = 0.001


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    mat.use_nodes = True
    surface = mat.node_tree.nodes.get("Principled BSDF")
    surface.inputs["Base Color"].default_value = (*color, 1.0)
    surface.inputs["Roughness"].default_value = 0.48
    return mat


def box(name, xyz_mm, size_mm, radius_mm, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=Vector(xyz_mm) * MM)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = Vector(size_mm) * MM
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bevel = obj.modifiers.new("Rounded edges", "BEVEL")
    bevel.width = radius_mm * MM
    bevel.segments = 4
    obj.modifiers.new("Planar face normals", "WEIGHTED_NORMAL")
    obj.data.materials.append(mat)
    return obj


def light(name, xyz, size, power):
    target = Vector((0, 0, 0.062))
    bpy.ops.object.light_add(type="AREA", location=xyz)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()
    obj.data.size = size
    obj.data.energy = power


def cradle(mat):
    # Two separate standing rails leave the middle and the rear open for a cable.
    for side in (-1, 1):
        box("Desk rail", (side * 19, 0, -13), (26, 52, 6), 2, mat)
        box("Cradle seat", (side * 11, 0, -5), (9, 25, 10), 1.2, mat)
        box("Locating wall", (side * 17, 1, 1), (4, 25, 19), 1.4, mat)
    box("Front bridge", (0, -17, -13), (14, 8, 4), 1, mat)


def folding_feet(mat, pins):
    # Each leaf folds upwards in a radial vertical plane about its own hinge.
    for side in (-1, 1):
        for end in (-1, 1):
            pivot = Vector((side * 16.4, 1 + end * 6, 16))
            toe = Vector((side * 26, 1 + end * 19, -14))
            travel = toe - pivot
            radial = Vector((travel.x, travel.y, 0)).normalized()
            axis = Vector((0, 0, 1)).cross(radial)
            leaf = box("Folding leg", (pivot + toe) / 2, (5.0, 3.3, travel.length), 1.2, mat)
            leaf.rotation_euler = travel.to_track_quat("Z", "Y").to_euler()
            box("Contact pad", toe, (6, 5, 4), 1, mat)
            box("Hinge boss", pivot, (5.5, 5.5, 6), 1.2, mat)
            bpy.ops.mesh.primitive_cylinder_add(
                vertices=32, radius=1.7 * MM, depth=6.5 * MM, location=pivot * MM
            )
            pin = bpy.context.object
            pin.name = "Hinge pin"
            pin.rotation_euler = axis.to_track_quat("Z", "Y").to_euler()
            pin.data.materials.append(pins)


def render(out):
    source = Path(bpy.data.filepath)
    if hashlib.sha256(source.read_bytes()).hexdigest() != V7_SHA256:
        raise ValueError("Open the archived DJI-Osmo-Pocket-4P-V7-Final.blend")
    out.mkdir(parents=True, exist_ok=False)
    original = bpy.context.scene
    original.frame_set(62)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    study = bpy.data.scenes.new("Desk support studies")
    body = material("Body clay", (0.52, 0.56, 0.59))
    detail = material("Display and controls clay", (0.19, 0.23, 0.26))
    stand = material("Proposed supports", (0.11, 0.30, 0.33))
    pin_mat = material("Pin caps", (0.30, 0.40, 0.40))
    for obj in original.objects:
        groups = {coll.name[:2] for coll in obj.users_collection}
        if obj.hide_render or obj.type not in {"MESH", "CURVE", "FONT"}:
            continue
        if not groups.intersection({"01", "02", "03", "04", "05"}):
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = bpy.data.meshes.new_from_object(evaluated, depsgraph=depsgraph)
        mesh.materials.clear()
        mesh.materials.append(detail if groups.intersection({"02", "03"}) else body)
        snapshot = bpy.data.objects.new(obj.name + " | frame 62", mesh)
        study.collection.objects.link(snapshot)
        snapshot.matrix_world = evaluated.matrix_world.copy()

    bpy.context.window.scene = study
    box("Desk", (0, 0, -18), (2000, 2000, 4), 0, material("Desk clay", (0.73, 0.76, 0.77)))
    bpy.ops.object.camera_add(location=(0.25, -0.46, 0.215))
    camera = bpy.context.object
    camera.rotation_euler = (Vector((0, 0, 0.067)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 0.207
    camera.data.clip_start = 0.001
    study.camera = camera
    light("Softbox", (-0.24, -0.26, 0.38), 0.26, 6)
    light("Fill", (0.28, 0.20, 0.32), 0.22, 4)
    study.world = bpy.data.worlds.new("Neutral ambient")
    study.world.color = (0.3, 0.3, 0.3)
    study.render.engine = "CYCLES"
    study.cycles.samples = 12
    study.cycles.use_denoising = True
    study.render.resolution_x, study.render.resolution_y = 520, 580
    study.render.resolution_percentage = 100
    study.render.image_settings.file_format = "PNG"
    for filename, create in (
        ("dji-desk-cradle.png", lambda: cradle(stand)),
        ("dji-desk-folding-feet.png", lambda: folding_feet(stand, pin_mat)),
    ):
        shared = set(study.objects)
        create()
        study.render.filepath = str(out / filename)
        bpy.ops.render.render(write_still=True, scene=study.name)
        for obj in set(study.objects) - shared:
            bpy.data.objects.remove(obj, do_unlink=True)


if __name__ == "__main__":
    render(Path(sys.argv[sys.argv.index("--") + 1]).resolve())
