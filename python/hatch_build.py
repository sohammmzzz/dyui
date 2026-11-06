"""Hatch build hook: compile ../web into dyui/_static so the wheel ships the UI.

- ``DYUI_SKIP_WEB_BUILD=1`` skips it (tests, CI for Python only).
- Skipped when ``../web/package.json`` is absent (building from an sdist, which
  already carries ``dyui/_static``).
- Otherwise the web app is rebuilt whenever ``dyui/_static`` is missing or older
  than any web source (``src/``, ``public/``, the HTML entries, package and Vite
  config), so a local build never ships a stale UI. ``DYUI_FORCE_WEB_BUILD=1``
  always rebuilds.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

_WEB_INPUTS = ("src", "public", "index.html", "gallery.html", "package.json", "package-lock.json",
               "vite.config.ts", "tsconfig.json")


def _newest_mtime(web: Path) -> float:
    newest = 0.0
    for name in _WEB_INPUTS:
        path = web / name
        if path.is_file():
            newest = max(newest, path.stat().st_mtime)
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_file():
                    newest = max(newest, child.stat().st_mtime)
    return newest


def needs_web_build(web: Path, static: Path, *, force: bool = False) -> bool:
    """Whether ``static`` must be (re)built from ``web``."""
    index = static / "index.html"
    if force or not index.is_file():
        return True
    return _newest_mtime(web) > index.stat().st_mtime


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict) -> None:
        root = Path(self.root)
        web = root.parent / "web"
        static = root / "dyui" / "_static"
        if os.environ.get("DYUI_SKIP_WEB_BUILD"):
            return
        if not (web / "package.json").is_file():
            return
        if not needs_web_build(web, static, force=bool(os.environ.get("DYUI_FORCE_WEB_BUILD"))):
            return
        npm = shutil.which("npm")
        if npm is None:
            if (static / "index.html").is_file():
                self.app.display_warning("dyui: npm not found — shipping the existing (possibly stale) web UI.")
            else:
                self.app.display_warning("dyui: npm not found — the wheel will not include the web UI.")
            return
        if not (web / "node_modules").is_dir():
            subprocess.run([npm, "ci"], cwd=web, check=True)
        subprocess.run([npm, "run", "build"], cwd=web, check=True)
        shutil.rmtree(static, ignore_errors=True)
        shutil.copytree(web / "dist", static)
