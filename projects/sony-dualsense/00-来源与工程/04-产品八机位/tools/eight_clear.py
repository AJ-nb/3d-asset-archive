"""Shot 03: the original DualSense shape with a translucent shell study."""

from collections import defaultdict
from math import radians

import bpy
from mathutils import Quaternion

from build_studio import (
    PARTS, camera_rig, collection, floor_stage, set_area, setup_scene, shot_scene,
    studio_world,
)


HOUSING = "Housing | shell, touchpad, controls and ports"
WHITE_SHELL = "Shell | frost-white satin polymer"


def outer_shell_faces(mesh, slot):
    """Find the three original shell panels by their connected spans."""
    parents = list(range(len(mesh.vertices)))

    def component(vertex):
        while parents[vertex] != vertex:
            parents[vertex] = parents[parents[vertex]]
            vertex = parents[vertex]
        return vertex

    for edge in mesh.edges:
        v1, v2 = edge.vertices
        parents[component(v1)] = component(v2)

    faces_by_component = defaultdict(list)
    for face in mesh.polygons:
        if face.material_index == slot:
            faces_by_component[component(face.vertices[0])].append(face)

    panels = []
    for faces in faces_by_component.values():
        verts = [mesh.vertices[index].co for face in faces for index in face.vertices]
        span_z = max(co.z for co in verts) - min(co.z for co in verts)
        span_x = max(co.x for co in verts) - min(co.x for co in verts)
        if span_z > 1.5 and span_x > .7:
            panels.append(faces)
    if len(panels) != 3:
        raise RuntimeError(f"Expected three outer shell panels, found {len(panels)}")
    return [face for panel in panels for face in panel]


def smoked_ice(source):
    material = source.copy()
    material.name = "Shell concept | Smoked ice polymer"
    material.diffuse_color = (.27, .54, .62, 1)
    tree = material.node_tree
    shader = next(node for node in tree.nodes if node.type == "BSDF_PRINCIPLED")
    shader.label = "Translucent molded polymer"
    shader.inputs["Base Color"].default_value = (.49, .72, .77, 1)
    shader.inputs["Transmission Weight"].default_value = .91
    shader.inputs["IOR"].default_value = 1.47
    shader.inputs["Coat Weight"].default_value = .16
    shader.inputs["Coat Roughness"].default_value = .18
    shader.inputs["Metallic"].default_value = 0
    roughness = shader.inputs["Roughness"].links[0].from_node
    roughness.label = "Frosted roughness range"
    roughness.inputs["To Min"].default_value = .14
    roughness.inputs["To Max"].default_value = .22
    for node in tree.nodes:
        if node.type == "BUMP":
            node.inputs["Strength"].default_value *= .50
    return material


def build_clear(source):
    """Build an editable 4:5 Cycles scene without changing the original mesh or CMF."""
    original = bpy.data.collections[PARTS]
    scene = shot_scene(source, "03 Material | Smoked Ice", original, "03-smoked-ice", (3072, 3840))
    scene.collection.children.unlink(original)
    scene.compositing_node_group = None
    variant = collection(scene, "03 Product | Shell material study")
    for obj in original.objects:
        if obj.name != HOUSING:
            variant.objects.link(obj)
            continue
        housing = obj.copy()
        housing.name = "03 Housing | Original panels with concept CMF"
        housing.data = obj.data.copy()
        housing.data.name = "03 Housing | Original geometry with shell material slot"
        variant.objects.link(housing)
        mesh = housing.data
        shell_slot = list(mesh.materials).index(bpy.data.materials[WHITE_SHELL])
        faces = outer_shell_faces(mesh, shell_slot)
        mesh.materials.append(smoked_ice(mesh.materials[shell_slot]))
        for face in faces:
            face.material_index = len(mesh.materials) - 1

    scene.world = studio_world(source)
    scene.world.name = "03 World | Dark neutral bounce"
    background = next(node for node in scene.world.node_tree.nodes if node.type == "BACKGROUND")
    background.inputs["Color"].default_value = (.38, .43, .49, 1)
    background.inputs["Strength"].default_value = .22
    floor_stage(source, scene, "03 Set | Mineral graphite", (.019, .026, .032), .32)
    camera, _ = camera_rig(scene, "03 Camera | Left elevated 82mm", (-.06, .02, .97), -45, 36, 9.8, 82)
    view = camera.rotation_euler.to_quaternion()
    camera.rotation_mode = "QUATERNION"
    camera.rotation_quaternion = view @ Quaternion((0, 0, 1), radians(-5))

    lights = collection(scene, "03 Lighting | Transmission and shell edge")
    for spec in (
        ("Eye key | Soft neutral", (-2.4, -4.55, 5.4), (0, 0, 1.05), 360, 4.1, 2.2, (1, .98, .95)),
        ("Edge left | White strip", (-3.2, .95, 2.45), (-1.0, .0, 1.10), 210, .40, 3.4, (.87, .94, 1)),
        ("Edge right | Warm strip", (3.6, -.9, 3.75), (1.1, 0, 1.35), 167, .62, 2.65, (1, .83, .65)),
        ("Transmission | Frost bank", (2.95, 2.4, 2.72), (.5, .12, .91), 425, 2.1, 2.7, (.56, .85, 1)),
        ("Transmission | White heel strip", (-.53, 2.32, .70), (-.74, -.1, .84), 121, 1.94, .37, (.80, .91, 1)),
        ("Stage | Far cyan wash", (.93, 3.3, 2.0), (1.0, 3.12, 0), 216, 3.7, 1.43, (.32, .67, .84)),
        ("Stage | Foreground white stripe", (-3.63, -1.5, 2.4), (-.42, .62, 0), 115, 3.3, .31, (.94, .98, 1)),
    ):
        set_area(lights, *spec)

    setup_scene(scene, 224)
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "16"
    scene.cycles.max_bounces = 12
    scene.cycles.transmission_bounces = 10
    scene.view_settings.exposure = .18
    scene["Concept"] = "The three source shell panels use a translucent concept material. Controls and touchpad retain source CMF."
    scene["Model scope"] = "The supplied model includes exterior parts. No internal electronics are depicted."
    return scene
