"""Local adapters for the skill's Blender motion and section evidence."""

import csv
import json
import math
import subprocess
from collections import Counter
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def input_file(ctx, name, suffix):
    path = ctx.input_path(name)
    if path.suffix.lower() != suffix:
        raise ValueError(f"Expected a {suffix} file: {name}")
    return path


def run_blender(ctx, source, script, args, log):
    command = [str(ctx.blender), "--background", "--factory-startup", "--disable-autoexec",
               str(source), "--python-exit-code", "1", "--python", str(SCRIPTS / script),
               "--", *map(str, args)]
    with log.open("xb") as stream:
        result = subprocess.run(command, cwd=log.parent, stdin=subprocess.DEVNULL,
                                stdout=stream, stderr=subprocess.STDOUT)
    return result.returncode


def check_execution(ctx, code, log):
    if code:
        with log.open("rb") as stream:
            stream.seek(max(0, log.stat().st_size - 1800))
            tail = stream.read().decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Blender exited {code}. See {log.relative_to(ctx.workspace).as_posix()}.\n{tail}")


def failure_example(check):
    example = {"id": check["id"], "type": check["type"]}
    if check["type"] == "skin":
        example.update(modifier_enabled=check["modifier_enabled"], bad_vertices=check["bad_vertices"],
                       vertices=check["vertices"], example_vertices=[row["vertex"] for row in check["examples"][:3]])
        return example
    samples = []
    for row in check["samples"]:
        if row["pass"]:
            continue
        sample = {key: value for key, value in row.items() if key not in ("pass", "pairs_with_surface_hits")}
        if "pairs_with_surface_hits" in row:
            hits = row["pairs_with_surface_hits"]
            sample.update(pair_hits_total=len(hits), pairs_with_surface_hits=hits[:3])
        samples.append(sample)
        if len(samples) == 3:
            break
    example["samples"] = samples
    return example


def passing_example(check):
    example = {"id": check["id"], "type": check["type"]}
    if "samples" in check:
        frames = sorted(row["frame"] for row in check["samples"])
        example.update(sample_count=len(frames), sampled_frame_bounds=[frames[0], frames[-1]],
                       sampled_frames=frames[:20], frames_truncated=len(frames) > 20)
    if "pairs" in check:
        example["pair_count"] = len(check["pairs"])
    if check["type"] == "skin":
        example.update(vertices=check["vertices"], bad_vertices=check["bad_vertices"])
    return example


def audit_assembly(ctx, blend: str, manifest: str) -> dict:
    source = input_file(ctx, blend, ".blend")
    checks = input_file(ctx, manifest, ".json")
    run = ctx.new_run()
    report_path, log = run / "assembly.json", run / "blender.log"
    code = run_blender(ctx, source, "rig_audit.py", ["--manifest", checks, "--out", report_path], log)
    # The CLI deliberately exits nonzero after writing a complete report when a check fails.
    if not report_path.is_file():
        check_execution(ctx, code, log)
        raise RuntimeError("Blender returned without an assembly report")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report["pass"]:
        check_execution(ctx, code, log)
    passed = [check for check in report["checks"] if check["pass"]]
    failures = [check for check in report["checks"] if not check["pass"] and "error" not in check]
    errors = [check for check in report["checks"] if "error" in check]
    return {
        "status": "incomplete" if errors else ("failed" if failures else "passed"),
        "checks_total": len(report["checks"]),
        "passed_count": len(passed),
        "passed_check_examples": [passing_example(c) for c in passed[:12]],
        "failed_count": len(failures),
        "failed_checks": [c["id"] for c in failures[:20]],
        "failure_examples": [failure_example(c) for c in failures[:6]],
        "evaluation_error_count": len(errors),
        "evaluation_errors": [{"id": c["id"], "type": c["type"], "error": c["error"][:300]} for c in errors[:6]],
        "scene": report["scene"],
        "blend_sha256": report["blend_sha256"],
        "manifest_sha256": report["manifest_sha256"],
        "blender_version": report["blender"],
        "report": report_path.relative_to(ctx.workspace).as_posix(),
        "log": log.relative_to(ctx.workspace).as_posix(),
        "scope": "Declared checks and sampled frames only. Surface intersections test mesh faces; "
                 "containment, minimum clearance and intervening poses require separate evidence.",
    }


def section_coverage(directory):
    with (directory / "coverage.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    missing = [row["part"] for row in rows if row["present_in_scene"] == "False"]
    unsectioned = [row["part"] for row in rows if row["present_in_scene"] == "True" and int(row["nonempty_stations"]) == 0]
    return {"missing_count": len(missing), "missing_parts": missing[:20], "unsectioned_count": len(unsectioned),
            "unsectioned_parts": unsectioned[:20]}


def bevel_example(row):
    result = {k: row[k] for k in ("feature", "part", "axis", "current_fit", "reference_fit")}
    for key in ("station_mm", "current_R_mm", "reference_R_mm", "delta_R_mm"):
        result[key] = float(row[key]) if row[key] else None
    return result


def compare_sections(ctx, blend: str, parts: list[str], pose: str, reference_blend: str | None = None,
                     axes: str = "XYZ", frame: int = 1, datum: str | None = None,
                     range_mm: list[float] | None = None, bevel_windows: str | None = None,
                     mm_per_unit: float | None = None, scene: str | None = None) -> dict:
    source = input_file(ctx, blend, ".blend")
    reference = input_file(ctx, reference_blend, ".blend") if reference_blend is not None else None
    windows = input_file(ctx, bevel_windows, ".json") if bevel_windows is not None else None
    if not parts or any(not p.strip() or p.startswith("-") for p in parts) or len(set(parts)) != len(parts):
        raise ValueError("Provide distinct mesh names. Empty or dash-prefixed names are unsupported.")
    if not pose.strip():
        raise ValueError("Specify the shared assembly pose")
    axes = axes.upper()
    if not axes or set(axes) - set("XYZ") or len(set(axes)) != len(axes):
        raise ValueError("axes must contain distinct letters from XYZ")
    args = ["--parts", *parts, f"--pose={pose}", f"--axes={axes}", "--frame", frame, "--step-mm", 1]
    if range_mm is not None:
        if len(range_mm) != 2 or not all(map(math.isfinite, range_mm)) or range_mm[0] > range_mm[1]:
            raise ValueError("range_mm must contain two finite ascending coordinates")
        args.extend(["--range-mm", *range_mm])
    if mm_per_unit is not None:
        if not math.isfinite(mm_per_unit) or mm_per_unit <= 0:
            raise ValueError("mm_per_unit must be positive and finite")
        args.extend(["--mm-per-unit", mm_per_unit])
    if datum is not None:
        args.append(f"--datum={datum}")
    if scene is not None:
        args.append(f"--scene={scene}")
    if windows is not None:
        args.extend(["--fits", windows])

    run = ctx.new_run()
    reference_coverage = None
    reference_metadata = {}
    if reference is not None:
        baseline = run / "reference"
        log = run / "reference.log"
        ref_args = [*args, "--allow-absent-parts", "--out", baseline]
        check_execution(ctx, run_blender(ctx, reference, "section_audit.py", ref_args, log), log)
        reference_coverage = section_coverage(baseline)
        reference_metadata = json.loads((baseline / "manifest.json").read_text(encoding="utf-8"))
        args.extend(["--reference", baseline])
    current = run / "current"
    log = run / "current.log"
    check_execution(ctx, run_blender(ctx, source, "section_audit.py", [*args, "--out", current], log), log)
    metadata = json.loads((current / "manifest.json").read_text(encoding="utf-8"))
    counts = Counter()
    worst = None
    with (current / "sections.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            counts[row["status"]] += 1
            if row["sample_max_mm"]:
                distance = float(row["sample_max_mm"])
                if worst is None or distance > worst["sample_max_mm"]:
                    worst = {"part": row["part"], "axis": row["axis"], "station_mm": float(row["station_mm"]),
                             "sample_max_mm": distance, "overlay": (current / row["svg"]).relative_to(ctx.workspace).as_posix()}
    with (current / "radii.csv").open(encoding="utf-8-sig", newline="") as stream:
        radii = list(csv.DictReader(stream))
    mode = "model_only"
    if reference is not None:
        mode = "same_source_comparison" if metadata["blend_sha256"] == metadata["reference_sha256"] else "reference_comparison"
    return {
        "status": "needs_review",
        "mode": mode,
        "step_mm": metadata["contract"]["step_mm"],
        "probe_mm": metadata["probe_mm"],
        "blend_sha256": metadata["blend_sha256"],
        "reference_sha256": metadata["reference_sha256"],
        "scene": metadata["scene"],
        "reference_scene": reference_metadata.get("scene"),
        "mm_per_unit": metadata["mm_per_unit"],
        "reference_mm_per_unit": reference_metadata.get("mm_per_unit"),
        "station_counts": dict(counts),
        "candidate_coverage": section_coverage(current),
        "reference_coverage": reference_coverage,
        "worst_compared_station": worst,
        "bevel_windows_total": len(radii),
        "bevel_windows_measured_both": sum(row["delta_R_mm"] != "" for row in radii),
        "bevel_examples": [bevel_example(row) for row in radii[:12]],
        "artifacts": {name: (current / name).relative_to(ctx.workspace).as_posix() for name in
                      ("index.html", "sections.csv", "radii.csv", "coverage.csv", "manifest.json")},
        "scope": "1 mm station spacing. Evaluate registration, reference provenance, one-sided stations, "
                 "coverage and sampled deviations against tolerances before acceptance.",
    }
