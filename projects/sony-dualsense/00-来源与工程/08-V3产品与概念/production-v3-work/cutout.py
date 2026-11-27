from pathlib import Path
import sys
import bpy

WORK = Path(__file__).resolve().parent
sys.path.insert(0,str(WORK))
import v3_common as c


def build():
    scene = c.new_scene('08','isolated-controller','Layout | isolated controller',(2048,2048),alpha=True)
    c.place(scene, pitch=-90, yaw=-10)
    cam = c.camera(scene,(-4.3,-7.3,6.7),(.0,.0,.51),lens=89)
    cam.data.shift_x = .040
    c.world(scene,(.86,.89,.95),.20)
    c.area(scene,'Silk across white shoulder',(.4,-4.6,4.5),(-.5,.2,.62),385,3.6,2.4,(1,.966,.91))
    c.area(scene,'Long strip on the controls',(3.4,.9,3.5),(.7,.3,.88),175,.68,3.4,(.87,.93,1))
    c.area(scene,'Broad front bounce',(2.5,-4.5,2.6),(.0,-.6,.45),103,3.1,2.45,(.91,.95,1))
    c.area(scene,'Raised edge on graphite',(-2.2,3.0,4.1),(-.42,.3,.92),125,2.7,1.4,(1,.95,.90))
    scene['Purpose'] = 'Transparent art for flexible backgrounds. No floor or baked shadow.'
    scene.cycles.samples = 224
    scene.cycles.adaptive_min_samples = 32
    layer = scene.view_layers[0]
    layer.use_pass_z = True
    layer.use_pass_normal = True
    layer.use_pass_diffuse_color = True
    layer.use_pass_glossy_direct = True
    return scene


def print_native(scene):
    c.gpu()
    bpy.context.window.scene = scene
    scene.frame_set(1)
    scene.cycles.device = 'GPU'
    png = c.OUT / 'masters' / '08-isolated-controller.png'
    exr = c.OUT / 'passes' / '08-isolated-linear.exr'
    png.parent.mkdir(parents=True,exist_ok=True)
    exr.parent.mkdir(parents=True,exist_ok=True)
    r = scene.render
    r.filepath = str(exr)
    fmt = r.image_settings
    fmt.media_type = 'MULTI_LAYER_IMAGE'
    fmt.file_format = 'OPEN_EXR_MULTILAYER'
    fmt.color_mode, fmt.color_depth, fmt.exr_codec = 'RGBA','16','ZIP'
    assert bpy.ops.render.render(scene=scene.name,write_still=True) == {'FINISHED'}
    fmt.media_type = 'IMAGE'
    fmt.file_format,fmt.color_mode,fmt.color_depth = 'PNG','RGBA','16'
    bpy.data.images['Render Result'].save_render(str(png),scene=scene)
    print(png,exr,flush=True)


if __name__ == '__main__':
    if 'native' in sys.argv:
        scene = next(s for s in bpy.data.scenes if s.name.startswith('08 '))
        print_native(scene)
    else:
        scene = build()
        c.save(WORK/'cutout.blend')
        c.render(scene,WORK/'cutout-proofs',preview=True)
