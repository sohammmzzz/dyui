"""Developer-authored HTML templates rendered as sandboxed ``html`` components.

``{{ key }}`` is HTML-escaped, ``{{{ key }}}`` is inserted raw. Templates are only
ever loaded from your own directory (path-traversal safe) and rendered client-side
in an ``<iframe sandbox="allow-scripts">`` without same-origin access. The LLM can
never produce HTML.
"""
from __future__ import annotations

import html as _html
import re
from pathlib import Path
from typing import Any, Optional, Union

from .ui import Html

__all__ = ["html_template", "render_template", "load_template", "register_template_root"]

_RAW = re.compile(r"\{\{\{\s*([\w.]+)\s*\}\}\}")
_ESC = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")
_TEMPLATE_SUFFIXES = (".html", ".htm")
_APP_DIRS: list[Path] = []


def register_template_root(path: Union[str, Path]) -> None:
    """Add a directory templates are looked up in (``dyui.App`` registers its own file's folder)."""
    p = Path(path).resolve()
    if p in _APP_DIRS:
        _APP_DIRS.remove(p)
    _APP_DIRS.append(p)


def _roots(root: Union[str, Path, None]) -> list[Path]:
    if root is not None:
        return [Path(root).resolve()]
    out: list[Path] = []
    for p in [*reversed(_APP_DIRS), Path.cwd().resolve()]:
        if p not in out:
            out.append(p)
    return out


def load_template(path: Union[str, Path], *, root: Union[str, Path, None] = None) -> str:
    """Read a template file safely.

    ``path`` is relative; it is looked up in ``<root>/templates/`` then ``<root>/``, where
    ``root`` is the given directory or else your app's directory, then the current
    directory. Only ``.html`` / ``.htm`` files inside those directories are readable:
    absolute paths, ``..`` escapes and symlinks pointing outside are refused.

    Raises:
        ValueError: If the path is unsafe or the template doesn't exist.
    """
    rel = str(path)
    if not rel or "\x00" in rel:
        raise ValueError("template path is empty or invalid")
    rel_path = Path(rel.replace("\\", "/"))
    if rel_path.is_absolute() or rel_path.drive or rel.startswith(("/", "\\")):
        raise ValueError(f"template {rel!r} must be a relative path")
    if rel_path.suffix.lower() not in _TEMPLATE_SUFFIXES:
        raise ValueError(f"template {rel!r} must be an .html file")
    roots = _roots(root)
    for base in roots:
        for folder in (base / "templates", base):
            target = (folder / rel_path).resolve()
            if target != base and base not in target.parents:
                raise ValueError(f"template {rel!r} is outside {base}")
            if target.is_file():
                return target.read_text(encoding="utf-8")
    raise ValueError(f"template {rel!r} not found (looked in: {', '.join(str(r) for r in roots)})")


def _lookup(props: dict[str, Any], key: str) -> Any:
    value: Any = props
    for part in key.split("."):
        value = value.get(part, "") if isinstance(value, dict) else ""
    return "" if value is None else value


def render_template(template: str, props: dict[str, Any]) -> str:
    """Fill ``{{ key }}`` (escaped) and ``{{{ key }}}`` (raw) placeholders."""
    out = _RAW.sub(lambda m: str(_lookup(props, m.group(1))), template)
    return _ESC.sub(lambda m: _html.escape(str(_lookup(props, m.group(1)))), out)


def html_template(path: Union[str, Path], *, root: Union[str, Path, None] = None,
                  height: Optional[int] = None, **props: Any) -> Html:
    """Render an HTML template file into a sandboxed ``ui.Html`` component.

    Args:
        path: Template path (see :func:`load_template` for where it is looked up).
        root: Directory templates must live in (default: your app's directory, then
            the current directory).
        height: Optional fixed iframe height in px (auto-sized otherwise).
        **props: Values for the placeholders.

    Raises:
        ValueError: If ``path`` is unsafe, escapes ``root`` or doesn't exist.
    """
    text = render_template(load_template(path, root=root), props)
    return Html(html=text, height=height) if height else Html(html=text)
