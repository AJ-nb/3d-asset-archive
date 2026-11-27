"""Composite the camera-visible geometric edge pass at native 4K and verify the three PNGs."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zlib

import numpy as np
from PIL import Image, ImageDraw

archive = Path(__file__).resolve().parent.parent
dest = archive / "05_同机位补拍/V7终版对照"
temp = Path(sys.argv[1])
width, height = 2160, 3840


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def original_chunks(path):
    data = path.read_bytes()
    offset = 8
    while offset < len(data):
        n, = struct.unpack(">I", data[offset:offset+4])
        yield data[offset+4:offset+8], data[offset+8:offset+8+n]
        offset += 12 + n


def chunk(tag, data):
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))


scene = json.loads((temp / "render-meta.json").read_text(encoding="utf-8"))
geom = json.loads((temp / "visible-meta.json").read_text(encoding="utf-8"))
with np.load(temp / "visible.npz") as data:
    smooth = data["smooth"]
    sharp = data["sharp"]

scale = 3
layer = Image.new("L", (width*scale, height*scale))
draw = ImageDraw.Draw(layer)
for lines, stroke, opacity in [(smooth, 5, 154), (sharp, 8, 196)]:
    for coords in np.rint(lines * scale).astype(np.int32).tolist():
        draw.line(coords, fill=opacity, width=stroke)
layer = layer.resize((width, height), Image.Resampling.LANCZOS)
mask = np.array(layer)
clay = dest / "01_整机白模.png"
wire = dest / "02_整机线框.png"
ffmpeg = shutil.which("ffmpeg")
details = subprocess.run([ffmpeg, "-v", "error", "-i", str(clay), "-frames:v", "1", "-f", "rawvideo",
                          "-pix_fmt", "rgb48le", "-"], check=True, capture_output=True)
base = np.frombuffer(details.stdout, "<u2").reshape(height, width, 3)
ink = np.array([30, 44, 54], dtype=np.uint32) * 257
out = np.empty(base.shape, dtype=">u2")
for idx in range(height):
    alpha = mask[idx, :, None].astype(np.uint32)
    out[idx] = (base[idx].astype(np.uint32) * (255-alpha) + ink * alpha + 127) // 255

# Preserve the color and physical-resolution metadata carried by the Blender clay PNG.
metadata_keys = {b"iCCP", b"sRGB", b"gAMA", b"cHRM", b"cICP", b"pHYs"}
metadata = [(tag, content) for tag, content in original_chunks(clay) if tag in metadata_keys]
with wire.open("wb") as stream:
    stream.write(b"\x89PNG\r\n\x1a\n")
    stream.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 16, 2, 0, 0, 0)))
    for tag, content in metadata:
        stream.write(chunk(tag, content))
    zipper = zlib.compressobj(5)
    buf = bytearray()
    for row in out.view("uint8").reshape(height, -1):
        filtered = row.copy()
        filtered[6:] -= row[:-6]
        buf.extend(zipper.compress(b"\1" + filtered.tobytes()))
        if len(buf) > 1024*1024:
            stream.write(chunk(b"IDAT", bytes(buf)))
            buf.clear()
    buf.extend(zipper.flush())
    stream.write(chunk(b"IDAT", bytes(buf)))
    stream.write(chunk(b"IEND", b""))

scene["plates"].append({"file": str(wire.relative_to(archive)), "sha256": sha(wire), "bytes": wire.stat().st_size,
                        "finished_utc": datetime.now(timezone.utc).isoformat(),
                        "method": "Original evaluated mesh polygon edges, including modifier output and excluding tessellation-only diagonals. Depth-tested from the hero perspective camera. Antialiased technical-line pass composited over the native Cycles clay at original resolution.",
                        "edge_pass": geom, "line_widths_px": [5/3, 8/3], "ink_srgb8": [30, 44, 54],
                        "line_strengths_0_255": [154, 196], "antialiasing_scale": scale,
                        "nonzero_mask_pixel_count": int(np.count_nonzero(mask)), "mask_bbox_xyxy": layer.getbbox(),
                        "geometry_segments_sha256": sha(temp / "visible.npz")})
scene["plates"].sort(key=lambda item: item["file"])
scene["source_sha256_after_render"] = sha(Path(scene["source_file"]))
assert scene["source_sha256_after_render"] == scene["source_sha256"]
for plate in scene["plates"]:
    path = archive / plate["file"]
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        image.load()
        assert image.size == (width, height)
    with path.open("rb") as stream:
        header = stream.read(29)
    assert header[24:26] == bytes([16,2]) and plate["sha256"] == sha(path)
scene["verification"] = {"all_png_crc_full_decode": True, "all_native_2160x3840_rgb16": True,
                         "source_hash_unchanged": True,
                         "composition": "Identical frame, lens, camera transform, sensor-fit, pose and resolution. The same clay pixels underlie the wire pass.",
                         "original_4k_archive": False}
proj = np.array(geom["camera_world_to_clip"])
max_delta = 0.0
for z, expected in scene["projected_test_points_pixels"].items():
    clip = proj @ [0., 0., float(z), 1.]
    xy = [(clip[0]/clip[3] + 1)*width/2, (1-clip[1]/clip[3])*height/2]
    max_delta = max(max_delta, float(np.max(np.abs(np.array(xy)-expected))))
assert max_delta < .005
scene["verification"]["max_camera_anchor_disagreement_px"] = round(max_delta, 6)
old = Path(scene["source_file"]).parent / "renders/01-Hero.png"
with Image.open(old) as im:
    assert im.size == (1680, 2048)
    reference = np.asarray(im.crop((264, 0, 1416, 2048)).resize((288,512), Image.Resampling.LANCZOS), dtype="float32")
with Image.open(dest / "03_整机成品.png") as im:
    current = np.asarray(im.resize((288,512), Image.Resampling.LANCZOS), dtype="float32")
errors = np.abs(reference-current)
scene["verification"]["historical_hero_reprojection"] = {
    "historical_source": str(old), "historical_sha256": sha(old), "historical_center_crop_xyxy": [264,0,1416,2048],
    "comparison_size": [288,512], "mean_abs_difference_u8": round(float(np.mean(errors)),4),
    "p95_abs_difference_u8": float(np.quantile(errors,.95)),
    "pearson_rgb": round(float(np.corrcoef(reference.ravel(),current.ravel())[0,1]),8)}
report = archive / "provenance/v7-reshoot.json"
report.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")

preview = Image.new("RGB", (3*360, 640))
for i, item in enumerate(scene["plates"]):
    with Image.open(archive / item["file"]) as image:
        preview.paste(image.resize((360, 640), Image.Resampling.LANCZOS), (i*360,0))
preview.save(temp / "triptych.jpg", quality=94)
with Image.open(wire) as im:
    im.crop((610,420,1570,1220)).save(temp / "wire-head.png")
print("Native 4K triptych verified and manifest written.")
