"""Validate evidence references, then create and read back the two ZIP archives."""
from collections import Counter
import csv
import hashlib
from html.parser import HTMLParser
from pathlib import Path
import json
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit
from zipfile import ZIP_STORED, ZipFile

from PIL import Image


root = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def digest(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def verify_image(path, size, icc=False):
    with Image.open(path) as image:
        image.load()
        assert image.format == "PNG" and image.size == tuple(size), path
        if icc:
            assert image.info.get("icc_profile"), path


class LocalLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        self.links.extend(value for name, value in attrs if name in {"href", "src"} and value)


def check_links(path, targets):
    count = 0
    for target in targets:
        parts = urlsplit(target)
        if parts.scheme or parts.netloc or not parts.path:
            continue
        assert (path.parent / unquote(parts.path)).exists(), (path.name, target)
        count += 1
    return count


archive = root / "历史效果图"
originals = rows(archive / "历版原图索引.csv")
assert len(originals) == len({row["SHA256"] for row in originals}) == 151
for item in originals:
    assert digest(archive / item["归档相对路径"]) == item["SHA256"], item["归档相对路径"]
sources = rows(root / "源工程与记录" / "原件清单.csv")
for item in sources:
    assert digest(root / item["归档路径"]) == item["SHA-256"], item["归档路径"]
source_digests = {item["SHA-256"] for item in sources if item["归档路径"].endswith(".blend")}

screens = rows(root / "工程界面" / "界面截图索引.csv")
assert len(screens) == 6
for item in screens:
    path = root / "工程界面" / item["截图"]
    verify_image(path, (2560, 1369))
    assert digest(path) == item["截图SHA256"], path
    assert item["原工程SHA256"] in source_digests, path

flow = sorted((root / "流程渲染").glob("*.png"))
assert len(flow) == 3
for path in flow:
    verify_image(path, (3840, 2160))

post = sorted((root / "小红书发布图").glob("*.png"))
assert len(post) == 10 and [p.name[:2] for p in post] == [f"{i:02d}" for i in range(1, 11)]
for path in post:
    verify_image(path, (1440, 1920), icc=True)
post_sources = rows(root / "小红书逐图溯源.csv")
assert set(item["发布图"] for item in post_sources) == {p.relative_to(root).as_posix() for p in post}
for item in post_sources:
    path = root / item["图源"]
    assert digest(path) == item["图源SHA256"], path
    with Image.open(path) as image:
        assert item["源像素"] == f"{image.width}×{image.height}", path
        x0, y0, x1, y1 = map(int, item["裁切xyxy"].split(","))
        assert 0 <= x0 < x1 <= image.width and 0 <= y0 < y1 <= image.height, item
    x, y, w, h = map(int, item["版面xywh"].split(","))
    assert 0 <= x < x+w <= 1440 and 0 <= y < y+h <= 1920, item

reopened = json.loads((root / "源工程与记录" / "工程打开复验.json").read_text(encoding="utf-8"))["工程"]
assert len(reopened) == 9 and all(r["场景"] and not r["缺失的外部静态图片"] for r in reopened)

verified_links = {}
for path in [root / "打开看图.html", archive / "历史原图浏览.html"]:
    parser = LocalLinks()
    parser.feed(path.read_text(encoding="utf-8"))
    verified_links[path.name] = check_links(path, parser.links)
for relative in ["制作流程与证据索引.md", "流程渲染/流程图来源.md"]:
    path = root / relative
    verified_links[path.name] = check_links(
        path, re.findall(r'\]\(([^ )]+)\)', path.read_text(encoding="utf-8"))
    )

movies = {}
for path in sorted((root / "动画原片").glob("*.mp4")):
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-map", "0:v:0", "-f", "null", "-"],
        capture_output=True, check=True,
    )
    assert not result.stderr, result.stderr
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,duration,nb_frames", "-of", "json", str(path)],
        capture_output=True, check=True,
    )
    movies[path.name] = json.loads(probe.stdout)["streams"][0]
assert len(movies) == 3

stem = "Mavic-4-Pro"
post_zip = root.parent / f"{stem}-小红书发图.zip"
full_zip = root.parent / f"{stem}-制作流程证据链.zip"
report_path = root / "交付复验.json"
report = {
    "发布图": len(post),
    "逐图溯源": len(post_sources),
    "4K补渲": len(flow),
    "截图": len(screens),
    "历史原图": dict(Counter(row["图像类别"] for row in originals)),
    "历史原工程与过程原件": len(sources),
    "工程重开": len(reopened),
    "网页和证据索引中的有效本地链接": verified_links,
    "已完整解码的动画": movies,
}
report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def packet(destination, files, base):
    temporary = destination.with_suffix(".zip.part")
    with ZipFile(temporary, "w", compression=ZIP_STORED) as file:
        for path in files:
            file.write(path, path.relative_to(base).as_posix())
    with ZipFile(temporary) as file:
        names = file.namelist()
        assert len(names) == len(set(names)) == len(files)
        assert not file.testzip(), destination
    temporary.replace(destination)
    print(f"{destination.name}\t{len(files)} entries\t{destination.stat().st_size} bytes", flush=True)


packet(post_zip, post, root / "小红书发布图")
full = sorted(p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
packet(full_zip, full, root)
print(json.dumps(report, indent=2, ensure_ascii=False))
