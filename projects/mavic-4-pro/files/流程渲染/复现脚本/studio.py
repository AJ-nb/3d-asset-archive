"""Art-directed photographs and reproducible Cycles camera presets, scene dimensions in metres."""
import json
from math import atan
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from stage_contact import contact_plane

ROOT='AIRCRAFT  |  millimetre model space'
SCENES={
    '01-hero':('展开主视觉',(0,0,64),(365,-750,365),None,3000,1900,1,'ink'),
    '02-plan':('展开平面形态',(0,0,65),(0,-.1,930),None,2400,1900,1,'paper'),
    '03-optics':('三摄与云台支承',(0,-150,66),(128,-530,89),159,2350,1570,1,'ink'),
    '04-hinge':('前机臂铰接',(65,-90,71),(240,-170,260),101,2200,1500,1,'paper'),
    '05-service':('电池与尾部装配',(0,150,67),(-130,435,235),258,2300,1550,101,'paper'),
    '06-motion':('机构动作中段',(0,0,64),(-369,-680,470),None,2400,1580,55,'float'),
    '07-neutral':('主视觉中性光复核',(0,0,64),(365,-750,365),None,2000,1266,1,'paper'),
    '08-cutout':('透明主视觉',(0,0,64),(365,-750,365),None,3000,1900,1,'alpha'),
}
def lookat(obj,point):
    obj.rotation_euler=(Vector(point)-obj.location).to_track_quat('-Z','Y').to_euler()
def vec(x):return Vector(x)*.001
def obj_in(col,name,data):
    ob=bpy.data.objects.new(name,data);col.objects.link(ob);return ob
def get_cam(key):return bpy.data.objects['Photo / '+key]
def framing(cam,root,aspect,frames=None):
    right,up=[cam.rotation_euler.to_matrix()@Vector(v) for v in ((1,0,0),(0,1,0))]
    dirs=np.array((right,up)).T;bounds=[]
    dg=bpy.context.evaluated_depsgraph_get()
    initial=bpy.context.scene.frame_current
    for frame in frames or [initial]:
        bpy.context.scene.frame_set(frame)
        for ob in root.children_recursive:
            if ob.type not in {'MESH','CURVE','FONT','SURFACE'} or ob.hide_render:continue
            ev=ob.evaluated_get(dg);mesh=ev.to_mesh()
            if mesh and mesh.vertices:
                co=np.empty(3*len(mesh.vertices),'f');mesh.vertices.foreach_get('co',co)
                mat=np.asarray(ev.matrix_world)
                points=(co.reshape(-1,3)@mat[:3,:3].T+mat[:3,3])@dirs
                bounds.extend((points.min(axis=0),points.max(axis=0)))
            ev.to_mesh_clear()
    bpy.context.scene.frame_set(initial)
    lo,hi=np.array(bounds).min(axis=0),np.array(bounds).max(axis=0)
    offset=(lo+hi)/2-np.asarray(cam.location)@dirs
    cam.location+=right*float(offset[0])+up*float(offset[1])
    cam.data.ortho_scale=float(max(hi[0]-lo[0],aspect*(hi[1]-lo[1]))/.86)

def setup(root):
    scene=bpy.context.scene
    for c in bpy.data.collections:
        if c.name.startswith(('05  /','06  /','07  /')):c.hide_render=True;c.hide_viewport=True
    for mark in list(scene.timeline_markers):scene.timeline_markers.remove(mark)
    if scene.sequence_editor:scene.sequence_editor_clear()
    gallery=bpy.data.collections.new('08  /  Photography');scene.collection.children.link(gallery)
    gallery.hide_select=True
    for name,position,target,size,power,color in [
        ('Key',(-365,-290,540),(0,-24,68),(.52,.36),26,(1,.93,.83)),
        ('Fill',(220,-415,187),(0,-100,63),(.26,.47),9,(.82,.90,1)),
        ('Strip',(250,320,310),(0,12,70),(.10,.53),25,(.80,.90,1)),
        ('Back',(-310,195,215),(0,38,62),(.27,.48),13,(1,.92,.85)),
        ('Lens card',(-98,-410,203),(0,-167,63),(.045,.115),1.4,(.83,1,.98))]:
        d=bpy.data.lights.new('Photo / '+name,'AREA');d.shape='RECTANGLE'
        d.size,d.size_y=[v*1.75 for v in size];d.energy=power*1.75**2;d.color=color
        lamp=obj_in(gallery,'Photo / '+name,d);lamp.location=vec(target)+(vec(position)-vec(target))*1.75;lookat(lamp,vec(target))
    mesh=bpy.data.meshes.new('Photography seamless')
    mesh.from_pydata([(-8,-8,0),(8,-8,0),(8,8,0),(-8,8,0)],[],[(0,1,2,3)])
    floor=obj_in(gallery,'Photo / supporting surface',mesh)
    mat=bpy.data.materials.new('Photo / seamless matte');floor.data.materials.append(mat)
    mat.use_nodes=True;next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED').inputs['Roughness'].default_value=.8
    scene.frame_set(1)
    contact=contact_plane(root)
    scene['Display contact plane']=json.dumps(contact)
    floor.rotation_euler.x=atan(contact['slope_dz_dy']);floor.location.z=contact['z_at_origin_mm']*.001
    scene.world=bpy.data.worlds.new('Photo / studio ambient');scene.world.use_nodes=True
    for key,(_,target,delta,width,rx,ry,frame,palette) in SCENES.items():
        scene.frame_set(frame)
        d=bpy.data.cameras.new('Photo / '+key)
        c=obj_in(gallery,'Photo / '+key,d);c.location=vec(target)+vec(delta);lookat(c,vec(target))
        d.type='ORTHO';d.clip_start=.001;d.clip_end=20
        d.ortho_scale=(width or 600)*.001
        if width is None:framing(c,root,rx/ry,(1,13,36,43,48,53,57,81,101,121) if key=='06-motion' else None)
    scene.render.engine='CYCLES';scene.render.use_sequencer=False
    scene.cycles.max_bounces=8;scene.cycles.transparent_max_bounces=8
    scene.cycles.samples=112;scene.cycles.adaptive_threshold=.021;scene.cycles.use_denoising=True
    scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_depth='8'
    scene.render.image_settings.compression=28;scene.render.use_file_extension=True
    configure('01-hero')
    return contact
def configure(key):
    label,target,delta,width,rx,ry,frame,palette=SCENES[key]
    scene=bpy.context.scene;scene.frame_set(frame);scene.camera=get_cam(key)
    scene.render.resolution_x=rx;scene.render.resolution_y=ry;scene.render.resolution_percentage=100
    floor=bpy.data.objects['Photo / supporting surface'];bs=next(n for n in floor.data.materials[0].node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    bg=next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND')
    paper=palette=='paper'
    bs.inputs['Specular IOR Level'].default_value=.22 if paper else .075
    bs.inputs['Base Color'].default_value=(.25,.255,.25,1) if paper else (.016,.020,.027,1)
    bg.inputs[0].default_value=(.55,.58,.63,1) if paper else (.32,.39,.48,1)
    bg.inputs[1].default_value=.54 if paper else .30
    for name,w in [('Key',26),('Fill',9),('Strip',25),('Back',13),('Lens card',1.4)]:
        ob=bpy.data.objects['Photo / '+name]
        ob.data.energy=w*1.75**2*({'Fill':1.30,'Strip':.65,'Back':.82}.get(name,1) if paper else 1)
    floor.hide_render=palette in ('float','alpha')
    if palette=='float':
        bg.inputs[0].default_value=(.275,.36,.43,1);bg.inputs[1].default_value=.70
    scene.render.film_transparent=palette=='alpha'
    scene.render.image_settings.color_mode='RGBA' if palette=='alpha' else 'RGB'
    scene.view_settings.exposure=-1.08 if paper else -1.16
    scene.render.filepath='//renders/'+key+'.png'
def device():
    scene=bpy.context.scene
    prefs=bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type='OPTIX';prefs.refresh_devices()
    for d in prefs.devices:d.use=(d.type=='OPTIX')
    scene.cycles.device='GPU' if any(d.use for d in prefs.devices) else 'CPU'

def render(base,keys,draft=False):
    device();s=bpy.context.scene;s.render.use_persistent_data=True
    out=base/('review/drafts' if draft else 'renders');out.mkdir(exist_ok=True,parents=True)
    for key in keys:
        configure(key);s.cycles.samples=10 if draft else 112;s.cycles.adaptive_threshold=.08 if draft else .021
        s.render.resolution_percentage=26 if draft else 100
        s.render.image_settings.file_format='PNG'
        s.render.filepath=str(out/(key+'.png'));bpy.ops.render.render(write_still=True)
        if not draft and key=='08-cutout':
            # A lossless linear multilayer master, separated from the display-referred PNG.
            layer=bpy.context.view_layer
            layer.use_pass_normal=True;layer.use_pass_z=True;layer.use_pass_object_index=True
            for i,ob in enumerate(sorted(bpy.data.objects[ROOT].children_recursive,key=lambda o:o.name),1):
                if ob.type in {'MESH','FONT','CURVE','SURFACE'}:ob.pass_index=i
            (out/'object-index.json').write_text(json.dumps({o.pass_index:o.name for o in bpy.data.objects[ROOT].children_recursive if o.pass_index},ensure_ascii=False,indent=2),encoding='utf8')
            s.render.image_settings.media_type='MULTI_LAYER_IMAGE'
            s.render.image_settings.file_format='OPEN_EXR_MULTILAYER';s.render.image_settings.color_depth='32';s.render.image_settings.exr_codec='ZIP'
            s.render.filepath=str(out/'08-linear-passes.exr');bpy.ops.render.render(write_still=True)
            s.render.image_settings.media_type='IMAGE'
            s.render.image_settings.file_format='PNG';s.render.image_settings.color_depth='8'
        print('PHOTOGRAPH',key,flush=True)
    if not draft and set(keys)==set(SCENES):
        import render_record
        render_record.save(bpy.data.filepath,[out/(k+'.png') for k in keys]+[out/'08-linear-passes.exr'],base/'review/photo-render-source.json')
if __name__=='__main__':
    import sys
    base=Path(__file__).resolve().parents[1]
    args=sys.argv[sys.argv.index('--')+1:]
    if 'prepare' in args:setup(bpy.data.objects[ROOT])
    render(base,[k for k in args if k in SCENES] or list(SCENES),draft='draft' in args)




