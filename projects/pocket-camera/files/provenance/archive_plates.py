"""Index Pocket project's historical image files and copy verified presentation plates."""
import hashlib
import io
import json
from collections import Counter
from pathlib import Path
import shutil
import struct
import zipfile

from PIL import Image


archive = Path(__file__).resolve().parents[1]
output = archive.parent
workspace = output.parent
sample = workspace / "render-workbench/samples/dji-pocket-4p"
studio_mirror = workspace.parent / "dji-dualsense-4k-render-studio"
versions = [output / ("dji-osmo-pocket-4p" + (f"-v{v}" if v > 1 else "")) for v in range(1, 8)]
roots = [sample, *versions, output / "dji-osmo-pocket-4p-cg15",
         output / "product-render-evidence", output / "xhs-product-render-portfolio",
         studio_mirror / "dji-osmo-pocket-4p", studio_mirror / "xiaohongshu"]
suffixes = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".exr", ".webp", ".bmp", ".avif"}


def project_file(path, root):
    if root.name == "product-render-evidence":
        return path.name.lower().startswith("dji-")
    if root.name in {"xiaohongshu", "xhs-product-render-portfolio"}:
        return "01-dji" in str(path.relative_to(root)).lower()
    return True


def cstring(stream):
    parts = bytearray()
    while True:
        char = stream.read(1)
        if char == b"":
            raise EOFError("invalid EXR header")
        if char == b"\0":
            return parts.decode("ascii")
        parts += char


def dimensions(stream, suffix):
    if suffix == ".exr":
        if stream.read(4) != b"\x76\x2f\x31\x01":
            raise ValueError("invalid EXR magic")
        stream.read(4)
        while name := cstring(stream):
            cstring(stream)
            length, = struct.unpack("<I", stream.read(4))
            value = stream.read(length)
            if name == "displayWindow":
                x0, y0, x1, y1 = struct.unpack("<4i", value)
                return x1 - x0 + 1, y1 - y0 + 1
        raise ValueError("missing EXR displayWindow")
    with Image.open(stream) as im:
        return im.size


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def relative(path):
    return path.relative_to(workspace).as_posix() if path.is_relative_to(workspace) else path.as_posix()


rows = {}
for root in roots:
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in suffixes or not project_file(path, root):
            continue
        with path.open("rb") as stream:
            width, height = dimensions(stream, path.suffix.lower())
        rows[path] = {"source": relative(path), "root": relative(root), "size": [width, height],
                      "bytes": path.stat().st_size, "sha256": digest(path)}

index_by_hash = {}
for row in rows.values():
    index_by_hash.setdefault(row["sha256"], []).append(row["source"])

copies = {}


def save(path, where, kind, **extra):
    row = rows[path]
    destination = archive / where / path.name
    if row["sha256"] in copies:
        row["archive"] = copies[row["sha256"]]
        row["byte_duplicate"] = True
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if digest(destination) != row["sha256"]:
                raise ValueError(f"Existing file differs: {destination}")
        else:
            shutil.copy2(path, destination)
        if digest(destination) != row["sha256"]:
            raise ValueError(f"Copy mismatch: {destination}")
        row["archive"] = copies[row["sha256"]] = destination.relative_to(archive).as_posix()
    row.update(kind=kind, **extra)


native4k_dir = sample / "4k/renders"
log = (sample / "_work/dji-4k-final.log").read_text(encoding="utf-8")
scene_map = {"classic-black": ("Classic Black", "01_经典黑"), "pearl-white": ("Pearl White", "02_珍珠白"),
             "white-clay": ("White Clay", "03_白模")}
expected_shots = {"classic-black": ["01-hero", "02-rear", "03-optics", "04-controls"],
                  "pearl-white": ["01-hero", "02-rear", "03-optics", "04-controls"],
                  "white-clay": ["01-hero", "02-rear", "06-profile"]}
for prefix, shots in expected_shots.items():
    scene, subdir = scene_map[prefix]
    for shot in shots:
        path = native4k_dir / f"{prefix}-{shot}.png"
        size = rows[path]["size"]
        assert set(size) == {2160, 3840}
        assert f"RENDER {scene} {shot} {size}" in log and f"{path.name}'" in log
        with path.open("rb") as stream:
            header = stream.read(29)
        assert header[24:26] == bytes([16, 2])  # PNG IHDR: 16-bit RGB
        save(path, f"01_历史4K原图/{subdir}", "native_4k_render", scene=scene, shot=shot,
             timeline_frame=int(shot[:2]) * 10, png_encoding="16-bit RGB",
             source_blend=relative(sample / "4k/dji-osmo-pocket-4p-4k.blend"))

for number, root in enumerate(versions[:6], 1):
    if number <= 4:
        names = ["01-classic-black", "02-rear-detail", "03-dual-camera"]
        if number >= 2:
            names.append("07-grip-under")
        if number == 4:
            names.append("10-rear-gimbal-macro")
    else:
        names = ["whole-front", "whole-rear", "controls", "lens-front", "lens-lower", "lens-oblique", "base-detail"]
    for name in names:
        save(root / f"previews/{name}.png", f"02_历版效果图/V{number}", "revision_preview", version=f"V{number}")
for path in sorted((versions[-1] / "renders").glob("*.png")):
    save(path, "02_历版效果图/V7_终版", "v7_final_render", version="V7")
save(versions[-1] / "renders/01-Hero-passes.exr", "02_历版效果图/V7_终版/合成通道", "v7_multilayer_exr", version="V7")
save(versions[-1] / "renders/渲染联系表.jpg", "02_历版效果图/V7_终版/联系表", "v7_contact_sheet", version="V7")
for path in sorted((sample / "cmf/views").glob("*.png")):
    save(path, "02_历版效果图/配色分支_材质预览", "cmf_preview")
for path in sorted((sample / "_work/angles").glob("*.png")):
    save(path, "02_历版效果图/配色分支_早期白模", "clay_preview")
save(sample / "4k/dji-4k-review.jpg", "02_历版效果图/配色分支_联系表", "4k_contact_sheet")
for path in [output / "product-render-evidence/dji-01-white-clay.png",
             output / "product-render-evidence/dji-03-final-render.png"]:
    save(path, "02_历版效果图/早期留档_白模与渲染", "prior_delivery_image")

wide = []
for path, row in rows.items():
    if max(row["size"]) >= 3840 and row.get("kind") != "native_4k_render":
        if path.is_relative_to(studio_mirror) and path.parent.name == "renders":
            same = rows[native4k_dir / path.name]
            assert same["sha256"] == row["sha256"]
            reason = "byte-identical mirrored native 4K render"
            row["byte_identical_to"] = same["source"]
            row["archive"] = same["archive"]
        elif path.name == "dji-4k-review.jpg":
            reason = "render contact sheet"
        elif "browser" in path.parts:
            reason = "full-page browser capture"
        else:
            raise ValueError(f"Unclassified high-resolution image: {path}")
        wide.append(dict(source=row["source"], size=row["size"], reason=reason))

zip_members = []
for root in roots:
    for zpath in sorted(root.rglob("*.zip")):
        with zipfile.ZipFile(zpath) as bundle:
            for name in sorted(bundle.namelist()):
                item = Path(name)
                if item.suffix.lower() not in suffixes or not project_file(root / item, root):
                    continue
                data = bundle.read(name)
                sha = hashlib.sha256(data).hexdigest()
                with io.BytesIO(data) as stream:
                    size = list(dimensions(stream, item.suffix.lower()))
                if max(size) >= 3840 and sha not in index_by_hash:
                    raise ValueError(f"Unmatched 4K archived image: {zpath}::{name}")
                zip_members.append({"archive_source": relative(zpath), "member": name, "size": size,
                                    "sha256": sha, "unpacked_matches": index_by_hash.get(sha, [])})

kind_counts = Counter(row["kind"] for row in rows.values() if "kind" in row)
assert kind_counts["native_4k_render"] == 11 and kind_counts["v7_final_render"] == 8
mirror_package = []
for name in ["dji-osmo-pocket-4p-4k.blend", "dji-4k-review.jpg"]:
    source_file = sample / "4k" / name
    mirror_file = studio_mirror / "dji-osmo-pocket-4p" / name
    sha = digest(source_file)
    assert digest(mirror_file) == sha
    mirror_package.append({"source": relative(source_file), "mirror": relative(mirror_file), "sha256": sha})
report = {"workspace": str(workspace), "path_base": "source and root relative to workspace unless absolute for external package; archive relative to delivery root",
          "roots": [relative(root) for root in roots], "image_extensions": sorted(suffixes),
          "scope": "Product project directories including work files, references, QA and CG sequence. In mixed portfolios, only product-specific image paths. ZIP contents inspected separately.",
          "branch_provenance": {"cmf": {"stages": ["_work/dji-high-detail.blend", "cmf/dji-osmo-pocket-4p-cmf.blend", "4k/dji-osmo-pocket-4p-4k.blend"],
                                         "source_root": relative(sample),
                                         "source_model_attribution": "User-supplied third-party model, as stated in historical delivery README",
                                         "delivery_readme": relative(studio_mirror / "README.md"),
                                         "logs": ["_work/cmf-build.log", "_work/dji-4k-project.log", "_work/dji-4k-final.log"],
                                         "shot_script": "_work/dji-render-4k.py", "delivery_mirror_matches": mirror_package},
                                 "v1_v7": "Separate scripted reconstruction. V7 plates are a separate set at their recorded native sizes."},
          "native_4k_criteria": "Native UHD 3840x2160 or 2160x3840, a single render from the historical scene, corroborated by saved render filename and scene/shot/size in original log.",
          "counts": {"on_disk_images": len(rows), "zip_image_members": len(zip_members),
                     "zip_members_with_unpacked_identical_image": sum(bool(m["unpacked_matches"]) for m in zip_members),
                     "selected_rows": sum(kind_counts.values()), "unique_copied_images": len(copies), "by_kind": kind_counts},
          "other_long_edge_at_least_3840": wide, "files": list(rows.values()), "zip_images": zip_members}
target = archive / "provenance/archive-plates.json"
target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report["counts"], ensure_ascii=False))
