from pathlib import Path
import sys

import bpy

root = Path.cwd()
arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
preview = 'preview' in arguments
selected = [arg for arg in arguments if arg != 'preview']
folder = root / ('_work/qa' if preview else '4k/renders')
folder.mkdir(exist_ok=True)
preferences = bpy.context.preferences.addons['cycles'].preferences
try:
    preferences.compute_device_type = 'OPTIX'
    preferences.refresh_devices()
    gpu = [dev for dev in preferences.devices if dev.type == 'OPTIX']
    for dev in preferences.devices:
        dev.use = dev in gpu
except RuntimeError:
    gpu = []
print('DEVICE', [dev.name for dev in gpu], flush=True)

for scene_name, prefix, frames in (
    ('DualSense White', 'dualsense-white', (10, 20, 30, 40, 60)),
    ('White Clay', 'white-clay', (10, 20, 50)),
):
    scene = bpy.data.scenes[scene_name]
    bpy.context.window.scene = scene
    scene.cycles.device = 'GPU' if gpu else 'CPU'
    if preview:
        scene.render.resolution_percentage = 27
        scene.render.image_settings.color_depth = '8'
        scene.cycles.samples = 38
        scene.cycles.adaptive_threshold = .045
    for frame in frames:
        scene.frame_set(frame)
        scene.camera = next(marker.camera for marker in scene.timeline_markers
                            if marker.frame == frame)
        shot = scene.camera.name.split(' | ')[0]
        name = prefix + '-' + shot
        if selected and name not in selected:
            continue
        scene.render.filepath = str(folder / (name + '.png'))
        print('RENDER', name, scene.render.resolution_percentage, flush=True)
        bpy.ops.render.render(write_still=True)
