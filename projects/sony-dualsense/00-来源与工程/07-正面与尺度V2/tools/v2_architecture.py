"""Rebuild the two architectural plates in an opened eight-scene project."""
from math import cos, sin, pi, radians
from pathlib import Path
from random import Random

import bpy
from mathutils import Vector, Matrix, Euler
import numpy as np

from faceup_architecture import Pieces, placed_controller, camera, text_sign, area, finish
from build_studio import PARTS, collection
from build_lineup import assembly_points

ROOT=Path(__file__).resolve().parents[1]/'v2-work'/'architecture'
ASSETS=ROOT/'assets'


def pic(path,colorspace=None):
    im=bpy.data.images.load(str(path),check_existing=True)
    if colorspace: im.colorspace_settings.name=colorspace
    if not im.packed_file: im.pack()
    return im


def scan_surface(name,texture,scale,tint=(1,1,1)):
    mat=finish(name,(.28,.30,.29),.72)
    t=mat.node_tree; n=t.nodes;l=t.links.new
    p=next(a for a in n if a.type=='BSDF_PRINCIPLED')
    pos=n.new('ShaderNodeNewGeometry')
    vec=n.new('ShaderNodeVectorMath'); vec.operation='SCALE';vec.inputs['Scale'].default_value=scale
    l(pos.outputs['Position'],vec.inputs[0])
    def tex(slot):
        path=next((ASSETS/texture).glob(slot+'.*'))
        node=n.new('ShaderNodeTexImage')
        node.image=pic(path,'Non-Color' if slot=='rough' else None)
        node.projection='BOX';node.projection_blend=.12
        l(vec.outputs['Vector'],node.inputs[0]);return node.outputs[0]
    color=tex('diff')
    mix=n.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1.
    mix.inputs[2].default_value=(*tint,1);l(color,mix.inputs[1])
    tone=n.new('ShaderNodeHueSaturation')
    tone.inputs['Saturation'].default_value=.69 if texture.startswith('damaged') else .79
    tone.inputs['Value'].default_value=1.15 if texture.startswith('damaged') else 2.1
    l(mix.outputs[0],tone.inputs['Color']);l(tone.outputs['Color'],p.inputs['Base Color'])
    if list((ASSETS/texture).glob('rough.*')):l(tex('rough'),p.inputs['Roughness'])
    bump=n.new('ShaderNodeBump');bump.inputs['Distance'].default_value=.012;bump.inputs['Strength'].default_value=.39
    l(color,bump.inputs['Height']);l(bump.outputs[0],p.inputs['Normal'])
    return mat


def world(sc,slug,yaw,strength):
    w=bpy.data.worlds.new('Photographic location | '+slug)
    if w.node_tree is None: w.use_nodes=True
    sc.world=w;t=w.node_tree;n=t.nodes;l=t.links.new
    bg=next(o for o in n if o.type=='BACKGROUND')
    env=n.new('ShaderNodeTexEnvironment');env.image=pic(ASSETS/(slug+'.hdr'))
    coord=n.new('ShaderNodeTexCoord');mapping=n.new('ShaderNodeMapping')
    mapping.inputs['Rotation'].default_value[2]=radians(yaw)
    l(coord.outputs['Generated'],mapping.inputs[0]);l(mapping.outputs[0],env.inputs[0])
    l(env.outputs[0],bg.inputs[0]);bg.inputs[1].default_value=strength
    # Separate camera backplate preserves the native detail of the 8K panorama.
    photo=n.new('ShaderNodeTexEnvironment');photo.image=pic(ROOT/(slug+'-photo.jpg'))
    l(mapping.outputs[0],photo.inputs[0])
    plate=n.new('ShaderNodeBackground');l(photo.outputs[0],plate.inputs[0])
    plate.inputs[1].default_value=1.04
    mix=n.new('ShaderNodeMixShader');path=n.new('ShaderNodeLightPath')
    l(path.outputs['Is Camera Ray'],mix.inputs[0]);l(bg.outputs[0],mix.inputs[1]);l(plate.outputs[0],mix.inputs[2])
    l(mix.outputs[0],next(o for o in n if o.type=='OUTPUT_WORLD').inputs['Surface'])
    return w


def scansource(name):
    title='Photogrammetry | '+name
    existing=bpy.data.collections.get(title)
    if existing: return existing
    source=bpy.data.collections.new(title)
    before=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(ASSETS/name/(name+'.gltf')))
    objs=set(bpy.data.objects)-before
    for ob in objs:
        for coll in list(ob.users_collection): coll.objects.unlink(ob)
        source.objects.link(ob)
    for ob in objs:
        if ob.type=='MESH':
            for mat in ob.data.materials:
                if mat and mat.node_tree:
                    for node in mat.node_tree.nodes:
                        if node.type=='TEX_IMAGE' and node.image and not node.image.packed_file: node.image.pack()
    return source


def prop(coll,name,position,length,tilt=(0,0,0)):
    group=scansource(name)
    inst=bpy.data.objects.new('Found object | '+name,None);coll.objects.link(inst)
    inst.instance_type='COLLECTION';inst.instance_collection=group
    rot=Euler(tuple(radians(a) for a in tilt),'XYZ'); inst.rotation_euler=rot
    bb=[rot.to_matrix()@(obj.matrix_world@Vector(v)) for obj in group.all_objects if obj.type=='MESH' for v in obj.bound_box]
    low=np.min(bb,axis=0);high=np.max(bb,axis=0)
    factor=length/max(high-low); inst.scale=(factor,)*3
    center=np.array(((low[0]+high[0])/2,(low[1]+high[1])/2,low[2]))*factor
    inst.location=Vector(position)-Vector(center)
    print('PROP',name,np.round((high-low)*factor,2),flush=True)
    return inst


def figure(coll,index,location,height,eye):
    # UV bounds record the opaque pixels in each 1024px source. The feet sit on the deck.
    bounds={0:(382,332,700,873),36:(349,99,690,971),38:(343,146,706,891),44:(366,154,662,892)}
    x0,y0,x1,y1=bounds[index]
    width=height*(x1-x0)/(y1-y0)
    me=bpy.data.meshes.new('Gendo | photographic-scale figure')
    me.from_pydata([(-width/2,0,0),(width/2,0,0),(width/2,0,height),(-width/2,0,height)],[],[(0,1,2,3)])
    uv=me.uv_layers.new()
    for item,coords in zip(uv.data,((x0,1024-y1),(x1,1024-y1),(x1,1024-y0),(x0,1024-y0))):
        item.uv=(coords[0]/1024,coords[1]/1024)
    ob=bpy.data.objects.new('Visitor | '+str(index),me);coll.objects.link(ob);ob.location=location
    eye_vec=Vector(eye)-Vector(location);eye_vec.z=0
    ob.rotation_euler=eye_vec.to_track_quat('-Y','Z').to_euler()
    mat=finish('Gendo | clothing '+str(index),(.4,.4,.4),.85)
    t=mat.node_tree;p=next(o for o in t.nodes if o.type=='BSDF_PRINCIPLED')
    im=t.nodes.new('ShaderNodeTexImage');im.image=pic(ASSETS/('figure-'+str(index)+'.png'))
    t.links.new(im.outputs[0],p.inputs['Base Color']);t.links.new(im.outputs['Alpha'],p.inputs['Alpha'])
    p.inputs['Specular IOR Level'].default_value=.07
    t.links.new(im.outputs[0],p.inputs['Emission Color']);p.inputs['Emission Strength'].default_value=.16
    ob.data.materials.append(mat)
    return ob


def getscene(num,title,slug):
    s=next(sc for sc in bpy.data.scenes if sc.name.startswith(num+' '))
    for c in list(s.collection.children):s.collection.children.unlink(c)
    for ob in list(s.collection.objects):s.collection.objects.unlink(ob)
    s.timeline_markers.clear()
    s.name=num+' '+title
    s.render.filepath='//renders/'+slug+'.png'
    s.view_settings.exposure=0.
    s.render.film_transparent=False
    if hasattr(s,'compositing_node_group'):s.compositing_node_group=None
    s.cycles.samples=96;s.cycles.adaptive_min_samples=16
    s.cycles.adaptive_threshold=.015
    bpy.context.window.scene=s
    return s,collection(s,num+' | V2 site')


def rail(q,a,b,m,height=1.04,spacing=1.65,chain=False):
    a,b=Vector(a),Vector(b)
    n=max(1,round((b-a).length/spacing))
    dz=Vector((0,0,height))
    for i in range(n+1):
        p=a+(b-a)*i/n
        q.tube(p,p+dz,.026,.024,m,10)
        q.box(p.x,p.y,p.z+.018,.13,.13,.036,m)
    for z in (.53,height):
        delta=Vector((0,0,z));q.tube(a+delta,b+delta,.019 if z<1 else .03,.019 if z<1 else .03,m,10)


def bathwater():
    mat=finish('Water | dark mineral lake',(.032,.082,.10),.145,.18)
    n=mat.node_tree.nodes;l=mat.node_tree.links.new
    p=next(o for o in n if o.type=='BSDF_PRINCIPLED')
    p.inputs['Coat Weight'].default_value=.52;p.inputs['Coat Roughness'].default_value=.075
    p.inputs['IOR'].default_value=1.333
    pos=n.new('ShaderNodeNewGeometry')
    vec=n.new('ShaderNodeVectorMath');vec.operation='MULTIPLY';vec.inputs[1].default_value=(.82,2.8,1.)
    l(pos.outputs['Position'],vec.inputs[0])
    no=n.new('ShaderNodeTexNoise');no.inputs['Scale'].default_value=2.05;no.inputs['Detail'].default_value=4.
    no.inputs['Roughness'].default_value=.60;l(vec.outputs[0],no.inputs[0])
    bu=n.new('ShaderNodeBump');bu.inputs['Distance'].default_value=.055;bu.inputs['Strength'].default_value=.28
    l(no.outputs[0],bu.inputs['Height']);l(bu.outputs[0],p.inputs['Normal'])
    dist=n.new('ShaderNodeVectorMath');dist.operation='DISTANCE'
    l(pos.outputs['Position'],dist.inputs[0]);dist.inputs[1].default_value=(2,-5,0)
    remap=n.new('ShaderNodeMapRange');remap.interpolation_type='SMOOTHERSTEP'
    remap.inputs['From Min'].default_value=5.;remap.inputs['From Max'].default_value=19.0
    l(dist.outputs['Value'],remap.inputs[0])
    transparent=n.new('ShaderNodeBsdfTransparent');combine=n.new('ShaderNodeMixShader')
    l(remap.outputs[0],combine.inputs[0]);l(p.outputs[0],combine.inputs[1]);l(transparent.outputs[0],combine.inputs[2])
    l(combine.outputs[0],next(o for o in n if o.type=='OUTPUT_MATERIAL').inputs[0])
    return mat


def base_mats():
    return {'concrete':scan_surface('Dry dock | timeworn concrete','damaged_concrete_floor_03',.24,(.81,.83,.84)),
            'timber':scan_surface('Waterline | greyed larch','weathered_planks',.49,(.80,.71,.60)),
            'steel':finish('Salt water stainless steel',(.37,.39,.40),.29,.82,1.9),
            'iron':finish('Dock iron',(.088,.087,.072),.48,.63,4.),
            'rust':finish('Weathered marine red oxide',(.26,.085,.031),.72,.17,3.),
            'yellow':finish('Dockside faded yellow',(.55,.31,.065),.67,.08,7.),
            'white':finish('Painted lettering',(.76,.72,.61),.72,0,13.),
            'teal':finish('Glazed deep petrol',(.028,.095,.102),.32,.31,0),
            'sail':finish('Canvas natural sailcloth',(.48,.43,.32),.84,0,29.),
            'stripe':finish('Cotton towel stripe',(.14,.25,.27),.88,0,54.),
            'water':bathwater()}


def drydock(product,cloud,m):
    sc,c=getscene('05','Dock 12 | A monument in dry dock','05-drydock-monument')
    world(sc,'docklands_01',30,1.05)
    q=Pieces(c,'Dock 12 | cast concrete, damp floor and access galleries')
    q.box(0,0,-.30,58,71,.6,m['concrete'])
    # Terrazo steps follow the profile of a real graving dock and cast scale-bearing shadows.
    for j in range(8):
        h=j*.78+.78
        for side in (-1,1):
            q.box(side*(17.75+j*.69),0,h*.5,.72,60,h,m['concrete'])
        q.box(0,16.8+j*.72,h*.5,48,.76,h,m['concrete'])
    q.box(0,37.6,3.12,84,33,6.24,m['concrete'])
    for side in (-1,1):
        q.box(side*32,0,3.12,18.5,74,6.24,m['concrete'])
    q.flush()
    # Embedded crane tracks and number stencils give the basin its original working scale.
    q=Pieces(c,'Dock 12 | crane track and old survey marks')
    for xx in (-13.95,14.75):
        q.box(xx,-5.0,.016,.072,46,.032,m['iron'])
        for y in range(-25,17,2):
            q.box(xx,y,.034,.13,.13,.018,m['rust'])
    for x in (-7.5,-4.1,-.7,2.7,6.1):
        q.box(x,-12.1,.005,1.76,.10,.01,m['yellow'])
    q.flush()
    f=bpy.data.curves.new('Dry dock service markings','FONT');f.body='12';f.align_x='CENTER'
    f.size=2.25;f.extrude=.0006
    o=bpy.data.objects.new('Dry dock | faded bay number',f);c.objects.link(o)
    o.location=(-9.1,-12.7,.009);o.rotation_euler.z=radians(-3);f.materials.append(m['white'])
    metal=Pieces(c,'Dock 12 | mooring bollards, safety rail and tide gauges')
    for xx in (-23.,23.):
        rail(metal,(xx,-30,6.25),(xx,21.5,6.25),m['iron'],1.03,2.3)
    rail(metal,(-23.,22.15,6.25),(23.,22.15,6.25),m['iron'],1.03,2.2)
    for xx in (-20,-11,-2,9,18):
        metal.tube((xx,23.55,6.25),(xx,23.55,6.31),.38,.39,m['iron'],20)
        metal.tube((xx,23.55,6.31),(xx,23.55,6.77),.23,.28,m['iron'],24)
        metal.ell(xx,23.55,6.78,.31,.31,.11,m['iron'])
    for x in (-15.5,14.3):
        for j in range(27):
            y=15.0+j*.30;z=.23*j
            metal.box(x,y,z+.065,1.38,.32,.13,m['iron'])
        rail(metal,(x-.73,15.0,.1),(x-.73,22.8,6.2),m['yellow'],.97,1.82)
        rail(metal,(x+.73,15.0,.1),(x+.73,22.8,6.2),m['yellow'],.97,1.82)
    metal.flush()
    for x,y,ang in ((-11,24.95,7),(-7.6,25.05,7),(13.9,23.40,0),(24.1,-9,88)):
        prop(c,'concrete_road_barrier_02',(x,y,6.25),2.45,(0,0,ang))
    prop(c,'hand_truck',(16.8,25.5,6.25),1.45,(0,0,-28))
    q=Pieces(c,'Dock 12 | floating datum posts')
    for x in (13.7,-14.6):
        q.box(x,17.03,1.67,.60,.15,3.36,m['teal'])
        for j in range(14):q.box(x-.13,16.94,.19+j*.22,.24 if j%3==0 else .13,.035,.045,m['white'])
    q.flush()
    # Two thirds occupied by the original horizontal shell. No new geometry on the controls.
    inst=placed_controller(c,product,cloud,-90,-15,7.7,(-.3,.0),.016,.05)
    camera(sc,c,(21.0,-36.1,14.2),(-.7,1.2,5.25),37.0)
    figure(c,36,(-8.75,-10.1,.018),1.69,sc.camera.location)
    figure(c,44,(-6.7,-10.0,.018),1.79,sc.camera.location)
    sc['design_reference']='Little Island, Heatherwick Studio — reveal foundation and surrounding human infrastructure'
    return sc


def towel(q,x,y,z,h,mat,stripe):
    # A bath sheet partially folded over the edge of the slatted bench.
    steps=24; rows=11
    co=[]
    for j in range(rows):
        for i in range(steps+1):
            u=i/steps;v=j/(rows-1)
            bend=max(0.,v-.44)
            co.append((x+(u-.5)*.71+.020*sin(v*7+u*6),
                       y+min(v,.44)*.85+sin(bend*pi)*.055,
                       z-bend*h+.014*sin(u*17+v*2)+.023*sin(u*6.6+v*8)))
    for j in range(rows-1):
        for i in range(steps):
            a=j*(steps+1)+i
            q.part([co[k] for k in (a,a+1,a+steps+2,a+steps+1)],[(0,1,2,3)],stripe if j in (6,8) else mat,True)


def sea_bath(product,cloud,m):
    sc,c=getscene('08','Tidal Room | A sheltered lake landing','08-tidal-room')
    world(sc,'small_harbor_02',179,.93)
    q=Pieces(c,'Tidal room | larch decking, stair treads and open bracing')
    def deck(x0,x1,y0,y1,z):
        count=round((x1-x0)/.175);width=(x1-x0)/count
        for j in range(count):
            xx=x0+(j+.5)*width
            q.box(xx,(y0+y1)/2,z-.048,width-.007,y1-y0,.096,m['timber'])
        for yy in (y0+.09,(y0+y1)/2,y1-.09):
            q.box((x0+x1)/2,yy,z-.20,x1-x0,.21,.23,m['timber'])
    deck(-8.5,7.1,-2.08,2.55,.96)
    deck(2.6,7.1,-15,-2.08,.96)
    for j in range(6):
        yy=2.55+j*.35
        deck(-3.15,2.3,yy,yy+.35,.96-.16*(j+1))
    for xx in (-8.14,-3.4,2.7,6.85):
        for yy in (-1.85,2.25):
            q.tube((xx,yy,-1),(xx,yy,.89),.225,.206,m['timber'],14)
    for yy in (-4,-7,-10,-13.5):
        for x in (2.78,6.92):q.tube((x,yy,-1.1),(x,yy,.91),.16,.14,m['timber'],12)
    q.flush()
    water=Pieces(c,'Tidal room | reflecting lake')
    water.box(0,-3,-.11,92,52,.16,m['water']);water.flush()
    tech=Pieces(c,'Tidal room | swim ladder, towel rail and mooring cleats')
    rail(tech,(6.94,-14.7,.965),(6.94,-2.34,.965),m['steel'],.96,1.98)
    rail(tech,(2.72,-14.7,.965),(2.72,-2.34,.965),m['steel'],.96,1.98)
    rail(tech,(-8.36,-1.92,.965),(-8.36,2.4,.965),m['steel'],.96)
    rail(tech,(-3.03,2.57,.82),(-3.03,4.65,-.085),m['steel'],.96,1.12)
    rail(tech,(2.18,2.57,.82),(2.18,4.65,-.085),m['steel'],.96,1.12)
    for side in (-1,1):
        xx=-5.6+side*.27
        pts=[(xx,2.06,.95),(xx,2.06,1.31)]
        pts.extend((xx,2.34-.28*cos(pi*j/15),1.31+.28*sin(pi*j/15)) for j in range(1,16))
        pts.append((xx,2.62,-.72))
        for a,b in zip(pts,pts[1:]):tech.tube(a,b,.028,.028,m['steel'],12)
    for j in range(6):tech.tube((-5.87,2.62,-.56+j*.26),(-5.33,2.62,-.56+j*.26),.026,.026,m['steel'])
    for xx in (-4.95,-3.39):
        tech.box(xx,-.55,1.18,.09,.52,.44,m['steel'])
    for i in range(5):
        tech.box(-4.17,-.78+i*.12,1.43,2.26,.095,.065,m['timber'])
    towel(tech,-4.64,-.83,1.475,.84,m['sail'],m['stripe'])
    tech.flush()
    prop(c,'lifebuoy',(-3.16,-.93,1.23),.79,(0,0,10))
    prop(c,'life_jacket',(-3.48,-.55,1.48),.65,(90,0,-19))
    # A dedicated weatherproof bracket makes the rescue ring reachable from the deck.
    stand=Pieces(c,'Tidal room | emergency ring cradle')
    stand.box(-3.16,-.74,1.51,.07,.08,1.08,m['steel']);stand.box(-3.16,-.75,.985,.28,.31,.05,m['steel']);stand.flush()
    inst=placed_controller(c,product,cloud,0,-8,4.65,(-.02,.04),.965,.05)
    # A pair of suspended changing curtains tied back on a rail attached to the shell.
    textile=Pieces(c,'Tidal room | hanging sailcloth and shower fittings')
    for x in (-4.9,-2.8):
        textile.tube((x,.52,3.18),(x,.52,4.70),.032,.032,m['steel'],12)
    textile.tube((-5.61,.52,3.18),(-2.03,.52,3.18),.036,.036,m['steel'],16)
    for x0 in (-5.51,-3.16):
        verts=[];faces=[];N=36;K=11
        for j in range(K+1):
            v=j/K
            width=.91-.25*sin(pi*v)
            for i in range(N+1):
                u=i/N
                verts.append((x0+u*width,
                              .52+.056*sin(u*pi*11+.44*v)+.081*v*v,
                              3.12-v*1.79+.016*sin(u*19)*v))
        for j in range(K):
            for i in range(N):
                k=j*(N+1)+i;faces.append((k,k+1,k+N+2,k+N+1))
        textile.part(verts,faces,m['sail'],True)
        for j in range(6):
            x=x0+j*.174;textile.tube((x,.52,3.08),(x,.52,3.18),.011,.011,m['steel'],8)
    textile.flush()
    area(c,(-3.9,-.25,3.72),(-3.7,-.8,.98),225,1.15,(1.,.72,.46))
    area(c,(1.9,-.10,3.73),(1.3,1,.96),165,1.5,(1.,.76,.55))
    camera(sc,c,(8.6,-13.9,2.65),(-.85,1.2,4.25),26)
    figure(c,38,(.45,.72,.963),1.77,sc.camera.location)
    figure(c,0,(-4.32,-.70,.963),1.29,sc.camera.location)
    sc['design_reference']='The Podium, MVRDV — visible continuous approach, changing level and destination'
    return sc


def revise():
    product=bpy.data.collections[PARTS]
    cloud=assembly_points(product);m=base_mats()
    return drydock(product,cloud,m),sea_bath(product,cloud,m)
