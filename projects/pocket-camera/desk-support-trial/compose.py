"""Build phone.png and directions.png from a completed render_batch.py run."""

import argparse
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


BACKGROUND = "#F6F4EE"
INK = "#182C2A"
SUBTLE = "#41534D"
GREEN = "#286254"
RULE = "#BFCBC1"
RESAMPLE = Image.Resampling.LANCZOS


def chinese_font(path, bold):
    if path:
        return ImageFont.truetype(str(path.resolve(strict=True)), 16)
    weight = "Bold" if bold else "Regular"
    candidates = [
        ("msyhbd.ttc" if bold else "msyh.ttc", 0),
        (f"NotoSansCJKsc-{weight}.otf", 0),
        (f"NotoSansCJK-{weight}.ttc", 2),  # Simplified Chinese face
        ("STHeiti Medium.ttc" if bold else "STHeiti Light.ttc", 0),
    ]
    for filename, index in candidates:
        try:
            return ImageFont.truetype(filename, 16, index=index)
        except OSError:
            continue
    # PingFang combines several regional families and weights in one collection.
    try:
        index = 0
        while True:
            face = ImageFont.truetype("PingFang.ttc", 16, index=index)
            family, style = face.getname()
            if family == "PingFang SC" and style.lower() == ("semibold" if bold else "regular"):
                return face
            index += 1
    except OSError:
        raise ValueError("Supply a Simplified Chinese font with --font and optionally --bold-font.") from None


def make_text(regular, bold):
    faces = {
        "regular": chinese_font(regular, False),
        "bold": chinese_font(bold or regular, True),
    }

    @lru_cache(maxsize=None)
    def font(size, face):
        return faces[face].font_variant(size=size)

    def draw_text(draw, xy, label, size, color=INK, face="regular"):
        draw.text(xy, label, fill=color, font=font(size, face), anchor="lt")

    return draw_text


def read_shot(shots, name):
    with Image.open(shots / name / "still.png") as image:
        return image.convert("RGB")


def phone_plate(shots, text):
    plate = Image.new("RGB", (1080, 1920), BACKGROUND)
    draw = ImageDraw.Draw(plate)
    text(draw, (54, 30), "桌面机位  /  可拆平底托", 28, GREEN, "bold")
    text(draw, (49, 78), "坐着讲课，看着镜头", 66, INK, "bold")
    text(draw, (54, 165), "镜头与预览屏一起朝向讲者。", 32, SUBTLE)
    hero = ImageOps.fit(read_shot(shots, "a"), (1080, 925), method=RESAMPLE, centering=(0.5, 0.56))
    plate.paste(hero, (0, 226))

    draw.rectangle((0, 1151, 1080, 1222), fill=GREEN)
    text(draw, (52, 1167), "供电线从底座右侧，接入笔记本侧面", 38, "#FFFFFF", "bold")
    routing = ImageOps.fit(read_shot(shots, "routing"), (1080, 389), method=RESAMPLE, centering=(0.5, 0.61))
    plate.paste(routing, (0, 1222))

    text(draw, (48, 1631), "讲者坐在哪里", 34, INK, "bold")
    text(draw, (574, 1631), "拔线后，机身可提离", 34, INK, "bold")
    draw.line([(540, 1635), (540, 1894)], fill=RULE, width=2)
    # Overhead diagram in the presenter's own left/right orientation.
    draw.rounded_rectangle((48, 1693, 492, 1790), radius=14, outline="#92A395", width=3)
    draw.rounded_rectangle((109, 1710, 175, 1769), radius=10, fill=GREEN)
    draw.rounded_rectangle((119, 1747, 165, 1756), radius=2, fill="#D5E2D8")
    draw.line([(175, 1737), (220, 1737), (240, 1727), (283, 1727)], fill="#AA5729", width=7)
    draw.rounded_rectangle((282, 1705, 427, 1766), radius=5, fill="#CBD2C7", outline=SUBTLE, width=3)
    text(draw, (323, 1723), "电脑", 22, SUBTLE)
    draw.line([(142, 1773), (142, 1815)], fill=GREEN, width=5)
    draw.polygon([(142, 1815), (133.75, 1800), (150.25, 1800)], fill=GREEN)
    draw.ellipse((121, 1819, 163, 1861), fill="#A9B9AE")
    draw.arc((105, 1848, 180, 1883), 180, 360, fill=GREEN, width=6)
    text(draw, (205, 1833), "讲者坐席 · 俯视", 27, SUBTLE, "bold")

    crop = read_shot(shots, "lift").crop((76, 0, 593, 475))
    plate.paste(ImageOps.fit(crop, (209, 188), method=RESAMPLE), (574, 1696))
    text(draw, (800, 1720), "小托座留桌，", 29, SUBTLE)
    text(draw, (800, 1773), "收起时与机身", 29, SUBTLE)
    text(draw, (800, 1826), "并排装袋。", 29, SUBTLE)
    return plate


def comparison_plate(shots, text):
    plate = Image.new("RGB", (1600, 1280), BACKGROUND)
    draw = ImageDraw.Draw(plate)
    text(draw, (48, 32), "同一张桌上的两种支撑", 56, INK, "bold")
    text(draw, (50, 109), "同一机身、俯仰、直头线与观察机位。", 28, SUBTLE)
    rows = [
        ("a", "A   可拆平底托", "取下即收，底面尺寸固定。", "lift", "机身提离"),
        ("b", "B   扇形收脚托", "三支脚可旋入一侧，增加枢轴与装配件。", "bundle", "支脚绕同轴收拢"),
    ]
    for index, (hero, title, description, packed, caption) in enumerate(rows):
        x = 40 + index * 785
        plate.paste(read_shot(shots, hero).resize((738, 723), RESAMPLE), (x, 174))
        text(draw, (x + 5, 922), title, 42, INK, "bold")
        text(draw, (x + 5, 986), description, 28, SUBTLE)
        crop = read_shot(shots, packed).crop((105, 77, 580, 433))
        plate.paste(ImageOps.fit(crop, (290, 186), method=RESAMPLE), (x + 5, 1050))
        text(draw, (x + 320, 1083), "收纳前状态", 30, GREEN, "bold")
        text(draw, (x + 320, 1140), caption, 27, SUBTLE)
    return plate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="Output directory of the render_batch.py render command")
    parser.add_argument("--out", type=Path, help="Write both plates here (default: the run directory)")
    parser.add_argument("--font", type=Path, help="Custom Simplified Chinese TTF, OTF or TTC font")
    parser.add_argument("--bold-font", type=Path, help="Custom bold font (defaults to --font if supplied)")
    args = parser.parse_args()
    destination = args.out or args.run
    try:
        text = make_text(args.font, args.bold_font)
        shots = args.run / "shots"
        phone = phone_plate(shots, text)
        comparison = comparison_plate(shots, text)
        destination.mkdir(parents=True, exist_ok=True)
        phone.save(destination / "phone.png")
        comparison.save(destination / "directions.png")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{parser.prog}: {exc}\n")


if __name__ == "__main__":
    main()
