from pathlib import Path

import bpy
from mathutils import Matrix

project = Path(bpy.data.filepath)
assert project.name == 'DualSense-4K-Studio.blend'
assert len(bpy.data.scenes) == 2
white = bpy.data.scenes['DualSense White']
clay = bpy.data.scenes['White Clay']
main = list(bpy.data.collections['Controller | Original FBX geometry'].objects)
overrides = list(bpy.data.collections['Controller | Linked white clay'].objects)
assert len(main) == len(overrides) == 12
assert {ob.data for ob in main} == {ob.data for ob in overrides}
assert all(ob['FBX object'] for ob in main)
assert sum(len(ob.data.vertices) for ob in main) == 480763
assert sum(len(ob.data.polygons) for ob in main) == 452132
assert set(o.data.name for o in main) == set(o.data.name for o in overrides)
assert all(slot.link == 'OBJECT' and slot.material.name.startswith('Clay |')
           for o in overrides for slot in o.material_slots)
for scene in (white, clay):
    assert scene.render.engine == 'CYCLES'
    assert (scene.render.resolution_x, scene.render.resolution_y,
            scene.render.resolution_percentage) == (3840, 2160, 100)
    assert scene.render.image_settings.color_depth == '16'
    assert len(scene.timeline_markers) == 6
    bpy.context.window.scene = scene
    for marker in scene.timeline_markers:
        scene.frame_set(marker.frame)
        assert scene.camera == marker.camera
        for o in main if scene == white else overrides:
            assert o.matrix_world == Matrix.Identity(4)
            assert all(v > .10 for v in o.dimensions), (scene.name, marker.frame, o.name, o.dimensions)
            assert o.animation_data is None
assert bpy.data.images['grip-symbol-height.png'].packed_file is not None
assert bpy.data.texts.get('START HERE | DualSense studio') is not None
print('PASS: Blend reopens with 2 scenes, 12 linked original meshes, 6 cameras, packed map, and UHD defaults.')
