"""Persistent, workspace-scoped jobs for the product CG render batch runner."""

import argparse
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import errno
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import render_batch as batch


def checked_jobs(workspace, manifest, jobs):
    """Constrain manifest inputs, retaining missing dependencies for Blender's receipt."""
    for job in jobs:
        files = job.get("required_files", [])
        if not isinstance(files, list):
            raise ValueError("required_files must be an array")
        for name in [job.get("blend"), *files]:
            if not isinstance(name, str) or not name.strip() or Path(name).is_absolute() or PureWindowsPath(name).anchor:
                raise ValueError("Manifest inputs must be relative file paths")
            if not (manifest.parent / name).resolve().is_relative_to(workspace):
                raise ValueError(f"Manifest input leaves the configured workspace: {name}")


def acquire(stream, *, wait):
    """Hold one OS-backed lock for the life of the worker. Closing the file releases it."""
    stream.seek(0)
    while True:
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError as exc:
            if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise
            if not wait:
                return False
            time.sleep(0.01)


@contextmanager
def progress_lock(folder):
    # On Windows even a short read can deny replacement of an open JSON file.
    with (folder / "progress.lock").open("r+b") as lock:
        acquire(lock, wait=True)
        yield


def batch_status(entries):
    statuses = {entry.get("status") for entry in entries.values()}
    if statuses == {"ok"}:
        return "completed"
    if statuses <= {"ok", "needs_review"} and "needs_review" in statuses:
        return "needs_review"
    return "failed"


def work(folder, workspace, blender):
    state_file = folder / "state.json"

    def checkpoint(path, data):
        with progress_lock(folder):
            batch.write_json(path, data)

    with (folder / "lease.lock").open("r+b") as lease:
        acquire(lease, wait=True)
        state = batch.read_json(state_file)
        if state["status"] != "queued":
            return
        state["status"] = "running"
        checkpoint(state_file, state)
        try:
            request = batch.read_json(folder / "request.json")
            manifest = (workspace / request["manifest"]).resolve()
            if not manifest.is_relative_to(workspace):
                raise ValueError("Manifest leaves the configured workspace")
            jobs = request["jobs"]
            checked_jobs(workspace, manifest, jobs)
            output = folder / "batch"
            output.mkdir()
            args = SimpleNamespace(manifest=manifest, mode=state["mode"])
            batch.execute(args, jobs, blender, output, write_report=checkpoint)
            state["status"] = batch_status(batch.read_json(output / "report.json")["jobs"])
        except Exception as exc:
            state.update(status="failed", error=str(exc))
        checkpoint(state_file, state)


def worker_online(ctx):
    path = ctx.output_dir("worker.lock")
    if not path.is_file():
        return False
    with path.open("r+b") as lock:
        return not acquire(lock, wait=False)


def serve(ctx):
    ready = ctx.output_dir("queue")
    ready.mkdir(exist_ok=True)
    with ctx.output_dir("worker.lock").open("a+b") as lock:
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        deadline = time.monotonic() + 0.25
        while not acquire(lock, wait=False):
            if time.monotonic() >= deadline:
                raise ValueError("Another render worker already serves this workspace")
            time.sleep(0.01)
        print(f"Watching {ready}; press Ctrl+C to stop.", flush=True)
        while True:
            for marker in sorted(ready.glob("*.ready"), key=lambda path: path.stat().st_mtime_ns):
                if not re.fullmatch(r"[0-9a-f]{32}", marker.stem):
                    continue
                folder = ctx.output_dir("jobs", marker.stem)
                with progress_lock(folder):
                    state = batch.read_json(folder / "state.json")
                if state["dispatch"] == "external" and state["mode"] == "render" and state["status"] == "queued":
                    with (folder / "worker.log").open("a", encoding="utf-8") as log:
                        with redirect_stdout(log), redirect_stderr(log):
                            work(folder, ctx.workspace, ctx.blender)
                marker.unlink(missing_ok=True)
            time.sleep(0.5)


def start(ctx, manifest, shot_ids, *, mode):
    path = ctx.input_path(manifest)
    if path.suffix.lower() != ".json":
        raise ValueError("Expected a render manifest with the .json extension")
    if shot_ids is not None and (
        not isinstance(shot_ids, list) or not shot_ids or not all(isinstance(item, str) for item in shot_ids)
        or len(set(shot_ids)) != len(shot_ids)
    ):
        raise ValueError("Supply a non-empty list of distinct shot IDs, or omit shot_ids for all")
    jobs = batch.select_jobs(path, shot_ids)
    checked_jobs(ctx.workspace, path, jobs)
    job_id = uuid.uuid4().hex
    folder = ctx.output_dir("jobs", job_id)
    folder.mkdir(parents=True, exist_ok=False)
    external = mode == "render" and ctx.external_render_worker
    state = {
        "job_id": job_id, "mode": mode, "status": "queued", "created_at": time.time(),
        "dispatch": "external" if external else "local",
        "shot_ids": [job["id"] for job in jobs],
    }
    batch.write_json(folder / "request.json", {"manifest": path.relative_to(ctx.workspace).as_posix(), "jobs": jobs})
    (folder / "progress.lock").write_bytes(b"0")
    (folder / "lease.lock").write_bytes(b"0")
    batch.write_json(folder / "state.json", state)
    if external:
        (folder / "worker.log").touch()
        ready = ctx.output_dir("queue")
        ready.mkdir(exist_ok=True)
        (ready / f"{job_id}.ready").touch(exist_ok=False)
        return render_status(ctx, job_id)
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
    try:
        with (folder / "worker.log").open("wb") as log:
            process = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), str(folder), str(ctx.workspace), str(ctx.blender)],
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, close_fds=True, **options,
            )
    except OSError as exc:
        state.update(status="failed", error=f"Could not start render worker: {exc}")
        batch.write_json(folder / "state.json", state)
    else:
        if mode == "check":
            process.wait()
            if process.returncode and batch.read_json(folder / "state.json")["status"] == "queued":
                state.update(status="failed", error=f"Preflight worker exited with code {process.returncode}")
                batch.write_json(folder / "state.json", state)
        else:
            threading.Thread(target=process.wait, daemon=True).start()
    return render_status(ctx, job_id)


def preflight_render(ctx, manifest: str, shot_ids: list[str] | None = None):
    return start(ctx, manifest, shot_ids, mode="check")


def submit_render(ctx, manifest: str, shot_ids: list[str] | None = None):
    return start(ctx, manifest, shot_ids, mode="render")


def render_status(ctx, job_id: str):
    if not isinstance(job_id, str) or not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise ValueError("Expected the 32-character job ID returned by the server")
    folder = ctx.output_dir("jobs", job_id)
    state_file = folder / "state.json"
    if not state_file.is_file():
        raise ValueError(f"Unknown render job: {job_id}")
    report = folder / "batch" / "report.json"
    with progress_lock(folder):
        state = batch.read_json(state_file)
        entries = batch.read_json(report)["jobs"] if report.is_file() else {}
        orphaned_queue = state["status"] == "queued" and state["dispatch"] == "local" and time.time() - state["created_at"] > 60
        if state["status"] == "running" or orphaned_queue:
            with (folder / "lease.lock").open("r+b") as lease:
                if acquire(lease, wait=False):
                    state.update(status="interrupted", error="The worker stopped before it recorded completion. Submit unfinished shots in a new job.")
    relative = folder.relative_to(ctx.workspace).as_posix()
    response = dict(state, job_directory=relative, worker_log=f"{relative}/worker.log")
    if state["dispatch"] == "external":
        response["worker_online"] = worker_online(ctx)
        if state["status"] == "queued" and not response["worker_online"]:
            response["worker_message"] = "Start render_jobs.py serve with the same workspace and Blender executable to consume this queue."
    shots = {key: {"status": "pending"} for key in state["shot_ids"]}
    if entries:
        response["report"] = f"{relative}/batch/report.json"
        for key, entry in entries.items():
            shots[key] = {field: entry[field] for field in (
                "status", "error", "scene", "camera", "pixels", "frames", "range", "source_sha256", "missing_source_warnings"
            ) if field in entry}
            if state["mode"] == "render" and entry["status"] == "ok":
                directory = f"{relative}/batch/shots/{key}"
                shots[key]["output_directory"] = directory
                if (ctx.workspace / directory / "still.png").is_file():
                    shots[key]["image"] = f"{directory}/still.png"
                else:
                    shots[key]["frame_pattern"] = f"{directory}/frame_{{frame:06d}}.png"
    if state["status"] in {"failed", "interrupted"}:
        for shot in shots.values():
            if shot["status"] in {"pending", "running"}:
                shot["status"] = "unfinished"
    response["shots"] = shots
    return response


if __name__ == "__main__":
    if len(sys.argv) == 4 and not sys.argv[1].startswith("-") and sys.argv[1] != "serve":
        work(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
    else:
        from workspace import Workspace

        parser = argparse.ArgumentParser(description="Consume a workspace's persistent render queue.")
        parser.add_argument("command", choices=["serve"])
        parser.add_argument("--workspace", type=Path, required=True)
        parser.add_argument("--blender", default=os.environ.get("BLENDER_BIN", "blender"))
        opts = parser.parse_args()
        root = opts.workspace.resolve()
        blender = shutil.which(opts.blender)
        if not root.is_dir() or not blender:
            parser.error("An existing workspace directory and Blender executable are required")
        try:
            serve(Workspace(root, str(Path(blender).resolve())))
        except ValueError as exc:
            parser.exit(2, f"{exc}\n")
        except KeyboardInterrupt:
            pass
