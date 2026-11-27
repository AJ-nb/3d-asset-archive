"""Three V3 photographs of the tactile controls, the mute lamp and a wired desk."""
import math
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector, Matrix
from v3_common import WORK, PRODUCT, new_scene, place, world, camera, area


HERE = WORK / 'function'
WARM = (1.,.94,.86)
DAY = (.85,.93,1.)


def material(name, color, rough=.45, metal=0.):
    name = 'V3F | '+name
    cached = bpy.data.materials.get(name)
    if cached: return cached
    mat = bpy.data.materials.new(name)
    if not mat.node_tree: mat.use_nodes = True
    shader = next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    shader.inputs['Base Color'].default_value = (*color,1)
    shader.inputs['Roughness'].default_value = rough
    shader.inputs['Metallic'].default_value = metal
    return mat


def obj(scene,name,mesh,mat):
    ob = bpy.data.objects.new(scene.name[:2]+' | '+name,mesh)
    scene.collection.objects.link(ob)
    if mat is not None: mesh.materials.append(mat)
    return ob


def box(scene,name,center,size,mat,radius=0.,rot=None):
    corners=[(sx*size[0]/2,sy*size[1]/2,sz*size[2]/2) for sz in (-1,1) for sy in (-1,1) for sx in (-1,1)]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(corners,[],[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)]);mesh.update()
    ob=obj(scene,name,mesh,mat);ob.location=center
    if rot is not None: ob.rotation_euler=rot.to_euler()
    if radius:
        mod=ob.modifiers.new('Machined edge radius','BEVEL');mod.width=radius;mod.segments=5;mod.harden_normals=True
        mod=ob.modifiers.new('Face normals','WEIGHTED_NORMAL');mod.keep_sharp=True
    return ob


def slab(scene,color):
    return box(scene,'Seamless matte card',(0,0,-.12),(45,45,.24),material('Grey card '+scene.name[:2],color,.73))


def loc(carrier,pos): return carrier.matrix_world @ Vector(pos)


def dolly(scene,target,offset,lens,focus=None,fstop=5.6):
    target=Vector(target);cam=camera(scene,target+Vector(offset),target,lens)
    if focus is not None:
        cam.data.dof.use_dof=True
        axis=(target-cam.location).normalized()
        cam.data.dof.focus_distance=(Vector(focus)-cam.location).dot(axis)
        cam.data.dof.aperture_fstop=fstop;cam.data.dof.aperture_blades=9
    return cam


def tactile():
    s=new_scene('05','surface-language','Tactile controls | Three surface finishes',(1800,1350))
    inst=place(s,-90,-31);bpy.context.view_layer.update()
    world(s,(.80,.86,.96),.14);slab(s,(.22,.225,.222))
    # Include all three finishes in a single working plane: matte rubber, satin shell and resin.
    t=loc(inst,(.80,-.45,1.56))
    dolly(s,t,(2.55,-2.77,3.73),96,t,5.)
    area(s,'Large booklight',(-1.9,-3.4,4.5),t,385,2.5,2.1,WARM)
    area(s,'Silk in resin edge',(3.3,2.7,4.1),t,210,1.0,3.3,DAY)
    area(s,'Soft black-side return',(-3.1,1,2.3),t,62,2.2,2.0,DAY)
    s['Purpose']='A single frame compares clear action caps, textured rubber and fine molded housing.'
    return s


def indicator(scene,carrier):
    housing=next(o for o in bpy.data.collections[PRODUCT].objects if 'Housing | shell' in o.name)
    mesh=housing.data
    coords=np.empty(len(mesh.vertices)*3,'f');mesh.vertices.foreach_get('co',coords)
    matrix=np.asarray(housing.matrix_world);coords=coords.reshape(-1,3)@matrix[:3,:3].T+matrix[:3,3]
    # Exact bounds from an independent welded-island audit of the mute key. Its neighboring logo
    # shares a material slot, but lies outside this closed bound. Select the front-facing surface.
    inside=np.all((coords>[-.099,-.345,.865])&(coords<[.099,-.282,.917]),axis=1)
    indices=np.empty(len(mesh.polygons),'i');mesh.polygons.foreach_get('material_index',indices)
    slot=next(i for i,m in enumerate(housing.material_slots) if 'Gloss black' in m.material.name)
    valid=[]
    toward=Vector((0,-.92,-.39)).normalized()
    for i in np.flatnonzero(indices==slot):
        poly=mesh.polygons[int(i)];ids=list(poly.vertices)
        if inside[ids].all() and (housing.matrix_world.to_3x3()@poly.normal).dot(toward)>.10:
            valid.append(ids)
    used=sorted({v for f in valid for v in f})
    assert 30<len(used)<1030 and len(valid)>20,(len(used),len(valid))
    remap={v:i for i,v in enumerate(used)}
    verts=[]
    for v in used:
        surface=Vector(coords[v])+(housing.matrix_world.to_3x3()@mesh.vertices[v].normal).normalized()*.00032
        verts.append(loc(carrier,surface))
    patch=bpy.data.meshes.new('Operating lamp | exact upper mute-key facets')
    patch.from_pydata(verts,[],[[remap[v] for v in face] for face in valid]);patch.update()
    for face in patch.polygons:face.use_smooth=True
    m=material('Steady amber | mic mute transmitting lens',(.65,.105,.002),.34)
    bs=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    bs.inputs['Emission Color'].default_value=(1,.135,.001,1);bs.inputs['Emission Strength'].default_value=.84
    o=obj(scene,'Operating state | microphone muted amber',patch,m)
    o['Source feature']='Exposed facets of the existing microphone mute switch, outward offset 0.016 mm'
    o['Source model bounds XYZ']='[-0.09857,-0.34472,0.86524] to [0.09857,-0.28236,0.91597] BU'
    return o


def mute():
    s=new_scene('06','microphone-muted','Function | Steady microphone mute indicator',(1800,1350))
    inst=place(s,-90,4);bpy.context.view_layer.update()
    world(s,(.81,.89,1),.16);slab(s,(.105,.115,.12))
    indicator(s,inst)
    t=loc(inst,(0,-.36,1.035));mark=loc(inst,(0,-.32,.895))
    dolly(s,t,(-.46,-2.10,2.91),86,mark,7.)
    area(s,'Long left softbox',(-2.6,-2.2,3.5),t,195,2.8,.86,DAY)
    area(s,'Camera-side open fill',(2.6,-2.6,2.2),t,55,2.1,2.,WARM)
    area(s,'Rear silk rim',(1.7,3,3.4),t,230,2.2,2.2,(.88,.92,1))
    s['Function']='Steady amber mute button: microphone muted after a short press. Hold-to-mute-all is a different blinking state.'
    s['Reference']='https://www.playstation.com/content/dam/global_pdc/en/corporate/support/manuals/ps5-docs/1000b-digital-edition/MEA_EN_PS5_Digital_Web_Quick_Start_Guide_ENGMEA_7033928.pdf'
    return s


def path(scene,name,pts,radius,mat):
    data=bpy.data.curves.new(name,'CURVE');data.dimensions='3D';data.resolution_u=24;data.bevel_resolution=5
    data.bevel_depth=radius;data.use_fill_caps=True
    sp=data.splines.new('BEZIER');sp.bezier_points.add(len(pts)-1)
    for bp,pt in zip(sp.bezier_points,pts):
        bp.co=pt;bp.handle_left_type=bp.handle_right_type='AUTO'
    ob=obj(scene,name,data,mat)
    return ob,sp


def print_label(scene,content,xy,z,size,ink):
    c=bpy.data.curves.new('Key legend','FONT');c.body=content;c.align_x='CENTER';c.align_y='CENTER';c.size=size;c.resolution_u=5
    ob=obj(scene,'Key legend '+content,c,ink);ob.location=(*xy,z)
    return ob


def computer(scene):
    # Generic clamshell with an open milled USB-C receptacle in the right sidewall.
    cx,cy=-3.16,1.53;w,d=5.68,3.94;right=cx+w/2
    aluminum=material('Graphite anodised aluminum',(.118,.132,.15),.34,.72)
    deckmat=material('Notebook palmrest aluminum',(.209,.220,.23),.39,.66)
    black=material('Inset keyboard baffle',(.012,.014,.018),.48)
    key=material('Soft black notebook key',(.031,.037,.044),.55)
    legend=material('Printed light-grey key legends',(.53,.56,.60),.58)
    box(scene,'Feet',(cx,cy,.055),(w-.36,d-.32,.11),black,.045)
    base=box(scene,'Notebook chassis',(cx,cy,.21),(w,d,.24),aluminum,.075)
    # Position the port beyond the palmrest, aligning its long axis fore-aft.
    py=cy+.60;pz=.21
    cutter=box(scene,'Socket subtractor',(right-.035,py,pz),(.22,.192,.075),None,.031)
    cut=base.modifiers.new('USB Type-C aperture','BOOLEAN');cut.operation='DIFFERENCE';cut.solver='EXACT';cut.object=cutter
    cutter.hide_render=True;cutter.display_type='WIRE'
    box(scene,'Socket liner',(right-.102,py,pz),(.018,.178,.062),black,.01)
    box(scene,'Palmrest plane',(cx,cy,.333),(w-.05,d-.053,.064),deckmat,.026)
    box(scene,'Touchpad recess',(cx,cy-.95,.367),(1.88,1.04,.008),aluminum,.006)
    box(scene,'Touchpad',(cx,cy-.95,.373),(1.851,1.014,.011),deckmat,.005)
    box(scene,'Keyboard bed',(cx,cy+.60,.371),(w-.36,2.02,.022),black,.012)
    rows=['esc|1|2|3|4|5|6|7|8|9|0|-|=|del','tab|Q|W|E|R|T|Y|U|I|O|P|[|]|\\','caps|A|S|D|F|G|H|J|K|L|;|\'|enter','shift|Z|X|C|V|B|N|M|,|.|/|shift','ctrl|fn|alt|win| |alt|←|↑|↓|→']
    for j,row in enumerate(rows):
        keys=row.split('|')
        weights=[{'tab':1.35,'caps':1.55,'shift':1.9,'enter':1.8,'del':1.5,' ':5.3,'ctrl':1.38}.get(k,1.) for k in keys]
        span=w-.50;unit=span/sum(weights);x=cx-span/2
        yy=cy+1.40-j*.38
        for k,width in zip(keys,weights):
            ww=width*unit;xx=x+ww/2;x+=ww
            box(scene,'Scissor key '+k,(xx,yy,.408),(ww-.034,.323,.071),key,.031)
            if k!=' ':print_label(scene,k,(xx,yy),.446,.088 if len(k)==1 else .071,legend)
    rot=Matrix.Rotation(math.radians(-13),3,'X')
    origin=Vector((cx,cy+d/2-.09,.395))
    def onlid(x,y,z):return origin+rot@Vector((x,y,z))
    box(scene,'Hinge spine',(cx,cy+d/2-.10,.403),(w-.71,.161,.158),black,.069)
    box(scene,'Screen lid',onlid(0,0,1.89),(w,.14,3.78),aluminum,.055,rot)
    box(scene,'Display mask',onlid(0,-.078,1.90),(w-.083,.041,3.68),black,.014,rot)
    glass=material('Standby dark neutral screen',(.02,.036,.055),.24,.28)
    box(scene,'Quiet blank display',onlid(0,-.104,1.94),(w-.26,.014,3.37),glass,.006,rot)
    return Vector((right,py,pz)),Vector((1,0,0))


def plug(scene,name,seat,out,width_axis,finish,metal):
    longitudinal=Vector(out).normalized(); width=(Vector(width_axis)-longitudinal*longitudinal.dot(Vector(width_axis))).normalized()
    thick=longitudinal.cross(width).normalized()
    basis=Matrix((width,thick,longitudinal)).transposed()
    def point(t):return Vector(seat)+t*longitudinal
    box(scene,name+' | exposed metal lip',point(.008),(.160,.050,.036),metal,.014,basis)
    box(scene,name+' | molded grip',point(.177),(.252,.123,.33),finish,.050,basis)
    box(scene,name+' | compliant tail',point(.39),(.134,.10,.165),finish,.039,basis)
    return point(.461)


def book(scene):
    filepath=HERE/'assets'/'binder_notebook'/'binder_notebook.gltf'
    before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(filepath))
    imported=set(bpy.data.objects)-before
    for ob in list(imported):
        if ob.name.startswith('binder_notebook_closed'):
            imported.remove(ob)
            bpy.data.objects.remove(ob,do_unlink=True)
    obs=sorted(imported,key=lambda ob:ob.name)
    container=bpy.data.collections.new('V3F | Scanned stationery')
    for ob in obs:
        for source in list(ob.users_collection): source.objects.unlink(ob)
        container.objects.link(ob)
    inst=bpy.data.objects.new('07 | Scanned linen notebook',None);scene.collection.objects.link(inst);inst.instance_type='COLLECTION';inst.instance_collection=container
    allpts=[]
    for ob in obs:
        if ob.type=='MESH':
            for x in ob.bound_box:allpts.append(ob.matrix_world @ Vector(x))
    xyz=np.array(allpts)
    extent=xyz.max(axis=0)-xyz.min(axis=0)
    ori=Matrix.Rotation(math.radians(-13),3,'Z')
    if np.argmin(extent)!=2:ori=ori@Matrix.Rotation(math.pi/2,3,'X' if np.argmin(extent)==1 else 'Y')
    xyz=xyz@np.asarray(ori).T;factor=float(3./max(xyz.max(axis=0)-xyz.min(axis=0)))
    inst.rotation_euler=ori.to_euler();inst.scale=(factor,)*3
    midpoint=(xyz.min(axis=0)+xyz.max(axis=0))/2
    inst.location=Vector((-2.67,-2.10,.003))-factor*Vector((midpoint[0],midpoint[1],xyz.min(axis=0)[2]))


def desk_surface(scene):
    sysdir=WORK.parent/'v2-work'/'product'
    m=material('Quarter cut walnut',(.20,.11,.064),.54);nodes=m.node_tree.nodes;link=m.node_tree.links.new
    bs=next(n for n in nodes if n.type=='BSDF_PRINCIPLED')
    uid=nodes.new('ShaderNodeTexCoord');v=nodes.new('ShaderNodeVectorMath');v.operation='MULTIPLY';v.inputs[1].default_value=(.073,.077,.073);link(uid.outputs['Object'],v.inputs[0])
    for key in ['diff','rough','nor_gl']:
        tx=nodes.new('ShaderNodeTexImage');im=bpy.data.images.load(str(sysdir/('smoked_walnut_veneer_'+key+'.jpg')),check_existing=True)
        im.colorspace_settings.name='sRGB' if key=='diff' else 'Non-Color';im.pack();tx.image=im;link(v.outputs[0],tx.inputs['Vector'])
        if key=='diff':
            tone=nodes.new('ShaderNodeHueSaturation');tone.inputs['Value'].default_value=.37;tone.inputs['Saturation'].default_value=.69;link(tx.outputs[0],tone.inputs['Color']);link(tone.outputs[0],bs.inputs['Base Color'])
        if key=='rough':
            remap=nodes.new('ShaderNodeMapRange');remap.inputs['To Min'].default_value=.43;remap.inputs['To Max'].default_value=.67;link(tx.outputs[0],remap.inputs[0]);link(remap.outputs[0],bs.inputs['Roughness'])
        if key=='nor_gl':
            # The surface is a planar XY desktop; tangent-free normal decoding is explicit.
            norm=nodes.new('ShaderNodeNormalMap');norm.space='OBJECT';norm.inputs['Strength'].default_value=.23
            link(tx.outputs[0],norm.inputs['Color']);link(norm.outputs[0],bs.inputs['Normal'])
    box(scene,'Walnut worktop',(0,0,-.20),(38,30,.4),m,.06)


def desk():
    s=new_scene('07','wired-desktop','Use | USB-C on a notebook desk',(2560,1600))
    world(s,(.83,.9,1),.23);desk_surface(s)
    inst=place(s,-96.719,-16,(1.86,-1.03,0));bpy.context.view_layer.update()
    # Use the actual aperture (not the rear face of the plug assembly). Archive +Z is the socket axis.
    seat=loc(inst,(0,-.2115,2.102));rot=inst.matrix_world.to_3x3()
    direction=(rot@Vector((0,-.05,1))).normalized()
    tpv,pcdir=computer(s);bpy.context.view_layer.update()
    finish=material('Braided black cable and molding',(.025,.029,.031),.52)
    metal=material('Nickel connector lip',(.47,.49,.50),.28,.87)
    start=plug(s,'Controller USB-C',seat,direction,rot@Vector((1,0,0)),finish,metal)
    end=plug(s,'Notebook USB-C',tpv,pcdir,(0,1,0),finish,metal)
    # Tangents at both strain reliefs follow the port axes. Gradually settle onto
    # the desk, run a single slack loop, then lift back to the side connector.
    cable_nodes=[
        (start, direction*.27),
        ((2.57,1.49,.112),(.050,.435,-.055)),
        ((2.48,2.59,.039),(-.155,.434,0)),
        ((1.73,2.92,.039),(-.414,-.07,0)),
        ((.81,2.34,.087),(-.30,-.207,.040)),
        (end,-pcdir*.27),
    ]
    ob,spline=path(s,'Data cable | continuous flexible jacket',[p for p,t in cable_nodes],.038,finish)
    for bp,(p,t) in zip(spline.bezier_points,cable_nodes):
        bp.handle_left_type=bp.handle_right_type='FREE'
        bp.handle_left=Vector(p)-Vector(t);bp.handle_right=Vector(p)+Vector(t)
    ob['Connection']='One unbroken curve from the seated top-center product connector to the visible notebook side port.'
    book(s)
    ink=material('Black lacquer pen',(.018,.022,.022),.26,.16)
    silver=material('Pen clip and chrome',(.49,.51,.51),.23,.82)
    p=Vector((-.68,-2.50,.065));a=Vector((.27,.963,0))
    path(s,'Capped fineliner',[p-.94*a,p+.94*a],.065,ink)
    path(s,'Pen cap band',[p-.23*a,p-.18*a],.067,silver)
    path(s,'Pen pocket clip',[p-.83*a+Vector((0,0,.066)),p-.78*a+Vector((0,0,.086)),p-.28*a+Vector((0,0,.083))],.017,silver)
    target=(.29,-.69,.38);dolly(s,target,(2.9,-8.0,11.9),59,loc(inst,(0,-.37,1.27)),6.3)
    area(s,'Studio window',(-5.9,2.7,7.4),(.2,0,.2),1370,4.9,3.5,WARM)
    area(s,'Large ceiling bounce',(3.6,-4.3,6.2),(1,0,.3),465,4.8,4.1,DAY)
    s['Set dressing']='Generic compatible notebook PC and unbranded USB-C cable; editorial context props.'
    s['Connectivity reference']='https://www.playstation.com/en-us/support/hardware/pair-dualsense-controller-bluetooth/'
    s['Texture credits']='Poly Haven: smoked_walnut_veneer and binder_notebook'
    return s


def build_all():
    return (tactile(),mute(),desk())
