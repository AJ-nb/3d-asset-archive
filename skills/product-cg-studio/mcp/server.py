"""Expose Product CG Studio's Blender production tools over local MCP stdio."""

import argparse
import asyncio
import os
from pathlib import Path
import shutil
from typing import Any

from mcp.server.fastmcp import FastMCP

import audits
import render_jobs
from workspace import Workspace


def create_server(ctx: Workspace) -> FastMCP:
    server = FastMCP("product-cg-studio")

    @server.tool()
    async def audit_assembly(blend: str, manifest: str) -> dict[str, Any]:
        """Evaluate the assembly checks, tolerances, frames and subframes named in a rig JSON manifest. Paths are relative to the workspace. Read the report for failed checks and samples."""
        return await asyncio.to_thread(audits.audit_assembly, ctx, blend, manifest)

    @server.tool()
    async def compare_sections(
        blend: str,
        parts: list[str],
        pose: str,
        reference_blend: str | None = None,
        axes: str = "XYZ",
        frame: int = 1,
        datum: str | None = None,
        range_mm: list[float] | None = None,
        bevel_windows: str | None = None,
        mm_per_unit: float | None = None,
        scene: str | None = None,
    ) -> dict[str, Any]:
        """Slice named meshes at 1 mm intervals. Supply a registered reference .blend to measure differences and a bevel-window JSON file to fit radii. Both scenes must share part names, pose and datum. All file paths are relative to the workspace."""
        return await asyncio.to_thread(
            audits.compare_sections, ctx, blend, parts, pose,
            reference_blend=reference_blend, axes=axes, frame=frame, datum=datum,
            range_mm=range_mm, bevel_windows=bevel_windows, mm_per_unit=mm_per_unit,
            scene=scene,
        )

    @server.tool()
    async def preflight_render(manifest: str, shot_ids: list[str] | None = None) -> dict[str, Any]:
        """Open the selected shots in Blender and check cameras, frames and dependencies. Takes a workspace-relative shot manifest. Writes a report for inspection."""
        return await asyncio.to_thread(render_jobs.preflight_render, ctx, manifest, shot_ids)

    @server.tool()
    async def submit_render(manifest: str, shot_ids: list[str] | None = None) -> dict[str, Any]:
        """Start a background PNG render. Omit shot_ids for all shots, or pass selected IDs for a new, isolated rerender. Save the returned job_id to poll after reconnecting."""
        return await asyncio.to_thread(render_jobs.submit_render, ctx, manifest, shot_ids)

    @server.tool()
    async def render_status(job_id: str) -> dict[str, Any]:
        """Read a render job or preflight receipt in this workspace. Return per-shot progress, diagnostics and available output paths."""
        return await asyncio.to_thread(render_jobs.render_status, ctx, job_id)

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True, help="Existing project directory for inputs and outputs.")
    parser.add_argument("--blender", default=os.environ.get("BLENDER_BIN", "blender"), help="Blender executable (default: BLENDER_BIN or PATH).")
    parser.add_argument("--external-render-worker", action="store_true",
                        help="Queue renders for the independently started worker in this workspace.")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        parser.error(f"Workspace is not an existing directory: {workspace}")
    executable = shutil.which(args.blender)
    if executable is None:
        parser.error(f"Blender executable not found: {args.blender}")
    ctx = Workspace(workspace, str(Path(executable).resolve()), args.external_render_worker)
    create_server(ctx).run(transport="stdio")


if __name__ == "__main__":
    main()
