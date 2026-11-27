from pathlib import Path
import sys
import bpy
work=Path(__file__).resolve().parent
sys.path.insert(0,str(work))
from v3_common import OUT, PRODUCT, save
import studio, functions, cutout

stills = [*studio.build_all(), *functions.build_all(), cutout.build()]
assert len(stills) == 8 and len(bpy.data.collections[PRODUCT].objects) == 12
for i,scene in enumerate(stills,1):
    assert scene.name.startswith(f'{i:02d} ') and scene.camera
    assert scene.render.filepath.startswith(f'//masters/{i:02d}-')
    scene.cycles.device = 'CPU'
note = bpy.data.texts.new('How to use these stills')
note.write('DualSense | White standard edition\n\n'
           'Product source contains the shared assembly. Every numbered scene instances it.\n'
           '01 and 02 have separate desk and phone compositions. Scene 06 adds only the amber mute-light state.\n'
           'The notebook and cable in 07 are context props. Scene 08 carries a straight-alpha PNG output and five '
           'enabled pass groups. Its supplied OpenEXR contains the scene-linear Combined, depth, normal, diffuse '
           'color and direct glossy passes. All production images are single frame 1.\n\n' +
           '\n'.join(s.name for s in stills))
bpy.context.window.scene = stills[0]
for screen in bpy.data.screens:
    for a in screen.areas:
        if a.type == 'VIEW_3D':
            a.spaces.active.region_3d.view_perspective='CAMERA'
save(OUT/'DualSense-Product-Photography.blend')
