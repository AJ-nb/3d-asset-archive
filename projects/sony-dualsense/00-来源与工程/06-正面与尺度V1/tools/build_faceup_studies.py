"""Assemble the face-up and scale studies from the original studio or its six-scene checkpoint."""

import argparse
from pathlib import Path
import sys

import bpy

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))


def numbered_scenes():
    return sorted((scene for scene in bpy.data.scenes
                   if scene.name[:2].isdigit() and scene.name[2:3] == " "), key=lambda s: s.name)


def add_group(module, source):
    bpy.context.window.scene = source
    source.frame_set(1)
    bpy.context.view_layer.update()
    return module.build(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", action="store_true",
                        help="Build the six product and material studies while the two architectural scenes are in development.")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    dest = args.output.resolve()
    if dest.exists():
        raise FileExistsError(dest)
    source = bpy.data.scenes["DualSense White"]
    six = ["01", "02", "03", "04", "06", "07"]
    existing = [scene.name[:2] for scene in numbered_scenes()]
    if not existing:
        import faceup_product
        import faceup_material_worlds
        add_group(faceup_product, source)
        add_group(faceup_material_worlds, source)
    elif existing != six or args.checkpoint:
        raise ValueError(f"Unexpected numbered scenes in input: {existing}")
    if not args.checkpoint:
        import faceup_architecture
        add_group(faceup_architecture, source)

    scenes = numbered_scenes()
    expected = six if args.checkpoint else [f"{n:02d}" for n in range(1, 9)]
    if [scene.name[:2] for scene in scenes] != expected:
        raise ValueError(f"Scene numbers do not match {expected}")
    for scene in scenes:
        render = scene.render
        fmt = render.image_settings
        if (render.engine, render.resolution_x, render.resolution_y, render.resolution_percentage,
            fmt.file_format, fmt.color_mode, fmt.color_depth) != ("CYCLES", 3840, 2560, 100, "PNG", "RGB", "16"):
            raise ValueError(f"Unexpected output configuration for {scene.name}")
        if not render.filepath.replace(chr(92), "/").startswith("//renders/" + scene.name[:2] + "-"):
            raise ValueError(f"Unexpected output path {render.filepath}")
        scene.frame_start = scene.frame_end = 1
        scene.frame_set(1)
        if not scene.camera or not any(m.camera == scene.camera and m.frame == 1 for m in scene.timeline_markers):
            raise ValueError(f"Missing bound camera for {scene.name}")
        scene.cycles.device = "CPU"

    if not args.checkpoint:
        guide = bpy.data.texts.new("00 | DualSense - face up and scale")
        guide.write("DUALSENSE  /  FACE UP AND SCALE\n\n"
                    + "\n".join(s.name for s in scenes)
                    + "\n\nSelect a numbered scene and render its first frame. Cycles, 3840 x 2560, RGB 16-bit PNG.\n"
                    "01-04 and 07 use the original twelve-part assembly rotated -90 degrees around X.\n"
                    "06 turns the archived grip-symbol height map into geometry at 100 times its project scale. "
                    "The large ground contours and wheel impressions were authored separately.\n"
                    "07 fits the sealing-wax contact surface to the shell and grip geometry.\n"
                    "05 and 08 are fictional architectural studies. The original DualSense White scene is retained.\n")
    bpy.context.window.scene = scenes[0]
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.region_3d.view_perspective = "CAMERA"
                area.spaces.active.region_3d.view_camera_zoom = 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.file.pack_all()
    result = bpy.ops.wm.save_as_mainfile(filepath=str(dest), relative_remap=False, compress=True)
    if result != {"FINISHED"} or not dest.exists():
        raise RuntimeError(f"Blender failed to save {dest}")
    print(f"Saved {len(scenes)} numbered scenes to {dest}", flush=True)


if __name__ == "__main__":
    main()
