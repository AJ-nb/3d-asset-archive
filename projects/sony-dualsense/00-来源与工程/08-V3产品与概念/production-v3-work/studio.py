"""Four independent still-life sets sharing the same neutral white controller."""

from math import cos, radians, sin
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from v3_common import area, camera, new_scene, place, points, world


def paper(name, rgb, roughness, grain=.08):
    mat = bpy.data.materials.new(name)
    if mat.node_tree is None:
        mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bs = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
    bs.inputs['Base Color'].default_value = (*rgb, 1)
    bs.inputs['Roughness'].default_value = roughness
    bs.inputs['Specular IOR Level'].default_value = .30
    if grain:
        geom = nodes.new('ShaderNodeNewGeometry')
        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 110
        noise.inputs['Detail'].default_value = 2
        links.new(geom.outputs['Position'], noise.inputs[0])
        bump = nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = grain
        bump.inputs['Distance'].default_value = .003
        links.new(noise.outputs['Fac'], bump.inputs['Height'])
        links.new(bump.outputs[0], bs.inputs['Normal'])
    return mat


def floor(scene, material, height=0):
    mesh = bpy.data.meshes.new(scene.name[:2] + ' | Ground')
    mesh.from_pydata([(-100,-100,height), (100,-100,height), (100,100,height), (-100,100,height)], [], [(0,1,2,3)])
    obj = bpy.data.objects.new(mesh.name, mesh)
    scene.collection.objects.link(obj)
    mesh.materials.append(material)


def riser(scene, material, outline, depth, edge):
    """A machined octagonal exhibition plinth, with a separate planar deck and softened edges."""
    count = len(outline)
    vertices = [(x, y, level) for level in (-depth, -.0001) for x, y in outline]
    faces = [tuple(reversed(range(count))), tuple(range(count, count*2))]
    faces.extend((k, (k+1)%count, count+(k+1)%count, count+k) for k in range(count))
    mesh = bpy.data.meshes.new(scene.name[:2] + ' | Lacquered display block')
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(mesh.name, mesh)
    scene.collection.objects.link(obj)
    bevel = obj.modifiers.new('Radiused edge', 'BEVEL')
    bevel.width, bevel.segments = edge, 8
    normal = obj.modifiers.new('Planar reflections', 'WEIGHTED_NORMAL')
    normal.keep_sharp = True


def photo(scene, azimuth, elevation, distance, aim, lens):
    a, e = radians(azimuth), radians(elevation)
    direction = Vector((sin(a)*cos(e), -cos(a)*cos(e), sin(e)))
    return camera(scene, Vector(aim) + distance*direction, aim, lens)


def frame(scene, carrier, center, max_width, max_height):
    """Fit the actual mesh envelope and shift the lens on its sensor to leave deliberate copy space."""
    cam = scene.camera
    bpy.context.view_layer.update()
    transform = np.array(cam.matrix_world.inverted() @ carrier.matrix_world)
    view = points() @ transform[:3, :3].T + transform[:3, 3]
    def bounds():
        edges = np.array(cam.data.view_frame(scene=scene))
        xy = view[:, :2] if cam.data.type == 'ORTHO' else view[:, :2] * (edges[0,2]/view[:,2,None])
        uv = (xy-edges[:,:2].min(axis=0)) / np.ptp(edges[:,:2],axis=0)
        return np.array([uv.min(axis=0), uv.max(axis=0)])
    size = np.diff(bounds(),axis=0)[0]
    zoom = min(max_width / size[0], max_height / size[1])
    if cam.data.type == 'ORTHO':
        cam.data.ortho_scale /= zoom
    else:
        cam.data.lens *= zoom
    current = bounds().mean(axis=0)
    cam.data.shift_x = .01
    dx = (bounds().mean(axis=0)-current)/.01
    cam.data.shift_x, cam.data.shift_y = 0, .01
    dy = (bounds().mean(axis=0)-current)/.01
    shift = np.linalg.solve(np.column_stack([dx,dy]), np.array(center)-current)
    cam.data.shift_x, cam.data.shift_y = shift
    box = bounds()
    if np.any(box < .02) or np.any(box > .98):
        raise ValueError((scene.name, box))
    scene['Product bounds normalized xy bottom-left'] = box.flatten().tolist()
    print('FRAMING', scene.name, box.round(4).tolist(), flush=True)


def horizontal_hero():
    scene = new_scene('01','desktop-hero','Hero | Horizontal campaign',(3000,1500))
    subject = place(scene, pitch=-90, yaw=-22)
    world(scene,(.71,.81,.99),.115)
    floor(scene,paper('01 | Ink cyclorama',(.017,.021,.034),.76),-.43)
    riser(scene,paper('01 | Midnight display lacquer',(.034,.051,.073),.43,.045),
          [(-2.35,-.80),(-1.41,-1.80),(5.8,-1.80),(6.35,-1.25),(6.35,4.4),(5.90,4.85),(-2.35,4.85)],.43,.057)
    photo(scene,7,32,12,(0,0,.64),65)
    frame(scene,subject,(.704,.53),.492,.79)
    area(scene,'Daylight book light',(-3.65,1.55,4.65),(-.25,.05,.53),545,2.3,3.7,(1,.94,.88))
    area(scene,'Near silver bounce',(.20,-4.9,2.4),(.00,-.1,.62),99,4.0,1.9,(.84,.91,1))
    area(scene,'Fine white contour',(3.52,2.0,3.7),(.68,.35,.86),200,.38,3.4,(.90,.96,1))
    area(scene,'Action key return',(3.7,-1.93,2.25),(.85,.27,.92),49,.7,1.9,(.96,.98,1))
    return scene


def mobile_hero():
    scene = new_scene('02','mobile-hero','Hero | Vertical campaign',(1440,1800))
    subject = place(scene, pitch=-90, yaw=31)
    world(scene,(.80,.84,.93),.21)
    floor(scene,paper('02 | Chalk studio paper',(.49,.44,.37),.81),-.26)
    riser(scene,paper('02 | Pale gallery board',(.67,.61,.51),.70),
          [(-4.9,-3.9),(-1.55,-4.75),(4.8,-.03),(6.10,1.9),(5.20,8.30),(-6.5,9.2)],.26,.027)
    photo(scene,-13,55,13,(0,0,.67),72)
    frame(scene,subject,(.496,.382),.88,.59)
    area(scene,'Soft pale daylight',(-3.95,.53,5.35),(-.19,0,.59),635,2.08,3.95,(1,.945,.88))
    area(scene,'High white reflector',(3.05,2.8,4.4),(.24,.2,.62),161,1.40,3.25,(.93,.95,1))
    area(scene,'Shade-side fill',(1.75,-3.8,2.2),(.2,-.3,.62),67,3.1,2.25,(.85,.90,1))
    return scene


def proportion_view():
    scene = new_scene('03','front-elevation','Reference | Front elevation',(2100,1500))
    subject = place(scene,pitch=-90)
    world(scene,(.89,.92,1),.18)
    sweep = paper('03 | Neutral backlit surface',(.90,.90,.90),.85,0)
    # A light table provides clear edges on the white outer grips. Stand-off remains legible in the soft shadow.
    bs = next(n for n in sweep.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bs.inputs['Emission Color'].default_value = (.99,.99,.99,1)
    bs.inputs['Emission Strength'].default_value = .57
    floor(scene,sweep,-.00025)
    cam = camera(scene,(0,0,9),(0,0,0),ortho=4.2)
    cam.rotation_euler = (0,0,0)
    frame(scene,subject,(.5,.5),.805,.846)
    area(scene,'Softbox over left',(-4.5,1.2,5.8),(-.58,.12,.5),630,3.2,4.25,(1,.97,.94))
    area(scene,'Softbox over right',(4.3,1.8,4.4),(.46,.21,.57),330,1.8,3.75,(.91,.95,1))
    area(scene,'Front black-bridge fill',(0,-4.5,3.1),(0,-.19,.58),118,3.3,1.7,(.93,.96,1))
    return scene


def rear_view():
    scene = new_scene('04','rear-shoulder','Reference | Rear and shoulder controls',(2100,1500))
    subject = place(scene,pitch=-4,yaw=8)
    world(scene,(.80,.87,1),.155)
    floor(scene,paper('04 | Blue graphite sweep',(.105,.127,.151),.76),-.00025)
    photo(scene,169,41,13.5,(0,0,1.05),78)
    frame(scene,subject,(.50,.52),.828,.83)
    area(scene,'Back shell silk',(-3.1,4.4,5.3),(-.68,0,1.35),560,3.7,3.05,(1,.955,.91))
    area(scene,'Rake across moulded marks',(2.7,1.3,4.8),(0,0,1.55),204,.60,3.1,(.89,.94,1))
    area(scene,'Dark trigger separation',(1.65,-3.3,3.9),(.50,.1,1.73),182,2.0,3.3,(.91,.96,1))
    area(scene,'Base reflection',(3.6,3,1.5),(1,.1,.45),75,2.4,2.4,(1,.93,.86))
    return scene


def build_all():
    return horizontal_hero(), mobile_hero(), proportion_view(), rear_view()
