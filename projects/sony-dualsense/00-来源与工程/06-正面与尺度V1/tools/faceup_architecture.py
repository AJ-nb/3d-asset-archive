"""Two metre-scale architectural photographs built around the archived assembly."""

from math import cos, sin, pi, radians
from pathlib import Path
from random import Random

import bpy
import numpy as np
from mathutils import Vector, Euler
from build_studio import PARTS, collection, bind_camera, shot_scene, setup_scene, aim
from build_lineup import assembly_points


class Pieces:
    """One editable architectural mesh per feature, with named finish slots."""
    def __init__(self, coll, name, origin=(0, 0, 0), yaw=0):
        self.coll, self.name = coll, name
        self.origin, self.yaw = origin, yaw
        self.verts, self.faces, self.face_slots, self.smooth, self.mats = [], [], [], [], []

    def part(self, verts, faces, mat, smooth=False):
        if mat not in self.mats:
            self.mats.append(mat)
        slot, start = self.mats.index(mat), len(self.verts)
        self.verts.extend(verts)
        self.faces.extend([tuple(start+i for i in f) for f in faces])
        self.face_slots.extend([slot]*len(faces))
        self.smooth.extend([smooth]*len(faces))

    def box(self, x,y,z, dx,dy,dz, mat):
        vs=[(x+i*dx/2,y+j*dy/2,z+k*dz/2) for k in (-1,1) for j in (-1,1) for i in (-1,1)]
        fs=[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)]
        self.part(vs,fs,mat)

    def tube(self, a,b,r1,r2,mat,n=10):
        a,b=Vector(a),Vector(b)
        axis=(b-a).normalized()
        tangent=axis.cross(Vector((0,0,1)) if abs(axis.z)<.95 else Vector((1,0,0))).normalized()
        bitangent=axis.cross(tangent)
        ring=[tangent*cos(2*pi*i/n)+bitangent*sin(2*pi*i/n) for i in range(n)]
        vs=[tuple(p+d*r) for p,r in ((a,r1),(b,r2)) for d in ring]
        self.part(vs,[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
                  +[tuple(reversed(range(n))),tuple(range(n,2*n))],mat,True)

    def ell(self,x,y,z,rx,ry,rz,mat):
        layers=((-1,.04),(-.78,.63),(-.36,.93),(.18,.985),(.7,.72),(1,.04))
        self.rings([(x,y,z+rz*h,rx*r,ry*r) for h,r in layers],mat)

    def rings(self,rings,mat,n=12):
        vs=[(x+rx*cos(2*pi*i/n),y+ry*sin(2*pi*i/n),z) for x,y,z,rx,ry in rings for i in range(n)]
        fs=[(j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i)
            for j in range(len(rings)-1) for i in range(n)]
        fs.extend([tuple(reversed(range(n))),tuple(range(len(vs)-n,len(vs)))])
        self.part(vs,fs,mat,True)

    def flush(self):
        mesh=bpy.data.meshes.new(self.name)
        mesh.from_pydata(self.verts,[],self.faces)
        for mat in self.mats:
            mesh.materials.append(mat)
        mesh.polygons.foreach_set("material_index",self.face_slots)
        mesh.polygons.foreach_set("use_smooth",self.smooth)
        mesh.update()
        ob=bpy.data.objects.new(self.name,mesh)
        self.coll.objects.link(ob)
        ob.location=self.origin
        ob.rotation_euler.z=radians(self.yaw)
        return ob


def finish(name,c,rough=.65,metal=0,noise=0,glow=0):
    m=bpy.data.materials.new("Quays | "+name)
    if m.node_tree is None:
        m.use_nodes=True
    m.diffuse_color=(*c,1)
    p=next(x for x in m.node_tree.nodes if x.type=="BSDF_PRINCIPLED")
    p.inputs['Base Color'].default_value=(*c,1)
    p.inputs['Roughness'].default_value=rough
    p.inputs['Metallic'].default_value=metal
    if glow:
        p.inputs['Emission Color'].default_value=(*c,1)
        p.inputs['Emission Strength'].default_value=glow
    if noise:
        n=m.node_tree.nodes.new('ShaderNodeTexNoise')
        pcoord=m.node_tree.nodes.new('ShaderNodeNewGeometry')
        m.node_tree.links.new(pcoord.outputs['Position'],n.inputs['Vector'])
        n.inputs['Scale'].default_value=noise
        n.inputs['Detail'].default_value=3.1
        ramp=m.node_tree.nodes.new('ShaderNodeValToRGB')
        for e,f in zip(ramp.color_ramp.elements,(.65,1.26)):
            e.color=(*[v*f for v in c],1)
        m.node_tree.links.new(n.outputs['Fac'],ramp.inputs['Fac'])
        m.node_tree.links.new(ramp.outputs[0],p.inputs['Base Color'])
        b=m.node_tree.nodes.new('ShaderNodeBump')
        b.inputs['Strength'].default_value=.20
        b.inputs['Distance'].default_value=.013
        m.node_tree.links.new(n.outputs['Fac'],b.inputs['Height'])
        m.node_tree.links.new(b.outputs['Normal'],p.inputs['Normal'])
    return m


def masonry(name, colors, mortar, width, height, joint, wall=False):
    m=finish(name,colors[0],.77)
    t=m.node_tree; n=t.nodes; l=t.links.new
    p=next(v for v in n if v.type=='BSDF_PRINCIPLED')
    geo=n.new('ShaderNodeNewGeometry')
    vec=geo.outputs['Position']
    if wall:
        sep=n.new('ShaderNodeSeparateXYZ'); l(vec,sep.inputs[0])
        add=n.new('ShaderNodeMath'); add.operation='ADD'
        l(sep.outputs['X'],add.inputs[0]); l(sep.outputs['Y'],add.inputs[1])
        comb=n.new('ShaderNodeCombineXYZ'); l(add.outputs[0],comb.inputs['X']); l(sep.outputs['Z'],comb.inputs['Y'])
        vec=comb.outputs[0]
    brick=n.new('ShaderNodeTexBrick')
    l(vec,brick.inputs['Vector'])
    for key,val in [('Scale',1.),('Brick Width',width),('Row Height',height),('Mortar Size',joint),
                    ('Mortar Smooth',.73),('Color1',(*colors[0],1)),('Color2',(*colors[1],1)),('Mortar',(*mortar,1))]:
        brick.inputs[key].default_value=val
    gr=n.new('ShaderNodeTexNoise'); gr.inputs['Scale'].default_value=13
    gr.inputs['Detail'].default_value=3; l(geo.outputs['Position'],gr.inputs[0])
    mix=n.new('ShaderNodeMixRGB'); mix.blend_type='MULTIPLY'; mix.inputs[0].default_value=.28
    l(brick.outputs['Color'],mix.inputs[1]); l(gr.outputs['Color'],mix.inputs[2]); l(mix.outputs[0],p.inputs['Base Color'])
    bump=n.new('ShaderNodeBump'); bump.invert=True
    bump.inputs['Distance'].default_value=.013; bump.inputs['Strength'].default_value=.49
    l(brick.outputs['Fac'],bump.inputs['Height']); l(bump.outputs[0],p.inputs['Normal'])
    return m


def palette():
    m={}
    for name,c,r,met,grain,em in (
        ('concrete',(.36,.35,.31),.8,0,.8,0),('coping',(.51,.51,.46),.72,0,6,0),
        ('dark',(.032,.04,.043),.51,.15,0,0),('steel',(.19,.23,.23),.38,.64,0,0),
        ('rail',(.34,.37,.39),.26,.85,0,0),('roof',(.19,.235,.229),.56,.52,4,0),
        ('zinc',(.38,.41,.40),.46,.7,0,0),('glass',(.075,.145,.16),.19,.54,0,0),
        ('glass2',(.12,.215,.235),.22,.5,0,0),('asphalt',(.097,.105,.104),.90,0,17,0),
        ('mark',(.76,.72,.59),.71,0,17,0),('tram',(.11,.29,.29),.34,.35,0,0),
        ('ivory',(.73,.70,.56),.48,.17,0,0),('copper',(.59,.205,.048),.47,.2,3,0),
        ('red',(.33,.047,.025),.38,.15,0,0),('rubber',(.025,.022,.023),.8,0,12,0),
        ('lamp',(1,.74,.41),.32,0,0,3.4),('white',(.88,.84,.71),.5,0,0,0),
        ('skin',(.47,.26,.15),.64,0,0,0),('skin2',(.26,.126,.081),.65,0,0,0),
        ('hair',(.061,.039,.027),.7,0,0,0),('navy',(.038,.079,.12),.8,0,0,0),
        ('workcoat',(.12,.205,.212),.8,0,0,0),('ochre',(.60,.33,.075),.74,0,0,0),
        ('sand',(.41,.32,.20),.78,0,0,0),('bark',(.146,.106,.071),.85,0,8,0),
        ('leaf',(.116,.175,.066),.6,0,0,0),('leaf2',(.191,.254,.091),.64,0,0,0),
        ('leaf3',(.085,.141,.069),.7,0,0,0),('water',(.053,.132,.156),.20,.3,1.9,0)
    ): m[name]=finish(name,c,r,met,grain,em)
    m['brick']=masonry('aged press brick',((.32,.112,.064),(.20,.061,.039)),(.32,.235,.162),.32,.092,.006,True)
    m['stone']=masonry('sawn limestone flags',((.48,.473,.418),(.34,.351,.323)),(.19,.194,.178),1.32,.69,.012)
    m['tile']=masonry('station terrazzo',((.24,.289,.285),(.20,.243,.241)),(.115,.147,.148),1.36,.81,.010)
    return m


def text_sign(coll,body,loc,size,material,yaw=0):
    f=bpy.data.curves.new('Wayfinding | '+body,'FONT')
    f.body=body; f.align_x='CENTER'; f.align_y='CENTER'
    f.size=size; f.extrude=.003; f.space_character=1.14
    o=bpy.data.objects.new(body,f); coll.objects.link(o)
    o.location=loc; o.rotation_euler=(pi/2,0,radians(yaw))
    f.materials.append(material)


def pedestrian(coll,m,x,y,heading,seed,z=0):
    r=Random(seed)
    q=Pieces(coll,'Pedestrian | '+str(seed),(x,y,z),heading)
    skin=m[r.choice(('skin','skin2'))]; jacket=m[r.choice(('ochre','red','navy','workcoat','sand','ivory'))]
    trouser=m[r.choice(('navy','dark','sand'))]; stride=r.choice((.10,.19,.27))
    mode=seed%5
    for s in (-1,1):
        hip=(s*.09,0,.9); knee=(s*.087,s*stride*.53-.035,.48); foot=(s*.095,s*stride,.12)
        q.tube(hip,knee,.097,.073,trouser); q.tube(knee,foot,.076,.059,trouser)
        q.ell(foot[0],foot[1]-.048,.065,.065,.13,.059,m['dark'])
    q.rings([(0,.018,.80 if mode in (1,3) else .88,.18,.125),(0,.008,1.03,.168,.116),(0,0,1.35,.211,.124),
             (0,-.006,1.43,.17,.102),(0,0,1.455,.095,.078)],jacket)
    q.ell(0,.11,1.40,.14,.077,.08,jacket)
    for s in (-1,1):
        sh=(s*.168,0,1.36); elbow=(s*.216,-s*stride*.52,1.14); hand=(s*.216,-s*stride*.89-.035,.98)
        if s==1 and mode==1: elbow=(.24,-.09,1.12); hand=(.13,-.18,1.30)
        if s==-1 and mode==3: elbow=(-.22,-.10,1.16); hand=(-.115,-.21,1.50)
        q.ell(*sh,.073,.084,.084,jacket)
        q.tube(sh,elbow,.072,.055,jacket); q.tube(elbow,hand,.057,.039,jacket)
        q.ell(*hand,.041,.038,.055,skin)
    q.tube((0,0,1.42),(0,-.002,1.52),.058,.057,skin)
    q.rings([(0,-.022,1.495,.043,.053),(0,-.028,1.53,.070,.075),(0,-.014,1.61,.085,.097),
             (0,-.005,1.67,.087,.095),(0,.006,1.72,.063,.062)],skin)
    q.ell(0,-.10,1.59,.021,.033,.030,skin)
    q.ell(0,.006,1.67,.089,.094,.059,m['hair'])
    if mode in (1,4): q.ell(0,.076,1.58,.083,.048,.095,m['hair'])
    if mode in (0,2):
        q.ell(0,.136,1.20,.145,.092,.193,m['navy' if mode==0 else 'sand'])
        for s in (-1,1):
            q.tube((s*.128,-.049,1.39),(s*.144,-.094,1.13),.018,.016,m['hair'])
    if mode==2:
        q.ell(0,0,1.69,.097,.10,.059,m['ochre'])
        q.ell(0,-.086,1.684,.081,.069,.009,m['ochre'])
    if mode==4:
        q.box(.255,.015,.77,.11,.23,.27,m['red'])
        q.tube((.245,0,.88),(.226,-.005,.969),.013,.012,m['hair'])
    ob=q.flush(); scale=r.uniform(.95,1.1); ob.scale=(scale,)*3


def avenue_tree(coll,m,x,y,seed,height=5.8):
    rng=Random(seed); q=Pieces(coll,'London plane | '+str(seed),(x,y,0))
    q.tube((0,0,0),(.05,0,2.85),.155,.092,m['bark'])
    for j in range(16):
        az=rng.random()*2*pi; d=rng.uniform(.55,1.75)
        end=(d*cos(az),d*sin(az),rng.uniform(3.45,5.30))
        base=(.03,0,rng.uniform(1.75,3))
        q.tube(base,end,.06,.018,m['bark'],7)
        for k in range(7):
            tx=end[0]+rng.uniform(-.58,.58); ty=end[1]+rng.uniform(-.53,.53); tz=end[2]+rng.uniform(-.15,.62)
            q.tube(end,(tx,ty,tz),.015,.005,m['bark'],4)
            for f in range(37):
                dx,dy,dz=[rng.uniform(-1,1) for _ in range(3)]
                if dx*dx+dy*dy+dz*dz>1: continue
                p=Vector((tx+.66*dx,ty+.63*dy,tz+.49*dz)); angle=rng.random()*2*pi
                side=Vector((.057*cos(angle),.057*sin(angle),rng.uniform(-.035,.035)))
                stem=Vector((-.12*sin(angle),.12*cos(angle),rng.uniform(-.10,.11)))
                q.part([p-stem,p+side,p+stem,p-side],[(0,1,2,3)],m[rng.choice(('leaf','leaf2','leaf3'))])
    ob=q.flush(); ob.scale=(height/5.8,)*3


def bench(q,m,x,y):
    for side in (-.7,.7):
        q.box(x+side,y,.23,.10,.39,.46,m['steel'])
    for j in range(5):
        q.box(x,y-.19+j*.092,.48,1.85,.078,.065,m['sand'])


def factory(coll,m,x,y,w,d,h,name,yaw=0):
    q=Pieces(coll,name,(x,y,0),yaw)
    q.box(0,0,h/2,w,d,h,m['brick'])
    for zz,dz in ((.31,.62),(h-.36,.16),(h+.02,.18)):
        q.box(0,0,zz,w+.24,d+.24,dz,m['coping'])
    bays=max(2,round(w/3.4)); bw=(w-.7)/bays
    rows=max(1,round(h/3.1))
    for k in range(bays):
        xx=(k+.5)*bw-w/2+.35
        for j in range(rows):
            zh=h/rows; zz=(j+.53)*zh
            q.box(xx,-d/2-.038,zz,bw-.56,.105,zh*.66,m['dark'])
            q.box(xx,-d/2-.101,zz,bw-.70,.045,zh*.61,m['glass2' if (k+j)%5==0 else 'glass'])
            q.box(xx,-d/2-.146,zz-.15,.045,.052,zh*.61,m['steel'])
            q.box(xx,-d/2-.148,zz+.18,bw-.66,.045,.045,m['steel'])
            q.box(xx,-d/2-.09,zz-zh*.335,bw-.36,.28,.10,m['coping'])
        q.box(xx-bw*.5,-d*.5-.052,h*.50,.22,.16,h-.6,m['brick'])
    # Folded industrial roof with standing seams, roof lanterns and vents.
    q.part([(-w/2,-d/2,h+.12),(w/2,-d/2,h+.12),(w/2,0,h+1.3),(-w/2,0,h+1.3),
            (-w/2,d/2,h+.12),(w/2,d/2,h+.12)],[(0,1,2,3),(3,2,5,4)],m['roof'])
    for i in range(int(w/.72)+1):
        xx=-w/2+i*.72
        q.tube((xx,-d/2,h+.15),(xx,0,h+1.33),.026,.026,m['zinc'],5)
    for i in range(bays//2):
        xx=-w/2+(i*2+1.3)*bw
        q.box(xx,-d*.22,h+.81,1.45,1.15,.30,m['dark'])
        q.box(xx,-d*.22,h+1,1.54,1.22,.09,m['glass2'])
    for s in (-1,1):
        q.part([(s*w/2,-d/2,h+.12),(s*w/2,d/2,h+.12),(s*w/2,0,h+1.3)],[(0,1,2)],m['brick'])
        side_bays=max(2,round(d/2.9))
        for k in range(side_bays):
            yy=(k+.5)*d/side_bays-d/2
            for j in range(rows):
                zz=(j+.53)*h/rows
                q.box(s*(w/2+.040),yy,zz,.082,d/side_bays*.67,h/rows*.61,m['glass'])
                q.box(s*(w/2+.095),yy,zz,.052,.048,h/rows*.61,m['steel'])
                q.box(s*(w/2+.095),yy,zz+.11,.052,d/side_bays*.67,.042,m['steel'])
                q.box(s*(w/2+.083),yy,zz-h/rows*.32,.27,d/side_bays*.76,.097,m['coping'])
    for k in range(bays):
        xx=(k+.5)*bw-w*.5+.35
        for j in range(rows):
            zh=h/rows; zz=(j+.53)*zh
            for dx in (-.32,.32):
                q.box(xx+dx*(bw-.7),-d*.5-.154,zz,.036,.032,zh*.60,m['steel'])
            q.box(xx,-d*.5-.106,zz+zh*.338,bw-.31,.20,.12,m['brick'])
    for xx in (-w*.5+.15,w*.5-.15):
        q.tube((xx,-d*.5-.19,.34),(xx,-d*.5-.19,h-.25),.060,.060,m['zinc'])
    q.flush()


def placed_controller(coll, product, points, pitch, yaw, scale, center, base, unit):
    inst=bpy.data.objects.new('DualSense | architectural-scale original assembly',None)
    coll.objects.link(inst)
    inst.instance_type='COLLECTION'
    inst.instance_collection=product
    inst.rotation_euler=Euler((radians(pitch),0,radians(yaw)),'XYZ')
    inst.scale=(scale,)*3
    transformed=(points @ np.array(inst.rotation_euler.to_matrix()).T)*scale
    low,high=transformed.min(axis=0),transformed.max(axis=0)
    inst.location=(center[0]-(low[0]+high[0])/2,center[1]-(low[1]+high[1])/2,base-low[2])
    inst['physical_scale_factor']=float(scale/unit)
    inst['overall_dimensions_m']=[float(v) for v in high-low]
    inst['archive_pitch_degrees']=pitch
    print('ARCH |',coll.name,'| metres',high-low,'| archive scale factor',scale/unit)
    return inst


def environment(scene,coll,daylight=True):
    w=bpy.data.worlds.new('Malthouse | late afternoon' if daylight else 'North Quay | dusk')
    if w.node_tree is None: w.use_nodes=True
    scene.world=w
    tree=w.node_tree
    bg=next(a for a in tree.nodes if a.type=='BACKGROUND')
    tex=tree.nodes.new('ShaderNodeTexCoord'); sep=tree.nodes.new('ShaderNodeSeparateXYZ')
    tree.links.new(tex.outputs['Generated'],sep.inputs['Vector'])
    gradient=tree.nodes.new('ShaderNodeValToRGB')
    tree.links.new(sep.outputs['Z'],gradient.inputs[0])
    col=((.80,.85,.90),(1.0,.95,.81),(.49,.62,.74),(.20,.35,.55)) if daylight else ((.38,.48,.62),(.58,.62,.68),(.23,.32,.48),(.079,.143,.25))
    gradient.color_ramp.elements.remove(gradient.color_ramp.elements[1])
    for j,(v,c) in enumerate(zip((0,.07,.36,.85),col)):
        el=gradient.color_ramp.elements[0] if not j else gradient.color_ramp.elements.new(v)
        el.color=(*c,1)
    tree.links.new(gradient.outputs[0],bg.inputs['Color'])
    bg.inputs['Strength'].default_value=.68 if daylight else .70
    # CC0 panoramas by Greg Zaal and the Poly Haven team. Pack for portability.
    stem='kloofendal_48d_partly_cloudy_puresky_2k' if daylight else 'qwantani_dusk_2_puresky_2k'
    hdr=Path(__file__).resolve().parents[1]/'faceup-work'/'architecture'/(stem+'.hdr')
    if hdr.exists() and hdr.stat().st_size>1000000:
        im=bpy.data.images.load(str(hdr),check_existing=True)
        if not im.packed_file: im.pack()
        texenv=tree.nodes.new('ShaderNodeTexEnvironment'); texenv.image=im
        mapping=tree.nodes.new('ShaderNodeMapping')
        mapping.inputs['Rotation'].default_value[2]=radians(32 if daylight else 110)
        tree.links.new(tex.outputs['Generated'],mapping.inputs[0])
        tree.links.new(mapping.outputs[0],texenv.inputs[0])
        tree.links.new(texenv.outputs[0],bg.inputs['Color'])
        bg.inputs['Strength'].default_value=.31 if daylight else .20
    sun=bpy.data.lights.new('Low sun through the quay','SUN')
    sun.energy=2.45 if daylight else .94
    sun.color=(1.,.832,.635) if daylight else (1.,.76,.55)
    sun.angle=radians(1.2 if daylight else 4.5)
    ob=bpy.data.objects.new(sun.name,sun); coll.objects.link(ob)
    ray=(.66,.43,-.62) if daylight else (.78,.42,-.44)
    ob.rotation_euler=Vector(ray).to_track_quat('-Z','Y').to_euler()


def area(coll,loc,target,energy,size,color):
    li=bpy.data.lights.new('Concourse indirect luminaire','AREA')
    li.energy=energy; li.shape='DISK'; li.size=size; li.color=color
    ob=bpy.data.objects.new(li.name,li); coll.objects.link(ob); ob.location=loc; aim(ob,target)


def camera(scene,coll,origin,target,lens):
    lens_data=bpy.data.cameras.new('Architectural perspective')
    lens_data.lens=lens; lens_data.sensor_fit='HORIZONTAL'
    lens_data.clip_end=1200; lens_data.clip_start=.1
    ob=bpy.data.objects.new('Architecture | photograph',lens_data)
    coll.objects.link(ob); ob.location=origin; aim(ob,target); bind_camera(scene,ob)


def setup_arch(source,product,title,slug):
    sc=shot_scene(source,title,product,slug,(3840,2560))
    if product in list(sc.collection.children): sc.collection.children.unlink(product)
    sc.unit_settings.system='METRIC'; sc.unit_settings.scale_length=1.
    if hasattr(sc,'compositing_node_group'): sc.compositing_node_group=None
    sc.render.engine='CYCLES'; setup_scene(sc,96)
    sc.cycles.adaptive_min_samples=16; sc.cycles.adaptive_threshold=.015
    sc.render.image_settings.file_format='PNG'; sc.render.image_settings.color_mode='RGB'
    sc.render.image_settings.color_depth='16'; sc.render.film_transparent=False
    sc.view_settings.exposure=.04
    return sc,collection(sc,title[:2]+' | city fabric')


def malthouse(source,product,points,m):
    sc,coll=setup_arch(source,product,'05 Malthouse | Monument in the square','05-malthouse-square')
    environment(sc,coll)
    ground=Pieces(coll,'Malthouse | setts, kerbs and road markings')
    ground.box(0,8,-.13,240,206,.26,m['asphalt'])
    ground.box(0,2,.09,46,30,.18,m['stone'])
    for y in (-13,17): ground.box(0,y,.10,46.1,.23,.20,m['coping'])
    for x in (-23,23): ground.box(x,2,.10,.23,30,.20,m['coping'])
    for i in range(-8,9):
        ground.box(i*5,-17.25,.009,2.3,.14,.018,m['mark'])
        ground.box(i*5,19,.009,2.3,.14,.018,m['mark'])
    for xx in (-19.4,19.4):
        for j in range(9): ground.box(xx,-13.7-j*.83,.011,3.1,.39,.022,m['mark'])
    for xx in (-19,-15,-11,-7,7,11,15,19):
        ground.tube((xx,-12.5,.18),(xx,-12.5,1.00),.09,.075,m['steel'])
        ground.tube((xx,-12.5,.83),(xx,-12.5,.89),.077,.077,m['zinc'])
    for xx,yy in ((-18,-7),(-19,6),(17.5,-5),(17,7)):
        ground.box(xx,yy,.178,2.12,2.12,.055,m['dark'])
        bench(ground,m,xx,yy-1.5)
    ground.flush()
    placed_controller(coll,product,points,-90,-8,8.8,(0,1.4),.181,source.unit_settings.scale_length)
    factory(coll,m,-11.5,25.5,26.4,9.9,10.9,'Malthouse | 1893 mill')
    factory(coll,m,13.0,26.8,21.2,9.0,7.0,'Malthouse | cooperage')
    factory(coll,m,-31,5.5,22,11,7.2,'Malthouse | yard offices',90)
    for i,(x,w,h) in enumerate(((-37,16,8.2),(-18,18,10.4),(2,18,8.8),(23,20,11.8),(44,17,9.6))):
        factory(coll,m,x,42,w,10,h,'Industrial skyline | '+str(i))
    for i,(x,y,w,h) in enumerate(((-50,7,16,13),(-46,26,19,10),(-64,27,13,16),(-69,42,16,15),(-56,44,12,13),(-53,61,18,16),(-32,62,19,17),(-11,61,16,12),(10,62,19,11),(32,64,18,17))):
        factory(coll,m,x,y,w,10,h,'Warehouse quarter | '+str(i))
    street=Pieces(coll,'Malthouse | flue, street lamps and district furniture')
    for xx,yy,dx,dy in ((-11.5,25.5,29.,11.1),(13.,26.8,22.8,10.5),(-47,27,20,12)):
        street.box(xx,yy,.083,dx,dy,.166,m['concrete'])
    for xx,yy,z in ((-15,26.2,12.2),(-12.8,26.2,12.2),(-14,26.2,12.2),(15,27.5,8.2)):
        street.tube((xx,yy,z),(xx,yy,z+1.36),.22,.21,m['zinc'],16)
        street.tube((xx,yy,z+1.36),(xx,yy,z+1.53),.32,.22,m['roof'],16)
    street.tube((-21.8,26,0),(-21.8,26,19),1.1,.64,m['brick'],42)
    for z in (1.7,11,17.5,18.3,18.8,19.1):
        r=1.1-.46*z/19+.1
        street.tube((-21.8,26,z),(-21.8,26,z+.11),r,r,m['dark'],36)
    for xx in (-23.4,23.4):
        for yy in (-11.6,11.8):
            street.tube((xx,yy,0),(xx,yy,5.1),.10,.072,m['steel'])
            street.tube((xx,yy,5.1),(xx+1.1,yy,5.50),.057,.045,m['steel'])
            street.box(xx+1.25,yy,5.48,.67,.29,.13,m['roof'])
    street.flush()
    text_sign(coll,'M A L T   H O U S E',(-11.5,20.46,10.2),.57,m['ivory'])
    for x,y,seed,h in ((-18,-7,31,5.1),(-19,6,32,6.1),(17.5,-5,33,4.5),(17,7,34,5.4),(-26,16,38,6.6),(25,17,35,6.5),(-35,23,39,8.),(-35,29,40,9.1),(-31,34,41,8.5),(-5.8,35.7,42,8.3),(20.7,35,43,7.6)):
        avenue_tree(coll,m,x,y,seed,h)
    for x,y,ang,paint in ((-10.5,-15.3,0,'tram'),(9.3,-18.9,180,'ivory'),(-14.5,18.5,0,'red'),(13.6,18.5,0,'sand'),(23.7,3.2,90,'ivory')):
        vehicle(coll,m,x,y,ang,'Road vehicle',paint)
    for seed,(x,y,rot) in enumerate(((-11,-9,25),(-10.3,-8.9,-50),(3,-10,55),(4.5,-10.4,120),(7.9,-7,-60),(-14,-3,70),(16,2,-130),(12.3,10,175),(-12,10,160),(20,-11.5,90),(-4.3,-11.1,20)),100):
        pedestrian(coll,m,x,y,rot,seed,.18)
    camera(sc,coll,(20,-43,32),(.2,3.8,3.2),37.5)
    return sc


def station(source,product,points,m):
    sc,coll=setup_arch(source,product,'08 North Quay | Walk-through transit gate','08-north-quay-gateway')
    environment(sc,coll,False)
    g=Pieces(coll,'North Quay | passenger route, platforms and tracks')
    g.box(0,3,-.15,240,160,.30,m['asphalt'])
    g.box(0,-12,.065,97,41.4,.13,m['tile'])
    for a in (-1,1):
        g.box(a*3.95,-8.05,.14,.19,33.4,.016,m['coping'])
        g.box(a*4.17,-8.05,.14,.035,33.4,.016,m['zinc'])
    for line_y in (8.1,15.7):
        g.box(0,line_y,.21,88,1.31,.42,m['concrete'])
        g.box(0,line_y-.08,.424,88,.15,.021,m['ochre'])
        g.box(0,line_y-.35,.424,88,.27,.021,m['coping'])
    for y in (10.50,11.94):
        g.box(0,y,.061,95,.083,.13,m['rail'])
    for i in range(-63,64):
        g.box(i*.68,11.22,.021,.20,2.23,.062,m['dark'])
    for xx in range(-36,40,11):
        g.tube((xx,15,0),(xx,15,6.55),.12,.078,m['zinc'])
        g.tube((xx,15,6.2),(xx,10.25,5.25),.045,.032,m['rail'])
        g.tube((xx,15,5.25),(xx,10.25,5.25),.061,.044,m['zinc'])
    for yy,zz in ((11.12,4.59),(11.55,5.19),(11.54,5.48)):
        g.tube((-67,yy,zz),(67,yy,zz),.014,.014,m['dark'],6)
    for x,y in ((-7.3,-9),(-7.4,3),(7.4,3),(9,-6)):
        bench(g,m,x,y)
    for xx in (-4.65,4.65):
        for yy in (-18,-10,-2,5):
            g.box(xx,yy,.47,.13,.17,.68,m['dark'])
            g.box(xx,yy-.005,.80,.11,.18,.065,m['lamp'])
    g.flush()
    placed_controller(coll,product,points,0,0,8.7,(0,0),.132,source.unit_settings.scale_length)
    vehicle(coll,m,-1.6,11.22,0,'Interurban tram','tram')
    depot=Pieces(coll,'North Quay | glazed shelter and departure clock')
    # Hanger rods terminate at the measured 6.51 m soffit of the original housing.
    for x in (-2.85,2.85):
        depot.tube((x,.00,5.99),(x,.00,6.55),.048,.048,m['steel'])
        depot.box(x,.00,6.49,.28,.32,.11,m['steel'])
    depot.box(0,0,5.68,7.5,.29,.68,m['dark'])
    depot.box(-3.10,-.16,5.68,1.11,.05,.63,m['tram'])
    text_sign(coll,'02',(-3.10,-.202,5.68),.47,m['lamp'])
    text_sign(coll,'NORTH   QUAY',(0.47,-.18,5.68),.44,m['lamp'])
    for xx in (-4.55,4.55):
        depot.box(xx,-.36,6.46,2.68,.13,.11,m['steel'])
        depot.box(xx,-.36,6.40,2.54,.095,.048,m['lamp'])
    for xx in (-2.7,2.7):
        depot.box(xx,1.15,.65,.37,.82,1.04,m['steel'])
        depot.box(xx,1.15,1.19,.39,.88,.10,m['dark'])
        depot.box(xx,.75,1.20,.29,.16,.07,m['tram'])
        depot.box(xx,.696,1.24,.18,.07,.016,m['lamp'])
    for x in (-21.4,17.8):
        depot.box(x,17.7,3.52,15.7,3.5,.27,m['zinc'])
        depot.box(x,17.7,3.36,15.63,3.45,.075,m['lamp'])
        for i in range(6):
            xx=x-6.9+i*2.75
            depot.box(xx,18.3,1.74,.12,.14,3.48,m['steel'])
            if i<5: depot.box(xx+1.37,18.62,1.76,2.68,.058,2.72,m['glass2'])
        for xx in (-3.2,3.2): bench(depot,m,x+xx,17.3)
    for x,y in ((-7.3,-5.7),(12.1,6.5)):
        depot.box(x,y,1.6,1.29,.31,3.0,m['dark'])
        depot.box(x,y,3.01,1.32,.35,.17,m['copper'])
        depot.box(x,y-.16,2.37,1.02,.035,.79,m['tram'])
        text_sign(coll,'M',(x,y-.189,2.37),.65,m['lamp'])
        text_sign(coll,'NORTH QUAY',(x,y-.179,1.50),.135,m['white'])
        text_sign(coll,'TRAM  02',(x,y-.179,1.23),.11,m['white'])
    depot.flush()
    # A setback office building and apartments give the plaza a true street horizon.
    for row,(xx,yy,w,h) in enumerate(((-40,38,12,12),(-24,40,17,8.4),(-6,46,10,11),(8,44,13,8),(26,36,16,14),(43,39,14,9))):
        q=Pieces(coll,'North Quay | perimeter block '+str(row))
        q.box(xx,yy,h/2,w,8,h,m['brick' if row%3==1 else 'concrete'])
        for k in range(round(h/2.9)):
            zz=1.55+k*2.9
            q.box(xx,yy-4.06,zz,w+.14,.19,1.29,m['glass'])
            for j in range(round(w/1.7)):
                q.box(xx-w/2+j*1.7+.6,yy-4.16,zz,.07,.12,1.35,m['steel'])
            q.box(xx,yy-4.04,zz-.74,w+.2,.38,.15,m['zinc'])
        if row%2:
            for j in range(round(w/2.2)):
                q.box(xx-w*.5+(j+.5)*2.2,yy-4.2,h*.51,.13,.48,h*.96,m['copper' if row==1 else 'zinc'])
        q.box(xx,yy,h+.09,w+.2,8.2,.2,m['zinc'])
        q.box(xx+w*.15,yy,h+.71,w*.4,4.5,1.25,m['roof'])
        q.flush()
    for i,(x,y,h) in enumerate(((-20,7,5.9),(19.2,4.4,5.8),(-13.6,22,6.2),(13,21,5.4))):
        avenue_tree(coll,m,x,y,71+i,h)
    for seed,(x,y,rot) in enumerate(((-1.6,-6,159),(-.75,-5.8,129),(1.9,-1.1,67),(.65,3.1,173),(-1.9,5.0,-35),(3.3,7.55,100),(-6.9,6.57,11),(8.1,-4.2,-52),(-8.65,-4.5,50),(3.7,-9,22)),210):
        pedestrian(coll,m,x,y,rot,seed,.132)
    for x in (-4.55,4.55):
        area(coll,(x,-.36,6.32),(x*.63,.6,.1),660,2.0,(1,.65,.35))
    area(coll,(-9.5,-19,20),(-2,-1,11),5200,14,(.76,.87,1.0))
    camera(sc,coll,(5.4,-38.5,4.1),(0,0,9.10),34)
    return sc


def build(source):
    product=bpy.data.collections[PARTS]
    points=assembly_points(product)
    m=palette()
    return malthouse(source,product,points,m),station(source,product,points,m)


def vehicle(coll,m,x,y,yaw,kind,pigment):
    q=Pieces(coll,kind,(x,y,.02),yaw)
    if kind=='Interurban tram':
        q.box(0,0,.85,16.9,2.65,1.02,m['tram'])
        q.box(0,0,1.97,16.75,2.62,1.23,m['ivory'])
        q.box(0,0,2.70,16.78,2.69,.28,m['ivory'])
        for s in (-1,1):
            for i in range(13):
                xx=-7.60+1.27*i
                q.box(xx,s*1.32,2.05,1.06,.055,.82,m['glass'])
                q.box(xx,s*1.35,2.16,1.05,.027,.029,m['steel'])
            for xx in (-5.,4.9):
                q.box(xx,s*1.35,1.54,.92,.045,1.89,m['dark'])
                for a in (-.23,.23): q.box(xx+a,s*1.39,1.96,.37,.038,.85,m['glass2'])
            q.box(0,s*1.358,1.38,16.62,.016,.07,m['copper'])
        for xx in (-8.44,8.44):
            q.box(xx,0,2.13,.10,2.22,1.03,m['glass'])
        for xx in (-4.2,3.6):
            q.box(xx,0,2.94,2.7,1.46,.26,m['steel'])
        q.tube((0,0,2.88),(1.25,0,3.63),.045,.045,m['dark']); q.tube((1.25,0,3.63),(0,0,4.31),.05,.04,m['dark'])
        q.box(0,0,4.33,.085,1.4,.052,m['rail'])
        wheels=(-6.5,-5.1,5.1,6.5); width=1.23; wr=.39
    else:
        # Curved cast body with longitudinal profile and rounded glasshouse.
        paint=m[pigment]
        def shell(sections,mat):
            verts=[]
            for xx,half,base,top in sections:
                verts.extend([(xx,-half*.86,base),(xx,half*.86,base),(xx,half,base+.09),
                              (xx,half,top-.1),(xx,half*.85,top),(xx,-half*.85,top),
                              (xx,-half,top-.10),(xx,-half,base+.09)])
            n=8
            faces=[(k*n+j,k*n+(j+1)%n,(k+1)*n+(j+1)%n,(k+1)*n+j) for k in range(len(sections)-1) for j in range(n)]
            faces.extend([tuple(reversed(range(n))),tuple(range(len(verts)-n,len(verts)))])
            q.part(verts,faces,mat)
        shell([(-2.2,.73,.32,.68),(-1.90,.86,.30,.83),(-.8,.91,.30,.94),(1.34,.88,.32,.93),(2.16,.80,.36,.82)],paint)
        shell([(-1.25,.77,.83,.94),(-.64,.73,.85,1.45),(.84,.74,.86,1.47),(1.42,.78,.85,.98)],m['glass'])
        q.box(.08,0,1.477,1.47,1.22,.042,paint)
        for s in (-1,1):
            q.box(.15,s*.744,1.14,.076,.055,.53,paint)
            q.box(-2.205,s*.54,.59,.032,.32,.12,m['lamp'])
            q.box(2.167,s*.53,.61,.032,.31,.12,m['red'])
        wheels=(-1.37,1.30); width=.868; wr=.32
    for xx in wheels:
        for s in (-1,1):
            q.tube((xx,s*(width-.075),wr),(xx,s*(width+.045),wr),wr,wr,m['rubber'],20)
            q.tube((xx,s*(width+.042),wr),(xx,s*(width+.052),wr),wr*.53,wr*.53,m['zinc'],16)
    q.flush()
