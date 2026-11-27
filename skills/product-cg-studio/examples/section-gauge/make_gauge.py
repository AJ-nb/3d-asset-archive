"""Build synthetic metrology fixtures. Run with Blender --background --factory-startup."""
import json
from pathlib import Path
import sys

import bpy


def main():
    output = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
    output.mkdir(parents=True, exist_ok=False)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 0.001  # 1 Blender unit = 1 mm
    bpy.ops.mesh.primitive_cube_add(size=2)
    block = bpy.context.object
    block.name = "Gauge"
    block.dimensions = (12, 10, 8)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bevel = block.modifiers.new("Edge radius", "BEVEL")
    bevel.width = 1
    bevel.segments = 12
    bevel.profile = 0.5
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "reference.blend"))
    block.location.x = 0.5
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "shifted.blend"))
    block.location.x = 0
    bevel.width = 2
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "draft.blend"))

    # Reopen the delivered draft and repair the offending feature on its modifier stack.
    bpy.ops.wm.open_mainfile(filepath=str(output / "draft.blend"))
    bpy.data.objects["Gauge"].modifiers["Edge radius"].width = 1
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "corrected.blend"))
    # Keep the window just outside the tangent points of both R1 and R2.
    fits = [{"feature": "upper-right fillet", "part": "Gauge", "axis": "Z",
             "station_mm": 0, "box_uv_mm": [3.99, 2.99, 6.01, 5.01]}]
    (output / "fits.json").write_text(json.dumps(fits, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
