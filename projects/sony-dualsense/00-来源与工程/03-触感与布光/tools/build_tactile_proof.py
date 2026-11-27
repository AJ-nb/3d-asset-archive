"""Build a matched DualSense look-development comparison from the archived source."""

import argparse
from math import exp, hypot
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_studio import (
    PARTS, bind_camera, camera_rig, collection, set_area, setup_scene,
    shot_scene, studio_world,
)


CONTACT = (1.378344, .234027, 0)


def contact_height(x, y):
    """Height of a damped outward response in the test surface, in scene units."""
    dx, dy = x - CONTACT[0], y - CONTACT[1]
    forward = .36 * dx - .933 * dy
    if forward <= 0:
        return 0
    across = .933 * dx + .36 * dy
    r = hypot(forward, 1.12 * across)
    if r > 1.05:
        return 0
    mask = (forward / r) ** 2 * min(1, max(0, (1.05 - r) / .15)) ** 2
    peaks = (
        (.30, .046, .069),
        (.54, .059, .035),
        (.79, .066, .015),
    )
    return mask * sum(height * exp(-((r - crest) / width) ** 2)
                      for crest, width, height in peaks)


def add_surface(scene, material, response):
    title = "Stage | Responsive graphite" if response else "Stage | Graphite sweep"
    assets = collection(scene, title)
    # Densify just the affected part of the floor. Outer coordinates form the backing sweep.
    xs = [-45, -.3] + [i * .013 for i in range(-22, 207)] + [3, 45]
    ys = [(y, 0) for y in [-45, -1.3] + [i * .013 for i in range(-99, 100)] + [1.4, 9]]
    ys += [(10, .1), (11, .45), (12, 1.05), (13, 1.9), (14, 3.25), (15, 5.2), (16, 22)]
    vertices = [(x, y, z + (contact_height(x, y) if response else 0))
                for y, z in ys for x in xs]
    nx = len(xs)
    faces = [(i, i + 1, i + nx + 1, i + nx)
             for row in range(len(ys) - 1) for i in range(row * nx, (row + 1) * nx - 1)]
    mesh = bpy.data.meshes.new(title)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh.materials.append(material)
    for face in mesh.polygons:
        face.use_smooth = True
    obj = bpy.data.objects.new(title, mesh)
    assets.objects.link(obj)
    return obj


def setup_pair(source):
    product = bpy.data.collections[PARTS]
    size = (3072, 3840)
    clean = shot_scene(source, "01 Study | Shaped light", product, "01-shaped-light", size)
    clean.compositing_node_group = None
    clean.world = studio_world(source)
    background = next(node for node in clean.world.node_tree.nodes if node.type == "BACKGROUND")
    background.inputs["Color"].default_value = (.43, .45, .49, 1)
    background.inputs["Strength"].default_value = .22

    material = bpy.data.materials.new("Stage | Fine graphite satin")
    tree = material.node_tree
    shader = next(node for node in tree.nodes if node.type == "BSDF_PRINCIPLED")
    shader.inputs["Base Color"].default_value = (.027, .032, .042, 1)
    shader.inputs["Roughness"].default_value = .41
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.label = "Fine matte floor grain"
    coordinates = tree.nodes.new("ShaderNodeTexCoord")
    bump = tree.nodes.new("ShaderNodeBump")
    noise.inputs["Scale"].default_value = 110
    noise.inputs["Detail"].default_value = 2
    bump.inputs["Strength"].default_value = .22
    bump.inputs["Distance"].default_value = .004
    tree.links.new(coordinates.outputs["Object"], noise.inputs["Vector"])
    tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    tree.links.new(bump.outputs["Normal"], shader.inputs["Normal"])

    camera, framing = camera_rig(
        clean, "Study | 82mm front quarter", (.21, -.10, .97), 22, 21, 10.95, 82
    )
    lights = collection(clean, "Studio | Shared reflection and grazing light")
    for row in (
        ("Key | overhead diffusion", (-3.8, -2.25, 5.25), (-.35, -.25, 1.05),
         425, 3.25, 2.35, (1, .963, .923)),
        ("Fill | low front bounce", (.2, -4.1, 2.45), (0, -.3, .98),
         62, 2.9, 1.9, (.95, .98, 1)),
        ("Strip | right polycarbonate edge", (3.85, -.6, 3.5), (1, -.35, 1.49),
         143, .40, 2.6, (1, .955, .906)),
        ("Rim | elevated cold strip", (1.8, 2.8, 3.14), (.2, 0, 1.24),
         248, .78, 3.5, (.76, .88, 1)),
        ("Rim | left outline", (-3.8, 2.5, 2.05), (-1.1, 0, 1.08),
         145, .65, 2.75, (.9, .95, 1)),
        ("Stage | cool pool", (-1.9, 3.3, 2.9), (-.8, 3.2, 0),
         109, 2.5, .8, (.55, .71, .90)),
        ("Stage | warm grazing strip", (4.3, -.28, .65), (1.5, -.2, .07),
         112, .78, .26, (1, .91, .76)),
    ):
        set_area(lights, *row)

    tactile = shot_scene(source, "02 Study | Tactile contact", product, "02-tactile-contact", size)
    tactile.compositing_node_group = None
    tactile.world = clean.world
    for assets in (lights, framing):
        tactile.collection.children.link(assets)
    add_surface(clean, material, response=False)
    add_surface(tactile, material, response=True)
    bind_camera(tactile, camera)
    for scene in (clean, tactile):
        setup_scene(scene, 256)
        scene.view_settings.exposure = .1
        scene["Status"] = "Look-development comparison"
        scene["Variant"] = "Matched camera, product geometry, stage material and lighting."
    return clean, tactile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--baseline-only", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    if args.output.exists():
        raise FileExistsError(args.output)

    source = bpy.data.scenes["DualSense White"]
    clean, tactile = setup_pair(source)
    if args.baseline_only:
        bpy.data.scenes.remove(tactile)
        active = clean
    else:
        from tactile_field import build_tactile_field

        field = build_tactile_field(tactile, origin=CONTACT, count=470, max_lift=.085)
        grains = next(iter(field.objects))
        for vertex in grains.data.vertices:
            x, y, z = vertex.co
            vertex.co.z = z + contact_height(x, y)
        grains.data.update()
        active = tactile
    bpy.context.window.scene = active
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.region_3d.view_perspective = "CAMERA"
                area.spaces.active.region_3d.view_camera_zoom = 0

    guide = bpy.data.texts.new("00 Studio Notes | Tactile Contact")
    guide.write(
        "DUALSENSE / TACTILE CONTACT\n\n"
        "01 Shaped light: matched studio baseline.\n"
        "02 Tactile contact: same set with a sculpted surface response and lifted grains.\n\n"
        "The tactile field depicts a design concept. It is not a hardware simulation.\n"
        "The original geometry is shared. Cycle through the scenes to compare.\n"
        "The numbers identify stills, and the scene paths reserve the native 4:5 renditions.\n"
    )
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()), relative_remap=False)


if __name__ == "__main__":
    main()
