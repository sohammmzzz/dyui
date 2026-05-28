"""Use your own HTML files as card templates -- no frontend code required.

Drop ``.html`` files in a folder, then emit them by name with props filled in::

    cards = HtmlTemplates("cards")          # ./cards/invoice.html, ./cards/weather.html, ...
    cards.emit("invoice", number=42, total="$1,200", customer="<Acme>")

Each ``{{ key }}`` placeholder in the template is replaced with the matching
prop, HTML-escaped by default. Use ``{{& key }}`` (or ``{{{ key }}}``) to inject
raw, pre-trusted HTML. The filled markup is emitted as a DyUI ``html`` card, so
the built-in served UI (or ``dyui-react``) renders it with no extra wiring.
"""

from __future__ import annotations

import html as _html
import re
from pathlib import Path
from typing import Any, Optional

from .emit import emit
from .events import UIEvent

# {{ key }} -> escaped ; {{& key }} or {{{ key }}} -> raw
_PLACEHOLDER = re.compile(r"\{\{\{\s*(\w+)\s*\}\}\}|\{\{\s*(&)?\s*(\w+)\s*\}\}")


def render_template(template: str, props: dict[str, Any]) -> str:
    """Fill ``{{ key }}`` / ``{{& key }}`` / ``{{{ key }}}`` placeholders."""

    def repl(m: re.Match) -> str:
        triple_key = m.group(1)
        if triple_key is not None:  # {{{ key }}} -> raw
            return str(props.get(triple_key, ""))
        raw = m.group(2) == "&"  # {{& key }} -> raw
        key = m.group(3)
        value = props.get(key, "")
        return str(value) if raw else _html.escape(str(value))

    return _PLACEHOLDER.sub(repl, template)


class HtmlTemplates:
    """A small registry that loads HTML card templates from a directory."""

    def __init__(self, directory: str | Path, *, cache: bool = True) -> None:
        self.directory = Path(directory)
        self._cache: dict[str, str] = {}
        self._use_cache = cache

    def _load(self, name: str) -> str:
        if self._use_cache and name in self._cache:
            return self._cache[name]
        path = self.directory / f"{name}.html"
        if not path.exists():
            raise FileNotFoundError(f"No card template '{name}.html' in {self.directory}")
        text = path.read_text(encoding="utf-8")
        if self._use_cache:
            self._cache[name] = text
        return text

    def render(self, name: str, **props: Any) -> str:
        """Return the filled HTML string for template ``name``."""
        return render_template(self._load(name), props)

    def emit(
        self,
        name: str,
        values: Optional[dict[str, Any]] = None,
        *,
        id: Optional[str] = None,
        status: str = "done",
        surface: str = "default",
        title: Optional[str] = None,
        icon: Optional[str] = None,
        accent: Optional[str] = None,
        ttl_ms: Optional[int] = None,
        **extra_values: Any,
    ) -> UIEvent:
        """Render template ``name`` and emit it as an ``html`` card.

        Pass the template's placeholder values in the ``values`` dict (and/or as
        keyword args). The card-config keywords (``id``, ``status``, ``surface``,
        ``title``, ``icon``, ``accent``, ``ttl_ms``) are reserved -- if your
        template uses a placeholder with one of those names (e.g. ``{{ status }}``),
        put it in the ``values`` dict so it isn't mistaken for card config.
        """
        props = {**(values or {}), **extra_values}
        markup = self.render(name, **props)
        return emit(
            "html",
            {"html": markup},
            id=id,
            status=status,  # type: ignore[arg-type]
            surface=surface,
            title=title,
            icon=icon,
            accent=accent,
            ttl_ms=ttl_ms,
            meta={"template": name},
        )

    def available(self) -> list[str]:
        """List template names available in the directory."""
        return sorted(p.stem for p in self.directory.glob("*.html"))
