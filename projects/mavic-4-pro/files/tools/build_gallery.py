"""Build the archive's offline, relative-link index."""
from html import escape
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageOps


root = Path(__file__).resolve().parents[1]
summaries = (
    "看最终渲染，再回到最早的工程。",
    "最早的体块文件和当时的预演分镜。",
    "早期 Blender 工程与原始试拍帧。",
    "三张 4K 图由同一矩阵的相机拍摄。",
    "同一角度对照后肩白模与线框。",
    "重开终版工程，核对整机和左后肩网格。",
    "机壳节点与 V6 三摄云台特写。",
    "折叠关键帧和原片动作联系表。",
    "用同投影检查后肩修订前后的收纳轮廓。",
    "后肩修订工程的展开与收纳原图。",
)


def link(path, label, style=""):
    assert (root / path).exists(), path
    return f'<a class="{style}" href="{quote(path)}">{escape(label)}</a>'


head = """<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DJI Mavic 4 Pro｜产品 CG 制作记录</title>
<style>
:root{color-scheme:light;--page:#f2f0e9;--ink:#202d2d;--sub:#52615f;--line:#b6bcb2}
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);font:16px/1.55 "Microsoft YaHei","PingFang SC",system-ui,sans-serif}
header,main,footer{width:min(1260px,100% - 40px);margin:auto}
header{padding:48px 0 36px;border-bottom:1px solid var(--line)}.eyebrow{color:var(--sub);letter-spacing:.12em;font-size:.83rem}
h1,h2,p,figure{margin:0}h1{font-size:clamp(2.2rem,7vw,4.6rem);letter-spacing:-.04em;margin:.1em 0}
h2{font-size:clamp(1.45rem,4vw,2.1rem);line-height:1.2;margin-bottom:10px}
section{padding:32px 0;border-bottom:1px solid var(--line)}p{color:var(--sub);max-width:65ch}
.links{display:flex;gap:9px 17px;flex-wrap:wrap;margin-top:17px}
a{color:#244a43;text-underline-offset:.24em}a:hover{color:#7b4e35}a:focus-visible{outline:3px solid #9a6142;outline-offset:4px}
.primary{background:var(--ink);color:#fff;padding:6px 12px;text-decoration:none}
.primary:hover{color:#fff;background:#42534f}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,214px),1fr));gap:22px 16px;margin-top:21px}
.grid a{display:block}.grid img{width:100%;height:auto;display:block;border:1px solid var(--line);background:#e2e2da;object-fit:contain}
.grid h3{font-size:1rem;margin:8px 0 4px;font-weight:700}.grid p{font-size:.88rem}
.wide{grid-template-columns:repeat(auto-fit,minmax(min(100%,306px),1fr))}
.actions a{display:inline-block;padding:3px 0}footer{padding:24px 0 42px;font-size:.9rem;color:var(--sub)}
</style>
<header><span class="eyebrow">DJI MAVIC 4 PRO  /  BLENDER</span><h1>从体块到成片</h1>
<p>最早的预演工程、历版原件、重新打开工程拍摄的界面，以及三张同机位重渲的原生 4K 流程图。</p>
<nav class="links" aria-label="快速入口">"""
parts = [
    head,
    '<a class="primary" href="#post">10 张发布图</a>',
    link("历史效果图/历史原图浏览.html", "历版原图筛选"),
    link("制作流程与证据索引.md", "制作记录与证据"),
    link("小红书发布文案.md", "复制发帖文案"),
    '</nav></header><main><section id="post"><h2>小红书发布顺序</h2>'
    '<p>点击缩略图查看对应 1440 × 1920 PNG。按编号顺序上传即可。</p><div class="grid">',
]

cards = sorted((root / "小红书发布图").glob("*.png"))
assert len(cards) == len(summaries)
for card, description in zip(cards, summaries):
    thumb = root / "预览缩略图" / (card.stem + ".jpg")
    title = card.stem.replace("-", "  ", 1)
    parts.append(
        f'<figure><a href="{quote(card.relative_to(root).as_posix())}"><img '
        f'src="{quote(thumb.relative_to(root).as_posix())}" width="432" height="576" '
        f'alt="{escape(title)}" loading="lazy"></a>'
        f'<figcaption><h3>{escape(title)}</h3><p>{escape(description)}</p></figcaption></figure>'
    )
parts.append('</div></section><section id="flow"><h2>原生 4K 流程图</h2>'
             '<p>从真实的 Blender 工程重新渲染，三张均为 3840 × 2160。白模和正式图共享几何、灯光与相机。</p><div class="grid wide">')
for stage in sorted((root / "流程渲染").glob("*.png")):
    with Image.open(stage) as full:
        thumb = ImageOps.contain(full.convert("RGB"), (720, 405), Image.Resampling.LANCZOS)
        path = root / "预览缩略图" / (stage.stem + ".jpg")
        thumb.save(path, quality=90)
    parts.append(
        f'<figure><a href="{quote(stage.relative_to(root).as_posix())}"><img '
        f'src="{quote(path.relative_to(root).as_posix())}" width="720" height="405" '
        f'alt="{escape(stage.stem)}" loading="lazy"></a><figcaption><h3>{escape(stage.stem)}</h3></figcaption></figure>'
    )
parts.append('</div><div class="links">' + link("流程渲染/流程图来源.md", "补渲出处和相机数据") + '</div></section>')
parts.append('<section><h2>工程界面与原件</h2><p>原始截图为整窗 2560 × 1369，可放大查看右侧层级与下方编辑面板。</p><div class="grid wide">')
for capture in sorted((root / "工程界面").glob("*.png")):
    with Image.open(capture) as full:
        thumb = ImageOps.contain(full.convert("RGB"), (684, 366), Image.Resampling.LANCZOS)
        path = root / "预览缩略图" / (capture.stem + "-界面.jpg")
        thumb.save(path, quality=90)
    parts.append(
        f'<figure><a href="{quote(capture.relative_to(root).as_posix())}"><img '
        f'src="{quote(path.relative_to(root).as_posix())}" width="{thumb.width}" height="{thumb.height}" '
        f'alt="{escape(capture.stem)}" loading="lazy"></a><figcaption><h3>{escape(capture.stem)}</h3></figcaption></figure>'
    )
parts.append('</div><div class="links">')
for path, text in [
    ("工程界面/界面截图索引.csv", "六张截图的出处"),
    ("源工程与记录/01-预演/layout.blend", "最早的预演工程"),
    ("源工程与记录/02-首轮装配/first-assembly.blend", "首轮装配工程"),
    ("源工程与记录/05-后肩修订/Mavic-4-Pro-Rear-Fit-Final.blend", "修订定稿工程"),
    ("源工程与记录/05-后肩修订/三轴1mm截面对照.html", "后肩截面对照"),
    ("小红书逐图溯源.csv", "发布图的逐图溯源"),
]:
    parts.append(link(path, text))
parts.append('</div></section><section><h2>历版效果图与动画</h2>'
             '<p>档案包含 151 份历史原件。其中旧原创效果图最高为 3000 × 1900。'
             '原片和原图均保留历史像素及编码。</p><div class="links actions">')
for path, text in [
    ("历史效果图/历史原图浏览.html", "浏览 151 份历史原件"),
    ("历史效果图/4K核查.csv", "历史 4K 核查"),
    ("动画原片/01-V1展开展示.mp4", "播放 V1 展开展示"),
    ("动画原片/02-V6产品短片.mp4", "播放 V6 产品短片"),
    ("动画原片/03-修订版折叠.mp4", "播放修订版折叠"),
]:
    parts.append(link(path, text))
parts.append('</div></section></main><footer>基于公开资料重建的独立 CG 项目。实际制造尺寸与装配公差未实测。</footer></html>')
(root / "打开看图.html").write_text("\n".join(parts), encoding="utf-8")
