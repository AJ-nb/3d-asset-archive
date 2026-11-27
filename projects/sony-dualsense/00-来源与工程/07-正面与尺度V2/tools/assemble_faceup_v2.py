"""Revise a copy of the delivered face-up studio and save its eight calibrated stills."""

import argparse
from pathlib import Path
import sys

import bpy

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

GROUPS = {"product": ("01", "02", "03", "04"), "material": ("06", "07"), "architecture": ("05", "08")}
PRODUCT_TITLES = {
    '01': ('Face up on pale marble', 'face-up-marble'),
    '02': ('Shoulder view on smoked walnut', 'shoulder-view-walnut'),
    '03': ('The four translucent action caps', 'transparent-action-caps'),
    '04': ('Rubber knurl and control bridge', 'rubber-knurl'),
}


def shots():
    return {s.name[:2]: s for s in bpy.data.scenes if s.name[:2].isdigit() and s.name[2:3] == " "}


def main():
    from importlib import import_module
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--groups", nargs="+", choices=list(GROUPS), default=list(GROUPS))
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    output = args.output.resolve()
    if output.exists() or set(shots()) != {f"{i:02}" for i in range(1, 9)}:
        raise RuntimeError("Start with all eight numbered views and a new output file")
    for name in args.groups:
        if any(shots()[key].get("New photography edition") for key in GROUPS[name]):
            raise RuntimeError(f"Already revised group {name}")
        bpy.context.window.scene = bpy.data.scenes["DualSense White"]
        bpy.context.scene.frame_set(1)
        import_module("v2_" + name).revise()
        for key in GROUPS[name]:
            scene = shots()[key]
            if name == 'product':
                title, slug = PRODUCT_TITLES[key]
                scene.name = f'{key} Studio | {title}'
                scene.render.filepath = f'//renders/{key}-{slug}.png'
                scene.camera.name = f'{key} Lens | {title}'
                next(m for m in scene.timeline_markers if m.camera == scene.camera and m.frame == 1).name = title
            scene["New photography edition"] = True
            scene.frame_start = scene.frame_end = 1
            scene.frame_set(1)
            render = scene.render
            fmt = render.image_settings
            if ((render.engine, render.resolution_x, render.resolution_y, render.resolution_percentage,
                 fmt.file_format, fmt.color_mode, fmt.color_depth) != ("CYCLES",3840,2560,100,"PNG","RGB","16")
                or not scene.camera or not any(m.frame==1 and m.camera==scene.camera for m in scene.timeline_markers)):
                raise ValueError(f"Invalid native still in {scene.name}")
            if not render.filepath.replace(chr(92),"/").startswith("//renders/" + key + "-"):
                raise ValueError(f"Nonportable path in {scene.name}: {render.filepath}")
            scene.cycles.device = "CPU"
            scene.cycles.samples = max(192, scene.cycles.samples)
            scene.cycles.adaptive_min_samples = max(24, scene.cycles.adaptive_min_samples)
            scene.cycles.adaptive_threshold = min(.010, scene.cycles.adaptive_threshold)
    current = shots()
    all_done = all(s.get("New photography edition") for s in current.values())
    if all_done:
        for doc in list(bpy.data.texts):
            if doc.name.startswith("00 | DualSense - face up and scale"):
                bpy.data.texts.remove(doc)
        note = bpy.data.texts.new("00 | DualSense - V2 photography")
        note.write("DUALSENSE / SECOND EDITION\n\n" + "\n".join(current[k].name for k in sorted(current))
                   + "\n\nSelect a numbered scene. Render frame 1. The original archive remains in DualSense White.\n"
                     "The eight relative render paths target 3840 x 2560, RGB16.\n"
                     "The hundredfold surface study follows the archived height map, object-space repeat and bump distance.\n"
                     "The architectural installations and the impression in clay are design visualizations.\n")
    bpy.context.window.scene = current["01"]
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.region_3d.view_perspective = "CAMERA"
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.file.pack_all()
    result = bpy.ops.wm.save_as_mainfile(filepath=str(output), relative_remap=False, compress=True)
    if result != {"FINISHED"}:
        raise RuntimeError(f"Failed saving {output}")
    print("Revised scenes:", [key for key,s in sorted(current.items()) if s.get("New photography edition")], flush=True)


if __name__ == "__main__":
    main()
