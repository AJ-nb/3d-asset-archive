"""Filesystem locations shared by the local production tools."""

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from uuid import uuid4


@dataclass(frozen=True)
class Workspace:
    workspace: Path
    blender: str
    external_render_worker: bool = False

    def _within(self, root: Path, name: str) -> Path:
        if not name.strip() or Path(name).anchor or PureWindowsPath(name).anchor:
            raise ValueError("Use a relative path inside the configured workspace.")
        result = (root / name).resolve()
        if not result.is_relative_to(root):
            raise ValueError(f"Path leaves the configured directory: {name}")
        return result

    def input_path(self, value: str) -> Path:
        path = self._within(self.workspace, value)
        if not path.is_file():
            raise ValueError(f"Input file does not exist: {value}")
        return path

    def state_dir(self) -> Path:
        root = self._within(self.workspace, ".product-cg-mcp")
        root.mkdir(exist_ok=True)
        return root

    def output_dir(self, *relative_parts: str) -> Path:
        return self._within(self.state_dir(), str(Path(*relative_parts)))

    def new_run(self) -> Path:
        path = self.output_dir("audits", uuid4().hex)
        path.mkdir(parents=True)
        return path
