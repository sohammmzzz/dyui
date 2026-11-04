"""Hatch build hook: compile ../web into dyui/_static so the wheel ships the UI.

- ``DYUI_SKIP_WEB_BUILD=1`` skips it (tests, CI for Python only).
- Skipped when ``../web/package.json`` is absent (building from an sdist).
- Skipped when ``dyui/_static/index.html`` already exists, unless ``DYUI_FORCE_WEB_BUILD=1``.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict) -> None:
        root = Path(self.root)
        web = root.parent / "web"
        static = root / "dyui" / "_static"
        if os.environ.get("DYUI_SKIP_WEB_BUILD"):
            return
        if not (web / "package.json").is_file():
            return
        if (static / "index.html").is_file() and not os.environ.get("DYUI_FORCE_WEB_BUILD"):
            return
        npm = shutil.which("npm")
        if npm is None:
            self.app.display_warning("dyui: npm not found — the wheel will not include the web UI.")
            return
        if not (web / "node_modules").is_dir():
            subprocess.run([npm, "ci"], cwd=web, check=True)
        subprocess.run([npm, "run", "build"], cwd=web, check=True)
        shutil.rmtree(static, ignore_errors=True)
        shutil.copytree(web / "dist", static)
