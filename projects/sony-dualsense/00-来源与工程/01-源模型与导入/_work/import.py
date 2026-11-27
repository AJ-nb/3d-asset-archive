from pathlib import Path
from mathutils import Vector
import bpy
src=next(Path('_work/source').glob('*.fbx'))
bpy.ops.import_scene.fbx(filepath=str(src))
dg=bpy.context.evaluated_depsgraph_get()
for o in sorted(bpy.context.scene.objects,key=lambda v:v.name):
 if o.type!='MESH': print('NONMESH',o.name,o.type); continue
 bb=[o.matrix_world @ Vector(c) for c in o.bound_box]
 mm=[tuple(round(fn(p[i] for p in bb),5) for i in range(3)) for fn in (min,max)]
 print('MESH',repr(o.name),'verts',len(o.data.vertices),'polys',len(o.data.polygons),'bounds',mm,'mats',[(m.name if m else None) for m in o.data.materials],flush=True)
for m in bpy.data.materials:
 print('MAT',m.name,m.diffuse_color[:],[(n.name,n.type) for n in m.node_tree.nodes] if m.node_tree else [],flush=True)
bpy.ops.wm.save_as_mainfile(filepath=str(Path('_work/import.blend').resolve()))
