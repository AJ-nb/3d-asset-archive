"""Rephotograph the four archived installations from complementary visitor and material viewpoints."""
from pathlib import Path
import sys, json
import bpy
from mathutils import Vector
W = Path(__file__).resolve().parent
sys.path.insert(0,str(W))
import v3_common as c
from verify_geometry import mesh_fingerprint
OUT=c.OUT/'concepts'
DATA=[
    ('C1','dock-floor','Dry dock at pedestrian level',(2560,1440),(-12.5,-31.5,4.65),(-.4,1.2,4.12),35),
    ('C2','relief-transect','Across the hundredfold grip relief',(2000,1500),(4.20,-4.16,3.15),(.84,.55,1.39),43),
    ('C3','clay-contact','Contact at the wet stoneware lip',(2000,1500),(-4.45,-5.48,4.10),(-.89,-.27,.51),75),
    ('C4','under-the-grips','Inside the lakeside changing pavilion',(2400,1500),(4.65,-9.65,2.60),(-.75,.67,2.83),30),
]
def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    initial=bpy.context.scene
    with bpy.data.libraries.load(str(W.parent/'delivery-faceup-v2'/'DualSense-Photography-V2.blend'),link=False) as (src,dest):
        dest.scenes=sorted(s for s in src.scenes if s[:2] in ('05','06','07','08'))
    scenes=dest.scenes
    with bpy.data.libraries.load(str(W/'base.blend'),link=False) as (src,dest):
        dest.collections=[c.PRODUCT]
    model=dest.collections[0]
    models_by_hash={mesh_fingerprint(o.data):o for o in model.objects}
    assert len(models_by_hash)==12
    report={}
    for sc,(no,slug,title,size,eye,target,lens) in zip(scenes,DATA):
        bpy.context.window.scene=sc
        sc.name=no+' | '+title
        sc.frame_set(1)
        cam=sc.camera
        for obj in sc.objects:
            if obj.name.startswith('Visitor |'):
                direction=Vector(eye)-obj.location
                direction.z=0
                obj.rotation_euler=direction.to_track_quat('-Y','Z').to_euler()
            coll=obj.instance_collection
            if coll and len(coll.objects)==12 and all(o.type=='MESH' for o in coll.objects):
                if set(mesh_fingerprint(o.data) for o in coll.objects)==set(models_by_hash):
                    obj.instance_collection=model
        if no=='C3':
            for group in sc.collection.children:
                if 'Product placement' in group.name:
                    for obj in group.all_objects:
                        if obj.type!='MESH': continue
                        h=mesh_fingerprint(obj.data)
                        if h in models_by_hash: obj.data=models_by_hash[h].data
        sc.camera=cam
        cam.name=no+' | '+title
        cam.location=eye
        c.aim(cam,target)
        cam.data.lens=lens
        cam.data.shift_x=cam.data.shift_y=0
        cam.data.dof.use_dof=False
        sc.render.resolution_x,sc.render.resolution_y=size
        sc.render.resolution_percentage=100
        sc.render.filepath='//masters/'+no+'-'+slug+'.png'
        sc.render.image_settings.file_format='PNG'
        sc.render.image_settings.color_mode='RGB'
        sc.render.image_settings.color_depth='16'
        sc.cycles.samples=192
        sc.cycles.adaptive_threshold=.010
        sc.cycles.adaptive_min_samples=24
        sc.cycles.device='CPU'
        sc.camera=cam
        if no=='C4':
            c.area(sc,'Soft skylight into the soffit',(-3.4,-4.5,3.20),(-2.4,.8,3.5),490,5.0,2.8,(.88,.93,1.))
        if no=='C2':
            for ob in sc.objects:
                if ob.type=='LIGHT' and ob.data.type=='SUN':
                    ob.rotation_euler=Vector((.87,-.39,-.177)).to_track_quat('-Z','Y').to_euler()
        bpy.context.view_layer.update()
        pts=[i.object.original.data.as_pointer() for i in bpy.context.evaluated_depsgraph_get().object_instances if i.object.type=='MESH']
        found=sum(pts.count(o.data.as_pointer()) for o in model.objects)
        assert found==(0 if no=='C2' else 12),(no,found)
        report[no]=dict(camera=list(eye),focus=list(target),lens_mm=lens,size=size,master=sc.render.filepath,shared_product_parts=found)
        if no=='C2':
            land=next(o for o in sc.objects if 'XY magnification' in o)
            assert land['XY magnification']==land['Z magnification']==100
            report[no]['surface_parameters']={k:land[k] for k in land.keys() if isinstance(land[k],(str,int,float))}
        if no in ('C1','C4'):
            inst=next(o for o in sc.objects if o.instance_collection==model)
            report[no]['model_bounds_m']=list(inst['overall_dimensions_m'])
        assert any(m.frame==1 and m.camera==cam for m in sc.timeline_markers)
    bpy.context.window.scene=scenes[0]
    bpy.data.scenes.remove(initial)
    bpy.data.orphans_purge(do_recursive=True)
    external=[(lib.name,[x.name for x in lib.users_id]) for lib in bpy.data.libraries]
    print('EXTERNAL',external,flush=True)
    assert not any(used for lib,used in external)
    for lib in list(bpy.data.libraries):
        bpy.data.libraries.remove(lib)
    assert all(i.packed_files for i in bpy.data.images if i.source in ('FILE','TILED'))
    c.save(OUT/'DualSense-Concept-Studies.blend')
    (c.OUT/'qa').mkdir(exist_ok=True)
    (c.OUT/'qa'/'concept-scenes.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return scenes

if __name__=='__main__':
    if 'native' in sys.argv:
        for scene in sorted(bpy.data.scenes,key=lambda s:s.name):
            if scene.name.startswith('C') and scene.name[:2] in [d[0] for d in DATA]:
                c.render(scene,OUT/'masters')
    else:
        for sc in build():
            c.render(sc,W/'concept-proofs',preview=True)
