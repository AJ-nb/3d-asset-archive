"""Build two editorial DualSense photographs from the original mesh collection."""

from math import radians

import bpy
from mathutils import Quaternion

from build_studio import PARTS, camera_rig, collection, floor_stage, set_area, setup_scene, shot_scene


PORTRAIT_4K = (3072, 3840)


def _studio(source, name, slug, floor_color, bounce_color, exposure):
    product = bpy.data.collections[PARTS]
    scene = shot_scene(source, name, product, slug, size=PORTRAIT_4K)
    scene.compositing_node_group = None
    scene.view_settings.exposure = exposure

    scene.world = source.world.copy()
    scene.world.name = f"{name} | Neutral ambient fill"
    ambient = next(node for node in scene.world.node_tree.nodes if node.type == "BACKGROUND")
    ambient.inputs["Color"].default_value = (*bounce_color, 1)
    ambient.inputs["Strength"].default_value = .19
    floor_stage(source, scene, f"{name} | Seamless set", floor_color, .62)

    setup_scene(scene, 224)
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "16"
    return scene


def build_rear_top(source):
    """Return rear-quarter and top shoulder scenes with independent studio rigs."""
    rear = _studio(source, "04 Rear | Molded shell", "04-rear-molded-shell",
                   (.037, .025, .022), (.45, .41, .40), .05)
    rear_cam, _ = camera_rig(rear, "04 | Rear oblique 102 mm", (-.055, .10, 1.10),
                             146, 14, 10.58, 102)
    rear_cam.rotation_mode = "QUATERNION"
    rear_cam.rotation_quaternion = rear_cam.rotation_euler.to_quaternion() @ Quaternion(
        (0, 0, 1), radians(-10)
    )
    rear_rig = collection(rear, "04 | Silk, rake and edge lights")
    for spec in (
        ("04 | Warm rear key", (-2.60, 3.80, 4.30), (-.44, .27, 1.24),
         390, 3.4, 2.1, (1, .920, .845)),
        ("04 | Shoulder silkscreen reflection", (.40, 1.77, 4.40), (0, .20, 1.90),
         188, 2.65, .89, (1, .970, .914)),
        ("04 | RH grip grazing strip", (3.10, 1.07, .99), (1.25, .26, .79),
         107, .19, 1.50, (1, .860, .715)),
        ("04 | Cool contour strip", (3.59, -2.63, 2.54), (.67, .12, 1.19),
         210, .71, 3.1, (.756, .862, 1)),
        ("04 | Far grip contour", (-3.65, -1.77, 2.70), (-1.05, .28, 1.33),
         142, .70, 3.0, (.855, .911, 1)),
        ("04 | Amber set pool", (-2.41, -2.04, 2.00), (-1.25, -2.18, .01),
         164, 3.10, 1.92, (1, .719, .553)),
    ):
        set_area(rear_rig, *spec)

    top = _studio(source, "05 Top | Shoulder assembly", "05-top-shoulder-usbc",
                  (.034, .047, .069), (.47, .53, .61), .1)
    shoulder_cam, _ = camera_rig(top, "05 | Shoulder rail 85 mm", (.08, -.035, 1.88),
                                 145, 69, 6.8, 85.3924)
    view = shoulder_cam.rotation_euler.to_quaternion()
    shoulder_cam.rotation_mode = "QUATERNION"
    shoulder_cam.rotation_quaternion = view @ Quaternion((0, 0, 1), radians(-21))
    shoulder_cam.data.shift_x = .0360613
    shoulder_cam.data.shift_y = -.0736723
    top_rig = collection(top, "05 | Broad overhead and folded shoulder strips")
    for spec in (
        ("05 | Cool overhead silk", (0, -.16, 5.40), (0, .13, 1.70),
         325, 3.78, 2.72, (.895, .951, 1)),
        ("05 | Warm longitudinal card", (-2.77, 1.42, 3.43), (-.85, .19, 1.87),
         190, 1.22, 3.1, (1, .942, .866)),
        ("05 | Cool longitudinal card", (2.77, 1.42, 3.43), (.85, .19, 1.87),
         175, 1.22, 3.1, (.820, .914, 1)),
        ("05 | Fine port rim", (0, 2.51, 2.75), (0, .28, 1.92),
         72, 2.78, .22, (.917, .959, 1)),
        ("05 | Dark-side separation", (0, -2.76, 2.59), (0, -.10, 1.62),
         139, 3.41, .62, (.774, .889, 1)),
        ("05 | Blue-gray floor pool", (0, 2.98, 2.41), (0, 2.36, 0),
         92, 2.55, 1.52, (.665, .811, 1)),
    ):
        set_area(top_rig, *spec)

    return rear, top
