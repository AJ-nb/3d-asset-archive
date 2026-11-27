"""One archived product and one color pipeline for the channel-specific photographs."""
from functools import lru_cache
from math import radians
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Euler, Vector

WORK = Path(__file__).resolve().parent
OUT = WORK.parent / 'delivery-product-v3'
PRODUCT = 'Product | Standard white DualSense'
sys.path.insert(0, str(WORK.parent / 'tools'))
from build_lineup import assembly_points


def new_scene(number, slug, title, size, alpha=False):
    scene = bpy.data.scenes.new(f'{number} {title}')
    bpy.context.window.scene = scene
    scene.use_fake_user = True
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = .05
    scene.frame_start = scene.frame_end = 1
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 160
    scene.cycles.adaptive_min_samples = 20
    scene.cycles.adaptive_threshold = .010
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 12
    scene.cycles.transmission_bounces = 10
    scene.cycles.transparent_max_bounces = 12
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.filepath = f'//masters/{number}-{slug}.png'
    scene.render.film_transparent = alpha
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA' if alpha else 'RGB'
    scene.render.image_settings.color_depth = '16'
    scene.render.image_settings.compression = 35
    scene.display_settings.display_device = 'sRGB'
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.view_settings.exposure = 0.
    scene.render.dither_intensity = 1.0
    return scene


@lru_cache(maxsize=1)
def points():
    return assembly_points(bpy.data.collections[PRODUCT])


def place(scene, pitch=-90, yaw=0, offset=(0,0,0)):
    carrier = bpy.data.objects.new(scene.name[:2] + ' | Complete controller', None)
    scene.collection.objects.link(carrier)
    carrier.instance_type = 'COLLECTION'
    carrier.instance_collection = bpy.data.collections[PRODUCT]
    carrier.rotation_euler = Euler((radians(pitch),0,radians(yaw)), 'XYZ')
    xyz = points() @ np.array(carrier.rotation_euler.to_matrix()).T
    low, high = xyz.min(axis=0), xyz.max(axis=0)
    baseline = np.array([-.5*(low[0]+high[0]), -.5*(low[1]+high[1]), -low[2]])
    carrier.location = tuple(baseline + np.array(offset))
    return carrier


def aim(obj, point):
    obj.rotation_euler = (Vector(point)-obj.location).to_track_quat('-Z','Y').to_euler()


def camera(scene, location, target, lens=55, ortho=None):
    data = bpy.data.cameras.new(scene.name[:2] + ' | Optics')
    obj = bpy.data.objects.new(scene.name[:2] + ' | Camera', data)
    scene.collection.objects.link(obj)
    obj.location = location
    aim(obj,target)
    data.lens = lens
    data.clip_start = .008
    if ortho is not None:
        data.type = 'ORTHO'
        data.ortho_scale = ortho
    scene.camera = obj
    marker = scene.timeline_markers.new(scene.name,frame=1)
    marker.camera = obj
    return obj


def area(scene, name, location, target, energy, width, height, color=(1,1,1)):
    name = scene.name[:2] + ' | ' + name
    data = bpy.data.lights.new(name, 'AREA')
    data.shape = 'RECTANGLE'
    data.size, data.size_y = width, height
    data.energy, data.color = energy, color
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = location
    aim(obj,target)
    return obj


def world(scene,color=(.8,.86,1),strength=.18):
    w = bpy.data.worlds.new(scene.name + ' | Ambient')
    if w.node_tree is None:
        w.use_nodes = True
    node = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
    node.inputs[0].default_value = (*color,1)
    node.inputs[1].default_value = strength
    scene.world = w
    return w


def save(path):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True,exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(path),compress=True,relative_remap=False)


def gpu():
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.refresh_devices()
    for device in prefs.devices:
        device.use = device.type == 'OPTIX'
    if not any(device.use for device in prefs.devices):
        raise RuntimeError('No OptiX device')


def render(scene, directory, preview=False):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True,exist_ok=True)
    gpu()
    bpy.context.window.scene = scene
    scene.frame_set(1)
    r, cy = scene.render, scene.cycles
    original = r.filepath, r.resolution_percentage, cy.samples, cy.adaptive_min_samples, cy.adaptive_threshold, cy.device
    stem = Path(r.filepath.replace(chr(92), '/').rsplit('/', 1)[-1]).stem
    filename = directory / (stem + ('-proof' if preview else '') + '.png')
    try:
        r.filepath, cy.device = str(filename),'GPU'
        if preview:
            r.resolution_percentage = 38
            cy.samples, cy.adaptive_min_samples, cy.adaptive_threshold = 40,8,.026
        assert bpy.ops.render.render(scene=scene.name,write_still=True) == {'FINISHED'}
    finally:
        r.filepath, r.resolution_percentage, cy.samples, cy.adaptive_min_samples, cy.adaptive_threshold, cy.device = original
    return filename
