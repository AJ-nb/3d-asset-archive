"""Create a localized, non-emitting graphite grain study in Blender."""

from math import cos, exp, floor, hypot, isfinite, pi, sin
from random import Random

import bpy


def _graphite_material(name, grey, roughness, metallic):
    material = bpy.data.materials.get(name)
    if material is not None:
        return material
    material = bpy.data.materials.new(name)
    # A faint cool bias in the graphite leaves the color of the key light legible.
    rgba = (grey * 0.94, grey, grey * 1.06, 1.0)
    material.diffuse_color = rgba
    shader = next(node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED")
    shader.inputs["Base Color"].default_value = rgba
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    return material


def build_tactile_field(
    scene,
    *,
    origin=(1.37834, 0.23403, 0.0),
    radius=0.82,
    count=1400,
    seed=82,
    direction=(0.36, -0.93),
    max_lift=0.055,
):
    """Link and return a collection with one editable, deterministic mesh.

    Origin marks contact with the stage. Radius limits the field in scene units.
    Direction points along the stage toward the visible part of the pressure front.
    Max lift bounds the clearance of a grain above the stage.
    """
    if not isfinite(radius) or radius <= 0:
        raise ValueError("radius must be a finite positive number")
    if not isinstance(count, int) or count < 1:
        raise ValueError("count must be a positive integer")
    if not isfinite(max_lift) or max_lift < 0:
        raise ValueError("max_lift must be finite and nonnegative")
    ox, oy, oz = origin
    dx, dy = direction
    length = hypot(dx, dy)
    if length == 0 or not all(map(isfinite, (ox, oy, oz, length))):
        raise ValueError("origin and direction must be finite, with nonzero direction")
    dx, dy = dx / length, dy / length

    rng = Random(seed)
    vertices, faces, material_indices = [], [], []
    occupied = {}
    grain_scale = radius / 0.82
    cell_width = 0.031 * grain_scale
    placed_count = 0
    lifted_count = 0
    for _ in range(count * 14):
        # Bias the field along the grip-to-viewer axis and keep the outskirts sparse.
        angle = rng.gauss(-0.10, 0.49)
        if abs(angle) > 1.13:
            continue
        crest = 0.395 + 0.023 * sin(angle * 5.0 + 0.5) + 0.013 * sin(angle * 10.0)
        if rng.random() < 0.54:
            radial = rng.gauss(crest, 0.091)
        else:
            radial = 0.13 + 0.86 * rng.random() ** 1.54
        if not 0.13 <= radial < 0.98:
            continue
        distance = radius * radial
        ahead = distance * cos(angle)
        sideways = distance * sin(angle)
        x = ox + dx * ahead - dy * sideways
        y = oy + dy * ahead + dx * sideways
        width = grain_scale * (0.0032 + 0.0095 * rng.random() ** 2.45)
        if distance + width >= radius:
            continue
        cell = floor(x / cell_width), floor(y / cell_width)
        if any(
            (x - px) ** 2 + (y - py) ** 2 < (width + previous_width) ** 2
            for ix in range(cell[0] - 1, cell[0] + 2)
            for iy in range(cell[1] - 1, cell[1] + 2)
            for px, py, previous_width in occupied.get((ix, iy), ())
        ):
            continue
        occupied.setdefault(cell, []).append((x, y, width))
        placed_count += 1

        crest_weight = exp(-0.5 * ((radial - crest) / 0.108) ** 2)
        angle_weight = exp(-0.5 * ((angle + 0.10) / 0.50) ** 2)
        close_weight = max(0.0, 1.0 - (radial - 0.13) / 0.59) ** 1.35
        energy = min(1.0, (0.86 * crest_weight + 0.14 * close_weight) * angle_weight)
        lift = 0.0
        if rng.random() < energy * 0.69:
            lift = max_lift * energy * (0.17 + 0.83 * rng.random() ** 1.8)
        lifted_count += int(lift > 0.0005 * grain_scale)

        height = width * rng.uniform(0.56, 1.10)
        z = oz + max(0.0002 * grain_scale, lift)
        rotation = rng.uniform(-pi, pi)
        sides = rng.choice((5, 6, 6))
        first = len(vertices)
        for j in range(sides):
            vertex_angle = rotation + 2 * pi * j / sides + rng.uniform(-0.15, 0.15)
            vertex_width = width * rng.uniform(0.58, 0.98)
            vertices.append((
                x + vertex_width * cos(vertex_angle),
                y + vertex_width * sin(vertex_angle),
                z + height * rng.uniform(0.18, 0.56),
            ))
        crown = len(vertices)
        vertices.append((x + width * rng.uniform(-0.32, 0.32),
                         y + width * rng.uniform(-0.32, 0.32), z + height))
        base = len(vertices)
        vertices.append((x, y, z))
        pigment = rng.choices((0, 1, 2), weights=(0.45, 0.44, 0.11))[0]
        for j in range(sides):
            this_vertex = first + j
            next_vertex = first + (j + 1) % sides
            faces.extend(((this_vertex, next_vertex, crown), (next_vertex, this_vertex, base)))
            material_indices.extend((pigment, 0))
        if placed_count == count:
            break

    mesh = bpy.data.meshes.new("Graphite grains | individual closed facets")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    for brief in (
        ("Graphite | Carbon", 0.042, 0.62, 0.12),
        ("Graphite | Slate", 0.072, 0.53, 0.17),
        ("Graphite | Glint", 0.115, 0.43, 0.22),
    ):
        mesh.materials.append(_graphite_material(*brief))
    mesh.polygons.foreach_set("material_index", material_indices)

    collection = bpy.data.collections.new("FX | Tactile contact graphite")
    scene.collection.children.link(collection)
    grains = bpy.data.objects.new("Graphite | Resting and lifted grains", mesh)
    collection.objects.link(grains)
    grains["Contact origin"] = tuple(origin)
    grains["Field direction"] = (dx, dy)
    grains["Field radius"] = radius
    grains["Maximum lift"] = max_lift
    grains["Requested grain count"] = count
    grains["Placed grain count"] = placed_count
    grains["Lifted grains"] = lifted_count
    grains["Seed"] = seed
    grains["Description"] = "Art-directed pressure response. All graphite grains use reflective materials."
    return collection
