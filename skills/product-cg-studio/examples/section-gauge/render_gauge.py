"""Render the loaded gauge using the same camera, surface finish and lights for every revision."""

from pathlib import Path
import sys

import bpy
from mathutils import Vector


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def material(name, color, metal, roughness):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Metallic"].default_value = metal
    shader.inputs["Roughness"].default_value = roughness
    return mat


def softbox(name, position, target, width, height, power):
    bpy.ops.object.light_add(type="AREA", location=position)
    light = bpy.context.object
    light.name = name
    light.data.shape = "RECTANGLE"
    light.data.size, light.data.size_y = width, height
    light.data.energy = power
    aim(light, target)


def main():
    output = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    gauge = scene.objects["Gauge"]
    gauge.data.materials.clear()
    gauge.data.materials.append(material("Satin aluminium", (0.59, 0.62, 0.67), 0.78, 0.29))
    for face in gauge.data.polygons:
        face.use_smooth = True
    # Face-area weighting retains the broad planes while smoothing the cut gauge's bevel facets.
    normals = gauge.modifiers.new("Studio corner normals", "WEIGHTED_NORMAL")
    normals.keep_sharp = True
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, -4))
    bpy.context.object.data.materials.append(material("Slate", (0.036, 0.049, 0.068), 0.05, 0.49))
    world = bpy.data.worlds.new("Studio")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.24
    softbox("Long highlight", (0, 12, 15), (0, 1, 0), 19, 6, 3100)
    softbox("Edge separation", (8, -9, 10), (0, 0, 0), 8, 15, 2700)
    softbox("Fill", (-12, 2, 9), (0, 0, 0), 13, 12, 1750)
    bpy.ops.object.camera_add(location=(19, 24, 15))
    camera = bpy.context.object
    aim(camera, (0, 0, -0.25))
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 21.4
    scene.camera = camera
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 40
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 720, 520
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "AgX"
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(output)
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
