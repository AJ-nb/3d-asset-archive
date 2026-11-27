"""Generate the offline gallery, verify links and content hashes, then pack both deliveries."""
from pathlib import Path
from hashlib import sha256
from urllib.parse import quote,unquote,urlsplit
from html.parser import HTMLParser
from html import escape
from PIL import Image,ImageOps,ImageCms
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
from collections import Counter
import json
ROOT=Path(__file__).resolve().parents[1]
EVID=ROOT/'provenance'
THUMBS=EVID/'gallery-thumbnails'
THUMBS.mkdir(exist_ok=True)
MOBILE=ROOT/'00_小红书发布图'
OUT_NAME='小红书发布包.zip'
FULL_NAME='完整证据包.zip'
ICC=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
def sha(p):
    h=sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def read(name):
    return json.loads((EVID/name).read_text(encoding='utf-8-sig'))
def rel(p):
    return p.relative_to(ROOT).as_posix()
def url(p):
    return quote(rel(p),safe='/')
def link(p,label):
    assert p.is_file(),p
    return '<a href="'+url(p)+'">'+escape(label)+'</a>'
def thumbnail(p):
    out=THUMBS/(sha(p)[:22]+'.jpg')
    if not out.exists():
        with Image.open(p) as im:
            im.thumbnail((425,460),Image.Resampling.LANCZOS)
            if 'A' in im.getbands():
                rgb=Image.new('RGB',im.size,'#d4dad7');rgb.paste(im,mask=im.getchannel('A'))
            else:rgb=im.convert('RGB')
            rgb.save(out,quality=83,optimize=True,icc_profile=ICC)
    return out
def cards(paths,caption=None):
    cv=[]
    for p in paths:
        with Image.open(p) as im:w,h=im.size
        label,desc=caption(p) if caption else (p.stem.replace('_',' · '),f'{w} × {h}')
        cv.append('<a class="card" href="'+url(p)+'"><div class="photo"><img decoding="async" loading="lazy" src="'+url(thumbnail(p))+'" alt="'+escape(label)+'"></div><b>'+escape(label)+'</b><small>'+escape(desc)+'</small></a>')
    return '<div class="grid">'+''.join(cv)+'</div>'
def section(head,body,inner):
    return '<section><h2>'+head+'</h2><p>'+body+'</p>'+inner+'</section>'
def imgs(folder):return sorted(p for p in folder.rglob('*') if p.suffix.lower() in ['.png','.jpg','.jpeg'])
def contact():
    sheet=Image.new('RGB',(1440,1920),'#c1c8c2')
    for i,p in enumerate(sorted(MOBILE.glob('*.jpg'))):
        with Image.open(p) as im:
            thumb=im.resize((474,632),Image.Resampling.LANCZOS)
            sheet.paste(thumb,(i%3*480+3,i//3*640+4))
    sheet.save(ROOT/'发布图总览.jpg',quality=92,icc_profile=ICC,optimize=True)
def source_map():
    rows=[]
    a=read('archive-plates.json')
    rows.extend((x['archive'],x['sha256']) for x in a['files'] if x.get('archive'))
    b=read('process-history.json')
    rows.extend((x['archive_path'],x['sha256']) for k in ['photos','evidence_documents'] for x in b[k])
    rows.extend((x['file'],x['screenshot_sha256']) for x in read('ui-captures.json')['captures'])
    rows.extend((x['file'],x['sha256']) for x in read('v7-reshoot.json')['plates'])
    rows.extend((x['file'],x['sha256']) for x in read('replay-v1.json')['stages'])
    rows.extend((x['file'],x['sha256']) for x in read('发布图来源.json')['pages'])
    rows.extend((s['source'],s['source_sha256']) for x in read('发布图来源.json')['pages'] for s in x['sources'])
    rows.extend((x['archive_path'],x['sha256']) for x in read('editable-projects.json')['files'])
    rows.extend((x['portable'],x['sha256']) for x in read('editable-projects.json')['relocation_test']['reports'])
    m={}
    for path,h in rows:
        p=ROOT/path
        if p not in m:m[p]=sha(p)
        assert m[p]==h,(p,h,m[p])
    return m
def html():
    history=imgs(ROOT/'01_历史4K原图')
    process=read('process-history.json')['photos']
    pmap={ROOT/r['archive_path']:r for r in process}
    new=ROOT/'05_同机位补拍'
    v7=ROOT/'02_历版效果图/V7_终版'
    port=ROOT/'06_自建工程与成片'
    hist_names={'classic-black':'经典黑','pearl-white':'珍珠白','white-clay':'白模'}
    angles={'hero':'主视觉','rear':'背面','optics':'镜头','controls':'操控区','profile':'侧面'}
    def hist_name(p):
        with Image.open(p) as im:w,h=im.size
        return (hist_names['-'.join(p.stem.split('-')[:2])]+' / '+angles[p.stem.split('-')[-1]],f'{w} × {h} · 16 bit PNG')
    h=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>从零做一台云台相机 · 项目档案</title><style>*{box-sizing:border-box}body{margin:0;background:#f3f0e9;color:#17282a;font:16px/1.6 "Microsoft YaHei",system-ui,sans-serif}main{max-width:1250px;margin:auto;padding:38px 5% 90px}header{border-top:6px solid #17282a;border-bottom:1px solid #7c8785;padding:24px 0 28px}header small{letter-spacing:.17em;color:#a54027}h1{font-size:clamp(36px,6vw,75px);line-height:1.13;margin:16px 0;font-weight:800;letter-spacing:-.04em}h2{font-size:clamp(24px,3.5vw,38px);margin:0 0 4px;line-height:1.24}p{color:#4e605e;margin:.6em 0 1.4em}section{padding:40px 0 15px;border-bottom:1px solid #bcc0b9}a{color:#844126;text-underline-offset:4px}nav{display:flex;gap:12px;flex-wrap:wrap}nav a{background:#17282a;color:#f3f0e9;padding:8px 15px;border-radius:3px;text-decoration:none}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(165px,1fr));gap:18px 12px;margin:19px 0 24px}.card{display:block;text-decoration:none;color:inherit;line-height:1.3}.photo{height:180px;background:#e3e3dc;display:grid;place-items:center;overflow:hidden}.photo img{display:block;max-width:100%;max-height:100%;height:100%;width:100%;object-fit:contain}.card b,.card small{display:block;margin:8px 0 3px}.card small{font-size:12px;color:#526563}details{padding:9px 0}summary{cursor:pointer;font-weight:700}.links{display:flex;flex-wrap:wrap;gap:10px 22px;margin:15px 0 25px}@media(max-width:600px){main{padding:20px 5% 56px}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.photo{height:155px}}</style><main><header><small>BLENDER / 制作档案</small><h1>从零做一台云台相机</h1><p>从 V1 的握把轮廓、V3 的现场反馈，到 V7 的同机位白模、边线和渲染。点击缩略图可打开原始尺寸。解压完整包后，可离线浏览。</p><nav>']
    for p,title in [(ROOT/'发布图总览.jpg','浏览九张发布图'),(ROOT/'发布文案.txt','发布文案'),(port/'工程索引.md','打开可编辑工程索引'),(EVID/'过程考证.md','核对过程与出处')]:h.append(link(p,title))
    h+=['</nav></header>',section('小红书发布顺序','九张 1440 × 1920 的 sRGB JPG。01—08 讲自建主线，09 为前作独立配色附页。',cards(sorted(MOBILE.glob('*.jpg'))))]
    h.append(section('从空场景到第一版','V1 原始脚本从空场景开始。下面三站是本次重跑脚本留下的过程图，统一机位与坐标网；图板标出了各站的可见几何对象数。',cards(imgs(new/'V1起模复演'))))
    h.append(section('版本演进与返工','按 V1 至 V7 排列。原项目中保留的 26 张资料覆盖参考、壳体截面、支臂与光学前板修复、关节、终版复核和动画。官方参考及屏内图出处见每张图的来源记录。',cards([ROOT/x['archive_path'] for x in process],lambda p:(p.stem,pmap[p]['version']+' · '+pmap[p]['category']))))
    h.append(section('工程界面','00 为用户当时提交的 V3 反馈原图。01—07 是本次在 Blender 中重新打开保存的工程后截取。',cards(imgs(ROOT/'04_Blender工程实拍'))))
    h.append(section('终版同机位 · 本次 4K 补渲','第 62 帧、88 mm 主视觉相机。白模与材质图保留原影棚，边线从最终求值网格生成，按真实遮挡合成。',cards(imgs(new/'V7终版对照'))))
    h.append(section('自建终版 · 原始成品','八张当时导出的成品图，保留原始分辨率。各版其他预览和 EXR 均在 02_历版效果图。',cards(sorted(v7.glob('[0-9][0-9]-*.png')))+'<div class="links">'+link(v7/'合成通道/01-Hero-passes.exr','主视觉多层 EXR')+link(port/'dji-osmo-pocket-4p-cg15/Pulse-15s.mp4','播放 15 秒成片')+'</div>'))
    h.append(section('前作 · 原有 4K 图库','历史配色工程的 11 张原片使用当时提供的第三方模型，自建主线的建模证据从 V1 开始。横竖版均为原生 4K。',cards(history,hist_name)))
    other=ROOT/'02_历版效果图'
    add=''
    for d in sorted(other.iterdir()):
        files=imgs(d)
        add+='<details><summary>'+escape(d.name)+'  ·  '+str(len(files))+' 张图</summary>'+cards(files)+'</details>'
    h.append(section('按原目录翻阅效果图','包括各版本和前作历史预览。多层 EXR 可从上方终版板块单独打开。',add))
    h.append(section('工程、引用与验证','原件保留源哈希。九份可携工程均在 Windows 上换盘复开。对照中的 1 mm 指几何采样间隔，内部配合和壁厚属于展示模型的重建。','<div class="links">'+''.join(link(p,t) for p,t in [(port/'工程索引.md','可携工程索引'),(EVID/'过程考证.md','阶段与资料说明'),(EVID/'发布图来源.json','逐张发布图的原片与裁切'),(EVID/'archive-plates.json','分辨率与去重清单'),(EVID/'process-history.json','过程原片出处'),(EVID/'ui-captures.json','界面版本、帧号与校验'),(EVID/'replay-v1.json','起模复演记录'),(EVID/'v7-reshoot.json','同机位补拍设置'),(EVID/'editable-projects.json','可编辑工程与复开记录')])+'</div>'))
    h.append('</main></html>')
    (ROOT/'开始阅读.html').write_text(''.join(h),encoding='utf-8')
class Refs(HTMLParser):
    def __init__(self):super().__init__();self.urls=[]
    def handle_starttag(self,tag,attrs):
        self.urls += [v for k,v in attrs if k in ('src','href')]
def included(p):
    if not p.is_file() or p.suffix=='.zip':return False
    s=p.relative_to(ROOT).parts
    if len(s)==1:return s[0] in ['发布文案.txt','发布图总览.jpg','开始阅读.html']
    if s[0]!='provenance':return s[0][:2].isdigit()
    if '__pycache__' in s or s[1].startswith(('preview_sources','review-')):return False
    return True
def zipfiles(path,entries):
    with ZipFile(path,'w',allowZip64=True) as z:
        for p,key in entries:
            zend=ZIP_STORED if p.suffix.lower() in ('.png','.jpg','.mp4','.exr','.blend') else ZIP_DEFLATED
            z.write(p,key,compress_type=zend)
    with ZipFile(path) as z:
        assert z.testzip() is None
        assert set(z.namelist())=={k for p,k in entries}
def main():
    contact();html()
    sources=source_map()
    ref=Refs();ref.feed((ROOT/'开始阅读.html').read_text(encoding='utf-8'))
    for u in set(ref.urls):
        assert (ROOT/unquote(urlsplit(u).path)).is_file(),u
    posts=sorted(MOBILE.glob('*.jpg'))
    assert len(posts)==9
    for p in posts:
        with Image.open(p) as im:
            im.load();assert im.size==(1440,1920) and im.info.get('icc_profile')
    public=[(p,p.name) for p in posts]+[(ROOT/'发布文案.txt','发布文案.txt')]
    zipfiles(ROOT/OUT_NAME,public)
    core=sorted(p for p in ROOT.rglob('*') if included(p) and p.name!='包内文件索引.json')
    manifest=EVID/'包内文件索引.json'
    manifest.write_text(json.dumps({'scope':'完整证据包。其中所有文件除本索引本身均列出 SHA-256，离线图库的相对链接已经验证。','verified_distinct_sourced_files':len(sources),'verified_gallery_link_targets':len(set(ref.urls)),'files':[{'file':rel(p),'bytes':p.stat().st_size,'sha256':sources[p] if p in sources else sha(p)} for p in core]},ensure_ascii=False,indent=2),encoding='utf-8')
    zipfiles(ROOT/FULL_NAME,[(p,rel(p)) for p in core+[manifest]])
    print('source hashes verified',len(sources),'gallery links',len(set(ref.urls)),'full files',len(core)+1)
    print([(name,(ROOT/name).stat().st_size) for name in (OUT_NAME,FULL_NAME)])
if __name__=='__main__':main()

