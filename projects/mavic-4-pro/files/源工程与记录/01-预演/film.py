"""Build the editable Mavic studio scene in a fresh Blender process."""
from pathlib import Path
from mathutils import Vector
import math
import sys
import bpy

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(HERE))
from common import mat, mesh, uv, empty, box

ARGS = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
LAYOUT = "--layout" in ARGS
scene = bpy.context.scene
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.context.preferences.filepaths.save_version = 0
scene.unit_settings.system = "METRIC"
scene.unit_settings.length_unit = "MILLIMETERS"
scene.render.engine = "CYCLES"
scene.cycles.samples = 28
scene.cycles.adaptive_threshold = .055
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 5
scene.cycles.transmission_bounces = 4
scene.cycles.glossy_bounces = 3
scene.cycles.transparent_max_bounces = 6
scene.cycles.sample_clamp_indirect = 4
scene.render.fps = 24
scene.frame_end = 360
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.render.image_settings.compression = 15
scene.render.film_transparent = False
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"
scene.view_settings.exposure = -.85
scene.render.use_sequencer = False


def collection(name):
    result = bpy.data.collections.new(name)
    scene.collection.children.link(result)
    return result


def move(obj, destination):
    if destination not in obj.users_collection:
        destination.objects.link(obj)
    for col in list(obj.users_collection):
        if col != destination:
            col.objects.unlink(obj)


def add_module(destination, fn, root):
    before = set(bpy.data.objects)
    result = fn(root)
    for obj in set(bpy.data.objects)-before:
        move(obj, destination)
    return result


def meters(co):
    return Vector(co) * .001


def aim(obj, point):
    obj.rotation_euler = (Vector(point)-obj.location).to_track_quat("-Z","Y").to_euler()


product = collection("01  /  Aircraft")
shells = collection("02  /  Fuselage and sensors")
motors = collection("03  /  Arms, motors and propellers")
optics = collection("04  /  Infinity Gimbal and optics")
studio = collection("05  /  Studio and light cards")
cameras = collection("06  /  Editorial cameras")
titles = collection("07  /  Screen typography")

root = empty("AIRCRAFT  |  millimetre model space")
root.scale = (.001,)*3
root.empty_display_size = 65
move(root, product)
if LAYOUT:
    neutral = mat("Layout clay",(.27,.28,.29))
    uv("Blockout shell",(0,0,84),(56,110,42),neutral,root)
    roll = empty("Camera roll",(0,-100,69),root)
    uv("Blockout gimbal",(0,0,0),(35,35,35),neutral,roll)
    for side in [-1,1]:
        for fore in [-1,1]:
            start = Vector((side*46,fore*54,78))
            end = Vector((side*175,fore*145,78))
            arm = box("Arm guide",(start+end)/2,(19,(end-start).length,19),neutral,root,5)
            arm.rotation_euler.z = -math.atan2((end-start).x,(end-start).y)
            box("Rotor bounds",end,(218,16,4),neutral,root,2)
else:
    from body import build_body
    from arms import build_arms
    from gimbal import build_gimbal
    add_module(shells, build_body, root)
    add_module(motors, build_arms, root)
    roll = add_module(optics, build_gimbal, root)
    shell = bpy.data.materials["Airframe | Basalt silver composite"]
    shell.diffuse_color = (.122,.128,.140,1)
    tree = shell.node_tree
    polymer = tree.nodes.get("Principled BSDF")
    polymer.inputs["Base Color"].default_value = shell.diffuse_color
    coords = tree.nodes.new("ShaderNodeTexCoord")
    grain = tree.nodes.new("ShaderNodeTexNoise")
    grain.label = "Fine moulded grain in local millimetres"
    grain.inputs["Scale"].default_value = 3.1
    grain.inputs["Detail"].default_value = 1.5
    tree.links.new(coords.outputs["Object"],grain.inputs["Vector"])
    rough = tree.nodes.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = .37
    rough.inputs["To Max"].default_value = .52
    tree.links.new(grain.outputs["Fac"],rough.inputs["Value"])
    tree.links.new(rough.outputs["Result"],polymer.inputs["Roughness"])
    relief = tree.nodes.new("ShaderNodeBump")
    relief.inputs["Distance"].default_value = .000028
    relief.inputs["Strength"].default_value = .17
    tree.links.new(grain.outputs["Fac"],relief.inputs["Height"])
    tree.links.new(relief.outputs["Normal"],polymer.inputs["Normal"])

roll.rotation_mode = "XYZ"
roll["Control"] = "Camera-module roll about local Y. Product is parked for these studio shots."
def gimbal_roll(frame):
    duration, ramp = 116, 18
    t = min(duration, max(0, frame - 124))
    speed = 360 / (duration - ramp)
    def start_area(elapsed):
        u = elapsed / ramp
        return ramp * (u**3 - .5*u**4)
    if t < ramp:
        return speed*start_area(t)
    if t > duration-ramp:
        return 360 - speed*start_area(duration-t)
    return speed*(t - ramp/2)


for frame in [1, *range(124,241), 360]:
    angle = gimbal_roll(frame)
    roll.rotation_euler.y = math.radians(angle)
    roll.keyframe_insert(data_path="rotation_euler", index=1, frame=frame)


def configure_handles(obj):
    action = obj.animation_data.action
    slot = obj.animation_data.action_slot
    for layer in action.layers:
        for strip in layer.strips:
            for fc in strip.channelbag(slot).fcurves:
                for key in fc.keyframe_points:
                    key.handle_left_type = "AUTO_CLAMPED"
                    key.handle_right_type = "AUTO_CLAMPED"


configure_handles(roll)
world = bpy.data.worlds.new("Cyclorama ambient")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs[0].default_value = (.31,.35,.41,1)
bg.inputs[1].default_value = .20

floor_material = mat("Stage  |  graphite satin",(.018,.025,.034),.02,.69)
floor_material.node_tree.nodes.get("Principled BSDF").inputs["Specular IOR Level"].default_value = .18
ground = mesh("Seamless graphite stage",[(-20,-20,-.0033),(20,-20,-.0033),(20,20,-.0033),(-20,20,-.0033)],
              [(0,1,2,3)],floor_material,smooth=False)
move(ground,studio)


def softbox(name, location, target, watts, width, height, rgb):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = watts*.25
    data.shape = "RECTANGLE"
    data.size = width
    data.size_y = height
    data.color = rgb
    obj = bpy.data.objects.new(name,data)
    studio.objects.link(obj)
    obj.location = meters(location)
    aim(obj,meters(target))
    return obj


softbox("KEY  |  silk, camera left",(-425,-345,585),(0,-10,65),40,.42,.65,(1,.93,.85))
softbox("RIM  |  long strip, right",(275,200,360),(0,5,65),38,.065,.65,(.82,.88,1))
softbox("TOP  |  overhead book light",(-105,240,550),(0,75,55),24,.50,.20,(1,.96,.89))
softbox("FRONT  |  optical strip",(135,-410,145),(0,-100,70),5,.11,.22,(.88,.94,1))
softbox("EDGE  |  narrow warm strip",(-380,130,288),(0,65,70),12,.055,.36,(1,.78,.55))
softbox("POOL  |  background falloff",(0,460,480),(0,420,0),12,.46,.38,(.79,.86,1))


def shot(name, first, last, lens, poses, shift=0):
    data = bpy.data.cameras.new(name)
    data.lens = lens
    data.sensor_width = 36
    data.clip_start = .001
    data.clip_end = 24
    data.shift_x = shift
    cam = bpy.data.objects.new(name,data)
    cameras.objects.link(cam)
    marker = scene.timeline_markers.new(name,frame=first)
    marker.camera = cam
    for frame, position, focus in poses:
        cam.location = meters(position)
        aim(cam,meters(focus))
        cam.keyframe_insert(data_path="location",frame=frame)
        cam.keyframe_insert(data_path="rotation_euler",frame=frame)
    configure_handles(cam)
    return cam


wide = shot("01  /  Front three-quarter",1,64,39,[
    (1,(570,-685,400),(0,0,62)),(32,(495,-720,360),(0,0,59)),(64,(412,-755,313),(0,0,57))])
detail = shot("02  /  Leading arm to optics",65,118,57,[
    (65,(210,-326,166),(88,-93,84)),(90,(172,-310,144),(63,-94,84)),(118,(142,-292,130),(38,-96,83))])
gcam = shot("03  /  Infinity Gimbal  |  locked",119,246,62,[
    (119,(0,-398,89),(0,-100,72))])
over = shot("04  /  Plan view",247,278,36,[
    (247,(-135,-143,737),(0,0,55)),(278,(-80,-165,710),(0,0,55))])
end = shot("05  /  Closing hero",279,360,37,[
    (279,(-410,-758,337),(0,0,61)),(326,(-360,-792,301),(0,0,61)),(360,(-342,-805,291),(0,0,61))],shift=-.024)
scene.camera = wide


def lettering(label, content, cam, first, last, left, top, height, spacing=1):
    # left and top refer to normalized screen coordinates measured from upper left.
    font = bpy.data.curves.new(label, "FONT")
    font.body = content
    font.space_character = spacing
    font.align_y = "TOP_BASELINE"
    font_path = BASE/"type"/"BarlowSemiCondensed-SemiBold.ttf"
    if font_path.exists():
        font.font = bpy.data.fonts.load(str(font_path),check_existing=True)
    obj = bpy.data.objects.new(label,font)
    titles.objects.link(obj)
    obj.parent = cam
    depth = .010
    span = depth*cam.data.sensor_width/cam.data.lens
    obj.location = ((left-.5+cam.data.shift_x)*span,(.5-top)*span*9/16,-depth)
    font.size = height*span
    white = bpy.data.materials.get("Type  |  pearl")
    if not white:
        white = bpy.data.materials.new("Type  |  pearl")
        white.use_nodes = True
        tree = white.node_tree
        shader = tree.nodes.new("ShaderNodeEmission")
        shader.inputs["Color"].default_value = (.90,.93,.98,1)
        shader.inputs["Strength"].default_value = 2.7
        tree.links.new(shader.outputs[0],tree.nodes.get("Material Output").inputs[0])
    font.materials.append(white)
    for prop in ["visible_shadow","visible_diffuse","visible_glossy","visible_transmission","visible_volume_scatter"]:
        setattr(obj,prop,False)
    for frame,hidden in [(1,True),(first,False),(last+1,True)]:
        obj.hide_render = hidden
        obj.hide_viewport = hidden
        obj.keyframe_insert(data_path="hide_render",frame=frame)
        obj.keyframe_insert(data_path="hide_viewport",frame=frame)
    return obj


lettering("Lens study caption","INFINITY GIMBAL",gcam,119,246,.055,.882,.0128,1.18)
lettering("Closing title","MAVIC 4 PRO",end,279,360,.050,.188,.047,1.01)

if not LAYOUT:
    editor = scene.sequence_editor_create()
    wav = BASE/"audio"/"Studio-score.wav"
    if wav.exists():
        strip = editor.strips.new_sound("Studio score  |  original",str(wav),channel=1,frame_start=1)
    bpy.ops.file.pack_all()

scene.frame_set(32)
scene.render.filepath = "//frames/mavic_"
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == "VIEW_3D":
            area.spaces.active.region_3d.view_perspective = "CAMERA"
            area.spaces.active.overlay.show_overlays = False
            area.spaces.active.shading.color_type = "MATERIAL"
scene["Production"] = "Editable visual reconstruction from public DJI views. Display motion only."
out = BASE/("review/layout.blend" if LAYOUT else "DJI-Mavic-4-Pro.blend")
out.parent.mkdir(exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True)
print("STUDIO_PROJECT",out,len(scene.objects),flush=True)
