"""Assemble the three uncropped archived Blender replay plates into a 3:4 reading layout."""
from pathlib import Path
import hashlib
import json
from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parent.parent
RECEIPT = BASE / "provenance/replay-v1.json"
data = json.loads(RECEIPT.read_text(encoding="utf-8"))
records = data["stages"]
sheet = Image.new("RGB",(1242,1656),"#F6F5F1")
draw = ImageDraw.Draw(sheet)
fonts = Path("C:/Windows/Fonts")
def font(size, bold=False):
    return ImageFont.truetype(str(fonts / ("msyhbd.ttc" if bold else "msyh.ttc")),size)
def line(loc, message, size, fill="#20282D", bold=False):
    draw.text(loc,message,font=font(size,bold),fill=fill,anchor="lt")
line((70,89),"从空场景到机身",90,bold=True)
line((74,228),"本次依 V1 原脚本复演",42,"#8B4634",True)
line((74,303),"三幅画面共用正交机位，坐标网格间距 10 mm。",31,"#485459")
stage_labels=["空场景","握把主壳放样","机身与横屏"]
xs=[69,443,817]
cell_w,cell_h=356,815
for i,(r,x,label) in enumerate(zip(records,xs,stage_labels)):
    line((x,421),label,38,bold=True)
    with Image.open(BASE/r["file"]) as im:
        left = (im.width - 632)//2 - 44
        crop = im.crop((left,28,left+632,1475))
        view = crop.resize((cell_w,cell_h),Image.Resampling.LANCZOS)
    sheet.paste(view,(x,510))
    line((x,1372),str(r["visible_parts"])+" 个",50,bold=True)
draw.line((70,1481,1173,1481),fill="#C7CBC8",width=2)
line((72,1515),"统计可见几何对象，含曲线和文字。",31,"#435058")
line((72,1576),"屏幕安装完毕时，程序尚未开始生成云台。",31,"#435058")
target=(BASE/records[0]["file"]).parent/"04_V1起模复演_竖版图板.jpg"
sheet.save(target,quality=95,subsampling=0)
with target.open("rb") as f:
    h=hashlib.file_digest(f,"sha256").hexdigest()
data["vertical_contact_sheet"]={"file":target.relative_to(BASE).as_posix(),"sha256":h,"pixels":list(sheet.size),"presentation":"原始三张 Blender 渲染同等裁幅、等比缩放、排版与文字标注。","script":Path(__file__).relative_to(BASE).as_posix()}
RECEIPT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
