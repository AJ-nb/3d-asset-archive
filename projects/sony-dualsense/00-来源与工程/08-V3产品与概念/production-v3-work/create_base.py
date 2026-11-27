"""Extract the approved photo assembly without carrying earlier sets into V3."""
from pathlib import Path
import bpy

work = Path(__file__).resolve().parent
source = work.parent / "delivery-faceup-v2" / "DualSense-Photography-V2.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)
with bpy.data.libraries.load(str(source), link=False) as (src, dest):
    key = "Photography | original meshes, photo finishes"
    assert key in src.collections
    dest.collections = [key]
product = dest.collections[0]
assert len(product.objects) == 12
product.name = "Product | Standard white DualSense"
scene = bpy.context.scene
scene.name = "Product source"
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = .05
scene.collection.children.link(product)
bpy.context.view_layer.update()
for obj in product.objects:
    print(obj.name, obj.data.name, list(obj.location), len(obj.data.vertices), flush=True)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(work/'base.blend'), compress=True)
