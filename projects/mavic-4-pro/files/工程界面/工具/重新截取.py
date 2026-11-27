"""Run a separate Blender GUI for each original project. Existing GUI sessions are untouched."""
import argparse
import os
import subprocess
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="+")
    parser.add_argument("--root", type=Path, default=Path("D:/oc"))
    parser.add_argument("--blender", type=Path)
    args = parser.parse_args()
    work = args.root
    blender = args.blender or work / "render-workbench/apps/blender-5.2.3-windows-x64/blender.exe"
    script = Path(__file__).resolve().with_name("原生界面取证.py")
    groups = [
        ("output/mavic-4-pro/review/layout.blend", ["layout"]),
        ("output/mavic-4-pro/review/first-assembly/first-assembly.blend", ["first"]),
        ("output/mavic-4-pro-fit-work/rear-shoulder/Mavic-4-Pro-Rear-Fit-Final.blend", ["clay", "mesh", "rig", "node"]),
    ]
    logs = Path(tempfile.gettempdir()) / "mavic-xhs-interface"
    logs.mkdir(exist_ok=True)
    failures = []
    for rel_path, stages in groups:
        chosen = [stage for stage in stages if not args.only or stage in args.only]
        if not chosen:
            continue
        log = logs / ("-".join(chosen) + ".log")
        print(f"Starting {chosen}, {log}", flush=True)
        command = [str(blender), "--factory-startup", "-M", "--no-window-focus", "-noaudio",
                   str(work / rel_path), "-P", str(script), "--", *chosen]
        with log.open("wb") as output:
            process = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT,
                                     timeout=210, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if process.returncode:
            failures.append((chosen, process.returncode, os.fspath(log)))
        print(f"{chosen} finished with {process.returncode}", flush=True)
    if failures:
        raise SystemExit(str(failures))


if __name__ == "__main__":
    main()
