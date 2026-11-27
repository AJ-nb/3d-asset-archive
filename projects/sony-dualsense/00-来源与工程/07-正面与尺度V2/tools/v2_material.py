"""Rebuild the two material photographs in an opened copy of the face-up master."""
from math import cos, pi, radians, sin
import bpy
import bmesh
import numpy as np
from mathutils import Vector
from build_studio import camera_rig, collection, set_area
from faceup_material_worlds import bilinear_texture, box, plain, relief_source, solid, surface, textured, tube


def scene_number(number):
    return next(s for s in bpy.data.scenes if s.name.startswith(number+' '))


def fresh(scene, keep=()):
    # Collections are unlinked only in this derived file. Preserve the actual source assembly.
    for group in list(scene.collection.children):
        if group.name not in keep:
            scene.collection.children.unlink(group)
    scene.timeline_markers.clear()
    bpy.context.window.scene=scene
    scene.frame_set(1)
    bpy.context.view_layer.update()


def bounce(scene, color, strength):
    node=next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND')
    node.inputs['Color'].default_value=(*color,1)
    node.inputs['Strength'].default_value=strength


def noise2(x,y):
    ix,iy=np.floor(x),np.floor(y)
    fx,fy=x-ix,y-iy
    fx=fx*fx*(3-2*fx)
    fy=fy*fy*(3-2*fy)
    def hashed(i,j):
        z=np.sin(i*127.1+j*311.7)*43758.5453123
        return 2*(z-np.floor(z))-1
    return ((1-fy)*((1-fx)*hashed(ix,iy)+fx*hashed(ix+1,iy))
            +fy*((1-fx)*hashed(ix,iy+1)+fx*hashed(ix+1,iy+1)))


def section_profile(x,y):
    # The gently folded carrier is the large-scale curvature under the sampled grip skin.
    return (1.03+.035*y+.20*np.sin(.60*x-.44*y)+.23*np.sin(.72*y+.26*x)
            +.15*np.cos(.83*x+.26*y)+.15*np.tanh((.35*x+.74*y+.85)*1.3)
            +.39*np.exp(-((y-.47*x-3.45)/1.07)**2)-.13*np.exp(-((y+.13*x-.60)/.61)**2))


def rect_volume(group,name,top,bottom,material,edge_material):
    """Build a watertight grid specimen with explicitly modeled outer and cut faces."""
    ny,nx=top.shape[:2]
    idx=np.arange(ny*nx).reshape(ny,nx)
    rim=np.concatenate((idx[0,:],idx[1:,-1],idx[-1,-2::-1],idx[-2:0:-1,0]))
    tgrid=top.reshape(-1,3)
    low=bottom.reshape(-1,3)[rim]
    # Each torn side has an irregular ledge and short granular facets through its thickness.
    high=tgrid[rim]
    fracture_scale=np.clip((high[:,2]-low[:,2])/.25,0.,1.)
    tangent=np.roll(high[:,:2],-1,axis=0)-np.roll(high[:,:2],1,axis=0)
    outward=np.column_stack((tangent[:,1],-tangent[:,0]))
    outward/=np.maximum(np.linalg.norm(outward,axis=1)[:,None],1e-8)
    walk=np.cumsum(np.linalg.norm(high[:,:2]-np.roll(high[:,:2],1,axis=0),axis=1))
    layers=[high]
    heights=(.08,.19,.32,.37,.48,.63,.79,.93,1.)
    for k in heights:
        ring=(1-k)*high+k*low
        if k<1:
            grit=noise2(walk*24,k*19+walk*.044)
            # Hand-sheared clay opens along a local bedding plane at mid-wall.
            ledge=(.018*np.sin(walk*7+k*5)+.028*grit+.012*noise2(walk*64,k*35))
            ledge+=(-.045 if k==.37 else .017 if k==.32 else 0)*(.65+.35*np.sin(walk*2))
            ring[:,:2]+=outward*(ledge*fracture_scale)[:,None]
            ring[:,2]+=(.014*noise2(walk*26,k*11)+.013*np.sin(5*walk+k*7))*np.sin(pi*k)*fracture_scale
        layers.append(ring)
    coords=np.concatenate((tgrid,*layers[1:]))
    start=idx[:-1,:-1]
    quad=np.stack((start,start+1,start+nx+1,start+nx),axis=-1).reshape(-1,4)
    nbase=len(tgrid)
    edge=np.arange(len(rim))
    side=[]
    for idx_layer in range(len(heights)):
        r0=rim if idx_layer==0 else nbase+(idx_layer-1)*len(rim)+edge
        r1=nbase+idx_layer*len(rim)+edge
        side.append(np.stack((r0,r1,np.roll(r1,-1),np.roll(r0,-1)),axis=-1))
    side=np.concatenate(side)
    nlow=nbase+(len(heights)-1)*len(rim)
    # All loops for the one lower n-gon are clockwise viewed from above.
    loops=np.concatenate((quad.reshape(-1),side.reshape(-1),(nlow+edge[::-1]))).astype('i')
    faces=len(quad)+len(side)+1
    mesh=bpy.data.meshes.new(name)
    mesh.vertices.add(len(coords))
    mesh.vertices.foreach_set('co',coords.astype('f').reshape(-1))
    mesh.loops.add(len(loops))
    mesh.loops.foreach_set('vertex_index',loops)
    mesh.polygons.add(faces)
    mesh.polygons.foreach_set('loop_start',np.arange(0,4*faces,4,dtype='i'))
    shaded=np.ones(faces,'?')
    shaded[-1]=False
    mesh.polygons.foreach_set('use_smooth',shaded)
    mesh.materials.append(material)
    mesh.materials.append(edge_material)
    mats=np.ones(faces,'i')
    mats[:len(quad)]=0
    mesh.polygons.foreach_set('material_index',mats)
    mesh.update(calc_edges=True)
    ob=bpy.data.objects.new(name,mesh)
    group.objects.link(ob)
    return ob


def small_type(group,name,value,loc,size,mat,spin=0,align='LEFT'):
    curve=bpy.data.curves.new(name,'FONT')
    curve.body=value
    curve.align_x=align
    curve.size=size
    curve.resolution_u=4
    ob=bpy.data.objects.new(name,curve)
    group.objects.link(ob)
    curve.materials.append(mat)
    ob.location=loc
    ob.rotation_euler.z=spin
    return ob


def powder_mat():
    mat,bsdf=textured('V2 06 | Warm-grey injection-moulded grip polymer',
        ((.45,.44,.41),(.58,.575,.55)),.51,140,.0014)
    bsdf.inputs['Specular IOR Level'].default_value=.28
    nt=mat.node_tree
    a=nt.nodes.new('ShaderNodeAttribute')
    a.attribute_name='Surface polish at the relief crests'
    # Mold high points have a more closed, gently burnished skin. Edges of the worn
    # survey specimen retain a narrow dust collar, exposing the true image contour.
    pigment=nt.nodes.new('ShaderNodeValToRGB')
    pigment.label='Frosted polymer with wear at raised shoulders'
    colors=((.0,(.47,.46,.43)),(.25,(.43,.42,.395)),(.43,(.29,.29,.275)),
            (.54,(.32,.32,.305)),(.62,(.55,.55,.523)),(.75,(.68,.675,.645)),(.89,(.65,.645,.62)))
    for elem,(pos,color) in zip(pigment.color_ramp.elements, (colors[0],colors[-1])):
        elem.position=pos;elem.color=(*color,1)
    for pos,color in colors[1:-1]:
        elem=pigment.color_ramp.elements.new(pos);elem.color=(*color,1)
    nt.links.new(a.outputs['Fac'],pigment.inputs[0]);nt.links.new(pigment.outputs[0],bsdf.inputs['Base Color'])
    gloss=nt.nodes.new('ShaderNodeMapRange')
    gloss.label='Subtle burnishing on the actual high points'
    gloss.inputs['To Min'].default_value=.53
    gloss.inputs['To Max'].default_value=.43
    nt.links.new(a.outputs['Fac'],gloss.inputs['Value'])
    nt.links.new(gloss.outputs[0],bsdf.inputs['Roughness'])
    return mat


def stations(group, terrain):
    orange,_=plain('V2 06 | Vermilion survey lacquer',(.73,.071,.014),.41)
    steel,_=plain('V2 06 | Brushed survey steel',(.23,.28,.28),.34,.64)
    black,_=plain('V2 06 | Instrument mount',(.014,.022,.023),.39,.16)
    optic,sh=plain('V2 06 | Coated optical prism',(.012,.20,.16),.14,.41)
    pale,_=plain('V2 06 | Printed staff graduations',(.80,.80,.67),.50)
    copper,_=plain('V2 06 | Waxed orange survey line',(.49,.113,.029),.61)
    # A real 20 mm mini-prism station with telescopic built legs; feet find the actual slopes.
    cx,cy=-.70,.30
    cz=terrain(cx,cy)
    top=(cx,cy,cz+.299)
    for i in range(3):
        angle=radians(26)+2*pi*i/3
        px,py=cx+.15*cos(angle),cy+.15*sin(angle)
        foot=np.array((px,py,terrain(px,py)+.002))
        axis=np.array(top)-foot
        tube(group,'V2 06 | Tripod foot',foot,foot+.11*axis,.015,black)
        tube(group,'V2 06 | Brushed lower tripod shaft',foot+.06*axis,foot+.57*axis,.009,steel)
        tube(group,'V2 06 | Enamelled telescopic legs',foot+.45*axis,foot+.99*axis,.014,orange)
        tube(group,'V2 06 | Tripod shaft collar',foot+.46*axis,foot+.53*axis,.017,black)
    tube(group,'V2 06 | Prism tribrach',(cx,cy,cz+.283),(cx,cy,cz+.312),.048,black)
    for side in (-1,1):
        box(group,'V2 06 | Pivoting prism carrier',(cx+side*.041,cy,cz+.35),(.012,.034,.086),orange,.004)
    tube(group,'V2 06 | Retroreflector body',(cx,cy+.018,cz+.36),(cx,cy-.018,cz+.36),.040,black)
    tube(group,'V2 06 | Prism aperture',(cx,cy-.018,cz+.36),(cx,cy-.021,cz+.36),.030,optic,6)
    anchors=[(-2.22,-1.36),(-1.52,-.44),(-.70,.30),(.08,.71),(.90,1.41),(1.66,1.92)]
    for j,(ax,ay) in enumerate(anchors):
        ground=terrain(ax,ay)
        if j!=2:
            tube(group,'V2 06 | Survey ground peg',(ax,ay,ground-.018),(ax,ay,ground+.084),.008,steel)
            tube(group,'V2 06 | Orange pin head',(ax,ay,ground+.077),(ax,ay,ground+.091),.013,orange)
        if j==4:
            for k in range(6):
                tube(group,'V2 06 | Two-millimetre staff bands',(ax,ay,ground+.04*k),(ax,ay,ground+.04*(k+1)),.012,orange if k%2 else pale)
    for a,b in zip(anchors,anchors[1:]):
        pairs=np.linspace(np.asarray(a),np.asarray(b),34)
        path=[(px,py,terrain(px,py)+.014+.012*np.sin(pi*k/33)) for k,(px,py) in enumerate(pairs)]
        cable=bpy.data.curves.new('V2 06 | Laid survey transect','CURVE')
        cable.dimensions='3D';cable.bevel_depth=.0035;cable.bevel_resolution=2
        spline=cable.splines.new('POLY');spline.points.add(len(path)-1)
        spline.points.foreach_set('co',np.asarray([(*p,1) for p in path],'f').ravel())
        ob=bpy.data.objects.new(cable.name,cable);group.objects.link(ob);cable.materials.append(copper)


def study06(scene):
    fresh(scene)
    scene.name='06 Material | 100x grip field section'
    scene.render.filepath='//renders/06-grip-field-section.png'
    bounce(scene,(.65,.78,.98),.34)
    scene.view_settings.exposure=.38
    meshgroup=collection(scene,'V2 06 | Relief sample and cross section')
    marks=collection(scene,'V2 06 | Metric field gauge')
    map_pixels,period,gain=relief_source()
    # A gently pitched prototype coupon retains the archive's sampled height at every XY point.
    x=np.linspace(-5.6,9.9,801)
    y=np.linspace(-5.15,14.5,985)
    xx,yy=np.meshgrid(x,y)
    lum=bilinear_texture(map_pixels,xx,yy,period).astype('f')
    carrier=section_profile(xx,yy)
    z=carrier+gain*lum
    topmat=powder_mat()
    land=surface(meshgroup,'V2 06 | Microtopographic survey of original grip / 100x',x,y,z,topmat)
    att=land.data.attributes.new('Surface polish at the relief crests','FLOAT','POINT')
    att.data.foreach_set('value',lum.reshape(-1))
    unit=scene.unit_settings.scale_length
    land['XY magnification']=land['Z magnification']=100.
    land['Input texture']='grip-symbol-height.png | bilinear archive height field'
    land['Texture repeat in model metres']=float(period*unit)
    land['Full-white relief in model metres']=float(gain*unit)
    land['Sampled maximum relief in model metres']=float(gain*unit*map_pixels.max())
    land['Surface construction']='Archived heightmap as a metric physical relief over a separately shaped shell carrier, with miniature transect markers and a recovered core.'
    # Physical front wall starts at the actual exposed edge of the independent top grid.
    cut,sh=textured('V2 06 | Freshly cored warm grey polymer',((.27,.27,.258),(.40,.40,.39)),.63,42,.001)
    backing,_=plain('V2 06 | Anthracite specimen carrier',(.019,.030,.033),.34,.25)
    brass,_=plain('V2 06 | Champagne datum liner',(.44,.264,.087),.30,.68)
    edgeidx=[(0,i) for i in range(len(x))]+[(j,len(x)-1) for j in range(1,len(y))]+[(len(y)-1,i) for i in range(len(x)-2,-1,-1)]+[(j,0) for j in range(len(y)-2,0,-1)]
    a=np.array([(xx[j,i],yy[j,i],z[j,i]) for j,i in edgeidx])
    for label,hi,lo,mat in [('Section wall',a[:,2],np.full(len(a),.055),cut),('Engraving datum',np.full(len(a),.055),np.full(len(a),.024),brass),('Mount heel',np.full(len(a),.024),np.full(len(a),-.15),backing)]:
        verts=np.concatenate((np.column_stack((a[:,:2],hi)),np.column_stack((a[:,:2],lo))))
        n=len(a)
        faces=[(i,n+i,n+(i+1)%n,(i+1)%n) for i in range(n)]
        solid(meshgroup,'V2 06 | '+label,verts,faces,mat)
    core_sample(meshgroup,land,x,y,z,lum,cut,topmat,gain,period,map_pixels)
    def ground(x,y):
        return float(section_profile(x,y)+gain*bilinear_texture(map_pixels,np.asarray(x),np.asarray(y),period))
    stations(marks,ground)
    cam,lights=camera_rig(scene,'V2 06 | Transverse grip survey',(-.15,.56,1.39),-18,19.5,7.15,46)
    cam.data.dof.use_dof=True
    cam.data.dof.focus_distance=7.0
    cam.data.dof.aperture_fstop=4.0
    sun=bpy.data.lights.new('V2 06 | Low raking daylight','SUN')
    sun.energy=4.1;sun.angle=radians(1.25);sun.color=(1.,.93,.82)
    source=bpy.data.objects.new(sun.name,sun);lights.objects.link(source)
    source.rotation_euler=Vector((1.,.24,-.20)).to_track_quat('-Z','Y').to_euler()
    set_area(lights,'V2 06 | Open sky diffuse fill',(2,-2,8),(0,1,1),130,7,6,(.73,.85,1.))
    return scene


def core_sample(group,land,x,y,z,lum,cut,topmat,gain,period,map_pixels):
    # The removed bore is actual open topology with an independent inner wall and bottom.
    ox,oy=1.82,.15
    radius=.585
    bm=bmesh.new()
    bm.from_mesh(land.data)
    dead=[f for f in bm.faces if (f.calc_center_median().x-ox)**2+(f.calc_center_median().y-oy)**2 < radius**2]
    bmesh.ops.delete(bm,geom=dead,context='FACES_ONLY')
    bm.to_mesh(land.data)
    bm.free()
    n=112
    angles=np.arange(n)*2*pi/n
    xx,yy=ox+radius*np.cos(angles),oy+radius*np.sin(angles)
    level=section_profile(xx,yy)+gain*bilinear_texture(map_pixels,xx,yy,period)
    interior,_=plain('V2 06 | Shadow within the core socket',(.16,.17,.17),.59)
    silver,_=plain('V2 06 | Freshly cut polymer rim',(.45,.46,.43),.57)
    rings=[]
    for rr,offset in ((radius+.018,.002),(radius-.012,.001),(radius-.023,-.014)):
        rings.append([(ox+rr*cos(a),oy+rr*sin(a),h+offset) for a,h in zip(angles,level)])
    rings.append([(ox+(radius-.023)*cos(a),oy+(radius-.023)*sin(a),.052) for a in angles])
    for j,(name,mat) in enumerate((('Specimen edge',silver),('Bore chamfer',silver),('Dark bore wall',interior))):
        faces=[(i,(i+1)%n,n+(i+1)%n,n+i) for i in range(n)]
        solid(group,'V2 06 | '+name,rings[j]+rings[j+1],faces,mat,True)
    solid(group,'V2 06 | Bottom of cored opening',rings[-1],[tuple(range(n))],interior)
    # Recovered matching cylinder lies beside the cut. Its cap carries the actual removed texture.
    pin=bpy.data.objects.new('V2 06 | 54.7 mm recovered core from 58.5 mm bore',None)
    group.objects.link(pin)
    corebefore=set(group.objects[:])
    R=radius-.038
    num=80
    rings=27
    pts=[(0,0,.30+gain*float(bilinear_texture(map_pixels,np.array(ox),np.array(oy),period)))]
    gray=[float(bilinear_texture(map_pixels,np.array(ox),np.array(oy),period))]
    for j in range(1,rings+1):
        for i in range(num):
            a=2*pi*i/num
            dx,dy=R*j/rings*cos(a),R*j/rings*sin(a)
            val=float(bilinear_texture(map_pixels,np.array(ox+dx),np.array(oy+dy),period))
            pts.append((dx,dy,.30+gain*val+section_profile(ox+dx,oy+dy)-section_profile(ox,oy)))
            gray.append(val)
    faces=[(0,1+i,1+(i+1)%num) for i in range(num)]
    for j in range(1,rings):
        for i in range(num):
            b=1+(j-1)*num
            faces.append((b+i,b+num+i,b+num+(i+1)%num,b+(i+1)%num))
    cap=solid(group,'V2 06 | Core cap with retained grip relief',pts,faces,topmat,True)
    att=cap.data.attributes.new('Surface polish at the relief crests','FLOAT','POINT')
    att.data.foreach_set('value',np.asarray(gray,'f'))
    outer=pts[-num:]
    other=[(k[0],k[1],0) for k in outer]
    solid(group,'V2 06 | Core section',outer+other,[(i,num+i,num+(i+1)%num,(i+1)%num) for i in range(num)]+[tuple(reversed(range(num,2*num)))],cut,False)
    for ob in set(group.objects[:])-corebefore:
        ob.parent=pin
    px,py=2.56,1.19
    pin.location=(px,py,float(section_profile(px,py)-.04))
    eps=.01
    dy=(section_profile(px,py+eps)-section_profile(px,py-eps))/(2*eps)
    dx=(section_profile(px+eps,py)-section_profile(px-eps,py))/(2*eps)
    pin.rotation_euler=Vector((-dx,-dy,1)).to_track_quat('Z','Y').to_euler()


def scalebar(group,metal,ink):
    root=bpy.data.objects.new('V2 06 | 50 mm calibration bar',None)
    group.objects.link(root)
    before=set(group.objects[:])
    box(group,'V2 06 | 50 mm gauge plate',(.50,.0,.023),(1.18,.255,.045),metal,.015)
    for i in range(51):
        length=.104 if not i%10 else .077 if not i%5 else .041
        box(group,'V2 06 | Engraved millimetre',(.02*i,.111-length*.5,.046),(.004 if i%5 else .007,length,.0015),ink)
    for i in range(0,51,10):
        small_type(group,'V2 06 | Scaled graduation',str(i),(.02*i,-.065,.047),.061,ink,0,'CENTER')
    small_type(group,'V2 06 | Gauge units','mm',(.5,-.109,.047),.034,ink,0,'CENTER')
    for ob in set(group.objects[:])-before:
        ob.parent=root
    return root
def clay_material(cut=False):
    tones=((.089,.033,.019),(.256,.104,.054)) if cut else ((.119,.049,.027),(.257,.121,.063))
    mat,sh=textured('V2 07 | Broken clay body' if cut else 'V2 07 | Compressed iron-red stoneware',tones,.79 if cut else .62,140 if cut else 110,.009 if cut else .004)
    nt=mat.node_tree
    tc=next(n for n in nt.nodes if n.type=='TEX_COORD')
    # Mineral inclusions / fine grog. Compressed top is smoother than the sheared edge.
    vor=nt.nodes.new('ShaderNodeTexVoronoi')
    vor.label='Exposed inclusions'
    vor.inputs['Scale'].default_value=115 if cut else 92
    nt.links.new(tc.outputs['Object'],vor.inputs['Vector'])
    speck=nt.nodes.new('ShaderNodeValToRGB')
    speck.color_ramp.elements[0].position=.10 if cut else .055
    speck.color_ramp.elements[0].color=(.52,.52,.52,1)
    speck.color_ramp.elements[1].position=.21 if cut else .125
    speck.color_ramp.elements[1].color=(0,0,0,1)
    nt.links.new(vor.outputs['Distance'],speck.inputs[0])
    mix=nt.nodes.new('ShaderNodeMixRGB')
    pigment=sh.inputs['Base Color'].links[0].from_socket
    nt.links.new(pigment,mix.inputs[1])
    mix.inputs[2].default_value=(.47,.262,.147,1)
    nt.links.new(speck.outputs[0],mix.inputs[0])
    nt.links.new(mix.outputs[0],sh.inputs['Base Color'])
    if not cut:
        moisture=nt.nodes.new('ShaderNodeTexNoise')
        moisture.inputs['Scale'].default_value=2.6
        moisture.inputs['Detail'].default_value=3.5
        nt.links.new(tc.outputs['Object'],moisture.inputs['Vector'])
        wet=nt.nodes.new('ShaderNodeMapRange')
        wet.inputs['From Min'].default_value=.32
        wet.inputs['From Max'].default_value=.68
        wet.inputs['To Min'].default_value=.52
        wet.inputs['To Max'].default_value=.76
        nt.links.new(moisture.outputs['Fac'],wet.inputs['Value'])
        contact=nt.nodes.new('ShaderNodeAttribute')
        contact.attribute_name='Water film at the pressed rim'
        contact.label='Water migrated into the compressed region'
        rough=nt.nodes.new('ShaderNodeMixRGB')
        nt.links.new(contact.outputs['Fac'],rough.inputs[0])
        nt.links.new(wet.outputs[0],rough.inputs[1])
        rough.inputs[2].default_value=(.25,.25,.25,1)
        nt.links.new(rough.outputs[0],sh.inputs['Roughness'])
        stain=nt.nodes.new('ShaderNodeMixRGB')
        nt.links.new(contact.outputs['Fac'],stain.inputs[0])
        nt.links.new(mix.outputs[0],stain.inputs[1])
        stain.inputs[2].default_value=(.128,.052,.024,1)
        nt.links.new(stain.outputs[0],sh.inputs['Base Color'])
    return mat


def polyline_groove(u,v,points,width):
    dist=np.full(u.shape,1e6)
    for (a,b),(c,d) in zip(points,points[1:]):
        dx,dy=c-a,d-b
        t=np.clip(((u-a)*dx+(v-b)*dy)/(dx*dx+dy*dy),0,1)
        dist=np.minimum(dist,(u-a-t*dx)**2+(v-b-t*dy)**2)
    return np.exp(-dist/width**2)


def torn_lump(group,rng,xy,radius,height,mat):
    count=21
    cx,cy=xy
    phase=rng.uniform(0,2*pi,6)
    az=rng.uniform(0,2*pi)
    # Damp crumbs roll at their free corners and retain local flat fractures where torn.
    # A few friable fragments have a larger sheared face; the others remain compact.
    cut=rng.uniform(.34,.56) if rng.random()<.22 else rng.uniform(.71,.91)
    levels=((0,.61),(.055,.79),(.14,.94),(.27,1.),(.46,.95),(.65,.80),(.81,.64),(.94,.38),(.987,.14))
    verts=[]
    for z,r in levels:
        for i in range(count):
            a=2*pi*i/count
            outline=(1+.18*cos(2*a+phase[0])+.14*sin(3*a+phase[1]+.25*z)
                     +.085*sin(5*a+phase[2]-.48*z)+.036*cos(8*a+phase[3]))
            xx,yy=r*outline*cos(a),r*outline*sin(a)
            # The shifted slice only meets one side of the otherwise rounded crumb.
            xx=min(xx,cut+.16*z-.12*yy)+.21*z*cos(phase[4])
            yy+=.21*z*sin(phase[4])
            dz=z*height*(1+r*(.14*sin(a+phase[5])+.055*cos(4*a+phase[4])))
            lx,ly=radius[0]*xx,radius[1]*yy
            verts.append((cx+lx*cos(az)-ly*sin(az),cy+lx*sin(az)+ly*cos(az),max(.0003,dz)))
    last=(len(levels)-1)*count
    faces=[tuple(reversed(range(count))),tuple(range(last,last+count))]
    for j in range(len(levels)-1):
        for i in range(count):
            a,b=j*count+i,j*count+(i+1)%count
            faces.append((a,b,b+count,a+count))
    crumb=solid(group,'V2 07 | Torn and partly rolled stoneware crumb',verts,faces,mat,True)
    crumb.data.polygons[0].use_smooth=False
    return crumb


def soften_contact(field, sigma):
    radius=int(np.ceil(3*sigma))
    k=np.arange(-radius,radius+1)
    weights=np.exp(-.5*(k/sigma)**2)
    weights/=weights.sum()
    for axis in range(2):
        trans=np.moveaxis(field,axis,0)
        padded=np.pad(trans,((radius,radius),(0,0)),mode='edge')
        field=np.moveaxis(sum(w*padded[i:i+len(trans)] for i,w in enumerate(weights)),0,axis)
    return field


def study07(scene):
    group_place=next(c for c in scene.collection.children if 'Product placement' in c.name)
    fresh(scene,(group_place.name,))
    scene.name='07 Material | Hand-pressed stoneware'
    scene.render.filepath='//renders/07-hand-pressed-stoneware.png'
    bounce(scene,(.51,.55,.52),.17)
    scene.view_settings.exposure=.08
    yaw=radians(-22.)
    def world(u,v):
        return u*cos(yaw)-v*sin(yaw),u*sin(yaw)+v*cos(yaw)
    graph=bpy.context.evaluated_depsgraph_get()
    clay=collection(scene,'V2 07 | Stoneware press bed')
    debris=collection(scene,'V2 07 | Fracture and tear-out pieces')
    claymat,cut=clay_material(),clay_material(True)
    xs=np.linspace(0,1,341)
    ys=np.linspace(0,1,291)
    s,t=np.meshgrid(xs,ys)
    # Slab footprint uses an oblique torn front, an irregular broken right edge and a squared far cut.
    left=-2.94+.045*np.sin(9*t)+.025*np.sin(36*t)
    right=-.48+.29*(1-t)+.095*np.sin(8*t+.4)+.045*np.sin(23*t)+.017*np.sin(95*t)
    u=left+(right-left)*s
    front=-1.81+.20*s+.11*np.sin(13*s+.8)+.045*np.sin(46*s)+.022*np.sin(92*s)
    back=.94+.17*np.cos(4*s)+.10*np.sin(8*s)
    v=front+(back-front)*t
    x,y=world(u,v)
    # Clay was laid down from the left and then depressed by the front of the real grip.
    # A vertical ray to every sample in this contact patch determines which skin is covered.
    top=np.full(s.shape,-3.)
    for j,i in zip(*np.where((u> -1.94)&(v> -1.4)&(v<1.2))):
        hit,p,_,_,_,_=scene.ray_cast(graph,(float(x[j,i]),float(y[j,i]),2.5),(0,0,-1),distance=3.)
        if hit:
            top[j,i]=p.z
    occupied=top>-2
    h=.43+.057*np.sin(1.97*u-.64*v)+.053*np.cos(1.8*v+.6*u)
    h+=.214*np.exp(-((u+1.61)/.43)**2-((v+.83)/.48)**2)
    h+=.256*np.exp(-((u+1.39)/.39)**2-((v+1.07)/.45)**2)
    h+=.080*np.exp(-((u+1.31)/.22)**2-((v+1.29)/.26)**2)
    h-=.065*np.exp(-((u+1.23)/.46)**2-((v+.14)/.58)**2)
    # Keep tool facets low and directional, reserving the most visible disruption for contact.
    strokes=np.zeros(s.shape)
    for centre,length in ((-1.31,1.1),(-.99,.86),(-.64,.78),(-.37,.52)):
        across=v-centre+.092*u-.034*np.sin(3*u)
        strength=np.exp(-((u+2.34)/length)**6)
        strokes-=.009*np.exp(-(across/.030)**2)*strength
        strokes+=.006*np.exp(-((across-.045)/.032)**2)*strength
    h+=strokes
    # A few thumb pad impressions over-press the left face. The short crest lines terminate within each pad.
    for mx,my,ang,rad in ((-2.20,-.63,.43,.30),(-2.51,-.36,.32,.27),(-2.59,.12,.60,.31)):
        du,dv=u-mx,v-my
        aa=du*cos(ang)+dv*sin(ang)
        bb=-du*sin(ang)+dv*cos(ang)
        rr=np.sqrt((aa/(rad*1.4))**2+(bb/rad)**2)
        h-=.042*np.exp(-rr**4*2)
        h+=.00155*np.cos(2*pi*(rr+.28*aa+.065*np.sin(11*bb)+.036*np.sin(19*aa))/.095)*np.exp(-rr**8*1.5)*np.clip((bb+.05)*9,0,1)
    # Short branched fissures start at the front rupture, becoming narrower and shallower inland.
    for points,w,depth in [
        ([(-2.49,-1.76),(-2.46,-1.65),(-2.39,-1.60),(-2.42,-1.53),(-2.35,-1.49)],.012,.037),
        ([(-2.40,-1.59),(-2.33,-1.58),(-2.29,-1.54)],.007,.018),
        ([(-1.88,-1.76),(-1.85,-1.63),(-1.88,-1.57),(-1.82,-1.50)],.009,.031),
        ([(-.46,-1.21),(-.60,-1.15),(-.64,-1.06),(-.71,-1.03)],.010,.038),
        ([(-.66,-1.06),(-.66,-.98),(-.71,-.94)],.008,.023)]:
        h-=depth*polyline_groove(u,v,points,w)
    # Outer peel breaks into a granular edge. The centre of the slab retains a continuous matte clay skin.
    edge_dist=np.minimum.reduce((s*2.4,(1-s)*2.4,t*2.6,(1-t)*2.6))
    fracture=np.exp(-(edge_dist/.092)**2)
    grit=(noise2(17*u,22*v)+.48*noise2(42*u,48*v)+.21*noise2(90*u,85*v))
    h+=fracture*(.027*grit-.023)
    h+=.0024*noise2(u*20,v*23)+.00125*noise2(u*52,v*50)
    # The displaced edge is continuous with the body of the slab. The contact pressure
    # tapers to zero on the shell instead of leaving a freestanding ribbon at its tip.
    wet=np.exp(-((u+1.40)/.37)**2-((v+.99)/.42)**2)
    close=np.exp(-((top-h)/.13)**2)*wet*occupied
    h+=soften_contact(close,2.7)*.064
    along=.89*(u+1.75)+.456*(v+1.12)
    side=-.456*(u+1.75)+.89*(v+1.12)
    width=.16-.065*np.clip(along/.73,0,1)
    pressure=np.exp(-((side+.019*np.sin(8*along))/width)**2-((along-.32)/.39)**4)
    measured=soften_contact(np.maximum(top-h,0)*occupied,2.9)
    support=soften_contact(occupied.astype(float),2.9)
    rise=measured/np.maximum(support,.21)
    bead=.060*(1-.64*np.clip(along/.73,0,1))
    h+=pressure*(rise+bead)
    # One broad compression roll fades into the wet meniscus on both sides.
    # It is displaced on the same slab grid and cannot leave a lifted edge.
    fold=side+.082-.018*np.sin(8.2*along)
    roll=np.exp(-((along-.30)/.31)**4)
    h+=roll*(.017*np.exp(-(fold/.048)**2)-.007*np.exp(-((fold+.058)/.032)**2))
    # Bevel around the free surface and continue to the ground through a thick, asymmetric fractured face.
    h-=.033*np.exp(-(edge_dist/.037)**2)
    ztop=np.stack((x,y,h),axis=-1)
    side_shift=.017*np.sin(v*24)+.025*np.sin(u*32+v*9)
    bx,by=world(u+side_shift,v-.028*np.sin(18*u+4*v))
    bottom=np.stack((bx,by,np.zeros(u.shape)+.001),axis=-1)
    slab=rect_volume(clay,'V2 07 | Cut clay slab with real left-grip contact',ztop,bottom,claymat,cut)
    saturation=np.empty(len(slab.data.vertices),'f')
    saturation.fill(0)
    saturation[:h.size]=(.90*np.exp(-((u+1.46)/.42)**2-((v+1.01)/.44)**2)
                           +.15*np.exp(-((u+2.20)/.55)**2-((v+.70)/.56)**2)).ravel()
    film=slab.data.attributes.new('Water film at the pressed rim','FLOAT','POINT')
    film.data.foreach_set('value',saturation)
    slab['Grip contact']='Engineered pressure field, with wet lip sampled against the elevated face of the actual left grip.'
    slab['Overlap sample count']=int((occupied&(h>top)).sum())
    # Rolled material has escaped towards the torn front, with a few chips left on the worktable.
    rng=np.random.default_rng(2607)
    hits=0
    while hits<46:
        uu=rng.uniform(-2.65,-.24)
        vv=rng.normal(-1.88,.24)
        if vv> -1.8+.16*(uu+2.5)/2: continue
        wx,wy=world(uu,vv)
        radius=rng.uniform(.012,.060)*(1.5 if hits<5 else 1.)
        torn_lump(debris,rng,(wx,wy),(radius,radius*rng.uniform(.48,.89)),radius*rng.uniform(.45,.85),cut)
        hits+=1
    for _ in range(13):
        uu,vv=rng.normal(-.26,.13),rng.uniform(-1.38,-.20)
        wx,wy=world(uu,vv)
        radius=rng.uniform(.013,.05)
        torn_lump(debris,rng,(wx,wy),(radius,radius*.63),radius*.55,cut)
    floor,_=textured('V2 07 | Blue-black work surface',((.020,.032,.033),(.045,.055,.052)),.61,46,.0021)
    box(clay,'V2 07 | Ceramics worktop',(0,0,-.111),(80,80,.22),floor)
    cam,rig=camera_rig(scene,'V2 07 | Process table',(-.48,-.10,.37),6.5,40,12.1,77)
    cam.data.dof.use_dof=False
    for args in [
        ('V2 07 | Cool side window',(-3.45,1.35,4.48),(-.9,-.05,.4),415,2.30,3.2,(.91,.96,1)),
        ('V2 07 | Front fill',(1.7,-4.6,3.2),(.3,-.1,.7),132,3.2,2.1,(1,.90,.77)),
        ('V2 07 | Shoulder edge',(5.3,3.1,1.95),(.8,.4,.85),218,.85,3.2,(.83,.93,1)),
        ('V2 07 | Earthenware rake',(-4.4,-1.5,1.25),(-1.45,-.9,.32),78,2.0,.36,(1,.78,.58))]:
        set_area(rig,*args)
    return scene


def revise():
    """Revise the two scene datablocks of a loaded master and return them."""
    return [study06(scene_number('06')),study07(scene_number('07'))]
