"""Content components: markdown, callout, code, quote, sources, badges, divider."""
from __future__ import annotations

from typing import Optional

from .base import Component, Model
from .types import Url, lax_enum

__all__ = ["Markdown", "Callout", "Code", "Quote", "Source", "Sources", "Badge", "Badges", "Divider"]

CalloutLevel = lax_enum(
    "info",
    "success",
    "warning",
    "error",
    aliases={"danger": "error", "warn": "warning", "note": "info", "tip": "info", "ok": "success"},
)
BadgeColor = lax_enum(
    "gray",
    "accent",
    "green",
    "amber",
    "red",
    "blue",
    "violet",
    aliases={"grey": "gray", "purple": "violet", "yellow": "amber", "orange": "amber", "indigo": "accent"},
)


class Markdown(Component):
    """Rich text (Markdown) inside layouts.

    Use it to place prose inside a ``card``, ``grid``, ``tabs`` or ``accordion``.
    Raw HTML in the Markdown is never rendered.

    Example:
        ``ui.Card("Summary", ui.Markdown("**Revenue** grew 12%."))``
    """

    group = "content"
    positional = ("text",)
    examples = [{"text": "**Note:** prices include taxes."}]

    text: str


class Callout(Component):
    """A tinted note for tips, warnings and outcomes.

    Example:
        ``ui.Callout("Your booking is confirmed.", level="success", title="Done")``
    """

    group = "content"
    positional = ("text",)
    examples = [{"text": "Prices may change before checkout.", "level": "warning"}]

    text: str
    level: CalloutLevel = "info"
    title: Optional[str] = None


class Code(Component):
    """A code snippet with syntax highlighting and a copy button.

    Example:
        ``ui.Code("pip install dyui", language="bash")``
    """

    group = "content"
    positional = ("code",)
    examples = [{"code": "pip install dyui", "language": "bash"}]

    code: str
    language: Optional[str] = None
    filename: Optional[str] = None


class Quote(Component):
    """A quotation with attribution.

    Example:
        ``ui.Quote("Simplicity is the ultimate sophistication.", author="Leonardo da Vinci")``
    """

    group = "content"
    positional = ("text",)

    text: str
    author: Optional[str] = None
    source: Optional[str] = None


class Source(Model):
    """One cited source (``title``, ``url``, optional ``snippet``)."""

    __positional__ = ("title", "url")
    __str_field__ = "url"

    title: Optional[str] = None
    url: Url
    snippet: Optional[str] = None


class Sources(Component):
    """Numbered source citations.

    Example:
        ``ui.Sources(ui.Source("DyUI docs", "https://example.com/docs"))``
    """

    group = "content"
    varargs = "items"
    examples = [{"items": [{"title": "Lisbon travel guide", "url": "https://example.com/lisbon"}]}]

    items: list[Source]


class Badge(Model):
    """One badge (``label``, optional ``color``)."""

    __positional__ = ("label", "color")
    __str_field__ = "label"

    label: str
    color: Optional[BadgeColor] = None


class Badges(Component):
    """A row of small labels or tags.

    Example:
        ``ui.Badges("Beta", ui.Badge("Paid", color="green"))``
    """

    group = "content"
    varargs = "items"

    items: list[Badge]


class Divider(Component):
    """A horizontal separator, optionally labeled.

    Example:
        ``ui.Divider("Results")``
    """

    group = "content"
    positional = ("label",)

    label: Optional[str] = None
