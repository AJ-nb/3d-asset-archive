"""Build the Osmo Pocket 4P exterior reconstruction from millimetre profiles.

Run from Blender in background with --python build_pocket.py. The optional
arguments after -- are --draft (reduced render settings) and --model-only.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT))
MM = 0.001


def mm(values):
    return tuple(value * MM for value in values)


def srgb(rgb):
    return tuple(c / 12.92 if c < 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb)


def material(name, color, rough=0.38, metal=0.0, grain=None, coat=0.0, emission=0.0):
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    result.diffuse_color = (*srgb(color), 1.0)
    nodes = result.node_tree.nodes
    links = result.node_tree.links
    shader = nodes.get("Principled BSDF")
    values = {
        "Base Color": result.diffuse_color,
        "Roughness": rough,
        "Metallic": metal,
        "Coat Weight": coat,
        "Coat Roughness": 0.13,
        "Emission Color": result.diffuse_color,
        "Emission Strength": emission,
    }
    for key, value in values.items():
        shader.inputs[key].default_value = value
    if grain:
        coordinates = nodes.new("ShaderNodeTexCoord")
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 1 / (grain * MM)
        noise.inputs["Detail"].default_value = 2
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.22
        bump.inputs["Distance"].default_value = 0.014 * MM
        links.new(coordinates.outputs["Object"], noise.inputs["Vector"])
        links.new(noise.outputs["Fac"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    return result


def collection(name, parent):
    result = bpy.data.collections.new(name)
    parent.children.link(result)
    return result


def pivot(name, loc, coll, parent=None):
    obj = bpy.data.objects.new(name, None)
    coll.objects.link(obj)
    obj.location = mm(loc)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.006
    if parent:
        reparent(obj, parent)
    return obj


def reparent(obj, parent):
    bpy.context.view_layer.update()
    transform = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_world = transform
    return obj


def mesh(name, verts, faces, coll, mat=None, smooth=False, parent=None):
    data = bpy.data.meshes.new(name)
    data.from_pydata([mm(v) for v in verts], [], faces)
    data.update()
    bm = bmesh.new()
    bm.from_mesh(data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(data)
    bm.free()
    obj = bpy.data.objects.new(name, data)
    coll.objects.link(obj)
    if mat:
        data.materials.append(mat)
    for face in data.polygons:
        face.use_smooth = smooth
    if parent:
        reparent(obj, parent)
    return obj


def rounded_points(width, height, radius, segments=16):
    a, b = width / 2, height / 2
    r = min(radius, a - 0.002, b - 0.002)
    corners = ((a-r,b-r,0),(-a+r,b-r,90),(-a+r,-b+r,180),(a-r,-b+r,270))
    return [
        (x + r * math.cos(math.radians(deg + 90 * i / segments)),
         y + r * math.sin(math.radians(deg + 90 * i / segments)))
        for x, y, deg in corners for i in range(segments + 1)
    ]


def section(a, b, depth, axis):
    if axis == "Z":
        return (a, b, depth)
    if axis == "Y":
        return (a, depth, b)
    return (depth, a, b)


def loft(name, profiles, axis, coll, mat=None, at=(0, 0, 0), parent=None):
    """Profiles contain (axis depth, width, height, radius, u offset, v offset)."""
    verts, faces = [], []
    for depth, width, height, radius, off_u, off_v in profiles:
        ring = rounded_points(width, height, radius)
        for u, v in ring:
            point = section(u + off_u, v + off_v, depth, axis)
            verts.append(tuple(c + d for c, d in zip(point, at)))
    count = len(ring)
    for j in range(len(profiles) - 1):
        for i in range(count):
            ni = (i + 1) % count
            faces.append((j*count+i, j*count+ni, (j+1)*count+ni, (j+1)*count+i))
    faces += [tuple(reversed(range(count))), tuple(range(len(verts)-count, len(verts)))]
    obj = mesh(name, verts, faces, coll, mat, smooth=True, parent=parent)
    for face in obj.data.polygons[-2:]:
        face.use_smooth = False
    return obj


def plaque(name, loc, width, height, depth, radius, fillet, axis, coll, mat=None, parent=None):
    fillet = min(fillet, depth * 0.48, radius * 0.7)
    profiles = []
    for side in (-1, 1):
        angles = range(90, -1, -18) if side < 0 else range(0, 91, 18)
        for angle in angles:
            a = math.radians(angle)
            inset = fillet * (1 - math.cos(a))
            d = side * (depth / 2 - fillet + fillet * math.sin(a))
            profiles.append((d, width-2*inset, height-2*inset, radius-inset, 0, 0))
    return loft(name, profiles, axis, coll, mat, loc, parent)


def revolved(name, loc, profile, axis, coll, mat=None, parent=None, segments=96):
    """Closed lathe cross-section (radius, axial distance)."""
    verts = []
    for radius, depth in profile:
        for i in range(segments):
            a = i * math.tau / segments
            point = section(radius * math.cos(a), radius * math.sin(a), depth, axis)
            verts.append(tuple(c + d for c, d in zip(point, loc)))
    faces = []
    for j in range(len(profile)):
        k = (j + 1) % len(profile)
        for i in range(segments):
            m = (i + 1) % segments
            faces.append((j*segments+i, j*segments+m, k*segments+m, k*segments+i))
    return mesh(name, verts, faces, coll, mat, smooth=True, parent=parent)


def disc(name, loc, radius, depth, axis, coll, mat, bevel=0.2, parent=None):
    return plaque(name, loc, 2*radius, 2*radius, depth, radius, bevel, axis, coll, mat, parent)


def cut(target, cutter, cutters):
    for current in list(cutter.users_collection):
        current.objects.unlink(cutter)
    cutters.objects.link(cutter)
    cutter.display_type = "WIRE"
    cutter.hide_render = True
    cutter.hide_set(True)
    mod = target.modifiers.new("Pocket — " + cutter.name, "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = cutter
    return mod


def split_sharp_normals(*shells):
    group = bpy.data.node_groups.new("Shell • preserve sharp recess edges", "GeometryNodeTree")
    group.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    incoming = group.nodes.new("NodeGroupInput")
    outgoing = group.nodes.new("NodeGroupOutput")
    angle = group.nodes.new("GeometryNodeInputMeshEdgeAngle")
    within_limit = group.nodes.new("ShaderNodeMath")
    within_limit.operation = "LESS_THAN"
    within_limit.inputs[1].default_value = math.radians(27)
    smooth = group.nodes.new("GeometryNodeSetShadeSmooth")
    smooth.domain = "EDGE"
    group.links.new(angle.outputs["Unsigned Angle"], within_limit.inputs[0])
    group.links.new(within_limit.outputs[0], smooth.inputs["Shade Smooth"])
    group.links.new(incoming.outputs["Geometry"], smooth.inputs["Geometry"])
    group.links.new(smooth.outputs["Geometry"], outgoing.inputs["Geometry"])
    for shell in shells:
        modifier = shell.modifiers.new("Separate normals at sharp recess rims", "NODES")
        modifier.node_group = group


def path(name, points, radius, coll, mat, parent=None, cyclic=False):
    data = bpy.data.curves.new(name, "CURVE")
    data.dimensions = "3D"
    data.bevel_depth = radius * MM
    data.bevel_resolution = 3
    data.use_fill_caps = True
    spline = data.splines.new("POLY")
    spline.points.add(len(points) - 1)
    spline.use_cyclic_u = cyclic
    for item, p in zip(spline.points, points):
        item.co = (*mm(p), 1)
    obj = bpy.data.objects.new(name, data)
    coll.objects.link(obj)
    data.materials.append(mat)
    if parent:
        reparent(obj, parent)
    return obj


def frontal_surface(profiles, x, z):
    for first, second in zip(profiles, profiles[1:]):
        if first[0] <= z <= second[0]:
            t = (z-first[0]) / (second[0]-first[0])
            width, depth, radius, center_x, center_y = [
                a + t*(b-a) for a,b in zip(first[1:],second[1:])
            ]
            h = max(0,abs(x-center_x)-width/2+radius)
            return center_y - depth/2 + radius - math.sqrt(max(0,radius**2-h**2))
    raise ValueError(f"Out of handle span: {z}")


def fascia(coll, mat, root, body_profiles, cutters):
    """Trace the lower control insert around the left joystick from the DJI diagram."""
    start = (-12.92,6.70)
    curves = [
        ((-12.92,3.74),(-11.00,3.17),(-8.45,3.17)),
        ((-3.0,3.17),(5.44,3.17),(8.52,3.17)),
        ((11.37,3.17),(13.02,4.85),(13.02,7.25)),
        ((13.02,12.24),(13.02,22.76),(13.02,27.55)),
        ((13.02,30.71),(10.93,32.64),(7.43,32.64)),
        ((5.22,32.64),(2.52,32.64),(1.35,32.64)),
        ((-0.13,32.64),(-0.81,31.64),(-0.66,30.31)),
        ((-0.02,24.85),(-3.22,20.06),(-9.16,19.99)),
        ((-11.91,19.96),(-12.92,19.30),(-12.92,17.19)),
        ((-12.92,13.38),(-12.92,9.72),(-12.92,6.70)),
    ]
    points = []
    for c1,c2,end in curves:
        for n in range(12):
            t = n / 12
            s = 1 - t
            x, z = tuple(s**3*a+3*s*s*t*b+3*s*t*t*c+t**3*d
                         for a,b,c,d in zip(start,c1,c2,end))
            points.append((x, z * 1.08))
        start = end
    outline = path("Controls • lower fascia perimeter",
                   [(x,frontal_surface(body_profiles,x,z)-0.20,z) for x,z in points],0.078,coll,
                   bpy.data.materials["Carbon black • joint line"],root,cyclic=True)
    outline["Reference"] = "DJI China support guide, front control view"
    ring = [(x,y,z) for y in (-8.5,-14.0) for x,z in points]
    n = len(points)
    faces = [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    faces += [tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
    insert = mesh("Controls • lower grip fascia", ring, faces, coll, mat, parent=root)
    surface = loft("Fascia conforming surface",body_profiles,"Z",cutters,at=(0,-0.19,0),parent=root)
    mod = cut(insert,surface,cutters)
    mod.operation = "INTERSECT"
    return insert


def mark(name, content, loc, width, coll, mat, parent=None):
    data = bpy.data.curves.new(name, "FONT")
    data.body = content
    data.align_x = "CENTER"
    data.align_y = "CENTER"
    data.size = 0.004
    data.space_character = 1.1
    obj = bpy.data.objects.new(name, data)
    coll.objects.link(obj)
    data.materials.append(mat)
    obj.location = mm(loc)
    obj.rotation_euler.x = math.pi / 2
    bpy.context.view_layer.update()
    obj.scale = (width * MM / obj.dimensions.x,) * 3
    if parent:
        reparent(obj, parent)
    return obj


def screen(root, coll, materials):
    center = 73.15
    hinge = pivot("Screen • rotate local Y 0° / −90°", (0, -13.6, center), coll, root)
    hinge["Use"] = "Rotation Y is keyframeable. 0° is landscape, −90° is portrait."
    plaque("Display pivot • rear support", (0,-13.14,center), 31.0, 28.6, 2.90, 5.0, 0.66,
           "Y", coll, materials["shell"], root)
    plaque("Display • carrier and outer frame", (0,-15.656,center), 53.8, 32.9, 2.168, 4.0, 0.74,
           "Y", coll, materials["shell"], hinge)
    plaque("Display • perimeter gasket", (0,-16.45,center), 51.6, 30.9, 0.52, 3.20, 0.19,
           "Y", coll, materials["gasket"], hinge)
    plaque("Display • bonded dark cover", (0,-16.55,center), 50.3, 29.8, 0.37, 2.95, 0.12,
           "Y", coll, materials["glass"], hinge)
    # 2.0 inch active diagonal with an aspect ratio of 556 by 314.
    diag = 50.8
    denominator = math.hypot(556, 314)
    w, h = diag * 556 / denominator, diag * 314 / denominator
    active = plaque("Display • OLED active area 2.0 in", (0,-16.65,center), w, h, 0.19, 1.1, 0.035,
                    "Y", coll, materials["oled"], hinge)
    active["Official active diagonal in mm"] = diag
    active["Official pixel matrix"] = "556×314"
    return hinge


def build_body(root, model, studio_cuts):
    housing = collection("01  Housing and rear grip", model)
    panel = collection("02  Buttons and separable controls", model)
    display = collection("03  Rotating OLED assembly", model)
    io = collection("04  Ports, contact faces and microphones", model)
    m = {
        "shell": material("Carbon black • satin polymer", (0.235,0.241,0.251), 0.49, grain=0.22),
        "inset": material("Carbon black • control plates", (0.194,0.201,0.209), 0.49, grain=0.19),
        "rubber": material("Carbon black • tactile elastomer", (0.117,0.124,0.133), 0.58, grain=0.14),
        "grip": material("Carbon black • diagonal insert", (0.154,0.162,0.173), 0.53, grain=0.22),
        "gasket": material("Carbon black • joint line", (0.073,0.079,0.088), 0.55),
        "void": material("Unlit cavities", (0.027,0.032,0.038), 0.63),
        "metal": material("USB shield • dark nickel", (0.35,0.37,0.39), 0.3, 0.76),
        "contact": material("Contact metal", (0.69,0.52,0.26), 0.29, 0.79),
        "glass": material("Touchscreen • tempered cover", (0.041,0.053,0.068), 0.15, 0.22, coat=0.36),
        "oled": material("Touchscreen • OLED standby", (0.051,0.071,0.092), 0.195, 0.15, coat=0.45),
        "grey": material("Controls • debossed neutral marks", (0.288,0.300,0.311), 0.53),
        "record": material("Controls • muted DJI red", (0.66,0.122,0.075), 0.39),
        "led": material("Status LED • ready", (0.086,0.51,0.20), 0.3, emission=0.68),
        "logo": material("Grip • subtle OSMO mark", (0.187,0.195,0.209), 0.43, 0.1),
    }

    # The rear tangent reaches +16.75 mm. The OLED face bounds the opposite side.
    body_profiles = [
        (1.40,28.1,24.6,7.2,0,1.20), (1.63,29.1,26.4,7.7,0,1.25),
        (2.40,30.35,27.8,8.1,0,1.32), (4.15,31.55,28.8,8.3,0,1.42),
        (8.0,33.20,29.95,8.1,0,1.62), (47.0,33.20,29.95,8.0,0,1.72),
        (59.2,33.30,30.0,8.1,0,1.75), (83.5,33.30,30.0,8.1,0,1.75),
        (88.8,32.90,29.95,8.9,0,1.72), (92.0,31.75,29.1,9.4,0,1.57),
        (94.7,29.95,26.6,9.25,0,1.12), (97.2,26.5,23.0,8.9,0,0.45),
        (98.7,23.7,21.55,9.0,0,0.06), (99.65,22.9,21.2,9.1,0,0),
    ]
    main = loft("Handle • molded upper shell", body_profiles, "Z", housing, m["shell"], parent=root)
    bottom = loft("Handle • lower cap and connector carrier", [
        (0.0,26.5,23.5,6.9,0,1.2), (0.15,27.45,24.14,7.05,0,1.2),
        (0.43,28.3,24.8,7.15,0,1.2), (1.35,28.3,24.8,7.25,0,1.2),
    ], "Z", housing, m["inset"], parent=root)
    loft("Handle • cap seam and internal ledge", [
        (1.1,27.65,24.1,7.1,0,1.2),(1.59,27.65,24.1,7.1,0,1.2)
    ], "Z", housing, m["gasket"], parent=root)

    # Ports and button beds use real cut geometry at the external mating surface.
    usb = plaque("USB-C cutter", (0,-0.15,0.65), 9.35, 3.65, 2.22, 1.81, 0.19,
                 "Z", housing, parent=root)
    cut(bottom, usb, studio_cuts)
    cut(main, usb, studio_cuts)
    shield_profile = [
        (-0.17,9.0,3.33,1.63), (-0.06,8.65,3.00,1.48),
        (1.50,8.65,3.00,1.48), (1.50,7.68,2.30,1.14),
        (-0.06,7.68,2.30,1.14), (-0.17,8.0,2.52,1.22),
    ]
    shield_rings = [
        [(x,y-0.15,z+0.30) for x,y in rounded_points(w,h,r)]
        for z,w,h,r in shield_profile
    ]
    count = len(shield_rings[0])
    faces = []
    for j in range(len(shield_rings)):
        k = (j+1) % len(shield_rings)
        for i in range(count):
            ni = (i+1) % count
            faces.append((j*count+i,j*count+ni,k*count+ni,k*count+i))
    mesh("USB-C • recessed nickel lining", sum(shield_rings,[]), faces, io, m["metal"], True, root)
    plaque("USB-C • cavity back", (0,-0.15,1.9), 8.25, 2.79, 0.24, 1.37, 0.08,
           "Z", io, m["void"], root)
    plaque("USB-C • tongue", (0,-0.15,1.10), 6.5, 0.86, 1.57, 0.36, 0.13, "Z", io, m["rubber"], root)
    for i in range(12):
        for side in (-1, 1):
            plaque(f"USB-C • pad {i+1:02d}/{side:+d}", ((i-5.5)*0.46,-0.15+side*0.435,1.065),
                  0.22,0.82,0.025,0.085,0.006,"Y",io,m["contact"],root)

    # Each rear rib is a separately editable section of the soft grip insert.
    rear_profiles = [
        (12.25,27.1,84.8,7.6,0,46.2), (15.55,24.2,83.1,7.1,0,46.4),
        (16.26,20.8,80.7,6.6,0,46.4),
    ]
    rear_recess = loft("Rear grip well cutter", [(p[0]+0.16,p[1]+0.32,p[2]+0.32,p[3]+0.12,p[4],p[5])
                      for p in rear_profiles] + [(18.25,20.8,80.7,6.6,0,46.4)], "Y", housing, parent=root)
    cut(main, rear_recess, studio_cuts)
    # Match the base cap shaft and cap seam while keeping a real border around the insert.
    rear = loft("Handle • rear molded elastomer insert", rear_profiles, "Y", housing, m["grip"], parent=root)
    rear["Reference"] = "DJI English User Manual v1.0, p.7 back overview"
    # Recessed-looking diagonal rib texture, with ends clipped against the rounded panel.
    a, b, r, mid = 10.17, 39.95, 6.35, 46.4
    for i in range(21):
        intercept = (i - 10) * 4.05
        points = []
        for s in range(241):
            x = -a + (2*a) * s / 240
            z = -0.96*x + intercept
            if math.hypot(max(0, abs(x)-a+r), max(0, abs(z)-b+r)) <= r:
                points.append((x,16.273,z+mid))
        if len(points) > 1:
            path(f"Grip • diagonal rib {i+1:02d}", (points[0],points[-1]), 0.115,
                 housing, m["rubber"], root)

    fascia(panel,m["inset"],root,body_profiles,studio_cuts)
    plaque("Controls • shortcut panel border", (0,-12.25,51.44), 30.6, 16.50, 1.92,
           3.65,0.53,"Y",panel,m["gasket"],root)
    plaque("Controls • shortcut button surround", (0,-12.62,51.39), 29.9, 15.65, 1.6,
           3.25,0.45,"Y",panel,m["inset"],root)
    for x, name in [(-7.47,"Zoom"),(7.47,"Custom")]:
        disc(f"{name} • recess", (x,-13.39,50.20), 4.70, 0.47, "Y", panel, m["gasket"], 0.15, root)
        disc(f"{name} • button", (x,-13.77,50.20), 4.03, 1.1, "Y", panel, m["shell"], 0.3, root)
    mark("Custom • C legend","C",(7.47,-14.35,50.20),2.53,panel,m["grey"],root)
    zoom_circle = [(-7.78+1.11*math.cos(t*math.tau/48),-14.34,50.44+1.11*math.sin(t*math.tau/48)) for t in range(48)]
    path("Zoom • magnifier outline",zoom_circle,0.135,panel,m["grey"],root,cyclic=True)
    path("Zoom • magnifier stem",[(-7.04,-14.34,49.65),(-6.31,-14.34,48.90)],0.12,panel,m["grey"],root)
    for points in ([(-8.25,-14.34,50.44),(-7.31,-14.34,50.44)],
                   [(-7.78,-14.34,49.97),(-7.78,-14.34,50.91)]):
        path("Zoom • plus",points,0.09,panel,m["grey"],root)

    xz = (-8.60, 30.26)
    disc("Joystick • recessed seal", (xz[0],-13.17,xz[1]), 6.15, 0.9, "Y", panel, m["gasket"], 0.32, root)
    disc("Joystick • raised collar", (xz[0],-13.91,xz[1]), 5.44, 1.64, "Y", panel, m["inset"], 0.39, root)
    disc("Joystick • rocking cap", (xz[0],-15.45,xz[1]), 4.58, 2.00, "Y", panel, m["rubber"], 0.42, root)
    # Shallow molded grip pattern clipped to the cap, with 60 small raised islands.
    knurl_verts, knurl_faces = [], []
    for row in range(-4,5):
        for col in range(-4,5):
            x, z = col*0.85, row*0.85
            if math.hypot(x,z) > 3.79:
                continue
            i = len(knurl_verts)
            cx, cz = x+xz[0], z+xz[1]
            for y, radius in [(-16.44,0.36), (-16.57,0.24)]:
                knurl_verts.extend([(cx+radius,y,cz),(cx,y,cz+radius),(cx-radius,y,cz),(cx,y,cz-radius)])
            knurl_faces.extend([(i,i+3,i+2,i+1),(i+4,i+5,i+6,i+7),
                               *[(i+j,i+(j+1)%4,i+4+(j+1)%4,i+4+j) for j in range(4)]])
    mesh("Joystick • molded thumb knurl",knurl_verts,knurl_faces,panel,m["grip"],False,root)

    disc("REC • recess", (7.10,-13.36,28.54), 4.95, 0.66,"Y",panel,m["gasket"],0.15,root)
    disc("REC • smooth button", (7.10,-13.77,28.54), 4.03, 1.12,"Y",panel,m["shell"],0.31,root)
    record_profile = [(2.29,-0.047),(2.29,0.042),(1.78,0.042),(1.78,-0.047)]
    revolved("REC • red ring", (7.10,-14.35,28.54), record_profile,"Y",panel,m["record"],root)
    mark("Lower fascia • OSMO", "OSMO", (0,frontal_surface(body_profiles,0,10.20)-0.225,10.20),
         13.7, panel, m["logo"], root)
    disc("Status LED • surround", (-8.42,-13.23,38.28), 0.92, 0.22,"Y",io,m["gasket"],0.07,root)
    disc("Status LED • green indicator", (-8.42,-13.40,38.28), 0.52, 0.19,"Y",io,m["led"],0.07,root)
    speaker = plaque("Speaker grille cutter", (0.0,-13.0,38.28), 8.85, 2.41, 1.5, 0.85, 0.16, "Y",io,parent=root)
    cut(main,speaker,studio_cuts)
    plaque("Speaker • mesh bed", (0.0,-12.41,38.28),8.63,2.16,0.36,0.72,0.13,"Y",io,m["void"],root)
    for i in range(3):
        plaque(f"Speaker grille • bar {i+1}",(0.0,-12.70,37.78+i*0.5),7.93,0.13,0.18,0.064,
               0.035,"Y",io,m["shell"],root)
    for i in range(9):
        plaque(f"Speaker grille • lattice {i+1}",((i-4)*0.85,-12.75,38.28),0.115,1.58,0.18,0.055,
               0.03,"Y",io,m["shell"],root)

    card = plaque("Card slot cutter", (-15.75,1.65,21.7), 8.35,15.6,2.38,1.42,0.37,"X",io,parent=root)
    cut(main,card,studio_cuts)
    plaque("microSD • gasket in recess",(-14.98,1.65,21.7),8.04,15.3,0.97,1.25,0.25,"X",io,m["gasket"],root)
    plaque("microSD • removable cover",(-15.62,1.73,21.7),7.4,14.77,0.92,1.18,0.35,"X",io,m["shell"],root)
    plaque("microSD • lower pull tab",(-15.99,1.71,16.9),4.48,1.21,0.31,0.52,0.105,"X",io,m["rubber"],root)
    for side in (-1,1):
        slot = plaque(f"Accessory latch cutter {side:+d}",(side*15.89,0.05,5.94),8.2,2.22,2.9,0.88,0.24,
                      "X",io,parent=root)
        cut(main,slot,studio_cuts)
        plaque(f"Accessory latch • recess {side:+d}",(side*14.67,0.05,5.94),7.90,1.95,0.46,0.79,0.13,
               "X",io,m["void"],root)

    lanyard = plaque("Lanyard channel cutter", (15.82,-1.2,13.68),2.75,10.45,2.6,1.25,0.23,"X",io,parent=root)
    cut(main,lanyard,studio_cuts)
    plaque("Lanyard • recessed channel",(14.56,-1.2,13.68),2.52,10.1,0.47,1.14,0.15,"X",io,m["void"],root)
    plaque("Lanyard • bridge",(15.40,-1.2,13.68),2.56,1.54,0.94,0.57,0.27,"X",io,m["shell"],root)

    for side in (-1,1):
        bore = plaque(f"Microphone bore {side:+d}",(side*16.10,2.52,85.65),1.07,1.9,1.82,0.52,0.13,
                      "X",io,parent=root)
        cut(main,bore,studio_cuts)
        plaque(f"Microphone • side {side:+d}",(side*15.32,2.52,85.65),0.98,1.76,0.23,0.45,0.09,
               "X",io,m["void"],root)
    plaque("Microphone • rear inset gasket",(0,16.28,83.13),0.94,1.52,0.12,0.44,0.052,
           "Y",io,m["void"],root)
    hinge = screen(root, display, m)
    split_sharp_normals(main, bottom)
    return {"shell":main,"screen":hinge,"screen_materials":m}


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def camera(name, loc, target, coll, lens=70, ortho=None):
    data = bpy.data.cameras.new(name)
    data.lens = lens
    data.clip_start = 0.004
    data.clip_end = 50
    if ortho:
        data.type, data.ortho_scale = "ORTHO", ortho
    obj = bpy.data.objects.new(name, data)
    coll.objects.link(obj)
    obj.location = loc
    aim(obj, target)
    return obj


def light(name, loc, target, strength, color, size, coll, height=None):
    data = bpy.data.lights.new(name, "AREA")
    data.shape = "RECTANGLE" if height else "DISK"
    data.size = size
    if height:
        data.size_y = height
    data.energy = strength * 0.13
    data.color = color
    obj = bpy.data.objects.new(name, data)
    coll.objects.link(obj)
    obj.location = loc
    aim(obj, target)
    return obj


def build_studio(scene):
    stage = collection("90  Studio • geometry and lights", scene.collection)
    cameras = collection("91  Cameras • product, macro and orthographic", scene.collection)
    sweep = material("Studio • cool graphite seamless", (0.19,0.225,0.26), 0.72, 0.03, grain=0.55)
    wall = [(260+275*math.sin(i*math.pi/64),-0.081+275*(1-math.cos(i*math.pi/64)))
            for i in range(33)]
    wall.append((535,2000))
    profile = [(-y,z) for y,z in reversed(wall)] + wall
    points = [(x,y,z) for y,z in profile for x in (-2500,2500)]
    mesh("Stage • seamless cyclorama", points,
         [(2*i,2*i+1,2*i+3,2*i+2) for i in range(len(profile)-1)],stage,sweep,True)

    focus = (0,0,0.088)
    light("Key • softbox", (-0.19,-0.19,0.244), focus, 18.5, (0.88,0.94,1.0), 0.24, stage, 0.28)
    light("Fill • near lens axis", (0.041,-0.32,0.160), focus, 4.0, (1.0,0.89,0.79), 0.21, stage, 0.20)
    light("Edge • vertical cool strip", (0.178,0.087,0.16), focus, 16.0, (0.60,0.76,1.0), 0.045, stage, 0.24)
    light("Rim • upper white", (-0.075,0.071,0.25), focus, 11.0, (1.0,0.92,0.84), 0.113, stage, 0.20)
    light("Backdrop • gradient", (-0.17,0.105,0.165), (0,0.34,0.12), 13.0,(0.49,0.69,1.0),0.17,stage)
    light("Rear detail • broad neutral", (-0.11,0.23,0.23), focus, 6.3,(0.94,0.96,1.0),0.18,stage)

    views = {
        "hero": camera("01 • Classic Black / landscape", (0.188,-0.414,0.165), (0,0,0.080), cameras, 81),
        "rear": camera("02 • Rear and side / portrait", (-0.196,0.403,0.155), (0,0,0.080), cameras, 78),
        "detail": camera("03 • Dual optics / macro", (0.092,-0.211,0.179), (0,-0.002,0.135), cameras, 86),
        "front": camera("04 • Front / orthographic", (0,-0.45,0.07975), (0,0,0.07975), cameras, ortho=0.181),
        "right": camera("05 • Right / orthographic", (0.45,0,0.07975), (0,0,0.07975), cameras, ortho=0.181),
        "back": camera("06 • Back / orthographic", (0,0.45,0.07975), (0,0,0.07975), cameras, ortho=0.181),
        "left": camera("07 • Left / orthographic", (-0.45,0,0.07975), (0,0,0.07975), cameras, ortho=0.181),
        "base": camera("08 • Bottom / orthographic", (0,0,-0.33), (0,0,0.054), cameras, ortho=0.047),
    }
    scene.camera = views["hero"]
    scene.world = bpy.data.worlds.new("Product studio world")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes.get("Background").inputs["Color"].default_value = (0.22,0.25,0.32,1)
    scene.world.node_tree.nodes.get("Background").inputs["Strength"].default_value = 0.23
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.resolution_x = 1440
    scene.render.resolution_y = 1440
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = -0.35
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 64
    scene.cycles.use_denoising = True
    scene.cycles.adaptive_threshold = 0.032
    scene.cycles.max_bounces = 8
    scene.cycles.glossy_bounces = 4
    scene.cycles.transmission_bounces = 5
    try:
        preferences = bpy.context.preferences.addons["cycles"].preferences
        for backend in ("OPTIX","CUDA"):
            preferences.compute_device_type = backend
            devices = preferences.get_devices_for_type(backend)
            if devices:
                for device in devices:
                    device.use = device.type != "CPU"
                scene.cycles.device = "GPU"
                print("Cycles GPU", backend, [device.name for device in devices])
                break
    except (AttributeError, TypeError, RuntimeError) as error:
        print("GPU unavailable, using Cycles CPU:", error)
    return views, stage


def bounds_and_topology(coll, cutters):
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    min_corner = Vector((math.inf,) * 3)
    max_corner = Vector((-math.inf,) * 3)
    counts = {"mesh_objects":0,"surface_marks":0,"vertices":0,"faces":0}
    findings = []
    for obj in coll.all_objects:
        if obj.type not in {"MESH","CURVE","FONT"} or obj.name in cutters.objects:
            continue
        mesh_object = obj.evaluated_get(deps)
        if obj.type == "MESH":
            counts["mesh_objects"] += 1
        else:
            counts["surface_marks"] += 1
        data = mesh_object.to_mesh()
        if not data or len(data.vertices) == 0:
            findings.append({"object":obj.name,"empty_evaluated_mesh":True})
            if data:
                mesh_object.to_mesh_clear()
            continue
        counts["vertices"] += len(data.vertices)
        counts["faces"] += len(data.polygons)
        for v in data.vertices:
            p = (mesh_object.matrix_world @ v.co) / MM
            for axis in range(3):
                min_corner[axis] = min(min_corner[axis],p[axis])
                max_corner[axis] = max(max_corner[axis],p[axis])
        if obj.type == "MESH":
            bm = bmesh.new()
            bm.from_mesh(data)
            bad_edges = sum(not e.is_manifold for e in bm.edges)
            tiny = sum(f.calc_area() < 1e-15 for f in bm.faces)
            if bad_edges or tiny:
                findings.append({"object":obj.name,"nonmanifold_edges":bad_edges,"tiny_faces":tiny})
            bm.free()
        mesh_object.to_mesh_clear()
    return {
        "model_min_xyz_mm":[round(v,4) for v in min_corner],
        "model_max_xyz_mm":[round(v,4) for v in max_corner],
        "model_width_depth_length_mm":[round(v,4) for v in max_corner-min_corner],
        "part_counts":counts,
        "topology_findings":findings,
    }


def verify_rig(model, controls, root):
    bpy.context.view_layer.update()
    results = {}
    for role, axis in (("screen",1),("pan",2),("roll",1),("tilt",0)):
        control = controls[role]
        children = [o for o in control.children_recursive if o.type == "MESH"]
        relatives = [o for o in model.all_objects if o.type == "MESH" and o not in children]
        child_world = {o:o.matrix_world.copy() for o in children}
        other_world = {o:o.matrix_world.copy() for o in relatives}
        starting_angle = control.rotation_euler[axis]
        test_angle = -90 if role == "screen" else 10
        control.rotation_euler[axis] += math.radians(test_angle)
        bpy.context.view_layer.update()
        moved = sum(o.matrix_world != matrix for o,matrix in child_world.items())
        unrelated_moved = sum(o.matrix_world != matrix for o,matrix in other_world.items())
        control.rotation_euler[axis] = starting_angle
        bpy.context.view_layer.update()
        results[role] = {
            "angle_test_degrees":test_angle, "child_meshes":len(children), "child_meshes_moved":moved,
            "outside_meshes_moved":unrelated_moved, "pass":bool(children) and moved == len(children) and not unrelated_moved,
        }
    results["assembly_root"] = root.name
    return results


def render(scene, views, stage, body, draft, verification_only=False):
    preview = OUT / "previews"
    preview.mkdir(exist_ok=True)
    if not verification_only:
        if draft:
            scene.render.resolution_x = scene.render.resolution_y = 800
            scene.cycles.samples = 24
        for name, filename in [("hero","01-classic-black.png"),("rear","02-rear-detail.png"),
                               ("detail","03-dual-camera.png")]:
            scene.camera = views[name]
            if name == "rear":
                body["screen"].rotation_euler.y = -math.pi / 2
            else:
                body["screen"].rotation_euler.y = 0
            scene.render.filepath = str(preview / filename)
            bpy.ops.render.render(write_still=True)
    body["screen"].rotation_euler.y = 0
    stage.hide_render = True
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.studiolight_rotate_z = 0.55
    scene.display.shading.show_shadows = False
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.display.shading.cavity_ridge_factor = 1.1
    scene.display.shading.cavity_valley_factor = 1.05
    scene.display.shading.show_object_outline = False
    scene.world.color = (0.285, 0.3, 0.32)
    scene.render.resolution_x = scene.render.resolution_y = 800
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"
    for name in ("front","right","back","left","base"):
        scene.camera = views[name]
        scene.render.filepath = str(preview / ("ortho-"+name+".png"))
        bpy.ops.render.render(write_still=True)


def main():
    args = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "DJI Osmo Pocket 4P | Classic Black"
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.unit_settings.scale_length = 1.0
    scene["Published exterior envelope L × W × H (mm)"] = [159.5,63.3,33.5]
    scene["Reconstructed landscape pose source width (mm)"] = 53.8
    scene["Published mass (g)"] = 230
    scene["Exterior source"] = "DJI official specification, gallery and User Manual v1.0 p.7–8"
    scene["Reconstruction scope"] = "Display exterior. Detail dimensions estimated from source images."
    model = collection("DJI Osmo Pocket 4P • exterior", scene.collection)
    cutters = collection("98  Recess cutters • hidden from viewport and render", model)
    cutters.hide_render = True
    root = pivot("00 • Osmo Pocket 4P / master control", (0,0,0), model)
    root.empty_display_size = 0.018
    body = build_body(root,model,cutters)
    gimbal_group = collection("05  3-axis gimbal and dual optical stack", model)
    from build_gimbal import build_gimbal
    gimbal = build_gimbal(gimbal_group)
    reparent(gimbal["pan"],root)
    for role, movement in {"pan":(-235,58),"roll":(-45,45),"tilt":(-125,58)}.items():
        gimbal[role]["DJI controllable degrees"] = movement
        gimbal[role]["Rig use"] = "Exterior visualization; only small illustrative moves verified."
    views, stage = build_studio(scene)
    report = bounds_and_topology(model,cutters)
    expected = [63.3,33.5,159.5]
    report["published_order_width_depth_length_mm"] = expected
    report["published_pose_unspecified"] = True
    photo_width, target_depth, target_length = 53.8, 33.5, 159.5
    reconstructed = [photo_width, target_depth, target_length]
    report["landscape_pose_targets_mm"] = reconstructed
    report["landscape_pose_target_notes"] = [
        "Width: 281 px in official store front image, independently scaled by the OLED active width.",
        "Depth: nominal specification used as a reconstruction target, without independent measurements.",
        "Length: scaled to published overall length in the landscape front reconstruction.",
    ]
    report["landscape_pose_target_deltas_mm"] = [round(a-b,4) for a,b in zip(report["model_width_depth_length_mm"],reconstructed)]
    report["landscape_pose_target_tolerance_mm"] = 0.25
    report["landscape_pose_target_pass"] = all(abs(d) <= 0.25 for d in report["landscape_pose_target_deltas_mm"])
    report["rig"] = verify_rig(model, {"screen":body["screen"], **gimbal},root)
    report["limitations"] = ["Published envelope pose unspecified.",
                             "Published 63.3 mm width retained as metadata; official normal front image scales to 53.8 mm.",
                             "No gimbal motion-envelope or physical fit certification."]
    (OUT / "建模校验.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    for screen_data in bpy.data.screens:
        for area in screen_data.areas:
            if area.type == "VIEW_3D":
                view = area.spaces.active
                view.clip_start = 0.002
                view.clip_end = 30
                view.region_3d.view_distance = 0.28
                view.region_3d.view_location = (0,0,0.082)
                view.region_3d.view_rotation = views["hero"].rotation_euler.to_quaternion()
                view.shading.color_type = "MATERIAL"
                view.overlay.show_extras = False
                view.overlay.show_floor = False
                view.overlay.show_axis_x = view.overlay.show_axis_y = False
    for obj in stage.objects:
        obj.hide_set(True)
    scene.render.filepath = str(OUT / "previews" / "01-classic-black.png")
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "DJI-Osmo-Pocket-4P-Classic-Black.blend"))
    if "--model-only" not in args:
        render(scene,views,stage,body,draft="--draft" in args,verification_only="--ortho-only" in args)


if __name__ == "__main__":
    main()
