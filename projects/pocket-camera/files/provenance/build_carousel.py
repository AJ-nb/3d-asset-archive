"""Build nine publication images from traceable local project plates."""
from pathlib import Path
from functools import lru_cache
from hashlib import sha256
from shutil import copyfile
import json
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageCms
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / '00_小红书发布图'
DEST.mkdir(exist_ok=True)
PROCESS = ROOT / '03_建模过程原片'
UI = ROOT / '04_Blender工程实拍'
FINAL = ROOT / '02_历版效果图/V7_终版'
CLAY = ROOT / '05_同机位补拍/V7终版对照'
REPLAY = ROOT / '05_同机位补拍/V1起模复演'
ARCH = ROOT / '01_历史4K原图'
FILM = ROOT / 'provenance/动画抽帧'
FILM.mkdir(exist_ok=True)
W,H=1440,1920
PAPER='#f3f0e9'; INK='#152328'; LIGHT='#e9e9df'; SLATE='#3f5256'; HOT='#b54423'; PINK='#ffa380'; MUTE='#4e605e'
PROFILE=ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
docs=[]
@lru_cache(maxsize=64)
def font(px,style='normal'):
    paths={'normal':'msyh.ttc','bold':'msyhbd.ttc','light':'msyhl.ttc','mono':'consola.ttf','eng':'bahnschrift.ttf'}
    return ImageFont.truetype('C:/Windows/Fonts/'+paths[style],px)
def digest(p):
    with p.open('rb') as f: return sha256(f.read()).hexdigest()
def find(folder,prefix):
    return next(iter(sorted(folder.glob(prefix+'*'))))
class Page:
    def __init__(self,number,slug,section,dark=False):
        self.number=number; self.slug=slug; self.sources=[]
        self.bg=INK if dark else PAPER; self.fg=LIGHT if dark else INK; self.mute='#b8c6c1' if dark else MUTE; self.accent=PINK if dark else HOT
        self.im=Image.new('RGB',(W,H),self.bg); self.d=ImageDraw.Draw(self.im)
        self.t(76,53,'建模手记',32,'bold')
        self.t(274,58,'/   '+section,23,'mono',self.mute)
        self.t(1362,54,f'{number:02d} / 09',31,'mono',self.mute,'rt')
        self.rule(76,112,1364)
    def t(self,x,y,s,size=36,face='normal',color=None,anchor='lt'):
        self.d.text((x,y),s,font=font(size,face),fill=color or self.fg,anchor=anchor,stroke_width=0)
    def rule(self,x,y,end,color=None,n=1):
        self.d.line((x,y,end,y),fill=color or self.mute,width=n)
    def title(self,head,sub):
        self.t(72,152,head,82,'bold')
        self.t(78,275,sub,35,'normal',self.mute)
    def footer(self,who,note):
        self.rule(76,1799,1364)
        self.t(77,1835,who,27,'bold')
        self.t(1364,1837,note,25,'normal',self.mute,'rt')
    def img(self,path,box,crop=None,mode='fit',center=(.5,.5),trim=False):
        path=Path(path); x,y,w,h=box
        with Image.open(path) as orig:
            im=orig.copy()
        if trim: im=im.crop(im.getchannel('A').getbbox())
        if crop:
            a,b,c,d=crop
            im=im.crop((round(a*im.width),round(b*im.height),round(c*im.width),round(d*im.height)))
        if mode=='fit': im=ImageOps.fit(im,(w,h),Image.Resampling.LANCZOS,centering=center)
        else:
            im=ImageOps.contain(im,(w,h),Image.Resampling.LANCZOS)
            x+=round((w-im.width)*center[0]); y+=round((h-im.height)*center[1])
        if 'A' in im.getbands(): self.im.paste(im,(x,y),im.getchannel('A'))
        else:self.im.paste(im.convert('RGB'),(x,y))
        self.sources.append({'source':path.relative_to(ROOT).as_posix(),'source_sha256':digest(path),'normalized_crop':crop,'frame_on_page':box,'fit':mode,'trim_transparent_margin':trim})
    def save(self):
        p=DEST/f'{self.number:02d}_{self.slug}.jpg'
        self.im.save(p,quality=93,subsampling=0,icc_profile=PROFILE,optimize=True)
        docs.append({'file':p.relative_to(ROOT).as_posix(),'sha256':digest(p),'sources':self.sources})
        print(p.name,flush=True)

def panel_label(p,x,y,name,code):
    p.t(x,y,code,28,'mono',p.accent)
    p.t(x,y+47,name,41,'bold')
def make():
    # Cover pairs an unaltered transparent product render with actual work-in-progress crops.
    p=Page(1,'封面_从零做一台云台相机','PROJECT ARCHIVE',True)
    p.t(69,160,'从零做一台',106,'bold')
    p.t(68,295,'云台相机',146,'bold')
    p.t(78,494,'从握把的第一圈轮廓，到最后一帧。',39,'normal',p.mute)
    p.rule(78,593,1362)
    p.img(find(FINAL,'06-'),(490,619,797,1137),mode='contain',trim=True)
    for yy,source,crop,label in [
        (644,find(REPLAY,'02_'),(.08,.12,.92,.9),'壳体放样'),
        (1016,find(PROCESS,'20_'),(.13,.13,.86,.86),'云台白模'),
        (1388,find(FINAL,'08-'),(.16,.10,.83,.79),'镜头成品')]:
        if yy==644:
            p.d.rectangle((78,yy,389,yy+243),fill='#363f48')
            p.img(source,(78,yy,312,244),crop,mode='contain')
        else:
            p.img(source,(78,yy,312,244),crop)
        p.t(79,yy+267,label,33,'bold')
    p.footer('Blender 制作档案','自建工程 V1—V7  /  成片 15 秒')
    p.save()

    p=Page(2,'起模_空场景到横屏','BLOCKOUT')
    p.title('第一个零件，是握把','重跑 V1 原脚本，在三个节点停下。三张图共用同一机位。')
    for i,(stem,count,name) in enumerate([('01_','000','空场景'),('02_','001','握把放样'),('03_','103','装上横屏')]):
        x=76+i*434
        p.img(find(REPLAY,stem),(x,376,418,687))
        panel_label(p,x,1097,name,count+'  OBJ')
    p.rule(76,1230,1364)
    p.img(find(PROCESS,'03_'),(76,1303,606,422),(.033,.154,.966,.97),mode='contain')
    p.t(738,1308,'比例如何确定？',48,'bold')
    p.t(740,1401,'V1 把官方正面照、模型正视图',33)
    p.t(740,1460,'和轮廓叠图并排，先核对高度',33)
    p.t(740,1519,'和屏幕位置，再向侧面扩展。',33)
    p.t(740,1644,'正面参照图来源 DJI 商店',28,'normal',p.mute)
    p.footer('起模三图 · 本次依原脚本复演','数字为可见几何对象数，包含曲线和文字')
    p.save()

    p=Page(3,'结构_从侧面找到问题','SECTION / SUPPORT')
    p.title('转到侧面，问题就出现了','V3 的后壳与支臂挤在一起。V4 重新安排了后桥和支撑臂。')
    for i,(area,tag) in enumerate([((.032,.162,.482,.910),'V3  /  调整前'),((.518,.162,.969,.910),'V4  /  调整后')]):
        x=76+650*i
        p.img(find(PROCESS,'07_'),(x,373,634,652),area)
        p.t(x,1053,tag,37,'bold')
    p.rule(76,1150,1364)
    p.img(find(UI,'00_'),(76,1224,372,431),(.443,.102,.607,.438))
    p.t(78,1681,'V3 当时反馈截图 · 局部',25,'normal',p.mute)
    p.img(find(PROCESS,'04_'),(501,1230,394,392),(.065,.176,.584,.867),mode='contain')
    p.t(500,1681,'V2 握把横截面',25,'normal',p.mute)
    p.t(941,1227,'逐层看轮廓',42,'bold')
    p.t(943,1323,'截面间隔 1 mm，',34)
    p.t(943,1382,'用来比对新旧几何。',34)
    p.t(943,1465,'外形来自照片配准，',29,'normal',p.mute)
    p.t(943,1517,'内腔来自展示模型。',29,'normal',p.mute)
    p.footer('V2—V4 · 同期校核原片','上方为同视角模型对照；下方保留历史反馈')
    p.save()

    p=Page(4,'几何_镜头正面与支承','GEOMETRY / REPAIR')
    p.title('一道异常高光，追到了网格','镜头前板在近景里出现三角亮斑。修复后，侧光下再看一次。')
    for i,(area,label) in enumerate([((.021,.150,.478,.928),'V4  /  正面破面'),((.507,.150,.966,.928),'V5  /  修复后')]):
        x=76+i*650
        p.img(find(PROCESS,'11_'),(x,374,634,661),area)
        p.t(x,1064,label,38,'bold')
    p.rule(76,1150,1364)
    p.img(find(PROCESS,'22_'),(76,1215,386,437),mode='contain')
    p.img(find(PROCESS,'23_'),(469,1215,386,437),mode='contain')
    p.t(77,1670,'V7 支承内构 · 同机位白模与线框',28,'normal',p.mute)
    p.t(920,1226,'26 → 0',76,'bold',p.accent)
    p.t(921,1346,'前板自相交三角面对数',32,'bold')
    p.t(921,1430,'同一检测阈值下复查。',30)
    p.t(921,1490,'右上 V5 另加条灯，',30,'normal',p.mute)
    p.t(921,1544,'下方用素模读支承形状。',30,'normal',p.mute)
    p.footer('V4—V7 · 近景及几何复核','计数对应镜头前板这一件零件')
    p.save()

    p=Page(5,'同机位_白模线框成品','SAME CAMERA',True)
    p.title('同一机位，三次看整机','固定终版工程第 62 帧，从表面形状、边线看到最终材质。')
    for i,(stem,num,label) in enumerate([('01_','01 / CLAY','白模'),('02_','02 / WIRE','可见边线'),('03_','03 / BEAUTY','材质成品')]):
        x=76+434*i
        p.img(find(CLAY,stem),(x,395,418,962),mode='fit')
        panel_label(p,x,1401,label,num)
    p.rule(76,1544,1364)
    p.t(78,1613,'88 mm',68,'eng',p.accent)
    p.t(429,1616,'主视觉相机',47,'bold')
    p.t(429,1694,'三张原片均为 2160 × 3840，保留完整竖幅。',33,'normal',p.mute)
    p.footer('V7 Final · 本次同机位补渲','屏内示例图取自 DJI 商店')
    p.save()

    p=Page(6,'工程_材质节点与摄影棚','SHADER / STUDIO')
    p.title('打开工程看材质，也看光','支臂如何反光、轮廓如何从深色背景中分出来，都能回到工程里看。')
    p.img(find(UI,'05_'),(76,367,1288,574),(.036,.102,.845,.836))
    p.t(76,969,'支臂材质',40,'bold')
    p.t(359,980,'同一界面中的实际零件与着色节点',31,'normal',p.mute)
    p.img(find(UI,'07_'),(76,1081,1288,571),(.033,.083,.968,.803))
    p.t(76,1680,'棚灯与机位',40,'bold')
    p.t(359,1690,'六盏面光围绕产品布置，右侧回看主视觉',31,'normal',p.mute)
    p.footer('V7 Final · 本次打开 Blender 补拍','发布图取界面局部，完整桌面截图另存')
    p.save()

    p=Page(7,'成品_双镜与云台','FINISHED PLATES',True)
    p.title('正面读镜片，侧后读结构','从三个方向看同一版成品，让玻璃、金属和机身各自说清楚。')
    p.img(find(FINAL,'08-'),(76,363,898,768))
    p.img(find(FINAL,'02-'),(988,363,376,375),(.285,.075,.744,.535))
    p.img(find(FINAL,'02-'),(988,754,376,377),(.293,.515,.744,.968))
    p.t(77,1153,'双镜斜正面',36,'bold')
    p.img(find(FINAL,'03-'),(76,1252,634,421),(.02,.01,.99,.95),center=(.5,.38))
    p.img(find(FINAL,'04-'),(726,1252,638,421),(.123,.09,.933,.79),center=(.5,.49))
    p.t(77,1701,'横滚后桥与支臂',32)
    p.t(727,1701,'转屏与操控区',32)
    p.footer('V7 Final · 同期成品图','各处特写裁自终版渲染，屏内示例图来源 DJI 商店')
    p.save()

    p=Page(8,'动画_转屏与关键帧','MOTION / TIMELINE',True)
    p.title('最后，让它动起来','用同一套硬质零件做转屏、偏航和俯仰，再把动作接进剪辑。')
    frames=[(19,'录制键'),(95,'转屏途中'),(257,'双镜侧切')]
    for i,(fr,name) in enumerate(frames):
        src=FILM/f'Pulse-{fr:04d}.png'
        if not src.exists():copyfile(ROOT.parent/'dji-osmo-pocket-4p-cg15/frames'/src.name,src)
        x=76+i*434
        p.img(src,(x,371,418,664),mode='fit')
        p.t(x,1065,name,38,'bold')
        p.t(x,1125,f'FRAME  {fr:03d}',27,'mono',p.accent)
    p.img(find(UI,'06_'),(76,1235,776,440),mode='contain')
    p.t(77,1706,'第 95 帧 · 工程界面与时间线',27,'normal',p.mute)
    p.t(912,1247,'15 秒',69,'bold')
    p.t(915,1383,'13 个镜头',42,'bold')
    p.t(915,1460,'30 fps  /  450 帧',32,'eng',p.accent)
    p.t(915,1558,'上方取自实际渲染序列。',29,'normal',p.mute)
    p.footer('CG 独立工程 · 渲染帧与实拍界面','成片为 1080 × 1920；亮屏素材来源 DJI 商店')
    p.save()

    p=Page(9,'前作附页_三套4K棚拍','PREVIOUS PROJECT')
    p.title('附页｜前作的三组棚拍','早期工程使用已有模型，分别保留了经典黑、珍珠白和白模原图。')
    for i,(pattern,lab,ct) in enumerate([('classic-black-01-hero.png','经典黑','4 PLATES'),('pearl-white-01-hero.png','珍珠白','4 PLATES'),('white-clay-01-hero.png','白模','3 PLATES')]):
        x=76+i*434
        p.img(next(ARCH.rglob(pattern)),(x,395,418,960))
        panel_label(p,x,1392,lab,ct)
    p.rule(76,1544,1364)
    p.t(78,1610,'11 张',64,'bold',p.accent)
    p.t(420,1616,'历史 4K 原始 PNG',43,'bold')
    p.t(420,1692,'第三方几何由用户提供，单独归档其配色与布光。',32,'normal',p.mute)
    p.footer('前作 · 独立配色工程','9 张竖幅、2 张横幅  /  RGB 16 bit')
    p.save()

if __name__=='__main__':
    make()
    (ROOT/'provenance/发布图来源.json').write_text(json.dumps({'size':[W,H],'color':'embedded sRGB IEC61966-2.1','method':'Original project images, cropped for publication; typography added. No generative process imagery. Coordinates are fractions of sources.','pages':docs},ensure_ascii=False,indent=2),encoding='utf-8')

