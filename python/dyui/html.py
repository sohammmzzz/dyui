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

__all__ = ["html_template", "render_template"]

_RAW = re.compile(r"\{\{\{\s*([\w.]+)\s*\}\}\}")
_ESC = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


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
        path: Template path, relative to ``root`` (default: the current directory).
        root: Directory templates must live in.
        height: Optional fixed iframe height in px (auto-sized otherwise).
        **props: Values for the placeholders.

    Raises:
        ValueError: If ``path`` escapes ``root``.
    """
    base = Path(root or Path.cwd()).resolve()
    target = (base / path).resolve()
    if base != target and base not in target.parents:
        raise ValueError(f"template {path!r} is outside {base}")
    text = render_template(target.read_text(encoding="utf-8"), props)
    return Html(html=text, height=height) if height else Html(html=text)
