"""Copy the project records selected for the Mavic evidence archive, byte for byte."""
from pathlib import Path
import csv
import hashlib
import shutil

PACKAGE = Path(__file__).resolve().parents[1]
OUTPUT = PACKAGE.parent
SOURCE = PACKAGE / "源工程与记录"
V1 = "mavic-4-pro"
FIT = "mavic-4-pro-fit-work"
V6 = "mavic-4-pro-v6"

files = [
    (V1, "review/layout.blend", "01-预演/layout.blend"),
    (V1, "review/layout-sheet.jpg", "01-预演/layout-sheet.jpg"),
    (V1, "review/layout-render.log", "01-预演/layout-render.log"),
    (V1, "review/proxy-shots.jpg", "01-预演/proxy-shots.jpg"),
    (V1, "src/film.py", "01-预演/film.py"),
    (V1, "review/first-assembly/first-assembly.blend", "02-首轮装配/first-assembly.blend"),
    (V1, "review/first-assembly/mavic_0032.png", "02-首轮装配/mavic_0032.png"),
    (V1, "review/first-assembly/mavic_0119.png", "02-首轮装配/mavic_0119.png"),
    (V1, "review/first-assembly/mavic_0279.png", "02-首轮装配/mavic_0279.png"),
    (V1, "review/before-after.jpg", "02-首轮装配/before-after.jpg"),
    (V1, "制作记录.md", "03-V1交付/制作记录.md"),
    (V1, "研究与复盘.md", "03-V1交付/研究与复盘.md"),
    (V1, "review/audit.json", "03-V1交付/audit.json"),
    (V1, "review/media-qa.json", "03-V1交付/media-qa.json"),
    (V1, "DJI-Mavic-4-Pro.blend", "03-V1交付/DJI-Mavic-4-Pro.blend"),
    ("mavic-4-pro-v2", "DJI-Mavic-4-Pro-V2.blend", "04-历版/DJI-Mavic-4-Pro-V2.blend"),
    ("mavic-4-pro-v3", "DJI-Mavic-4-Pro-V3.blend", "04-历版/DJI-Mavic-4-Pro-V3.blend"),
    ("mavic-4-pro-v4", "DJI-Mavic-4-Pro-V4.blend", "04-历版/DJI-Mavic-4-Pro-V4.blend"),
    ("mavic-4-pro-v5", "DJI-Mavic-4-Pro-V5.blend", "04-历版/DJI-Mavic-4-Pro-V5.blend"),
    (V6, "DJI-Mavic-4-Pro-V6.blend", "04-历版/DJI-Mavic-4-Pro-V6.blend"),
    (V6, "结构复验.md", "04-历版/V6-结构复验.md"),
    (FIT, "rear-shoulder/Mavic-4-Pro-Rear-Fit-Final.blend", "05-后肩修订/Mavic-4-Pro-Rear-Fit-Final.blend"),
    (FIT, "rear-shoulder/后肩装配复验.md", "05-后肩修订/后肩装配复验.md"),
    (FIT, "reference/公开图约束后肩.md", "05-后肩修订/公开图约束后肩.md"),
    (FIT, "reference/后臂铰接实物依据.md", "05-后肩修订/后臂铰接实物依据.md"),
    (FIT, "review/delivery-surface-summary.json", "05-后肩修订/delivery-surface-summary.json"),
    (FIT, "review/delivery-full-sweep.json", "05-后肩修订/delivery-full-sweep.json"),
    (FIT, "review/成片回读.json", "05-后肩修订/成片回读.json"),
    (FIT, "sections/截面读数.md", "05-后肩修订/截面读数.md"),
    (FIT, "sections/三轴1mm截面对照.html", "05-后肩修订/三轴1mm截面对照.html"),
    (FIT, "后肩修订对照.jpg", "05-后肩修订/后肩修订对照.jpg"),
    (FIT, "review/折叠动画抽帧.jpg", "05-后肩修订/折叠动画抽帧.jpg"),
    (FIT, "AGENTS.md", "05-后肩修订/复验规则.md"),
]
clips = [
    (V1, "Mavic-4-Pro-Studio.mp4", "01-V1展开展示.mp4"),
    (V6, "产品展示短片.mp4", "02-V6产品短片.mp4"),
    (FIT, "后臂收纳.mp4", "03-修订版折叠.mp4"),
]

def digest(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()

rows = []
for folder, records in ((SOURCE, files), (PACKAGE/"动画原片", clips)):
    for version, original, name in records:
        source = OUTPUT / version / original
        dest = folder / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        checksum = digest(source)
        assert digest(dest) == checksum
        rows.append([dest.relative_to(PACKAGE).as_posix(), version+"/"+original,
                     source.stat().st_size, checksum])

with (SOURCE / "原件清单.csv").open("w",encoding="utf-8-sig",newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["归档路径","原项目路径（相对 output）","字节","SHA-256"])
    writer.writerows(rows)
