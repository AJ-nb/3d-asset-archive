from pathlib import Path
from PIL import Image, ImageDraw
p=Path(__file__).resolve().parents[2]
files=sorted((p/"04_Blender工程实拍").glob("*.png"))
canvas=Image.new("RGB",(1536,((len(files)+1)//2)*457),(22,26,32))
for i,file in enumerate(files):
    with Image.open(file) as raw:
        raw.thumbnail((768,435))
        canvas.paste(raw,(i%2*768,i//2*457))
    ImageDraw.Draw(canvas).text((i%2*768+12,i//2*457+435),"V3 / ORIGINAL FEEDBACK" if i==0 else f"UI / {i:02d}",fill="white")
canvas.save(p/"provenance/ui-work/contact.jpg",quality=90)

