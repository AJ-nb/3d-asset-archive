import csv
import hashlib
from pathlib import Path

from PIL import Image, ImageCms, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
POST = ROOT / "小红书发布图"
PREVIEW = ROOT / "预览缩略图"
PAGE_SIZE = (1440, 1920)
PAPER = "#f2f0e9"
INK = "#202d2d"
SUB = "#536260"
RULE = "#b6bcb2"
DARK = "#172427"
LIGHT = "#f0f0e8"
SOFT = "#bbcbc6"
ACCENT = "#ba8057"
MARGIN = 84
WIDTH = PAGE_SIZE[0] - 2 * MARGIN
PROFILE = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
FONTS = Path("C:/Windows/Fonts")

HISTORY = "历史效果图"
V6 = HISTORY + "/07-V6/效果图/棚拍"
FIT = HISTORY + "/08-后肩修订定稿/效果图/后肩专题摄影"
FIT_DETAIL = HISTORY + "/08-后肩修订定稿/结构检视/后肩白模及线框"
SOURCE = "源工程与记录"
LAYOUT = SOURCE + "/01-预演"
FIRST = SOURCE + "/02-首轮装配"
FINAL = SOURCE + "/05-后肩修订"
SCREEN = "工程界面"
FLOW = "流程渲染"
RENDER = FLOW + "/03-材质灯光-4K补渲.png"

PAGES = []
TRACK = []


def font(size, kind):
    names = {"bold": "msyhbd.ttc", "normal": "msyh.ttc", "latin": "seguisb.ttf"}
    return ImageFont.truetype(FONTS / names[kind], size)


def fit_lines(draw, sentence, face, width):
    for paragraph in sentence.split("\n"):
        line = ""
        for char in paragraph:
            if line and draw.textlength(line + char, font=face) > width:
                yield line
                line = char
            else:
                line += char
        yield line


class Card:
    def __init__(self, number, slug, title, strap="", dark=False):
        self.number = number
        self.name = f"{number:02d}-{slug}.png"
        self.theme = DARK if dark else PAPER
        self.ink = LIGHT if dark else INK
        self.sub = SOFT if dark else SUB
        self.rule = "#546763" if dark else RULE
        self.image = Image.new("RGB", PAGE_SIZE, self.theme)
        self.draw = ImageDraw.Draw(self.image)
        self.text("DJI MAVIC 4 PRO  /  BLENDER", MARGIN, 67, 32, "latin", self.sub)
        self.draw.line((MARGIN, 132, PAGE_SIZE[0] - MARGIN, 132), fill=self.rule, width=2)
        self.text(title, MARGIN, 176, 95, "bold")
        if strap:
            self.text(strap, MARGIN, 304, 37, color=self.sub)
        self.draw.line((MARGIN, 1790, PAGE_SIZE[0] - MARGIN, 1790), fill=self.rule, width=2)
        self.text("产品 CG 制作记录", MARGIN, 1826, 31, color=self.sub)
        self.text(f"{number:02d} / 10", 1236, 1826, 31, "latin", self.sub)

    def text(self, value, x, y, size, kind="normal", color=None, width=None, leading=None):
        face = font(size, kind)
        lines = fit_lines(self.draw, value, face, width) if width else value.split("\n")
        for line in lines:
            self.draw.text((x, y), line, font=face, fill=color or self.ink, anchor="lt")
            y += leading or round(size * 1.47)
        return y

    def picture(self, relative, x, y, width, height, evidence, crop=None):
        path = ROOT / relative
        with Image.open(path) as loaded:
            size = loaded.size
            if loaded.info.get("icc_profile"):
                from io import BytesIO

                incoming = ImageCms.ImageCmsProfile(BytesIO(loaded.info["icc_profile"]))
                image = ImageCms.profileToProfile(loaded, incoming, PROFILE, outputMode="RGB")
            else:
                image = loaded.convert("RGB")
        if crop:
            sx, sy, ex, ey = crop
            crop_box = (round(sx * size[0]), round(sy * size[1]), round(ex * size[0]), round(ey * size[1]))
            image = image.crop(crop_box)
        else:
            crop_box = (0, 0, *size)
        image = ImageOps.contain(image, (width, height), Image.Resampling.LANCZOS)
        pos = (x + (width - image.width) // 2, y + (height - image.height) // 2)
        self.image.paste(image, pos)
        self.draw.rectangle((pos[0], pos[1], pos[0] + image.width - 1, pos[1] + image.height - 1), outline=self.rule)
        TRACK.append({
            "发布图": "小红书发布图/" + self.name,
            "图源": relative,
            "图源类别": evidence,
            "源像素": f"{size[0]}×{size[1]}",
            "裁切xyxy": ",".join(map(str, crop_box)),
            "版面xywh": ",".join(map(str, (*pos, image.width, image.height))),
            "图源SHA256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })

    def label(self, name, note, y, x=MARGIN, width=WIDTH):
        y = self.text(name, x, y, 43, "bold", width=width)
        return self.text(note, x, y + 7, 34, color=self.sub, width=width, leading=49)

    def save(self):
        self.image.save(POST / self.name, icc_profile=PROFILE.tobytes(), compress_level=5)
        preview = ImageOps.contain(self.image, (432, 576), Image.Resampling.LANCZOS)
        preview.save(PREVIEW / (Path(self.name).stem + ".jpg"), quality=88, icc_profile=PROFILE.tobytes())
        PAGES.append((self.name, preview))


def build():
    POST.mkdir(exist_ok=True)
    PREVIEW.mkdir(exist_ok=True)

    card = Card(1, "封面", "从体块到成片", "DJI Mavic 4 Pro  ·  产品建模与渲染", dark=True)
    card.picture(RENDER, MARGIN, 411, WIDTH, 717, "本次原生 4K 补渲")
    card.label("从最早的工程开始看", "预演体块 → 首轮装配 → 白模与线框 → 材质 → 折叠动作 → 成片", 1194)
    card.picture(FLOW + "/01-基础体块-补绘.png", MARGIN, 1400, 610, 345, "历史体块原几何，本次同机位补渲")
    card.picture(FLOW + "/02-白模-补绘.png", 746, 1400, 610, 345, "定稿几何，本次原生 4K 白模补渲")
    card.save()

    card = Card(2, "从预演开始", "最早的体块", "先确立机身、四条机臂和镜头构图")
    card.picture(SCREEN + "/01-预演体块.png", MARGIN, 393, WIDTH, 682, "本次重新打开历史预演工程截图")
    card.label("01  预演工程", "从现存最早的 Blender 文件补拍。此时只用简单形体确认位置和比例。", 1096)
    card.picture(LAYOUT + "/layout-sheet.jpg", MARGIN, 1310, WIDTH, 366, "历史预演联系表原件")
    card.text("历史预演联系表  /  原始画面", MARGIN, 1693, 34, color=card.sub)
    card.save()

    card = Card(3, "首轮装配", "首轮装配", "体块变成可分件编辑的模型")
    card.picture(SCREEN + "/02-首轮装配.png", MARGIN, 385, WIDTH, 683, "本次重新打开历史首轮装配工程截图")
    card.label("02  建立部件层级", "首轮已能辨认外壳、臂根、螺旋桨与云台。下方保留当时的两张原始测试帧。", 1095)
    card.picture(FIRST + "/mavic_0032.png", MARGIN, 1310, 612, 345, "历史首轮装配原始测试帧 0032")
    card.picture(FIRST + "/mavic_0119.png", 744, 1310, 612, 345, "历史首轮装配原始测试帧 0119")
    card.text("原始测试帧 0032", MARGIN, 1692, 34, color=card.sub)
    card.text("原始测试帧 0119", 744, 1692, 34, color=card.sub)
    card.save()

    card = Card(4, "同机位三阶段", "同机位三阶段", "固定相机，比较同一视角下模型和光线的变化", dark=True)
    for y, relative, name, note, evidence in [
        (408, FLOW + "/01-基础体块-补绘.png", "历史体块", "使用早期预演文件的原几何重拍。", "历史体块原几何，本次同机位补渲"),
        (865, FLOW + "/02-白模-补绘.png", "定稿白模", "统一灰材质，检查轮廓、倒角与接缝。", "定稿几何，本次原生 4K 白模补渲"),
        (1322, RENDER, "材质灯光", "恢复原材质和棚拍照明，验证高光与接触阴影。", "本次原生 4K 补渲"),
    ]:
        card.picture(relative, MARGIN, y, 747, 421, evidence)
        card.label(name, note, y + 99, x=881, width=475)
    card.save()

    card = Card(5, "白模与线框", "白模与线框", "后肩关节  /  同一角度检查表面和网格")
    card.picture(FIT_DETAIL + "/09-rear-shoulder-clay.png", MARGIN, 386, WIDTH, 607, "后肩修订定稿的历史白模原图")
    card.text("白模查看肩座、轴套与壳体的过渡", MARGIN, 1013, 40, "bold")
    card.picture(FIT_DETAIL + "/10-rear-shoulder-wire.png", MARGIN, 1095, WIDTH, 607, "后肩修订定稿的历史线框原图")
    card.text("线框查看转轴附近的网格与分件", MARGIN, 1722, 37, "bold")
    card.save()

    card = Card(6, "工程白模与后肩网格", "回到工程视口", "全机轮廓与关节局部分别核对")
    card.picture(SCREEN + "/03-正式白模.png", MARGIN, 381, WIDTH, 592, "本次重新打开修订定稿的白模工作区截图")
    card.text("正式白模  /  展开姿态", MARGIN, 990, 39, "bold")
    card.picture(SCREEN + "/04-后肩编辑网格.png", MARGIN, 1087, WIDTH, 598, "本次重新打开修订定稿的后肩编辑模式截图")
    card.text("真实编辑网格  /  后肩转轴与相邻连接件", MARGIN, 1710, 37, "bold")
    card.save()

    card = Card(7, "材质与光线", "材质与光线", "从机壳节点到相机前的玻璃和金属")
    card.picture(SCREEN + "/06-机壳材质节点.png", MARGIN, 383, WIDTH, 630, "本次重新打开修订定稿的机壳节点截图")
    card.text("机壳材质在工程中可编辑", MARGIN, 1041, 39, "bold")
    card.picture(V6 + "/03-optics.png", MARGIN, 1131, WIDTH, 538, "V6 历史原图，云台三摄特写")
    card.text("V6 棚拍原图  /  三摄云台与镜片反光", MARGIN, 1702, 37, color=card.sub)
    card.save()

    card = Card(8, "折叠机构与动画", "让机臂折起来", "把展开、过渡、收纳放在时间轴上看")
    card.picture(SCREEN + "/05-折叠机构与动作.png", MARGIN, 391, WIDTH, 662, "本次重新打开修订定稿的动作编辑界面截图")
    card.label("工程中的折叠动作", "机臂随枢轴转动。用展开、中间与收拢画面检查运动连续性。", 1090)
    card.picture(FINAL + "/折叠动画抽帧.jpg", MARGIN, 1295, WIDTH, 455, "修订版原片的历史抽帧联系表")
    card.save()

    card = Card(9, "后肩修订前后", "后肩修订前后", "同投影对照 V6 与修订后的收纳轮廓")
    card.picture(FINAL + "/后肩修订对照.jpg", MARGIN, 414, WIDTH, 1137, "历史后肩修订对照图，含两版同投影视图")
    card.label("从折叠终点往回查", "把最终收纳轮廓的差异，追回到后肩轴线与后臂位置。", 1601)
    card.save()

    card = Card(10, "最终效果", "展开与收纳", "后肩修订定稿  /  两种姿态的历史原图", dark=True)
    card.picture(FIT + "/01-open.png", MARGIN, 387, WIDTH, 608, "后肩修订定稿的历史展开效果图")
    card.text("展开", MARGIN, 1013, 38, "bold")
    card.picture(FIT + "/02-fold.png", MARGIN, 1087, WIDTH, 609, "后肩修订定稿的历史收纳效果图")
    card.text("收纳", MARGIN, 1711, 38, "bold")
    card.save()

    with (ROOT / "小红书逐图溯源.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(TRACK[0]))
        writer.writeheader()
        writer.writerows(TRACK)

    contact = Image.new("RGB", (1410, 777), "#c9cdc5")
    for i, (_, preview) in enumerate(PAGES):
        thumb = ImageOps.contain(preview, (254, 339), Image.Resampling.LANCZOS)
        contact.paste(thumb, (39 + (i % 5) * 274, 38 + (i // 5) * 363))
    contact.save(ROOT / "小红书图组总览.jpg", quality=91, icc_profile=PROFILE.tobytes())


if __name__ == "__main__":
    build()
