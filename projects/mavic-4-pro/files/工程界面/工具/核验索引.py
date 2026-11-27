"""Fully decode each original screenshot, verify its source hash and refresh the CSV."""
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for data in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def main():
    tools_dir = Path(__file__).resolve().parent
    image_dir = tools_dir.parent
    records = sorted((json.loads(path.read_text("utf-8")) for path in (tools_dir / "记录").glob("*.json")),
                     key=lambda record: record["file"])
    assert len(records) == 6 and {r["file"] for r in records} == {p.name for p in image_dir.glob("*.png")}
    rows = []
    for record in records:
        path = image_dir / record["file"]
        source = Path(record["source"])
        with Image.open(path) as picture:
            picture.load()
            assert picture.format == "PNG" and list(picture.size) == record["screen_px"]
        assert sha256(path) == record["sha256"]
        assert sha256(source) == record["source_sha256"]
        rows.append([path.name, record["description"], *record["screen_px"], record["blender"], record["scene"],
                     record["frame"], record["mode"], record["active"], record["captured_utc"], source,
                     datetime.fromtimestamp(source.stat().st_mtime, timezone.utc).isoformat(),
                     record["source_sha256"], record["sha256"], record["method"]])
    dest = image_dir / "界面截图索引.csv"
    with dest.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["截图", "画面内容", "原始宽px", "原始高px", "Blender版本", "场景", "帧", "模式", "活动对象",
                         "截图时间UTC", "原工程路径", "原工程文件修改时间UTC", "原工程SHA256", "截图SHA256", "取证方式"])
        writer.writerows(rows)
    print(f"{len(rows)} PNG files and their source .blend hashes verified.")


if __name__ == "__main__":
    main()
