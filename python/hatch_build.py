"""Hatch build hook: ship the web UI (dyui/_static) and the docs (dyui/_docs) in the wheel.

Docs (for the offline MCP server, ``dyui mcp``): ``../docs/src/content/docs/**/*.{md,mdx}``
(without the generated ``reference/api/``), ``../examples/*.py``, ``../docs/examples/**/*.py``
and ``../CHANGELOG.md`` are copied into ``dyui/_docs/`` with their repository-relative paths, so
MDX ``?raw`` imports resolve the same way as in a checkout. Runs for both the sdist and the
wheel target; skipped for editable installs (they read the checkout directly) and when
``../docs`` is absent (building a wheel from an sdist, which already carries ``_docs``).

Web UI:

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


_DOC_GLOBS = (
    ("docs/src/content/docs", ("**/*.md", "**/*.mdx")),
    ("examples", ("*.py",)),
    ("docs/examples", ("**/*.py",)),
)
_DOC_FILES = ("CHANGELOG.md",)
_DOC_SKIP = ("docs/src/content/docs/reference/api/",)


def bundle_docs(repo: Path, dest: Path) -> int:
    """Copy the docs sources the MCP server reads from ``repo`` into ``dest``; return the file count.

    ``dest`` is rebuilt from scratch so pages deleted upstream do not linger.
    """
    files: list[Path] = []
    for base, patterns in _DOC_GLOBS:
        folder = repo / base
        if not folder.is_dir():
            continue
        for pattern in patterns:
            for path in folder.glob(pattern):
                rel = path.relative_to(repo).as_posix()
                if path.is_file() and "__pycache__" not in path.parts and not rel.startswith(_DOC_SKIP):
                    files.append(path)
    files += [repo / f for f in _DOC_FILES if (repo / f).is_file()]
    shutil.rmtree(dest, ignore_errors=True)
    for path in sorted(set(files)):
        out = dest / path.relative_to(repo)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, out)
    return len(set(files))


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict) -> None:
        root = Path(self.root)
        if version != "editable" and (root.parent / "docs" / "src" / "content" / "docs").is_dir():
            bundle_docs(root.parent, root / "dyui" / "_docs")
        if self.target_name == "sdist":
            return  # the sdist only needs the docs; the web UI is built for wheels (as before)
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
