"""Build the 100x grip topography and the face-up impression in pigmented wax."""
from math import cos, pi, radians, sin
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree
from build_lineup import assembly_points
from build_studio import PARTS, camera_rig, collection, set_area, setup_scene, shot_scene, studio_world
from faceup_product import placement

SIZE = (3840, 2560)


def scene_base(source, product, title, filename, ambient, gain):
    scene = shot_scene(source, title, product, filename, SIZE)
    scene.collection.children.unlink(product)
    scene.compositing_node_group = None
    scene.world = studio_world(source)
    scene.world.name = title + ' | Environment'
    bg = next(n for n in scene.world.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = (*ambient, 1)
    bg.inputs['Strength'].default_value = gain
    setup_scene(scene, 88)
    scene.cycles.adaptive_min_samples = 16
    scene.cycles.adaptive_threshold = .017
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_depth = '16'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.compression = 35
    return scene


def plain(name, rgb, rough=.5, metal=0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (*rgb, 1)
    bsdf.inputs['Metallic'].default_value = metal
    bsdf.inputs['Roughness'].default_value = rough
    mat.diffuse_color = (*rgb, 1)
    return mat, bsdf


def textured(name, tones, rough, grain_size, grain_depth):
    mat, bsdf = plain(name, tones[1], rough)
    nt = mat.node_tree
    nodes, link = nt.nodes, nt.links.new
    coords = nodes.new('ShaderNodeTexCoord')
    coords.location = (-780, 0)
    cloud = nodes.new('ShaderNodeTexNoise')
    cloud.label = 'Slow variation in the cast pigment'
    cloud.location = (-540, 80)
    cloud.inputs['Scale'].default_value = 1.1
    cloud.inputs['Detail'].default_value = 4.5
    link(coords.outputs['Object'], cloud.inputs['Vector'])
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.location = (-280, 100)
    for elem, pos, color in zip(ramp.color_ramp.elements, (.22,.8), tones):
        elem.position = pos
        elem.color = (*color, 1)
    link(cloud.outputs['Fac'], ramp.inputs[0])
    link(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    noise = nodes.new('ShaderNodeTexNoise')
    noise.label = 'Fine surface tooth'
    noise.location = (-540, -180)
    noise.inputs['Scale'].default_value = grain_size
    noise.inputs['Detail'].default_value = 2.3
    noise.inputs['Roughness'].default_value = .65
    link(coords.outputs['Object'], noise.inputs['Vector'])
    bump = nodes.new('ShaderNodeBump')
    bump.location = (-260, -170)
    bump.inputs['Strength'].default_value = .25
    bump.inputs['Distance'].default_value = grain_depth
    link(noise.outputs['Fac'], bump.inputs['Height'])
    link(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat, bsdf


def surface(group, name, x, y, z, mat):
    h, w = z.shape
    xy = np.meshgrid(x, y)
    coords = np.stack((*xy,z), axis=-1).astype('f').reshape(-1)
    indices = np.arange(w*h, dtype='i').reshape(h,w)[:-1,:-1]
    quads = np.stack((indices,indices+1,indices+1+w,indices+w), axis=-1).reshape(-1)
    count = len(quads)//4
    me = bpy.data.meshes.new(name)
    me.vertices.add(w*h)
    me.vertices.foreach_set('co',coords)
    me.loops.add(4*count)
    me.loops.foreach_set('vertex_index', quads)
    me.polygons.add(count)
    me.polygons.foreach_set('loop_start', np.arange(0,len(quads),4,dtype='i'))
    me.polygons.foreach_set('use_smooth',np.ones(count, '?'))
    me.update(calc_edges=True)
    obj = bpy.data.objects.new(name, me)
    group.objects.link(obj)
    me.materials.append(mat)
    return obj


def solid(group,name,verts,faces,mat,smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    if smooth:
        me.polygons.foreach_set('use_smooth',np.ones(len(faces),'?'))
    ob = bpy.data.objects.new(name,me)
    group.objects.link(ob)
    me.materials.append(mat)
    return ob


def bevel(obj, width):
    mod = obj.modifiers.new('Rounded fabrication edges','BEVEL')
    mod.width = width
    mod.segments = 3
    norm = obj.modifiers.new('Face normals','WEIGHTED_NORMAL')
    norm.keep_sharp = True


def box(group,name,loc,dims,mat,edge=0,rot=None):
    x,y,z = (s*.5 for s in dims)
    v=[(a*x,b*y,c*z) for c in (-1,1) for b in (-1,1) for a in (-1,1)]
    f=[(0,2,3,1),(4,5,7,6),(0,1,5,4),(1,3,7,5),(3,2,6,7),(2,0,4,6)]
    obj=solid(group,name,v,f,mat)
    obj.location=loc
    if rot:
        obj.rotation_euler = rot
    if edge:
        bevel(obj,edge)
    return obj


def tube(group,name,p,q,r,mat,n=16):
    p,q = Vector(p),Vector(q)
    axis=(q-p).normalized()
    u=axis.orthogonal().normalized()*r
    v=axis.cross(u)
    circle=[u*cos(i*2*pi/n)+v*sin(i*2*pi/n) for i in range(n)]
    verts=[pt+o for pt in (p,q) for o in circle]
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    faces+=[(i,(i+1)%n,n+(i+1)%n,n+i) for i in range(n)]
    ob=solid(group,name,verts,faces,mat)
    for poly in list(ob.data.polygons)[2:]:
        poly.use_smooth=True
    return ob


def relief_source():
    shell=bpy.data.materials['Shell | frost-white satin polymer']
    texture=next(n for n in shell.node_tree.nodes if n.type=='TEX_IMAGE' and n.image and 'grip-symbol-height' in n.image.name)
    scale=texture.inputs['Vector'].links[0].from_node.inputs['Scale'].default_value
    distance=next(n for n in shell.node_tree.nodes if n.type=='BUMP' and 'Raised grip' in n.label).inputs['Distance'].default_value
    img=texture.image
    pixels=np.empty(len(img.pixels),'f')
    img.pixels.foreach_get(pixels)
    return pixels.reshape(img.size[1],img.size[0],4)[:,:,0],100/scale,100*distance


def bilinear_texture(a,x,y,period):
    h,w=a.shape
    u=((x/period+.205)*w-.5) % w
    v=((y/period+.426)*h-.5) % h
    ix=np.floor(u).astype(int)
    iy=np.floor(v).astype(int)
    u,v=u-ix,v-iy
    return ((1-u)*(1-v)*a[iy,ix]+u*(1-v)*a[iy,(ix+1)%w]+
            v*(1-u)*a[(iy+1)%h,ix]+u*v*a[(iy+1)%h,(ix+1)%w])


def rover(group, ground):
    paint,_=plain('06 | Cadmium enamel',(.90,.172,.017),.29,.18)
    dark,_=plain('06 | Tire rubber',(.023,.029,.028),.72)
    alu,_=plain('06 | Brushed aluminium',(.46,.54,.55),.32,.78)
    pv,_=plain('06 | Navy solar laminate',(.026,.08,.115),.26,.38)
    lens,_=plain('06 | Lidar optical glass',(.011,.035,.043),.13,.49)
    pale,_=plain('06 | Reflective marker paint',(.83,.79,.62),.35)
    root=bpy.data.objects.new('06 | Six-wheel micro surveyor | 48 mm chassis',None)
    group.objects.link(root)
    angle=radians(-27)
    rx,ry=.84,-.53
    root.location=(rx,ry,float(ground(np.asarray(rx),np.asarray(ry))))
    # Align the rocker bogie with the measured mean terrain gradient.
    du=.31
    gx=(ground(np.asarray(rx+du),np.asarray(ry))-ground(np.asarray(rx-du),np.asarray(ry)))/(2*du)
    gy=(ground(np.asarray(rx),np.asarray(ry+du))-ground(np.asarray(rx),np.asarray(ry-du)))/(2*du)
    normal=Vector((-gx,-gy,1)).normalized()
    yawed_x=Vector((cos(angle),sin(angle),0))
    local_y=normal.cross(yawed_x).normalized()
    local_x=local_y.cross(normal)
    frame=Matrix((local_x,local_y,normal)).transposed()
    root.rotation_euler=frame.to_euler()
    before=set(group.objects[:])
    box(group,'Surveyor | Belly', (0,0,.229),(.43,.81,.115),dark,.035)
    box(group,'Surveyor | Signal-orange chassis',(0,-.015,.303),(.50,.79,.195),paint,.054)
    box(group,'Surveyor | Raised service deck',(0,-.04,.415),(.46,.73,.052),alu,.015)
    box(group,'Surveyor | Solar panel',(0,-.09,.449),(.435,.59,.025),pv,.009)
    for xx in np.linspace(-.163,.163,5):
        box(group,'Surveyor | Photovoltaic busbar',(xx,-.09,.4635),(.0038,.575,.0022),alu)
    for yy in np.linspace(-.32,.14,5):
        box(group,'Surveyor | Cell separation',(0,yy,.4636),(.426,.004,.0023),alu)
    for side in (-1,1):
        for y in (-.315,.004,.316):
            center=np.array([side*.314,y,.145])
            tube(group,'Surveyor | Tire',(side*.25,y,.145),(side*.38,y,.145),.142,dark,28)
            tube(group,'Surveyor | Recessed wheel hub',(side*.378,y,.145),(side*.386,y,.145),.088,alu,24)
            tube(group,'Surveyor | Drive motor end plate',(side*.385,y,.145),(side*.394,y,.145),.047,paint,20)
            for a in np.arange(0,2*pi,pi/8):
                p=center+np.array([side*.015,sin(a)*.141,cos(a)*.141])
                box(group,'Surveyor | Chevron cleat',p,(.127,.024,.014),dark,.002,(float(-a),side*.11,0))
            tube(group,'Surveyor | Rocker-bogie arm',(side*.244,y,.145),(side*.233,y*.40,.299),.023,alu)
        box(group,'Surveyor | Corner beacon',(side*.165,.365,.366),(.088,.021,.047),pale,.005)
    tube(group,'Surveyor | Mast',(.115,.265,.416),(.115,.265,.695),.018,alu)
    box(group,'Surveyor | Stereo instrument',(.11,.252,.69),(.243,.088,.082),paint,.018)
    for xx in (.042,.175):
        tube(group,'Surveyor | Optic', (xx,.274,.69),(xx,.308,.69),.028,lens)
    for xx in (.042,.175):
        tube(group,'Surveyor | Rear stereo optic',(xx,.222,.69),(xx,.201,.69),.025,lens)
    for side in (-1,1):
        tube(group,'Surveyor | Deck grab rail',(side*.229,-.305,.458),(side*.229,.14,.458),.009,alu,10)
        for yy in (-.30,.14):
            tube(group,'Surveyor | Rail mount',(side*.229,yy,.424),(side*.229,yy,.46),.011,alu,10)
        for yy in (-.28,-.12,.05,.20):
            box(group,'Surveyor | Chassis ventilation',(side*.252,yy,.31),(.005,.085,.013),dark,.002)
    tube(group,'Surveyor | Communications aerial',(-.176,-.215,.43),(-.20,-.25,.735),.007,alu,8)
    # Match every wheel to the sampled surface, individually, including symbol ridges.
    wheel_offsets={}
    for side in (-1,1):
        for wy in (-.315,.004,.316):
            base=frame @ Vector((side*.314,wy,0))
            z_surface=ground(np.asarray(rx+base.x),np.asarray(ry+base.y))
            wheel_offsets[(side,wy)]=(z_surface-root.location.z-base.z)/normal.z
    for ob in set(group.objects[:])-before:
        if 'Tire' in ob.name or 'wheel hub' in ob.name or 'Drive motor' in ob.name or 'Chevron cleat' in ob.name:
            if ob.location.length==0:
                local=sum((v.co for v in ob.data.vertices),Vector())/len(ob.data.vertices)
            else:
                local=ob.location.copy()
            key=min(wheel_offsets,key=lambda k:abs(local.x-k[0]*.314)*1.25+abs(local.y-k[1]))
            ob.location.z+=wheel_offsets[key]
        ob.parent=root
    # Two survey stations with 5 mm alternating staff divisions.
    for number,(mx,my,high) in enumerate(((-1.55,.65,.44),(1.61,2.80,.37)),1):
        mz=float(ground(np.asarray(mx),np.asarray(my)))
        for k in range(5):
            tube(group,'Station %02d | Graduated staff'%number,(mx,my,mz+k*high/5),(mx,my,mz+(k+1)*high/5),.015,paint if k%2==0 else pale,12)
        for ang in (.26,2.36,4.46):
            tx,ty=mx+cos(ang)*.083,my+sin(ang)*.083
            tube(group,'Station %02d | Tripod foot'%number,(mx,my,mz+.16),(tx,ty,float(ground(np.asarray(tx),np.asarray(ty)))),.009,alu,10)
        tube(group,'Station %02d | Marker head'%number,(mx,my,mz+high),(mx,my,mz+high+.038),.034,paint)
    return root


def survey_world(source,product):
    scene=scene_base(source,product,'06 Material | Grip survey at 100x','06-grip-survey-100x',(.41,.54,.73),.24)
    scene.view_settings.exposure=.36
    group=collection(scene,'06 | Displaced grip field')
    texture,period,amplitude=relief_source()
    def field(x,y):
        relief=bilinear_texture(texture,x,y,period)*amplitude
        # The broad molded carrier is independent of the repeated XY/Z-calibrated symbols.
        profile=.19*np.sin(.81*x+.29*y)+.24*np.cos(.47*y-.61*x)+.10*np.cos(.98*y+.36*x)
        # Parallel tracks terminate under the rear axle of the micro surveyor.
        theta=radians(-27)
        dx=x-.84
        dy=y+.53
        across=dx*np.cos(theta)+dy*np.sin(theta)
        along=-dx*np.sin(theta)+dy*np.cos(theta)
        path=across-.14*np.sin((along+.35)*1.6)
        band=np.exp(-((np.abs(path)-.315)/.061)**4)
        tail=np.clip((-along-.29)*10,0,1)*np.clip((along+4.4)*1.5,0,1)
        tread=.5+.5*np.cos(2*pi*(along+np.abs(path)*.36)/.084)
        return profile+relief-tail*band*(.003+.010*tread**3)
    x=np.linspace(-8.7,8.7,691)
    y=np.linspace(-8.6,13.3,830)
    xx,yy=np.meshgrid(x,y)
    land,shader=textured('06 | Frost polymer with mineral-scale grain',((.34,.41,.44),(.62,.63,.59)),.61,25,.012)
    ground=surface(group,'06 | Packed grip image, displaced survey mesh',x,y,field(xx,yy),land)
    # A slight, smoother polish at the high points exposes the shallow embossing in raking light.
    gray=bilinear_texture(texture,xx,yy,period).astype('f')
    crests=ground.data.attributes.new('Surface polish at the relief crests','FLOAT','POINT')
    crests.data.foreach_set('value',gray.reshape(-1))
    nt=land.node_tree
    att=nt.nodes.new('ShaderNodeAttribute')
    att.attribute_name=crests.name
    att.location=(-570,330)
    mix=nt.nodes.new('ShaderNodeMixRGB')
    mix.blend_type='MIX'
    mix.label='Satin polish on raised grip marks'
    mix.location=(-10,215)
    pigment=shader.inputs['Base Color'].links[0].from_socket
    nt.links.new(att.outputs['Fac'],mix.inputs[0])
    nt.links.new(pigment,mix.inputs[1])
    mix.inputs[2].default_value=(.75,.77,.745,1)
    nt.links.new(mix.outputs[0],shader.inputs['Base Color'])
    gloss=nt.nodes.new('ShaderNodeMapRange')
    gloss.label='Smooth crest, molded base'
    gloss.location=(-20,-200)
    gloss.inputs['To Min'].default_value=.63
    gloss.inputs['To Max'].default_value=.38
    nt.links.new(att.outputs['Fac'],gloss.inputs['Value'])
    nt.links.new(gloss.outputs[0],shader.inputs['Roughness'])
    unit=source.unit_settings.scale_length
    ground['Input texture']='grip-symbol-height.png | original packed grayscale, bilinear sample'
    ground['XY magnification']=100.
    ground['Z magnification']=100.
    ground['Texture repeat in model metres']=float(period*unit)
    ground['Full-white relief in model metres']=float(amplitude*unit)
    ground['Sampled maximum relief in model metres']=float(amplitude*unit*texture.max())
    ground['Surface construction']='Image grayscale times original Bump Distance times 100; shader normal mix strength is not a displacement scale. Carrier curvature and rover tread are independent layers.'
    props=collection(scene,'06 | Survey equipment')
    rover(props,field)
    camera,rig=camera_rig(scene,'06 | Macro expedition',(.03,.07,.16),13,34,12.6,75)
    camera.data.dof.use_dof=True
    camera.data.dof.focus_distance=12.5
    camera.data.dof.aperture_fstop=14
    sun=bpy.data.lights.new('06 | Low raking light','SUN')
    sun.energy=3.65
    sun.color=(1,.77,.51)
    sun.angle=radians(4.7)
    ob=bpy.data.objects.new(sun.name,sun)
    rig.objects.link(ob)
    ob.rotation_euler=Vector((.88,-.39,-.19)).to_track_quat('-Z','Y').to_euler()
    set_area(rig,'06 | Overhead sky',(-.5,1.7,5),(0,0,0),75,7,5,(.66,.82,1))
    return scene
def contour_distance(mask,spacing):
    """Continuous Euclidean distance to the original projected silhouette."""
    boundary=(mask != np.roll(mask,1,0)) | (mask != np.roll(mask,-1,0)) | (mask != np.roll(mask,1,1)) | (mask != np.roll(mask,-1,1))
    coords=np.argwhere(boundary)
    tree=KDTree(len(coords))
    for number,(j,i) in enumerate(coords):
        tree.insert((float(i),float(j),0),number)
    tree.balance()
    d=np.full(mask.shape,2.,dtype='f')
    j0,i0=coords.min(axis=0)-int(1.15/spacing)
    j1,i1=coords.max(axis=0)+int(1.15/spacing)
    for j in range(max(0,j0),min(mask.shape[0],j1+1)):
        for i in range(max(0,i0),min(mask.shape[1],i1+1)):
            d[j,i]=tree.find((i,j,0))[2]*spacing
    return np.where(mask,-d,d)


def wax_world(source,product):
    scene=scene_base(source,product,'07 Material | Impression in sealing wax','07-vermilion-wax-impression',(.57,.36,.29),.21)
    scene.view_settings.exposure=.12
    yaw=-22
    placement(scene,product,assembly_points(product),yaw)
    bpy.context.window.scene=scene
    bpy.context.view_layer.update()
    dg=bpy.context.evaluated_depsgraph_get()
    # Ray-cast only the original assembly before creating the wax and lighting.
    # Every retained shell-contact point uses the actual upper intersection.
    steps=.019
    x=np.arange(-4.2,4.21,steps)
    y=np.arange(-4.5,5.31,steps)
    xx,yy=np.meshgrid(x,y)
    upper=np.full(xx.shape,-3.,dtype='f')
    for j in np.where((y>-2)&(y<2))[0]:
        for i in np.where((x>-2.4)&(x<2.4))[0]:
            hit,pt,_,_,_,_=scene.ray_cast(dg,(float(x[i]),float(y[j]),2.8),(0,0,-1),distance=4)
            if hit:
                upper[j,i]=pt.z
    mask=upper> -2
    if mask.sum()<6000:
        raise RuntimeError('Wax impression needs an evaluated controller surface')
    sd=contour_distance(mask,steps)
    for _ in range(5):
        sd=(sd*4+np.roll(sd,1,0)+np.roll(sd,-1,0)+np.roll(sd,1,1)+np.roll(sd,-1,1))/8
    a=radians(yaw)
    u=xx*cos(a)+yy*sin(a)
    v=-xx*sin(a)+yy*cos(a)
    # Gradually draped cast bed plus flow from opposite directions of thumb pressure.
    bed=(.32+.054*np.sin(1.55*u+.68*v)+.04*np.cos(2.4*v-.46*u)
         +.045*np.sin(.88*u-1.12*v))
    push=np.exp(-((u+1.33)/.57)**2-((v+.64)/.68)**2)
    second=np.exp(-((u-1.37)/.57)**2-((v+.26)/.76)**2)
    centre=np.exp(-(u/.70)**2-((v+.56)/.70)**2)
    front=np.clip((-v-.26)/.78,0,1)
    pattern=(.45+.55*np.sin(u*4.5-v*3.7+np.sin(4*v))**2)
    # Surface flow is directionally biased; it laps farthest over the left grip.
    lap=.018+.18*push+.11*second+.17*front+.06*centre+.019*pattern
    pressure=.11+.24*push+.105*second+.07*front
    dry=bed+pressure*np.exp(-((sd-.09)/.19)**2)
    dry-= (.045+.067*push+.035*second)*np.exp(-((sd-.39-.07*np.sin(v*7+u*1.5))/.087)**2)
    dry+= .05*(.15+push+second)*np.exp(-((sd-.56)/.12)**2)
    # Lobes follow the individual grip ends while smaller ridges spread into the bed.
    folds=np.zeros(sd.shape)
    for ox,oy,angle,length,amplitude,width in (
        (-1.23,-1.22,-123,1.12,.12,.080),(-1.25,-.99,-143,.99,.093,.054),
        (-1.58,-.65,-163,1.06,.087,.052),(-1.51,-.40,166,.97,.065,.051),
        (1.44,-.64,-32,1.1,.14,.072),(1.34,-.84,-49,1.03,.11,.053),
        (1.40,-.87,-69,.62,.075,.039),(1.51,.35,23,.8,.078,.065),
        (.65,1.03,59,.87,.055,.068),(-.75,.97,103,1.10,.06,.060)):
        ang=radians(angle)
        dx,dy=u-ox,v-oy
        along=dx*cos(ang)+dy*sin(ang)
        across=-dx*sin(ang)+dy*cos(ang)
        along=np.asarray(along)
        taper=np.exp(-((along-.30*length)/(.57*length))**2)*np.clip((along+.15)/.24,0,1)
        curve=across-.13*np.sin(2.45*along+.45)
        folds+=taper*amplitude*(np.exp(-(curve/width)**2)-.40*np.exp(-((curve-width*1.45)/(1.15*width))**2))
    dry+=folds
    # Each rising lip is tall enough to touch and overlap the sampled hardware.
    # Fade it below the original shell beyond its wet line.
    inner=np.maximum(-sd,0)
    contact=.09+.91*np.clip(2.05*push+1.40*second+.77*front-.11,0,1)
    rim=upper+.021+.026*np.exp(-((inner-lap*.48)/.10)**2)+.017*pattern
    crest=rim*contact+np.minimum(upper-.09,bed+.005)*(1-contact)
    s=np.clip((inner-lap+.07)/.13,0,1)
    s=s*s*(3-2*s)
    wax_under=crest*(1-s)+(np.minimum(upper-.19,bed-.12))*s
    # Propagate the sampled edge elevation out into the berm for seamless build-up.
    edge_z=np.where(mask,upper,0)
    valid=mask.copy()
    for _ in range(int(.54/steps)):
        total=np.zeros_like(upper)
        count=np.zeros_like(upper)
        for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
            total+=np.roll(edge_z,(dy,dx),(0,1))
            count+=np.roll(valid,(dy,dx),(0,1))
        fresh=(~valid)&(count>0)
        edge_z[fresh]=total[fresh]/count[fresh]
        valid|=fresh
    edge_target=(edge_z+.041)*contact+np.minimum(edge_z-.075,bed+.005)*(1-contact)
    lift=(edge_target-dry)*np.exp(-(np.maximum(sd,0)/(.14+.13*push+.05*second))**1.6)
    outside=dry+lift
    z=np.where(mask,wax_under,outside)
    # Blend the discretization only over the shell contact/wet line.
    for _ in range(3):
        softened=(z*4+np.roll(z,1,0)+np.roll(z,-1,0)+np.roll(z,1,1)+np.roll(z,-1,1))/8
        z=np.where(np.abs(sd)<.48,softened,z)
    group=collection(scene,'07 | Moulded sealing wax')
    wax,bsdf=textured('07 | Iron oxide / red encaustic wax',((.125,.011,.016),(.35,.048,.027)),.50,75,.004)
    bsdf.inputs['Coat Weight'].default_value=.14
    bsdf.inputs['Coat Roughness'].default_value=.38
    bsdf.inputs['Subsurface Weight'].default_value=.042
    bsdf.inputs['Subsurface Radius'].default_value=(.12,.046,.019)
    # Ribbons of iron-oxide pigment fold through the same wax body.
    nt=wax.node_tree
    texcoord=next(n for n in nt.nodes if n.type=='TEX_COORD')
    mapping=nt.nodes.new('ShaderNodeVectorMath')
    mapping.operation='MULTIPLY'
    mapping.location=(-550,410)
    mapping.inputs[1].default_value=(.5,2.1,1.0)
    nt.links.new(texcoord.outputs['Object'],mapping.inputs[0])
    striae=nt.nodes.new('ShaderNodeTexNoise')
    striae.label='Drawn-out pigment seams'
    striae.location=(-340,420)
    striae.inputs['Scale'].default_value=1.2
    striae.inputs['Detail'].default_value=3.4
    striae.inputs['Distortion'].default_value=1.65
    nt.links.new(mapping.outputs[0],striae.inputs[0])
    veins=nt.nodes.new('ShaderNodeValToRGB')
    veins.location=(-110,420)
    vr=veins.color_ramp
    vr.elements[0].position=.455
    vr.elements[0].color=(0,0,0,1)
    vr.elements[1].position=.565
    vr.elements[1].color=(0,0,0,1)
    for pos,value in ((.478,.17),(.498,.07),(.516,.25),(.531,.015)):
        ve=vr.elements.new(pos)
        ve.color=(value,value,value,1)
    nt.links.new(striae.outputs['Fac'],veins.inputs['Fac'])
    swirl=nt.nodes.new('ShaderNodeMixRGB')
    swirl.location=(100,280)
    swirl.label='Dispersed warm umber'
    pigment=bsdf.inputs['Base Color'].links[0].from_socket
    nt.links.new(pigment,swirl.inputs[1])
    nt.links.new(veins.outputs[0],swirl.inputs[0])
    swirl.inputs[2].default_value=(.34,.087,.040,1)
    nt.links.new(swirl.outputs[0],bsdf.inputs['Base Color'])
    sheet=surface(group,'07 | Compression bed and wax over the grip ends',x,y,z,wax)
    sheet['Contact']='World-space vertical rays from actual face-up assembly; custom pressure field varies the overlap and builds directional folds.'
    sheet['Enveloping wax, maximum requested lap in BU']=float(lap.max())
    scene['Orientation']='Original controller rotated -90 degrees about X and spun -22 degrees about Z.'
    cam,lights=camera_rig(scene,'07 | Pigment impression',(0,.0,.47),2.0,53,11.1,78)
    for args in [
       ('07 | Warm north window',(-3.35,2.0,4.6),(-.2,.05,.45),450,2.5,4.0,(1,.91,.78)),
       ('07 | Cool frontal bounce',(1.1,-4.2,3.05),(.15,-.15,.64),130,3.8,2.7,(.75,.87,1)),
       ('07 | Thin rim for compressed wax',(3.9,1.75,2.4),(1.05,.12,.34),155,.58,3.65,(1,.80,.61)),
       ('07 | Grip white card',(-3.7,-2.1,2.65),(-.8,-.2,.66),58,.72,2.4,(1,.89,.78))]:
        set_area(lights,*args)
    return scene


def build(source):
    product=bpy.data.collections[PARTS]
    return [survey_world(source,product),wax_world(source,product)]
