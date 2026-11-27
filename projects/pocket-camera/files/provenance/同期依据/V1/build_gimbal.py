"""Build the DJI Osmo Pocket 4P exterior gimbal and camera assembly.

The shell, bores, joints and ports are estimated from public DJI photos.
The photographed hero posture spans 49.4 mm across its motors, with the
head at 159.5 mm above the handle base. This is an exterior display model.
"""

import math

import bmesh
import bpy


MM = 0.001
PAN = (0.0, 0.0, 99.6)
ROLL = (16.2, 10.5, 135.3)
TILT = (0.0, -2.0, 135.3)


def _material(name, color, metallic, roughness, **settings):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1.0)
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    for socket, value in settings.items():
        shader.inputs[socket].default_value = value
    return material


def _move(obj, parent, xyz):
    obj.parent = parent
    origin = parent["origin_mm"] if parent else (0.0, 0.0, 0.0)
    obj.location = tuple((value - zero) * MM for value, zero in zip(xyz, origin))


def _pivot(collection, name, xyz, parent, axis):
    obj = bpy.data.objects.new(name, None)
    collection.objects.link(obj)
    obj.empty_display_type = "ARROWS"
    obj.empty_display_size = 0.009
    obj["origin_mm"] = xyz
    obj["axis"] = axis
    obj.rotation_mode = "XYZ"
    _move(obj, parent, xyz)
    return obj


def _mesh(collection, name, center, vertices, faces, material=None, parent=None):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v * MM for v in point) for point in vertices], [], faces)
    topology = bmesh.new()
    topology.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(topology, faces=list(topology.faces))
    topology.to_mesh(mesh)
    topology.free()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    _move(obj, parent, center)
    if material:
        mesh.materials.append(material)
    return obj


def _round_rect(width, height, radius, steps=12):
    vertices = []
    for corner, (sign_x, sign_z) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
        center_x = sign_x * (width / 2 - radius)
        center_z = sign_z * (height / 2 - radius)
        for step in range(steps + 1):
            angle = math.pi / 2 * (corner + step / steps)
            vertices.append((center_x + radius * math.cos(angle), center_z + radius * math.sin(angle)))
    return vertices


def _ring_faces(ring_size, ring_count, loop=False):
    faces = [] if loop else [tuple(reversed(range(ring_size)))]
    for level in range(ring_count if loop else ring_count - 1):
        start = level * ring_size
        next_level = ((level + 1) % ring_count) * ring_size
        for index in range(ring_size):
            after = (index + 1) % ring_size
            faces.append((start + index, start + after, next_level + after, next_level + index))
    if not loop:
        faces.append(tuple(range((ring_count - 1) * ring_size, ring_count * ring_size)))
    return faces


def _orient(face_a, face_b, axis_value, axis):
    if axis == 'X':
        return axis_value, face_a, face_b
    if axis == 'Z':
        return face_a, face_b, axis_value
    return face_a, axis_value, face_b


def _loft(collection, name, center, profiles, material=None, parent=None, axis='Y', skew=0.0):
    vertices = []
    for depth, width, height, radius in profiles:
        points = _round_rect(width, height, radius)
        vertices.extend(_orient(a + skew * b, b, depth, axis) for a, b in points)
    obj = _mesh(collection, name, center, vertices, _ring_faces(len(points), len(profiles)), material, parent)
    for face in list(obj.data.polygons)[1:-1]:
        face.use_smooth = True
    return obj


def _lathe(collection, name, center, profiles, material, parent, axis='Y', loop=False):
    steps = 96
    vertices = [
        _orient(radius * math.cos(i * math.tau / steps), radius * math.sin(i * math.tau / steps), depth, axis)
        for depth, radius in profiles for i in range(steps)
    ]
    faces = _ring_faces(steps, len(profiles), loop)
    obj = _mesh(collection, name, center, vertices, faces, material, parent)
    sides = obj.data.polygons if loop else list(obj.data.polygons)[1:-1]
    for face in sides:
        face.use_smooth = True
    return obj


def _cut(target, cutters):
    for cutter in cutters:
        boolean = target.modifiers.new("Machined recess", 'BOOLEAN')
        boolean.operation = 'DIFFERENCE'
        boolean.solver = 'EXACT'
        boolean.object = cutter
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(target.evaluated_get(graph), depsgraph=graph)
    old_mesh = target.data
    target.modifiers.clear()
    target.data = mesh
    mesh.name = target.name
    bpy.data.meshes.remove(old_mesh)
    for cutter in cutters:
        tool_mesh = cutter.data
        bpy.data.objects.remove(cutter, do_unlink=True)
        bpy.data.meshes.remove(tool_mesh)


def _mark(collection, name, value, center, size, material, parent):
    font = bpy.data.curves.new(name, 'FONT')
    font.body = value
    font.align_x = 'CENTER'
    font.align_y = 'CENTER'
    font.size = size * MM
    obj = bpy.data.objects.new(name, font)
    collection.objects.link(obj)
    font.materials.append(material)
    obj.rotation_euler.x = math.pi / 2
    _move(obj, parent, center)


def _arm(collection, name, layers, contour, material, parent):
    xs, zs = zip(*contour)
    cx = sum(xs) / len(xs)
    cz = sum(zs) / len(zs)
    vertices = [
        (cx + (x - cx) * scale, depth, cz + (z - cz) * scale)
        for depth, scale in layers for x, z in contour
    ]
    obj = _mesh(collection, name, (0, 0, 0), vertices, _ring_faces(len(contour), len(layers)), material, parent)
    bevel = obj.modifiers.new("Soft machined edges", 'BEVEL')
    bevel.width = 0.62 * MM
    bevel.segments = 3
    normals = obj.modifiers.new("Weighted face normals", 'WEIGHTED_NORMAL')
    normals.keep_sharp = True
    return obj


def _make_optic(collection, parent, name, z, outer, pupil, materials):
    metal, gasket, glass, sensor = materials
    center = (0.0, 0.0, z)
    _lathe(collection, f"{name} / coated lens barrel", center, [
        (-13.55, pupil + 0.57), (-13.55, outer - 0.38), (-13.42, outer - 0.04),
        (-13.16, outer), (-12.94, outer), (-12.61, outer + 0.10),
        (-11.79, outer + 0.10), (-11.79, pupil + 0.36), (-13.35, pupil + 0.36),
    ], metal, parent, loop=True)
    _lathe(collection, f"{name} / optical isolator", center, [
        (-13.61, pupil + 0.04), (-13.55, pupil + 0.30), (-13.49, pupil + 0.56),
        (-13.03, pupil + 0.55), (-12.77, pupil + 0.30), (-12.77, pupil - 0.12),
        (-13.36, pupil - 0.12),
    ], gasket, parent, loop=True)
    _lathe(collection, f"{name} / light trap", center, [
        (-13.229, pupil - 0.18), (-12.95, pupil), (-12.75, pupil),
    ], sensor, parent)
    dome = [(-14.66, 0.12), (-14.645, pupil * 0.36), (-14.51, pupil * 0.66),
            (-14.22, pupil * 0.88), (-13.84, pupil), (-13.58, pupil),
            (-13.36, pupil - 0.12), (-13.27, pupil - 0.32)]
    obj = _lathe(collection, f"{name} / convex optical glass", center, dome, glass, parent)
    obj["surface"] = "Convex coated optical element estimated from product detail photographs"


def build_gimbal(collection):
    """Link the assembly to collection and return its Pan, Roll, Tilt pivots."""
    shell = _material("04P | Graphite-anodized shell", (0.057, 0.060, 0.064), 0.52, 0.33)
    arm = _material("04P | Graphite gimbal alloy", (0.062, 0.065, 0.069), 0.56, 0.37)
    face = _material("04P | Satin milled optical plate", (0.059, 0.061, 0.062), 0.59, 0.31)
    rubber = _material("04P | Black optical isolator", (0.011, 0.013, 0.014), 0.04, 0.52)
    trim = _material("04P | Bead-blast graphite trim", (0.035, 0.037, 0.038), 0.63, 0.33)
    glass = _material("04P | Coated optical glass", (0.057, 0.149, 0.100), 0.06, 0.115,
                      **{"Transmission Weight": 0.52, "IOR": 1.56, "Coat Weight": 0.75,
                         "Coat Roughness": 0.078, "Coat IOR": 1.42})
    sensor = _material("04P | Light trap", (0.010, 0.021, 0.018), 0.10, 0.29)
    contacts = _material("04P | Brushed gold contacts", (0.42, 0.30, 0.115), 0.8, 0.29)
    print_ink = _material("04P | Neutral grey legends", (0.38, 0.39, 0.38), 0.11, 0.49)

    pan = _pivot(collection, "04P | Pan pivot Z", PAN, None, 'Z')
    roll = _pivot(collection, "04P | Roll pivot Y", ROLL, pan, 'Y')
    tilt = _pivot(collection, "04P | Tilt pivot X", TILT, roll, 'X')
    pan["reference"] = "Neutral model span measured on DJI store front image; exact axis centers estimated."
    axes = {"pan": pan, "roll": roll, "tilt": tilt}

    _lathe(collection, "04P | Pan motor rotating collar", PAN, [
        (0.0, 10.1), (0.32, 11.2), (0.76, 11.5), (5.25, 11.5),
        (5.90, 11.10), (7.40, 9.85), (8.30, 9.18),
    ], arm, pan, 'Z')
    _lathe(collection, "04P | Pan seat seam", PAN, [
        (0.05, 10.7), (0.17, 11.35), (0.35, 11.36), (0.58, 11.12),
    ], rubber, pan, 'Z')
    _arm(collection, "04P | Offset rising pan arm", [(2.6, .93), (3.7, 1), (11.0, 1), (12.0, .96)], [
        (-8.5, 105.2), (6.0, 105.0), (9.3, 106.2), (10.9, 109.6),
        (12.4, 113.9), (15.3, 119.4), (21.3, 127.2), (23.5, 133.0),
        (22.2, 137.9), (19.2, 140.5), (15.9, 140.2), (12.1, 137.7),
        (10.2, 130.8), (7.9, 121.4), (3.1, 115.1), (-4.4, 112.6),
        (-8.0, 109.4),
    ], arm, pan)
    _lathe(collection, "04P | Roll motor stator", ROLL, [
        (1.0, 7.07), (1.5, 8.2), (3.35, 8.5), (4.2, 8.23), (4.8, 7.8),
    ], arm, pan)
    _lathe(collection, "04P | Roll motor face", ROLL, [
        (4.79, 7.72), (5.12, 7.72), (5.45, 7.29), (5.57, 6.88),
    ], trim, roll)
    _arm(collection, "04P | Rear roll bridge", [(11.12, .93), (11.77, 1), (13.30, 1), (14.20, .96)], [
        (-23.4, 134.3), (-22.3, 129.8), (-20.0, 127.5), (-15, 126.5),
        (-11.0, 127.9), (3.0, 128.7), (12.3, 129.0), (17.9, 128.8),
        (22.4, 130.4), (23.1, 134.9), (21.1, 140.1), (16.6, 142.1),
        (10.1, 142.0), (-0.9, 141.6), (-10.6, 141.9), (-17.5, 142.1),
        (-21.3, 140.6), (-23.1, 137.2),
    ], arm, roll)
    for side, label in ((-1, "Left"), (1, "Right")):
        _loft(collection, f"04P | {label} tilt support web", (side * 19.15, 0, 135.3), [
            (5.18, 3.75, 7.8, 1.32), (6.85, 5.45, 10.8, 1.94),
            (9.12, 6.42, 12.1, 2.05), (12.1, 5.80, 11.4, 1.96),
        ], arm, roll)
        side_casing = [
            (16.12, 9.10), (16.49, 9.49), (17.13, 9.77), (22.42, 9.77),
            (23.29, 9.49), (23.77, 9.03), (23.9, 8.48),
        ]
        _lathe(collection, f"04P | {label} tilt side casing", TILT,
              sorted((side * x, r) for x, r in side_casing), arm, roll, 'X')
        cap_profile = [(23.93, 8.45), (24.15, 8.65), (24.38, 8.45),
                       (24.64, 7.75), (24.70, 7.13)]
        _lathe(collection, f"04P | {label} tilt motor end cap", TILT,
              sorted((side * x, r) for x, r in cap_profile), shell, roll, 'X')

    head_center = (0.0, 0.0, 135.45)
    _loft(collection, "04P | Dual camera rear housing", head_center, [
        (-13.04, 28.3, 43.8, 6.45), (-12.79, 30.6, 46.2, 7.40),
        (-11.85, 32.1, 47.6, 8.05), (-9.45, 32.6, 48.1, 8.30),
        (3.65, 32.6, 48.1, 8.30), (7.52, 32.06, 47.64, 8.20),
        (8.95, 30.77, 46.95, 7.68), (9.73, 29.68, 46.1, 7.42),
    ], shell, tilt)
    optical_plate = _loft(collection, "04P | Milled dual-pocket optical face", head_center, [
        (-16.04, 31.32, 46.99, 7.74), (-15.98, 31.52, 47.24, 7.90),
        (-15.70, 31.99, 47.73, 8.03), (-14.99, 32.42, 48.00, 8.19),
        (-14.31, 32.55, 48.09, 8.26), (-13.10, 32.55, 48.09, 8.26),
        (-12.82, 32.30, 47.81, 8.12),
    ], face, tilt)
    cutters = []
    for label, z, w, h, inner_w, inner_h, radius in (
        ("Tele", 147.6, 23.9, 17.55, 15.3, 15.10, 4.24),
        ("Wide", 125.8, 24.8, 21.48, 17.2, 16.9, 4.42),
    ):
        cutters.append(_loft(collection, f"{label} recess tool", (0, 0, z), [
            (-16.8, w, h, radius), (-15.97, w, h, radius),
            (-15.68, w - 0.27, h - 0.20, radius),
            (-15.05, (w + inner_w) / 2, (h + inner_h) / 2, radius),
            (-14.39, inner_w, inner_h, radius),
            (-13.9, inner_w, inner_h, radius), (-12.36, inner_w, inner_h, radius),
        ], parent=tilt))
    _cut(optical_plate, cutters)
    optical_plate["reference"] = "DJI official hero and head detail. Pocket depths estimated."

    optics = (trim, rubber, glass, sensor)
    _make_optic(collection, tilt, "04P | 3X telephoto", 147.6, 7.26, 4.35, optics)
    _make_optic(collection, tilt, "04P | 1-inch wide angle", 125.8, 8.06, 3.10, optics)
    _mark(collection, "04P | Telephoto legend", "3X", (0, -16.055, 137.18), 1.72, print_ink, tilt)
    _mark(collection, "04P | Sensor legend", "1-INCH", (0, -16.055, 113.74), 1.53, print_ink, tilt)

    for z, name in ((148.35, "Upper"), (120.55, "Lower")):
        insert = _loft(collection, f"04P | {name} rear cooling bank", (0, 0, z), [
            (9.39, 16.60, 9.15, 2.60), (9.85, 16.60, 9.15, 2.60),
            (10.13, 16.22, 8.78, 2.44), (10.28, 15.88, 8.53, 2.35),
        ], shell, tilt)
        slots = []
        for slot in range(8):
            x = (slot - 3.5) * 1.57
            height = 5.83 - 0.06 * abs(slot - 3.5) ** 2
            profiles = [(9.77, 0.63, height - 0.18, 0.26), (10.20, 0.76, height, 0.32),
                        (10.55, 0.80, height + 0.08, 0.34)]
            slots.append(_loft(collection, f"{name} rear air slot tool {slot + 1}", (x, 0, z),
                               profiles, parent=tilt, skew=0.26))
        _cut(insert, slots)

    contact_center = (17.65, 0, 135.3)
    _loft(collection, "04P | Accessory contact insulator", contact_center, [
        (15.32, 8.3, 2.65, 1.12), (15.71, 8.5, 2.67, 1.13),
        (16.13, 8.1, 2.42, 1.02),
    ], rubber, roll)
    for contact in range(3):
        x = contact_center[0] + (contact - 1) * 2.05
        _lathe(collection, f"04P | Gold accessory contact {contact + 1}", (x, 0, contact_center[2]), [
            (16.03, 0.48), (16.11, 0.49), (16.20, 0.40),
        ], contacts, roll)

    return axes
