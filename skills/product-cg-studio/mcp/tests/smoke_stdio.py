"""Exercise the published MCP tools from an independent stdio client and real Blender."""

import argparse
import asyncio
import csv
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zipfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SERVER = Path(__file__).resolve().parents[1] / "server.py"
EXAMPLES = SERVER.parent.parent / "examples"


def prepare(workspace):
    files = ("rig/checks.json", "rig/none.blend", "rig/oversize_pin.blend",
             "sections/draft.blend", "sections/reference.blend", "sections/fits.json")
    with zipfile.ZipFile(EXAMPLES / "verification-data.zip") as archive:
        for name in files:
            archive.extract(name, workspace)
    shutil.copyfile(EXAMPLES / "demo.blend", workspace / "demo.blend")
    hero = {"id": "hero", "blend": "demo.blend", "scene": "Studio", "camera": "Hero",
            "resolution": [64, 48], "frame": 1}
    missing = dict(hero, id="missing", required_files=["undelivered-texture.png"])
    (workspace / "shots.json").write_text(json.dumps({"version": 1, "jobs": [hero, missing]}), encoding="utf-8")


@asynccontextmanager
async def connect(workspace, blender, external_worker=False):
    args = [str(SERVER), "--workspace", str(workspace), "--blender", blender]
    if external_worker:
        args.append("--external-render-worker")
    server = StdioServerParameters(command=sys.executable, args=args)
    async with stdio_client(server) as streams, ClientSession(*streams) as client:
        await client.initialize()
        yield client


async def call(client, name, **args):
    result = await client.call_tool(name, args)
    assert not result.isError, (name, result.content)
    return result.structuredContent


async def run(workspace, blender):
    prepare(workspace)
    async with connect(workspace, blender) as client:
        tools = {tool.name for tool in (await client.list_tools()).tools}
        required = {"audit_assembly", "compare_sections", "preflight_render", "submit_render", "render_status"}
        assert required <= tools, required - tools
        for filename, expected in [("none", "passed"), ("oversize_pin", "failed")]:
            report = await call(client, "audit_assembly", blend=f"rig/{filename}.blend", manifest="rig/checks.json")
            assert report["status"] == expected, report
            evidence = json.loads((workspace / report["report"]).read_text(encoding="utf-8"))
            assert evidence["pass"] == (expected == "passed"), evidence
            if expected == "failed":
                assert "radial-clearance-fixed-eye-and-pin" in report["failed_checks"], report
        sections = await call(client, "compare_sections", blend="sections/draft.blend", parts=["Gauge"],
                              pose="assembled", reference_blend="sections/reference.blend", axes="Z",
                              range_mm=[-1, 1], bevel_windows="sections/fits.json")
        assert sections["step_mm"] == 1 and sections["station_counts"]["compared"] == 3, sections
        assert sections["status"] == "needs_review" and sections["mode"] == "reference_comparison", sections
        with (workspace / sections["artifacts"]["radii.csv"]).open(encoding="utf-8-sig", newline="") as stream:
            radius = next(csv.DictReader(stream))
        for field, expected in [("current_R_mm", 2), ("reference_R_mm", 1), ("delta_R_mm", 1)]:
            assert abs(float(radius[field]) - expected) < 0.001, radius
        for selection, expected in [("hero", "completed"), ("missing", "needs_review")]:
            preflight = await call(client, "preflight_render", manifest="shots.json", shot_ids=[selection])
            assert preflight["status"] == expected and set(preflight["shots"]) == {selection}, preflight
        with tempfile.TemporaryDirectory(dir=workspace.parent) as sibling:
            outside = Path(sibling) / "outside.json"
            shutil.copyfile(workspace / "shots.json", outside)
            shutil.copyfile(workspace / "demo.blend", outside.with_name("demo.blend"))
            rejected = await client.call_tool("preflight_render", {
                "manifest": os.path.relpath(outside, workspace), "shot_ids": ["hero"],
            })
            assert rejected.isError, rejected

    # A desktop client may terminate its entire process tree on disconnect.
    # Run this worker under the test runner, independently of both MCP servers.
    command = [sys.executable, str(SERVER.with_name("render_jobs.py")), "serve",
               "--workspace", str(workspace), "--blender", blender]
    with (workspace / "smoke-worker.log").open("wb") as log:
        worker = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        try:
            await verify_reconnect(workspace, blender, worker)
        finally:
            if worker.poll() is None:
                worker.terminate()
            worker.wait(timeout=15)
    print("Passed stdio discovery, assembly pass/fail, 1 mm sections, bevel radii, render preflight, "
          "missing dependency, path rejection, server restart and independent selected-shot PNG renders.")


async def verify_reconnect(workspace, blender, worker):
    selection = {"manifest": "shots.json", "shot_ids": ["hero"]}
    async with connect(workspace, blender, external_worker=True) as client:
        job = await call(client, "submit_render", **selection)
        deadline = time.monotonic() + 60
        while job["status"] == "queued":
            assert worker.poll() is None, (workspace / "smoke-worker.log").read_text(errors="replace")
            assert time.monotonic() < deadline, job
            await asyncio.sleep(0.2)
            job = await call(client, "render_status", job_id=job["job_id"])
        assert job["status"] in {"running", "completed"}, job
        print(f"Disconnecting the first client with render {job['job_id']} {job['status']}.")
    async with connect(workspace, blender, external_worker=True) as client:
        retry = await call(client, "submit_render", **selection)
        assert retry["job_id"] != job["job_id"], retry
        paths = []
        for submitted in (job, retry):
            deadline = time.monotonic() + 180
            while True:
                assert worker.poll() is None, (workspace / "smoke-worker.log").read_text(errors="replace")
                status = await call(client, "render_status", job_id=submitted["job_id"])
                if status["status"] not in {"queued", "running"}:
                    break
                assert time.monotonic() < deadline, status
                await asyncio.sleep(0.5)
            assert status["status"] == "completed" and set(status["shots"]) == {"hero"}, status
            path = workspace / status["shots"]["hero"]["image"]
            with path.open("rb") as stream:
                header = stream.read(24)
            assert header[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", header[16:]) == (64, 48), path
            paths.append(path)
        assert paths[0] != paths[1] and all(path.is_file() for path in paths), paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", default=os.environ.get("BLENDER_BIN", "blender"))
    parser.add_argument("--output", type=Path, help="Optional new directory in which to keep the test evidence")
    options = parser.parse_args()
    if options.output:
        options.output.mkdir(parents=True, exist_ok=False)
        asyncio.run(run(options.output.resolve(), options.blender))
    else:
        with tempfile.TemporaryDirectory(prefix="product-cg-mcp-test-") as directory:
            asyncio.run(run(Path(directory), options.blender))
