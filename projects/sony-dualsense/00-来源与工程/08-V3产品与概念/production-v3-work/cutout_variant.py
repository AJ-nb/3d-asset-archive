from pathlib import Path
import sys
import bpy
work=Path(__file__).resolve().parent
sys.path.insert(0,str(work))
from v3_common import aim,render
s=next(s for s in bpy.data.scenes if s.name.startswith('08 '))
s.camera.data.shift_x=.040
key=s.objects['08 | Silk across white shoulder']
rim=s.objects['08 | Raised edge on graphite']
for i,(location,back) in enumerate([((-4.2,1.2,3.7),(-1.2,3.6,3.6)),((.4,-4.6,4.5),(-2.2,3.0,4.1)),((-4.9,-.35,3.3),(1.65,3.3,3.8))],1):
    key.location=location
    aim(key,(-.5,.2,.62))
    rim.location=back
    aim(rim,(-.42,.3,.92))
    s.render.filepath=f'//masters/08-candidate-{i}.png'
    render(s,work/'cutout-proofs',True)
