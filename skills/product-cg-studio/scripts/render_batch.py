"""Check or render named Blender shots from a portable JSON manifest."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def integer(value, lo, hi):
    return type(value) is int and lo <= value <= hi


def select_jobs(path, selection):
    manifest = read_json(path)
    if not isinstance(manifest, dict) or set(manifest) != {"version", "jobs"}:
        raise ValueError("Manifest must contain version and jobs")
    if not integer(manifest["version"], 1, 1) or not isinstance(manifest["jobs"], list) or not manifest["jobs"]:
        raise ValueError("Expected version 1 and a non-empty jobs array")
    by_id = {}
    for job in manifest["jobs"]:
        key = job.get("id") if isinstance(job, dict) else None
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", key):
            raise ValueError(f"Invalid job id: {key!r}")
        if re.fullmatch(r"con|prn|aux|nul|com[1-9]|lpt[1-9]", key) or key in by_id:
            raise ValueError(f"Duplicate or reserved job id: {key}")
        by_id[key] = job
    unknown = set(selection or ()) - by_id.keys()
    if unknown:
        raise ValueError(f"Unknown selection: {sorted(unknown)}")
    return [job for key, job in by_id.items() if not selection or key in selection]


def prepare_job(job, manifest_dir):
    extra = set(job) - {"id", "blend", "scene", "camera", "frame", "range", "resolution"}
    if extra:
        raise ValueError(f"Unknown fields: {sorted(extra)}")
    for key in ("blend", "scene", "camera"):
        if not isinstance(job.get(key), str) or not job[key].strip():
            raise ValueError(f"Expected non-empty {key}")
    path = Path(job["blend"])
    if path.is_absolute() or PureWindowsPath(job["blend"]).anchor or path.suffix.lower() != ".blend":
        raise ValueError("blend must be a relative .blend path")
    source = (manifest_dir / path).resolve(strict=True)
    if not source.is_file():
        raise ValueError(f"Expected a file: {source}")
    if ("frame" in job) == ("range" in job):
        raise ValueError("Supply either frame or range")
    interval = job.get("range", [job.get("frame")] * 2)
    if not isinstance(interval, list) or len(interval) != 2 or not all(integer(n, 0, 1048574) for n in interval):
        raise ValueError("Frames must be integers from 0 to 1048574")
    if interval[0] > interval[1]:
        raise ValueError("range must be ordered [first, last], inclusive")
    if "resolution" in job:
        size = job["resolution"]
        if not isinstance(size, list) or len(size) != 2 or not all(integer(n, 4, 65536) for n in size):
            raise ValueError("resolution must be [width, height] in pixels, each 4 to 65536")
    return dict(job, blend=str(source))


def source_version(path, cache):
    stat = path.stat()
    stamp = (stat.st_size, stat.st_mtime_ns)
    key = (path, stamp)
    if key not in cache:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        cache[key] = digest.hexdigest()
    return stamp, cache[key]


def run_job(job, mode, blender, workspace, root, versions):
    key = job["id"]
    job_dir = root / "work" / key
    job_dir.mkdir(parents=True)
    request = job_dir / "request.json"
    prepared = prepare_job(job, workspace)
    source = Path(prepared["blend"])
    stamp, digest = source_version(source, versions)
    write_json(request, {"mode": mode, "job": prepared})
    log = root / "logs" / (key + ".log")
    command = [
        blender, "--background", "--factory-startup", "--disable-autoexec", prepared["blend"],
        "--python-exit-code", "1", "--python", str(Path(__file__).with_name("render_worker.py").resolve()),
        "--", str(request),
    ]
    with log.open("wb") as sink:
        result = subprocess.run(command, stdout=sink, stderr=subprocess.STDOUT, check=False)
    receipt = job_dir / "result.json"
    if not receipt.is_file():
        tail = ""
        with log.open("rb") as stream:
            stream.seek(max(0, log.stat().st_size - 1400))
            tail = stream.read().decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Blender exited {result.returncode} without a receipt. {tail}")
    info = read_json(receipt)
    if result.returncode or not info.get("ok"):
        raise RuntimeError(info.get("error") or f"Blender exited {result.returncode}")
    stat = source.stat()
    if (stat.st_size, stat.st_mtime_ns) != stamp:
        raise RuntimeError("Source .blend changed during this job. Retry with a frozen copy.")
    info["source_sha256"] = digest
    if mode == "render":
        (job_dir / "images").rename(root / "shots" / key)
    return info


def execute(args, jobs, blender, root):
    for subdir in ("work", "logs", "shots"):
        (root / subdir).mkdir()
    summary = {job["id"]: {"status": "pending"} for job in jobs}
    report = {"mode": args.mode, "manifest": str(args.manifest.resolve()), "jobs": summary}
    report_file = root / "report.json"
    versions = {}
    write_json(report_file, report)
    for job in jobs:
        key = job["id"]
        summary[key] = {"status": "running"}
        write_json(report_file, report)
        print(f"[{key}] {args.mode}", flush=True)
        try:
            details = run_job(job, args.mode, blender, args.manifest.resolve().parent, root, versions)
            summary[key] = {"status": "ok", **details}
            print(f"  {details['scene']} / {details['camera']} | {details['pixels']} px | {details['frames']} frame(s)", flush=True)
            for warning in details["missing_source_warnings"]:
                print(f"  Missing source: {warning}", flush=True)
        except (OSError, ValueError, RuntimeError) as exc:
            summary[key] = {"status": "failed", "error": str(exc)}
            print(f"  ERROR: {exc}", file=sys.stderr, flush=True)
        write_json(report_file, report)
    return int(any(result["status"] != "ok" for result in summary.values()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("check", "render"))
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--blender", default=os.environ.get("BLENDER_BIN", "blender"))
    parser.add_argument("--out", type=Path, help="New output directory (required for render, optional for check)")
    parser.add_argument("--only", nargs="+", metavar="ID", help="Process only these job IDs")
    args = parser.parse_args()
    if args.mode == "render" and args.out is None:
        parser.error("render requires --out NEW_DIRECTORY")
    try:
        jobs = select_jobs(args.manifest, args.only)
        blender = shutil.which(args.blender)
        if not blender:
            raise ValueError(f"Cannot find Blender executable: {args.blender}")
        if args.out is None:
            with TemporaryDirectory(prefix="product-cg-check-") as folder:
                return execute(args, jobs, blender, Path(folder))
        root = args.out.resolve()
        root.mkdir(parents=True, exist_ok=False)
        print(f"Report: {root / 'report.json'}", flush=True)
        return execute(args, jobs, blender, root)
    except KeyboardInterrupt:
        print("Interrupted. Use --only and a fresh --out to retry unfinished jobs.", file=sys.stderr)
        return 130
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
