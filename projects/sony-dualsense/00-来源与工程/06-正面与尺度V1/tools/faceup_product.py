"""Four landscape photographs of the source controller turned face up."""

from math import radians

import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

from build_lineup import assembly_points
from build_studio import (
    PARTS, camera_rig, collection, floor_stage, set_area, setup_scene, shot_scene, studio_world,
)


SIZE = (3840, 2560)


def placement(scene, product, points, yaw):
    group = collection(scene, scene.name[:2] + " | Product placement")
    carrier = bpy.data.objects.new(scene.name[:2] + " | Buttons up", None)
    group.objects.link(carrier)
    carrier.instance_type = "COLLECTION"
    carrier.instance_collection = product
    carrier.empty_display_size = .22
    carrier.rotation_euler = Euler((radians(-90), 0, radians(yaw)), "XYZ")
    # Find the floor and visual centre in the unspun face-up orientation.
    horizontal = np.asarray(Matrix.Rotation(radians(-90), 3, "X"))
    laid = points @ horizontal.T
    lower, upper = laid.min(axis=0), laid.max(axis=0)
    shift = -.5 * (upper + lower)
    shift[2] = -.0003 - lower[2]
    spin = Matrix.Rotation(radians(yaw), 3, "Z")
    carrier.location = spin @ Vector(shift)
    carrier["Source pitch in degrees"] = -90.0
    carrier["Yaw in degrees"] = yaw
    return spin


def stage(source, product, points, title, slug, yaw, ground, world, exposure):
    scene = shot_scene(source, title, product, slug, SIZE)
    scene.collection.children.unlink(product)
    scene.compositing_node_group = None
    scene.world = studio_world(source)
    scene.world.name = f"{slug} | Bounce"
    background = next(n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND")
    background.inputs["Color"].default_value = (*world[0], 1)
    background.inputs["Strength"].default_value = world[1]
    floor_stage(source, scene, title[:2] + " | Infinity sweep", ground, .55)
    spin = placement(scene, product, points, yaw)
    scene.view_settings.exposure = exposure
    setup_scene(scene, 112)
    scene.cycles.adaptive_threshold = .014
    scene.cycles.adaptive_min_samples = 20
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "16"
    scene.render.image_settings.compression = 35
    scene["Orientation"] = "Source -90 degrees about X, followed by a rotation about world Z."
    return scene, spin


def lighting(scene, specs):
    group = collection(scene, scene.name[:2] + " | Reflection cards and softboxes")
    for name, location, target, power, width, height, colour in specs:
        set_area(group, scene.name[:2] + " | " + name, location, target, power, width, height, colour)


def build(source):
    product = bpy.data.collections[PARTS]
    points = assembly_points(product)
    top, _ = stage(source, product, points, "01 Face up | Overhead portrait",
                   "01-face-up-overhead", 0, (.32, .29, .24), ((.66, .63, .58), .16), .04)
    cam, _ = camera_rig(top, "01 | Plan view 90 mm", (0, -.005, .65), 0, 88.5, 11.05, 90)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 4.42
    lighting(top, [
        ("North-west silk", (-3.7, 1.4, 5.4), (-.24, 0, .55), 545, 3.0, 2.45, (1,.925,.81)),
        ("Bronze shoulder rake", (-3.0, -1.32, 2.72), (-.9, 0, .85), 122, .46, 2.4, (1,.91,.77)),
        ("Near soft return", (3.15, -3.8, 3.9), (.5, -.15, .7), 170, 4.0, 2.0, (.87,.94,1)),
        ("Crown edge", (3.45, 1.56, 2.38), (1, .3, .94), 90, .35, 2.1, (.94,.97,1)),
    ])

    hero, _ = stage(source, product, points, "02 Face up | Blue hour",
                    "02-face-up-blue-hour", -27, (.012,.026,.046), ((.43,.55,.67),.14), .12)
    camera_rig(hero, "02 | Three-quarter elevation 77 mm", (.01,.035,.47), 9, 33, 10.35, 77)
    lighting(hero, [
        ("Broad left silk", (-3.8,-2.7,4.75), (-.4,-.3,.7), 500, 3.4, 2.45, (.91,.96,1)),
        ("Counter reflector", (3.5,-4.05,2.35), (.7,-.1,.66), 124, 2.5, 2.1, (1,.89,.77)),
        ("Cold folded edge", (3.85,1.5,3.85), (.5,.36,.95), 245, .52, 3.0, (.53,.77,1)),
        ("Rubber crown", (-2.8,2.65,2.2), (-.55,.3,.9), 108, .40, 2.8, (.78,.88,1)),
        ("Background falloff", (-1.6,3.3,2.0), (-.42,2.83,0), 142, 2.1, 1.1, (.35,.67,1)),
    ])

    caps, spin = stage(source, product, points, "03 Face up | Four action caps",
                       "03-face-up-action-caps", 16, (.10,.105,.105), ((.58,.61,.64),.17), .04)
    target = spin @ Vector((1.02,.42,1.07))
    cap_cam, _ = camera_rig(caps, "03 | Keycap glass 103 mm", target, 32, 51, 4.22, 103)
    cap_cam.data.dof.use_dof = True
    cap_cam.data.dof.focus_distance = 4.21
    cap_cam.data.dof.aperture_fstop = 11
    cap_cam.data.dof.aperture_blades = 9
    lighting(caps, [
        ("Window silk", (-3.4,-2.1,4.5), (.9,.52,1.0), 390, 2.5, 3.6, (.98,.98,1)),
        ("Cap rim strip", (3.2,-.6,2.65), (.9,.48,1.0), 98, .28, 2.3, (.77,.88,1)),
        ("Shoulder return", (1.5,3.65,2.15), (.65,.7,1.03), 135, 1.1, 2.2, (1,.86,.70)),
        ("Near inlay card", (0,-4.2,1.7), (.7,.4,.98), 56, 2.2, .53, (.92,.98,1)),
    ])

    sticks, spin = stage(source, product, points, "04 Face up | Stick and control bridge",
                         "04-face-up-control-bridge", -9, (.035,.03,.025), ((.52,.51,.49),.15), .08)
    target = spin @ Vector((-.085,-.035,1.02))
    stick_cam, _ = camera_rig(sticks, "04 | Joystick bridge 96 mm", target, -24, 21, 5.9, 96)
    stick_cam.data.dof.use_dof = True
    stick_cam.data.dof.focus_distance = 5.65
    stick_cam.data.dof.aperture_fstop = 8.5
    stick_cam.data.dof.aperture_blades = 9
    lighting(sticks, [
        ("Warm relief strip", (-3.3,-1.2,2.6), (-.5,.0,1.12), 216, .44, 1.9, (1,.85,.69)),
        ("Graphite sweep", (.2,-4.2,2.5), (0,-.1,.84), 110, 2.85, .65, (.84,.91,1)),
        ("Far silk", (2.4,2.8,3.4), (.42,.0,1.12), 290, 2.4, 1.56, (.79,.89,1)),
        ("Shell fill", (-2.9,2.0,4.4), (.16,.22,.99), 172, 3.7, 2.8, (1,.96,.89)),
    ])
    return top, hero, caps, sticks
