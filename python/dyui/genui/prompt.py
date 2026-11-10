"""Prompt text generation for a :class:`~dyui.genui.catalog.Catalog` (SPEC §3.6)."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from ..ui.base import Component

if TYPE_CHECKING:  # pragma: no cover
    from .catalog import Catalog

__all__ = ["build_prompt", "usage_hint", "example_lines"]

_EXAMPLE_PREFERENCE = ("stat", "table", "chart", "card", "callout", "quick_replies")

_FENCE_INTRO = """\
## UI components
You can show UI components inside your reply. To do so, write a fenced code block
tagged `dyui` containing one JSON object per line: {"ui": "<name>", ...props}.
Components support your written answer; they do not replace it. Always write prose
outside the block as well: a sentence that introduces what you are showing, and a
short takeaway or explanation after it. Never reply with components alone. Use plain
text only when a component isn't clearly better."""

_TOOLS_INTRO = """\
## UI components
You can show UI components inside your reply by calling the render_<name> tools;
each call renders one component at that point in your reply. Components support
your written answer; they do not replace it. Always write normal text as well: a
sentence that introduces what you are showing, and after the tool calls a short
takeaway or explanation. Never reply with components alone. Use plain text only
when a component isn't clearly better."""


def _has_children(cls: type[Component]) -> bool:
    fields = cls.model_fields
    if "children" in fields:
        return True
    for name in ("tabs", "items"):
        f = fields.get(name)
        if f is not None and "children" in str(f.annotation):
            return True
    return False


def _has_actions(cls: type[Component]) -> bool:
    return getattr(cls.declared_actions, "__func__", None) is not getattr(Component.declared_actions, "__func__", None)


def usage_hint(cls: type[Component]) -> str:
    """Short usage hint appended to a component's tool description."""
    info = cls.__dyui__
    parts = []
    if _has_children(cls):
        parts.append(
            'Children are component objects written as JSON strings, e.g. '
            '"{\\"ui\\":\\"stat\\",\\"label\\":\\"Users\\",\\"value\\":1200}".'
        )
    if info.name == "quick_replies":
        parts.append("Tapping an option sends it to you as the user's next message.")
    elif _has_actions(cls):
        parts.append('The user\'s response comes back to you as a message like "[action:<name>] {...}".')
    if not parts:
        parts.append("Renders inline where you call it.")
    if info.hint:
        parts.append(info.hint)
    return " ".join(parts)


def _line(name: str, example: dict[str, Any]) -> str:
    return json.dumps({"ui": name, **example}, ensure_ascii=False, separators=(",", ":"))


def example_lines(catalog: "Catalog", limit: int = 2) -> list[str]:
    """Pick up to ``limit`` validated example lines (customs first, then a built-in)."""
    candidates: list[tuple[str, dict[str, Any]]] = []
    for cls in catalog:
        info = cls.__dyui__
        if not info.builtin and info.examples:
            candidates.append((info.name, info.examples[0]))
            break
    for pref in _EXAMPLE_PREFERENCE:
        cls = catalog.get(pref)
        if cls is not None and cls.__dyui__.examples:
            candidates.append((pref, cls.__dyui__.examples[0]))
            break
    if not candidates:
        for cls in catalog:
            if cls.__dyui__.examples:
                candidates.append((cls.__dyui__.name, cls.__dyui__.examples[0]))
                break
    lines: list[str] = []
    for name, example in candidates:
        node = catalog.validate({"ui": name, **example}, id="c_example")
        if node.get("status") != "error":
            lines.append(_line(name, example))
        if len(lines) >= limit:
            break
    return lines


def build_prompt(catalog: "Catalog", mode: str = "fence") -> str:
    """Build the full prompt section for ``catalog`` in ``mode`` (``fence``/``tools``)."""
    if mode not in ("fence", "tools"):
        raise ValueError(f"unknown prompt mode {mode!r}; expected 'fence' or 'tools'")
    classes = list(catalog)
    if not classes:
        return ""
    any_layout = any(_has_children(c) for c in classes)
    any_action = any(_has_actions(c) for c in classes)
    out = [_FENCE_INTRO if mode == "fence" else _TOOLS_INTRO]
    if any_layout:
        if mode == "fence":
            out.append('Layout components take "children": [ ...component objects... ].')
        else:
            out.append('Layout components take "children": component objects written as JSON strings.')
    if any_action:
        out.append(
            'Interactive components ("action" props) send the user\'s choice back to you as a message '
            'like [action:<name>] {...}.'
        )
    out.append("")
    out.append("Components:")
    if mode == "fence":
        out.extend(c.signature() for c in classes)
    else:
        for c in classes:
            info = c.__dyui__
            out.append(f"{catalog.tool_name(info.name)} — {info.description}" if info.description else catalog.tool_name(info.name))
    if mode == "fence":
        lines = example_lines(catalog)
        if lines:
            out.append("")
            out.append("Example:")
            out.append("<a sentence introducing what you are showing>")
            out.append("```dyui")
            out.extend(lines)
            out.append("```")
            out.append("<one or two sentences on what it means>")
    return "\n".join(out)
