"""Reproducible product plates. Coordinates in mm, final images in display-referred sRGB."""
from pathlib import Path
import argparse, json, math, sys
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parent.parent
# Camera target and direction are in assembly space. Film height sets true scale per shot.
SHOTS={
    "01-Hero": ((0,0,79),(.54,-1,.22),188, 88,1680,2048,62,"studio"),
    "02-Optics": ((0,-12,136.4),(.045,-1,.035),58,135,1760,1760,62,"optics"),
    "03-Axis": ((0,7,127),(-.88,1,.38),86,110,1920,1536,62,"studio"),
    "04-Controls": ((0,-10,60),(.34,-1,.16),96,105,1600,1800,62,"studio"),
    "05-Standby": ((0,0,79),(.22,-1,.12),188,95,1550,1940,1,"studio"),
    "06-Cutout": ((0,0,79),(.54,-1,.22),188,88,1550,1940,62,"alpha"),
    "07-Front": ((0,-8,80),(0,-1,0),177,0,1450,2080,62,"neutral"),
    "08-Optics-Oblique": ((0,-10,135.5),(-.46,-1,.23),65,115,1856,1640,62,"raking"),
}
def track(obj,point):
    obj.rotation_euler=(point-obj.location).to_track_quat("-Z","Y").to_euler()

def configure_gpu(scene):
    prefs=bpy.context.preferences.addons["cycles"].preferences
    for backend in ("OPTIX","CUDA"):
        try:
            prefs.compute_device_type=backend
            devices=prefs.get_devices_for_type(backend)
            if any(d.type==backend for d in devices):
                for device in devices: device.use=device.type==backend
                scene.cycles.device="GPU"
                return
        except (TypeError,RuntimeError):
            continue

def install():
    s=bpy.context.scene
    for light in s.objects:
        if light.name.startswith("Stage •"):
            light.hide_render=True
    collection=bpy.data.collections.new("92 | V7 Product photography")
    s.collection.children.link(collection)
    def area(name,xyz,focus,power,color,width,height):
        data=bpy.data.lights.new(name,"AREA")
        data.shape="RECTANGLE"
        data.size=width*.001
        data.size_y=height*.001
        data.energy=power*.11
        data.color=color
        ob=bpy.data.objects.new("Studio V7 | "+name,data)
        collection.objects.link(ob)
        ob.location=Vector(xyz)*.001
        track(ob,Vector(focus)*.001)
        return ob
    area("Key",(-135,-135,238),(0,-2,102),2.65,(1,.955,.911),105,174)
    area("Upright strip",(109,55,159),(0,3,96),2.0,(.81,.90,1),42,187)
    area("Soft fill",(96,-182,137),(0,-5,68),1.26,(.92,.96,1),118,166)
    area("Rear",(-86,104,226),(0,0,115),2.65,(.92,.96,1),96,133)
    area("Crown",(8,1,248),(0,0,117),.74,(1,.99,.95),108,36)
    eye=area("Eye strip",(-10,-145,148),(0,-14,134),.48,(.83,.91,1),46,8)
    receivers=bpy.data.collections.get("Studio | optical reflection receivers")
    if receivers: eye.light_linking.receiver_collection=receivers
    floor_mesh=bpy.data.meshes.new("V7 continuous sweep")
    rings=[(.34,-.000015)]+[(.34+.30*math.sin(i*math.pi/48),-.000015+.30*(1-math.cos(i*math.pi/48))) for i in range(1,25)]+[(.64,2)]
    sides=112
    vertices=[(r*math.cos(i*2*math.pi/sides),r*math.sin(i*2*math.pi/sides),z) for r,z in rings for i in range(sides)]
    faces=[tuple(range(sides))]
    for j in range(len(rings)-1):
        for i in range(sides):
            a=j*sides+i
            b=j*sides+(i+1)%sides
            faces.append((b,a,a+sides,b+sides))
    floor_mesh.from_pydata(vertices,[],faces)
    for poly in floor_mesh.polygons: poly.use_smooth=True
    floor=bpy.data.objects.new("Studio V7 | sweep",floor_mesh)
    collection.objects.link(floor)
    floor_mat=bpy.data.materials.new("Studio V7 | basalt")
    bs=next(n for n in floor_mat.node_tree.nodes if n.type=="BSDF_PRINCIPLED")
    bs.inputs["Base Color"].default_value=(.032,.045,.059,1)
    bs.inputs["Roughness"].default_value=.89
    floor.data.materials.append(floor_mat)
    s.world=bpy.data.worlds.new("V7 soft studio")
    bg=next(n for n in s.world.node_tree.nodes if n.type=="BACKGROUND")
    bg.inputs[0].default_value=(.24,.27,.32,1)
    bg.inputs[1].default_value=.20
    for name,(target,direction,height,lens,width,h,frame,mode) in SHOTS.items():
        camdata=bpy.data.cameras.new(name)
        camera=bpy.data.objects.new("Plate | "+name,camdata)
        collection.objects.link(camera)
        center=Vector(target)*.001
        camdata.sensor_fit="VERTICAL"
        camdata.sensor_height=32
        if lens:
            camdata.lens=lens
            dist=height*.001*lens/camdata.sensor_height
        else:
            camdata.type="ORTHO"
            camdata.ortho_scale=height*.001
            dist=.215
        camdata.clip_start=.0006
        camdata.clip_end=8
        camera.location=center+Vector(direction).normalized()*dist
        track(camera,center)
        camera["output size"]=[width,h]
        camera["rig frame"]=frame
        camera["light setup"]=mode
    s.render.engine="CYCLES"
    configure_gpu(s)
    s.cycles.samples=160
    s.cycles.use_adaptive_sampling=True
    s.cycles.adaptive_threshold=.014
    s.cycles.use_denoising=True
    s.cycles.max_bounces=14
    s.cycles.transmission_bounces=10
    s.cycles.glossy_bounces=6
    s.cycles.transparent_max_bounces=10
    s.cycles.sample_clamp_indirect=5
    s.view_settings.view_transform="AgX"
    s.view_settings.look="AgX - Medium High Contrast"
    s.view_settings.exposure=-.55
    s.view_settings.gamma=1
    s.view_layers[0].use_pass_z=True
    s.view_layers[0].use_pass_normal=True
    s.view_layers[0].use_pass_diffuse_color=True
    s.view_layers[0].use_pass_cryptomatte_object=True
    select("01-Hero")
    s.render.filepath="//renders/01-Hero.png"
    return s

def select(name):
    s=bpy.context.scene
    target,dir,height,lens,w,h,frame,mode=SHOTS[name]
    s.frame_set(frame)
    s.camera=s.objects["Plate | "+name]
    s.render.resolution_x,s.render.resolution_y=w,h
    s.render.resolution_percentage=100
    s.render.film_transparent=mode=="alpha"
    s.objects["Studio V7 | sweep"].hide_render=mode=="alpha"
    # Keep reflectors out of the direct lens axis. Broader neutral fill separates the baffle and glass.
    s.objects["Studio V7 | Soft fill"].data.energy=.075 if mode in ("optics","neutral") else .14
    s.objects["Fill • near lens axis"].hide_render=mode in ("optics","neutral")
    s.objects["Studio V7 | Upright strip"].data.energy=.48 if mode=="raking" else .22
    s.render.image_settings.media_type="IMAGE"
    s.render.image_settings.file_format="PNG"
    s.render.image_settings.color_mode="RGBA" if mode=="alpha" else "RGB"
    s.render.image_settings.color_depth="16"
    return s

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--proof",action="store_true")
    parser.add_argument("--shots",nargs="+",default=list(SHOTS))
    args=parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    s=bpy.context.scene
    if "Plate | 01-Hero" not in s.objects:
        if not args.proof: raise ValueError("Install the studio before rendering release plates")
        sys.path.insert(0,str(Path(__file__).resolve().parent))
        import display
        display.apply()
        install()
    configure_gpu(s)
    for name in args.shots:
        s=select(name)
        if args.proof:
            s.render.resolution_percentage=26
            s.cycles.samples=24
            folder=ROOT/"review"/"proofs"
        else:
            s.cycles.samples=224 if name=="02-Optics" else 152
            folder=ROOT/"renders"
        folder.mkdir(parents=True,exist_ok=True)
        s.render.filepath=str(folder/(name+".png"))
        bpy.ops.render.render(write_still=True)
        if name=="01-Hero" and not args.proof:
            s.render.image_settings.media_type="MULTI_LAYER_IMAGE"
            s.render.image_settings.file_format="OPEN_EXR_MULTILAYER"
            s.render.image_settings.color_depth="16"
            s.render.image_settings.exr_codec="PIZ"
            bpy.data.images["Render Result"].save_render(str(folder/"01-Hero-passes.exr"),scene=s)
        print("PLATE",name,flush=True)
if __name__=="__main__": main()

