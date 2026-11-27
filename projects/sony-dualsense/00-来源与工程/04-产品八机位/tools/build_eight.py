"""Build eight editable DualSense 4:5 stills from the archived original project."""

import argparse
from math import radians
from pathlib import Path
import sys

import bpy
from mathutils import Euler, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_studio import (
    PARTS, camera_rig, collection, floor_stage, set_area, setup_scene, shot_scene, studio_world,
)


SIZE = (3072, 3840)


def studio(source, title, slug, floor_color, floor_roughness, world_color, world_power):
    scene = shot_scene(source, title, bpy.data.collections[PARTS], slug, SIZE)
    scene.compositing_node_group = None
    scene.world = studio_world(source)
    scene.world.name = f"{slug} | Ambient bounce"
    world = next(node for node in scene.world.node_tree.nodes if node.type == "BACKGROUND")
    world.inputs["Color"].default_value = (*world_color, 1)
    world.inputs["Strength"].default_value = world_power
    floor_stage(source, scene, f"{slug} | Studio cyclorama", floor_color, floor_roughness)
    return scene


def add_lights(scene, lights):
    rig = collection(scene, f"{scene.name[:2]} | Photography lights")
    for specs in lights:
        set_area(rig, *specs)


def front(source):
    scene = studio(source, "01 Front | Ceramic studio", "01-front-studio",
                   (.30, .33, .36), .52, (.65, .68, .74), .24)
    camera_rig(scene, "Front | 84 mm", (-.015, -.03, 1.06), -15, 12, 10.40, 84)
    add_lights(scene, (
        ("Key | white overhead silk", (-4.4, -1.1, 5.6), (-.4, -.1, 1.0),
         425, 3.6, 2.4, (1, .98, .95)),
        ("Fill | near-axis bounce", (0, -4.5, 2.75), (0, -.3, 1),
         76, 3.0, 2.5, (.95, .98, 1)),
        ("Edge | clear control seam", (3.25, -.48, 3.45), (1, -.22, 1.22),
         141, .54, 2.55, (.96, .98, 1)),
        ("Rim | soft return", (-2.7, 2.36, 3.62), (-.55, .18, 1),
         180, 1.2, 3.0, (.85, .94, 1)),
        ("Set | brighter horizon", (2.9, 4.8, 4.15), (0, 4.7, 0),
         314, 3.2, 2.2, (.89, .96, 1)),
    ))
    return scene


def airborne(source):
    scene = studio(source, "02 Airborne | Diagonal hover", "02-airborne-diagonal",
                   (.035, .052, .073), .35, (.53, .60, .71), .22)
    product = bpy.data.collections[PARTS]
    scene.collection.children.unlink(product)
    placement = collection(scene, "02 | Airborne transform")
    pivot = bpy.data.objects.new("Airborne controller | linked original assembly", None)
    pivot.instance_type = "COLLECTION"
    pivot.instance_collection = product
    pivot.rotation_euler = Euler((radians(-15), radians(-26), radians(-21)), "XYZ")
    pivot.location = Vector((0, .09, 1.99)) - pivot.rotation_euler.to_matrix() @ Vector((0, 0, 1.06))
    pivot.empty_display_size = .35
    placement.objects.link(pivot)
    camera_rig(scene, "Airborne | 76 mm", (.03, -.03, 1.59), 7, 11, 10.25, 76)
    add_lights(scene, (
        ("Key | cool overhead silk", (-4.8, -.2, 5.4), (-.35, -.2, 2.0),
         470, 3.1, 2.2, (.82, .92, 1)),
        ("Fill | clean control bounce", (1.3, -5.2, 3.15), (0, -.45, 1.75),
         87, 2.75, 1.6, (.93, .97, 1)),
        ("Kick | warm diagonal strip", (4.15, 1.32, 4.25), (.42, .0, 2.12),
         408, .72, 3.78, (1, .80, .62)),
        ("Rim | back seam", (-3.45, 2.9, 3.8), (-.29, .1, 1.92),
         242, .95, 4.1, (.55, .73, 1)),
        ("Set | foreground oval", (1.45, -1.6, 3.0), (.38, .17, 0),
         124, 1.5, .82, (.79, .88, 1)),
        ("Set | muted horizon", (-1.8, 4.3, 3.2), (.65, 5.2, 0),
         173, 3.5, 1.56, (.42, .65, .96)),
    ))
    return scene


def profile(source):
    scene = studio(source, "08 Profile | Raking light", "08-low-profile",
                   (.074, .052, .043), .43, (.61, .55, .51), .21)
    camera_rig(scene, "Profile | 87 mm", (.24, -.04, 1.08), 69, 6.5, 8.7, 87)
    add_lights(scene, (
        ("Key | tall ivory silk", (4.45, -2.8, 4.74), (.86, .09, 1.0),
         396, 2.0, 3.85, (1, .92, .79)),
        ("Fill | front symbols", (.1, -4.1, 2.1), (.65, -.37, 1.15),
         108, 2.25, 2.1, (.83, .92, 1)),
        ("Rim | rear grip rake", (2.38, 2.85, 1.89), (1.25, .24, .74),
         211, .41, 2.15, (1, .86, .72)),
        ("Rim | opposite shoulder", (-3.5, 2.0, 3.95), (.3, .06, 1.6),
         173, .82, 2.3, (.76, .89, 1)),
        ("Set | warm graphite pool", (-2.1, 3.32, 3.12), (-1.91, 1.55, .0),
         108, 3.0, 1.18, (1, .77, .60)),
    ))
    return scene


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--local-only", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    if args.output.exists():
        raise FileExistsError(args.output)

    source = bpy.data.scenes["DualSense White"]
    scenes = [front(source), airborne(source), profile(source)]
    if not args.local_only:
        from eight_clear import build_clear
        from eight_macros import build_eight_macros
        from eight_rear_top import build_rear_top

        scenes.extend([build_clear(source), *build_rear_top(source), *build_eight_macros(source)])
    scenes.sort(key=lambda scene: scene.name)
    for shot in scenes:
        setup_scene(shot, 256)
        shot.frame_start = shot.frame_end = 1
        shot.frame_set(1)
        shot.render.resolution_x, shot.render.resolution_y = SIZE
        shot.render.resolution_percentage = 100
        shot.render.image_settings.file_format = "PNG"
        shot.render.image_settings.color_mode = "RGB"
        shot.render.image_settings.color_depth = "16"
        shot.render.image_settings.compression = 40
        shot["Output"] = "3072 x 3840, Cycles, 16-bit RGB PNG"

    notes = bpy.data.texts.new("00 START HERE | Eight angles")
    notes.write(
        "SONY DUALSENSE / EIGHT ANGLES\n\n"
        "Choose a numbered scene from the scene menu, and frame 1 for its intended still.\n"
        + "\n".join(scene.name for scene in scenes)
        + "\n\nThe airborne assembly references original mesh data via a collection instance. "
        "The translucent material is a concept. The source model has no electronic internals.\n"
        "The number in each output filename matches its scene. Cycles is set to CPU for portability.\n"
    )
    bpy.context.window.scene = scenes[0]
    for screen in bpy.data.screens:
        for viewport in (area for area in screen.areas if area.type == "VIEW_3D"):
            viewport.spaces.active.region_3d.view_perspective = "CAMERA"
            viewport.spaces.active.region_3d.view_camera_zoom = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()), relative_remap=False)


if __name__ == "__main__":
    main()
