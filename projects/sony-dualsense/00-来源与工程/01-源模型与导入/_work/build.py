from collections import Counter
from math import cos, pi, radians, sin
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

ROOT = Path.cwd()
DELIVERY = ROOT / '4k'
DELIVERY.mkdir(exist_ok=True)
RENDERS = DELIVERY / 'renders'
RENDERS.mkdir(exist_ok=True)
WORK = ROOT / '_work'
SCENE = bpy.context.scene
SCENE.name = 'DualSense White'
SCALE = 20.0


def collection(scene, name):
    group = bpy.data.collections.new(name)
    scene.collection.children.link(group)
    return group


def move_to(obj, collection):
    collection.objects.link(obj)
    for group in list(obj.users_collection):
        if group != collection:
            group.objects.unlink(obj)


parts = collection(SCENE, 'Controller | Original FBX geometry')
studio = collection(SCENE, 'Studio | Shared cameras, lights and stage')
lighting = bpy.data.collections.new('Light rig')
studio.children.link(lighting)
cameras = bpy.data.collections.new('Shot cameras')
studio.children.link(cameras)

mesh_inventory = {}
source_objects = [obj for obj in bpy.data.objects if obj.type == 'MESH'
                  and obj.name != 'Cube']
assert len(source_objects) == 12
source_matrices = {obj.name: obj.matrix_world.copy() for obj in source_objects}
source_height = min((source_matrices[obj.name] @ v.co).z
                    for obj in source_objects for v in obj.data.vertices)
normalize = Matrix.Scale(SCALE, 4) @ Matrix.Translation((0, .011, -source_height))
names = {
    'Arrow Bottom': 'D-pad | down',
    'Arrow Left': 'D-pad | left',
    'Arrow Right': 'D-pad | right',
    'Arrow Top': 'D-pad | up',
    'Bottom O': 'Face button | circle',
    'Bottom Pryramid': 'Face button | triangle',
    'Bottom Square': 'Face button | square',
    'Bottom X': 'Face button | cross',
    'Cover': 'Housing | shell, touchpad, controls and ports',
    'Left Big Button': 'Shoulder group | left',
    'Right Big Button': 'Shoulder group | right',
    'polySurface505.001': 'Analog sticks | rubber caps and shafts',
}
for obj in source_objects:
    original_name = obj.name
    counts = (len(obj.data.vertices), len(obj.data.polygons))
    roles = [m.name for m in obj.data.materials]
    obj.animation_data_clear()
    obj.parent = None
    obj.data.transform(normalize @ source_matrices[original_name])
    obj.matrix_world = Matrix.Identity(4)
    move_to(obj, parts)
    obj.name = names[original_name.removeprefix('PS5 Controller_')]
    obj.data.name = obj.name
    obj['FBX object'] = original_name
    obj['FBX material slots'] = ', '.join(roles)
    mesh_inventory[obj.name] = counts
    print('SOURCE', obj.name, counts, Counter(roles[p.material_index] for p in obj.data.polygons),
          flush=True)

for obj in list(bpy.data.objects):
    if obj not in source_objects:
        bpy.data.objects.remove(obj, do_unlink=True)
for group in list(SCENE.collection.children):
    if group not in (parts, studio) and not group.all_objects:
        bpy.data.collections.remove(group)


def srgb(hex_code):
    channels = [int(hex_code[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
                 for c in channels) + (1.0,)


def node(nodes, kind, label, xy):
    item = nodes.new(kind)
    item.label = label
    item.location = xy
    return item


def surface(name, color, roughness, *, coat=0, ior=1.47, metallic=0):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = srgb(color)
    material['sRGB · visual target'] = '#' + color
    shader = material.node_tree.nodes.get('Principled BSDF')
    shader.location = (335, 180)
    material.node_tree.nodes.get('Material Output').location = (670, 180)
    shader.inputs['Base Color'].default_value = material.diffuse_color
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Metallic'].default_value = metallic
    shader.inputs['IOR'].default_value = ior
    shader.inputs['Coat Weight'].default_value = coat
    shader.inputs['Coat Roughness'].default_value = .24 if coat else .32
    return material, shader


def grain(material, shader, scale, roughness, spread, relief, amount):
    nodes, links = material.node_tree.nodes, material.node_tree.links
    coords = node(nodes, 'ShaderNodeTexCoord', 'Mold coordinates', (-855, 130))
    pores = node(nodes, 'ShaderNodeTexNoise', 'Sub-millimetre grain', (-615, -45))
    pores.inputs['Scale'].default_value = scale
    pores.inputs['Detail'].default_value = 2.5
    links.new(coords.outputs['Object'], pores.inputs['Vector'])
    sheen = node(nodes, 'ShaderNodeTexNoise', 'Local gloss variance', (-615, 245))
    sheen.inputs['Scale'].default_value = 43
    sheen.inputs['Detail'].default_value = 2
    links.new(coords.outputs['Object'], sheen.inputs['Vector'])
    response = node(nodes, 'ShaderNodeMapRange', 'Measured-width roughness interval', (-350, 245))
    response.inputs['To Min'].default_value = roughness - spread / 2
    response.inputs['To Max'].default_value = roughness + spread / 2
    links.new(sheen.outputs['Fac'], response.inputs['Value'])
    links.new(response.outputs['Result'], shader.inputs['Roughness'])
    bump = node(nodes, 'ShaderNodeBump', 'Micron-scale molded surface relief', (-375, -135))
    bump.inputs['Strength'].default_value = amount
    bump.inputs['Distance'].default_value = relief
    links.new(pores.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], shader.inputs['Normal'])
    if shader.inputs['Coat Weight'].default_value > 0:
        links.new(bump.outputs['Normal'], shader.inputs['Coat Normal'])
    return coords, bump


def grip_pattern(material, shader, coords, micro):
    image_path = WORK / 'grip-symbol-height.png'
    if not image_path.exists():
        return
    texture = bpy.data.images.load(str(image_path))
    texture.colorspace_settings.name = 'Non-Color'
    texture.pack()
    nodes, links = material.node_tree.nodes, material.node_tree.links
    coord_scale = node(nodes, 'ShaderNodeVectorMath', 'Grip symbols at sub-millimetre pitch', (-1130, -495))
    coord_scale.operation = 'SCALE'
    coord_scale.inputs['Scale'].default_value = 6
    links.new(coords.outputs['Object'], coord_scale.inputs[0])
    transfer = node(nodes, 'ShaderNodeTexImage', 'Packed molding height tile', (-895, -490))
    transfer.image = texture
    transfer.projection = 'BOX'
    transfer.projection_blend = .12
    transfer.extension = 'REPEAT'
    links.new(coord_scale.outputs['Vector'], transfer.inputs['Vector'])
    axis = node(nodes, 'ShaderNodeSeparateXYZ', 'Controller grip mask', (-1125, -845))
    links.new(coords.outputs['Object'], axis.inputs['Vector'])
    lateral = node(nodes, 'ShaderNodeMath', 'Both handles', (-900, -845))
    lateral.operation = 'ABSOLUTE'
    links.new(axis.outputs['X'], lateral.inputs[0])
    ramps = []
    for index, (input_socket, label, lo, hi, invert) in enumerate((
        (lateral.outputs[0], 'Outside of center housing', .72, .97, False),
        (axis.outputs['Y'], 'Rear side only', -.11, .04, False),
        (axis.outputs['Z'], 'Below shoulders', 1.48, 1.79, True),
    )):
        ramp = node(nodes, 'ShaderNodeMapRange', label, (-660, -770 - index * 250))
        ramp.interpolation_type = 'SMOOTHSTEP'
        ramp.inputs['From Min'].default_value = lo
        ramp.inputs['From Max'].default_value = hi
        ramp.inputs['To Min'].default_value = float(invert)
        ramp.inputs['To Max'].default_value = float(not invert)
        links.new(input_socket, ramp.inputs['Value'])
        ramps.append(ramp.outputs['Result'])
    height = transfer.outputs['Color']
    for index, ramp in enumerate(ramps):
        multiply = node(nodes, 'ShaderNodeMath', 'Feather at housing boundary', (-410 + index * 175, -585))
        multiply.operation = 'MULTIPLY'
        links.new(height, multiply.inputs[0])
        links.new(ramp, multiply.inputs[1])
        height = multiply.outputs[0]
    relief = node(nodes, 'ShaderNodeBump', 'Raised grip marks, appearance layer', (85, -335))
    relief.inputs['Strength'].default_value = .55
    relief.inputs['Distance'].default_value = .00065
    links.new(height, relief.inputs['Height'])
    links.new(micro.outputs['Normal'], relief.inputs['Normal'])
    links.new(relief.outputs['Normal'], shader.inputs['Normal'])
    links.new(relief.outputs['Normal'], shader.inputs['Coat Normal'])


definitions = {
    'Matte White': ('Shell | frost-white satin polymer', 'DEE0E5', .385, .09, (268, .045, .00015, .38)),
    'Dark Cover': ('Inner housing | graphite molded polymer', '23262F', .425, .035, (302, .065, .00017, .40)),
    'Black': ('Black controls | well and grille detail', '191C23', .52, .01, (305, .04, .00014, .32)),
    'Gloss Black': ('Gloss black | logo and polished insets', '181C23', .215, .21, (475, .028, .00008, .23)),
    'Matte Black': ('Shoulders | low-satin graphite', '272A32', .43, .047, (275, .048, .00019, .37)),
    'Gloss White': ('Keycap core | pale white', 'DFE2EB', .26, .08, None),
    'Gray': ('Glyphs | neutral gray markings', '686F7B', .43, .055, None),
    'Glass': ('Keycap overmold | clear polycarbonate', 'F0F3FB', .13, .11, None),
    'Blue LED': ('Light pipe | ice-blue status accent', '4078DB', .23, .2, None),
    'Steel': ('Port hardware | dark brushed alloy', '727E8B', .31, 0, None),
    'Matte Gray Bump': ('Stick caps | textured soft rubber', '242730', .58, .015, (189, .105, .00049, .54)),
    'Matte Gray no Bump': ('Stick shafts | satin graphite', '1D2028', .38, .055, (295, .047, .00015, .38)),
}

role_materials = {}
for role, (name, color, roughness, coat, micro) in definitions.items():
    ior = 1.56 if role == 'Glass' else 1.47
    metal = .82 if role == 'Steel' else 0
    material, shader = surface(name, color, roughness, coat=coat, ior=ior, metallic=metal)
    material['FBX material'] = role
    role_materials[role] = material
    if micro:
        frequency, spread, height, amount = micro
        coords, bump = grain(material, shader, frequency, roughness, spread, height, amount)
        if role == 'Matte White':
            grip_pattern(material, shader, coords, bump)
    if role == 'Glass':
        shader.inputs['Transmission Weight'].default_value = .96
        shader.inputs['Coat Roughness'].default_value = .14
    if role == 'Blue LED':
        shader.inputs['Emission Color'].default_value = srgb('4B8DEE')
        shader.inputs['Emission Strength'].default_value = 1.1
    if role == 'Steel':
        shader.inputs['Anisotropic'].default_value = .3
for obj in source_objects:
    for index, original in enumerate(obj.data.materials):
        obj.data.materials[index] = role_materials[original.name]

clay_material, clay_surface = surface('Clay | matte neutral ceramic', 'CDD0D4', .62, ior=1.43)
clay_surface.inputs['Specular IOR Level'].default_value = .31
CLAY = SCENE.copy()
CLAY.name = 'White Clay'
CLAY.use_fake_user = True
CLAY.collection.children.unlink(parts)
clay_parts = collection(CLAY, 'Controller | Linked white clay')
for original in source_objects:
    duplicate = original.copy()
    duplicate.name = original.name + ' [Clay]'
    clay_parts.objects.link(duplicate)
    for slot in duplicate.material_slots:
        slot.link = 'OBJECT'
        slot.material = clay_material

for original in source_objects:
    assert mesh_inventory[original.name] == (len(original.data.vertices), len(original.data.polygons))


def cyclorama():
    segs = 128
    radius = 14.0
    sweep = 8.0
    silhouette = [(0.001, -.0003), (radius, -.0003)]
    silhouette.extend((radius + sweep * sin(i * pi / 24), sweep * (1 - cos(i * pi / 24)))
                      for i in range(1, 13))
    silhouette.append((radius + sweep, 22.0))
    vertices = [(r * cos(i * 2 * pi / segs), r * sin(i * 2 * pi / segs), h)
                for r, h in silhouette for i in range(segs)]
    faces = [tuple(range(segs))]
    for ring in range(len(silhouette) - 1):
        for a in range(segs):
            b = (a + 1) % segs
            p = ring * segs
            faces.append((p + a, p + a + segs, p + b + segs, p + b))
    mesh = bpy.data.meshes.new('Continuous floor and curved wall')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    stage = bpy.data.objects.new('Cyclorama | continuous slate floor', mesh)
    studio.objects.link(stage)
    finish, shader = surface('Stage | matte blue-gray paint', '485768', .73, ior=1.43)
    shader.inputs['Specular IOR Level'].default_value = .26
    mesh.materials.append(finish)
    for poly in mesh.polygons:
        poly.use_smooth = True


cyclorama()
world = bpy.data.worlds.new('Studio | neutral bounce')
world.use_nodes = True
world_shader = world.node_tree.nodes.get('Background')
world_shader.inputs['Color'].default_value = (.35, .40, .50, 1)
world_shader.inputs['Strength'].default_value = .32

LIGHTS = (
    ('Key | broad upper silk', (-3.65, -4.15, 5.4), (0, -.02, 1.2), 560, 4.5, 3.0, (1, .956, .905)),
    ('Fill | front bounce', (3.4, -4.5, 2.45), (0, 0, 1.24), 195, 3.5, 2.65, (.88, .94, 1)),
    ('Rim | cool vertical strip', (3.55, 2.5, 3.55), (.1, 0, 1.45), 430, 1.6, 4.9, (.65, .81, 1)),
    ('Back | broad silk', (-3.05, 3.55, 4.4), (0, .02, 1.16), 375, 3.9, 3.7, (.97, .985, 1)),
    ('Top | button edge sweep', (.35, -.7, 5.9), (.05, -.02, .95), 105, 2.8, 1.1, (1, .985, .96)),
)
for name, position, target, power, width, height, color in LIGHTS:
    data = bpy.data.lights.new(name, 'AREA')
    data.shape = 'RECTANGLE'
    data.energy = power
    data.size = width
    data.size_y = height
    data.color = color
    light = bpy.data.objects.new(name, data)
    lighting.objects.link(light)
    light.location = position
    light.rotation_euler = (Vector(target) - light.location).to_track_quat('-Z', 'Y').to_euler()

SHOTS = (
    ('01-hero', 'Front three-quarter', 25, 13, (.015, -.055, 1.10), 86, 13.0),
    ('02-front', 'Straight front', 0, 5.5, (0, -.03, 1.13), 86, 12.75),
    ('03-controls', 'Buttons, touchpad and analog stick', 18, 13, (.65, -.54, 1.40), 84, 5.85),
    ('04-rear', 'Rear three-quarter and grip', 156, 13.8, (-.025, .08, 1.10), 86, 13.56),
    ('05-shoulder', 'Side and shoulder profile', -70, 25, (-.065, -.035, .99), 82, 13.85),
    ('06-grip', 'Molded grip surface detail', 156, 16, (1.24, .28, .73), 88, 4.60),
)
shot_objects = {}
for slug, label, azimuth, elevation, target, lens, distance in SHOTS:
    a, e = radians(azimuth), radians(elevation)
    direction = Vector((sin(a) * cos(e), -cos(a) * cos(e), sin(e)))
    name = slug + ' | ' + label
    optic = bpy.data.cameras.new(name)
    optic.lens = lens
    optic.sensor_fit = 'HORIZONTAL'
    optic.sensor_width = 36
    optic.clip_start = .03
    optic.clip_end = 100
    optic.passepartout_alpha = .98
    camera = bpy.data.objects.new(name, optic)
    cameras.objects.link(camera)
    camera.location = Vector(target) + distance * direction
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera['UHD output'] = '3840 × 2160'
    camera['Focus target'] = target
    shot_objects[slug] = camera

for scene in (SCENE, CLAY):
    scene.world = world
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0 / SCALE
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 144
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = .018
    scene.cycles.adaptive_min_samples = 24
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 12
    scene.cycles.transmission_bounces = 8
    scene.cycles.glossy_bounces = 6
    scene.render.resolution_x = 3840
    scene.render.resolution_y = 2160
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '16'
    scene.render.image_settings.compression = 27
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.view_settings.exposure = .27
    scene.frame_start = 1
    scene.frame_end = 60
    for marker in list(scene.timeline_markers):
        scene.timeline_markers.remove(marker)
    for index, (slug, label, *_) in enumerate(SHOTS, 1):
        marker = scene.timeline_markers.new(label, frame=index * 10)
        marker.camera = shot_objects[slug]
    scene.frame_set(10)
    scene.camera = shot_objects['01-hero']
    out_name = 'dualsense-white' if scene == SCENE else 'white-clay'
    scene.render.filepath = '//renders/' + out_name + '-01-hero.png'
    scene['Official CMF reference'] = 'https://www.sony.com/en/SonyInfo/design/stories/PS5/'
    scene['Source mesh'] = 'PlayStation 5 Controller 3D Model High Poly.fbx (user ZIP)'

notes = bpy.data.texts.new('START HERE | DualSense studio')
notes.write('''DUALSENSE / PRODUCT VISUALIZATION

Scenes
  DualSense White - standard white / graphite CMF with blue light pipe.
  White Clay - linked source geometry with per-object matte overrides.

Shots
  10   Front three-quarter
  20   Straight front
  30   Buttons, touchpad and analog stick
  40   Rear three-quarter and grip
  50   Side and shoulder profile
  60   Molded grip surface detail
  Use the timeline markers to switch cameras. All cameras use 3840 by 2160.

Editing
  Controller collections contain the 12 supplied FBX meshes.
  Original vertex / face counts, topology and material assignments are retained.
  Original units map to one scene unit per 50 mm, only spatial placement changed.
  Render scenes freeze the imported model at its initial pose so no FBX
  animation drivers change the placement of parts when a camera is selected.
  Clay uses object material overrides. Shape edits on shared meshes affect both scenes.
  Studio collections are shared. Principled materials have named controls for finish.
  The shallow grip symbol pattern is an editable shading approximation. The tile
  is packed into this .blend so no external texture files are needed.

References
  https://www.playstation.com/en-us/accessories/dualsense-wireless-controller/
  https://www.sony.com/en/SonyInfo/design/stories/PS5/
  https://blog.playstation.com/2020/04/07/introducing-dualsense-the-new-wireless-game-controller-for-playstation-5/
''')

bpy.context.window.scene = SCENE
bpy.context.preferences.filepaths.save_version = 0
for view_layer in SCENE.view_layers:
    view_layer.objects.active = None
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.region_3d.view_perspective = 'CAMERA'
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(DELIVERY / 'DualSense-4K-Studio.blend'), compress=True)
