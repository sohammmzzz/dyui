"""The ordered registry of built-in components (SPEC §6 order)."""
from __future__ import annotations

from .agent import Plan, Reasoning, Step
from .base import Component
from .content import Badges, Callout, Code, Divider, Markdown, Quote, Sources
from .data import Chart, Json, KeyValue, Progress, Stat, Stats, Table, Timeline
from .developer import Html, Invalid
from .interactive import Buttons, Choice, Confirm, Form, QuickReplies, Rating
from .layout import Accordion, Card, Carousel, Grid, List, Tabs
from .media import Audio, File, Gallery, Image, LinkPreview, Video

__all__ = ["BUILTINS", "GROUPS", "LLM_BUILTINS", "builtin", "builtins_in"]

GROUPS: tuple[str, ...] = ("content", "data", "media", "interactive", "layout", "agent")
"""Catalog groups usable with :func:`dyui.catalog`."""

BUILTINS: tuple[type[Component], ...] = (
    # content
    Markdown, Callout, Code, Quote, Sources, Badges, Divider,
    # data
    Table, Stat, Stats, KeyValue, Chart, Progress, Timeline, Json,
    # media
    Image, Gallery, Video, Audio, File, LinkPreview,
    # interactive
    Buttons, QuickReplies, Choice, Form, Confirm, Rating,
    # layout
    Card, Grid, Tabs, Accordion, Carousel, List,
    # agent
    Step, Reasoning, Plan,
    # developer-only
    Html, Invalid,
)
"""Every built-in component class, in spec order."""

LLM_BUILTINS: tuple[type[Component], ...] = tuple(c for c in BUILTINS if c.__dyui__.llm)
"""Built-ins that may be offered to the LLM (excludes ``html`` and ``invalid``)."""

_BY_NAME = {c.__dyui__.name: c for c in BUILTINS}


def builtin(name: str) -> type[Component] | None:
    """Return the built-in class for an LLM name, or ``None``."""
    return _BY_NAME.get(name)


def builtins_in(*groups: str) -> list[type[Component]]:
    """Return LLM built-ins in the given groups (all groups when none given).

    Raises:
        ValueError: For an unknown group name.
    """
    for g in groups:
        if g not in GROUPS:
            raise ValueError(f"unknown component group {g!r}; expected one of {', '.join(GROUPS)}")
    wanted = set(groups) or set(GROUPS)
    return [c for c in LLM_BUILTINS if c.__dyui__.group in wanted]
