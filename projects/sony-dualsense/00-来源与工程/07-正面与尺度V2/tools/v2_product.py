"""Stage four photographs using the archival meshes and independent photo finishes."""

from math import cos, radians, sin
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

from build_studio import aim, set_area


ASSETS = Path(__file__).resolve().parents[1] / "v2-work" / "product"


def shader(mat):
    return next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def finish(source):
    mat = source.copy()
    mat.name = "Photo finish | " + source.name.split(" | ")[0]
    bs = shader(mat)
    # Calibrate the fine tooling and response of the original layered surfaces.
    finishes = {
        "Shell": ((.64, .665, .72), (.41, .52), 290, .0021, .58, .014),
        "Inner housing": ((.015, .019, .033), (.54, .63), 263, .00155, .49, .012),
        "Stick caps": ((.024, .029, .039), (.66, .78), 235, .0041, .67, 0),
        "Stick shafts": ((.014, .019, .024), (.42, .50), 269, .0012, .42, .014),
        "Shoulders": ((.021, .025, .034), (.46, .57), 232, .0021, .50, .018),
    }
    family = source.name.split(" | ")[0]
    if family in finishes:
        color, limits, grain, relief, strength, coat = finishes[family]
        nodes = mat.node_tree.nodes
        bs.inputs["Base Color"].default_value = (*color, 1)
        bs.inputs["Coat Weight"].default_value = coat
        nodes["Map Range"].inputs["To Min"].default_value = limits[0]
        nodes["Map Range"].inputs["To Max"].default_value = limits[1]
        nodes["Noise Texture"].inputs["Scale"].default_value = grain
        nodes["Bump"].inputs["Distance"].default_value = relief
        nodes["Bump"].inputs["Strength"].default_value = strength
        if family == "Stick caps":
            bs.inputs["Specular IOR Level"].default_value = .26
            bs.inputs["Sheen Weight"].default_value = .045
        if family == "Stick shafts":
            bs.inputs["Specular IOR Level"].default_value = .41
        if family == "Shell":
            nodes["Bump.001"].inputs["Distance"].default_value = .0015
    elif family == "Keycap overmold":
        bs.inputs["Base Color"].default_value = (.973, .980, .992, 1)
        bs.inputs["Roughness"].default_value = .082
        bs.inputs["Transmission Weight"].default_value = 1
        bs.inputs["Coat Weight"].default_value = .018
    elif family == "Keycap core":
        bs.inputs["Base Color"].default_value = (.78, .78, .80, 1)
        bs.inputs["Roughness"].default_value = .38
    elif family == "Glyphs":
        bs.inputs["Base Color"].default_value = (.119, .131, .157, 1)
    elif family == "Light pipe":
        bs.inputs["Emission Color"].default_value = (.09,.18,.84,1)
        bs.inputs["Emission Strength"].default_value = .55
    return mat


def photo_assembly(source):
    collection = bpy.data.collections.new("Photography | original meshes, photo finishes")
    materials = {}
    for original in source.objects:
        obj = original.copy()
        obj.name = "Photo | " + original.name
        collection.objects.link(obj)
        for slot in obj.material_slots:
            mat = slot.material
            if mat not in materials:
                materials[mat] = finish(mat)
            slot.link = "OBJECT"
            slot.material = materials[mat]
        assert obj.data == original.data
    return collection


def surface_material(asset):
    name = "Photography table | " + asset
    cached = bpy.data.materials.get(name)
    if cached:
        return cached
    mat = bpy.data.materials.new(name)
    nodes, links, bs = mat.node_tree.nodes, mat.node_tree.links, shader(mat)
    maps = {}
    for channel in ("diff", "rough", "nor_gl"):
        image = bpy.data.images.load(str(ASSETS / f"{asset}_{channel}.jpg"), check_existing=True)
        image.colorspace_settings.name = "sRGB" if channel == "diff" else "Non-Color"
        if not image.packed_file:
            image.pack()
        tex = nodes.new("ShaderNodeTexImage")
        tex.name = asset + " " + channel
        tex.image = image
        maps[channel] = tex.outputs["Color"]
    # Tone a photographed timber or honed stone swatch to a plausible tabletop finish.
    grade = nodes.new("ShaderNodeHueSaturation")
    wood = asset == "smoked_walnut_veneer"
    grade.inputs["Saturation"].default_value = .86 if wood else .67
    grade.inputs["Value"].default_value = .27 if wood else .86
    links.new(maps["diff"], grade.inputs["Color"])
    links.new(grade.outputs[0], bs.inputs["Base Color"])
    rough = nodes.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = .48 if wood else .51
    rough.inputs["To Max"].default_value = .68 if wood else .80
    links.new(maps["rough"], rough.inputs[0])
    links.new(rough.outputs[0], bs.inputs["Roughness"])
    normal = nodes.new("ShaderNodeNormalMap")
    normal.inputs["Strength"].default_value = .27 if wood else .48
    links.new(maps["nor_gl"], normal.inputs["Color"])
    links.new(normal.outputs[0], bs.inputs["Normal"])
    bs.inputs["Specular IOR Level"].default_value = .36
    return mat


def tabletop(scene, asset, size, angle, offset):
    coll = next(c for c in scene.collection.children if "Infinity sweep" in c.name)
    scene.collection.children.unlink(coll)
    material = surface_material(asset)
    mesh = bpy.data.meshes.new(scene.name[:2] + " | tabletop with photographed surface")
    corners = [(-100,-100), (100,-100), (100,100), (-100,100)]
    mesh.from_pydata([(x,y,-.0003) for x,y in corners], [], [(0,1,2,3)])
    mesh.update()
    layer = mesh.uv_layers.new(name="Grain direction")
    a, b = cos(radians(angle)), sin(radians(angle))
    for idx, (x, y) in enumerate(corners):
        layer.uv[idx].vector = ((a*x-b*y)/size+offset[0], (b*x+a*y)/size+offset[1])
    mesh.materials.append(material)
    obj = bpy.data.objects.new(mesh.name, mesh)
    scene.collection.objects.link(obj)


def lens(cam, target, azimuth, elevation, distance, focal, focus=None, fstop=3):
    target = Vector(target)
    a, e = radians(azimuth), radians(elevation)
    cam.location = target + distance * Vector((sin(a)*cos(e), -cos(a)*cos(e), sin(e)))
    aim(cam, target)
    cam.data.type = "PERSP"
    cam.data.lens = focal
    cam.data.dof.use_dof = focus is not None
    if focus is not None:
        optical_axis = (target - cam.location).normalized()
        cam.data.dof.focus_distance = (Vector(focus) - cam.location).dot(optical_axis)
        cam.data.dof.aperture_fstop = fstop
        cam.data.dof.aperture_blades = 9


def light(scene, world_strength, specs):
    group = next(c for c in scene.collection.children if "Reflection cards" in c.name)
    for obj in list(group.objects):
        group.objects.unlink(obj)
    bg = next(n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (.76,.80,.89,1)
    bg.inputs[1].default_value = world_strength
    for name, loc, target, power, w, h, col in specs:
        set_area(group, scene.name[:2] + " | " + name, loc, target, power, w, h, col)


def rotate(carrier, yaw):
    change = Matrix.Rotation(radians(yaw)-carrier.rotation_euler.z, 3, "Z")
    carrier.location = change @ carrier.location
    carrier.rotation_euler.z = radians(yaw)
    carrier["Yaw in degrees"] = yaw
    return Matrix.Rotation(radians(yaw), 3, "Z")


def revise():
    scenes = sorted((s for s in bpy.data.scenes if s.name[:3] in ("01 ", "02 ", "03 ", "04 ")), key=lambda s:s.name)
    assert len(scenes) == 4
    source = next(o for o in scenes[0].objects if o.instance_collection).instance_collection
    product = photo_assembly(source)
    near = (1,.945,.885)
    sky = (.81,.89,1)
    neutral = (.98,.985,1)
    yaws = (9, 27, -11, 18)
    for scene, yaw in zip(scenes,yaws):
        carrier = next(o for o in scene.objects if o.instance_collection)
        carrier.instance_collection = product
        spin = rotate(carrier,yaw)
        scene.view_settings.exposure = .12
        scene.cycles.samples = 128
        scene.cycles.adaptive_threshold = .013
        scene.cycles.adaptive_min_samples = 24
        index = scene.name[:2]
        if index == "01":
            tabletop(scene, "marble_01", 21.0, -13, (.485,.885))
            lens(scene.camera, (.04,.01,.52), -2, 68, 11.65, 88)
            light(scene,.075,[
                ("Large studio window", (-3.9,1.55,3.9), (-.5,-.2,.45), 645, 2.45, 2.1, near),
                ("Opposite silk", (3.4,-1.0,2.55), (.62,.1,.64), 55, 2.8, 3.6, sky),
                ("Frontal white card", (.4,-4.5,2.6), (-.4,-.22,.9), 51, 3.2, 1.7, neutral),
            ])
        elif index == "02":
            tabletop(scene, "smoked_walnut_veneer", 11.6, 28, (.52,.42))
            lens(scene.camera, (.03,.025,.56), 165, 34, 10.7, 81)
            light(scene,.067,[
                ("North window", (-3.4,-1.6,5.4), (.22,.06,.75), 575, 2.05, 2.8, neutral),
                ("Warm leaf bounce", (-2.5,2.9,2.3), (.3,.4,.65), 87, 2.55, 1.85, (1,.86,.72)),
                ("Ceiling return", (2.6,3.8,4.2), (-.3,.3,.8), 136, 2.3, 2.9, sky),
            ])
        elif index == "03":
            tabletop(scene, "marble_01", 21.0, -13, (.485,.885))
            target = spin @ Vector((1.03,.46,1.05))
            focus = spin @ Vector((1.06,.45,1.15))
            lens(scene.camera, target, 35, 34, 4.52, 103, focus, 2.0)
            light(scene,.085,[
                ("Narrow bank across caps", (-2.8,1.8,3.5), (.95,.4,1.02), 385, 1.2, 3.0, neutral),
                ("Etched edge on near side", (3.6,-2.4,2.90), (.88,.47,1.04), 95, .37, 2.8, sky),
                ("Contour fill", (1.65,3.8,1.9), (.65,.74,.94), 70, 2.3, 2.1, near),
            ])
        else:
            tabletop(scene, "smoked_walnut_veneer", 11.6, 28, (.52,.42))
            target = spin @ Vector((-.32,.038,1.064))
            focus = spin @ Vector((-.54,-.03,1.235))
            lens(scene.camera, target, -14, 29, 4.15, 102, focus, 1.7)
            light(scene,.073,[
                ("Grazing crepe-rubber light", (-2.4,-1.35,2.75), (-.35,.05,1.08), 295, 1.1, 2.1, near),
                ("Touch surface silk", (2.65,2.2,3.2), (0,.2,.9), 176, 2.6, 2.9, sky),
                ("Quiet camera fill", (.25,-3.4,2), (-.1,-.06,.82), 25, 2.7, 1.45, neutral),
            ])
    return tuple(scenes)
