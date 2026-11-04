"""Layout components: card, grid, tabs, accordion, carousel, list."""
from __future__ import annotations

from typing import Annotated, Any, Mapping, Optional

from pydantic import BeforeValidator

from .base import Component, Model
from .interactive import Button
from .types import TS, Children, JsonObject, OptUrl

__all__ = ["Card", "Grid", "Tab", "Tabs", "AccordionItem", "Accordion", "Carousel", "ListItem", "List"]


class Card(Component):
    """A container with a title, children and action buttons.

    The default container. Leading string arguments set the title; component
    arguments become children (extra strings become markdown children).

    Example:
        ``ui.Card("TAP · Fri 18:05", ui.Stat("Price", "$189"), actions=[ui.Button("Book", action="book")])``
    """

    group = "layout"
    positional = ("title",)
    varargs = "children"
    examples = [
        {
            "title": "Lisbon · 3 nights",
            "subtitle": "Fri – Mon",
            "children": [{"ui": "stat", "label": "Total", "value": "$642"}],
            "actions": [{"label": "Book", "action": "book_trip"}],
        }
    ]

    title: Optional[str] = None
    subtitle: Optional[str] = None
    image: OptUrl = None
    badge: Optional[str] = None
    children: Children = []
    actions: Optional[list[Button]] = None

    @classmethod
    def declared_actions(cls, props: Mapping[str, Any]) -> list[tuple[str, Optional[dict[str, Any]]]]:
        return [(b["action"], b.get("data")) for b in props.get("actions") or [] if isinstance(b, dict) and b.get("action")]


def _clamp_columns(value: Any) -> Any:
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return 2
    return max(1, min(4, n))


class Grid(Component):
    """Lay children out in columns (1–4).

    Example:
        ``ui.Grid(ui.Stat("A", 1), ui.Stat("B", 2), columns=2)``
    """

    group = "layout"
    positional = ("columns",)
    varargs = "children"

    columns: Annotated[int, BeforeValidator(_clamp_columns)] = 2
    children: Children = []


class Tab(Model):
    """One tab: a ``label`` and its ``children``."""

    __positional__ = ("label",)
    __varargs__ = "children"

    label: str
    children: Children = []


class Tabs(Component):
    """Group children into tabs.

    Example:
        ``ui.Tabs(ui.Tab("Overview", ui.Markdown("...")), ui.Tab("Data", ui.Table(...)))``
    """

    group = "layout"
    varargs = "tabs"

    tabs: Annotated[list[Tab], TS("{label: string, children: component[]}[]")]


class AccordionItem(Model):
    """One collapsible section: a ``title`` and its ``children``."""

    __positional__ = ("title",)
    __varargs__ = "children"

    title: str
    children: Children = []


class Accordion(Component):
    """Collapsible sections.

    Example:
        ``ui.Accordion(ui.AccordionItem("Details", ui.Markdown("...")))``
    """

    group = "layout"
    varargs = "items"

    items: Annotated[list[AccordionItem], TS("{title: string, children: component[]}[]")]


class Carousel(Component):
    """A horizontally scrolling row of children.

    Example:
        ``ui.Carousel(ui.Card("One"), ui.Card("Two"), ui.Card("Three"))``
    """

    group = "layout"
    varargs = "children"

    children: Children = []


class ListItem(Model):
    """One list row. With ``action``, the row is clickable and sends that action."""

    __positional__ = ("title", "subtitle")
    __str_field__ = "title"

    title: str
    subtitle: Optional[str] = None
    image: OptUrl = None
    meta: Optional[str] = None
    action: Optional[str] = None
    data: JsonObject = None


class List(Component):
    """A list of rows (title, subtitle, image); rows with an action are clickable.

    Example:
        ``ui.List(ui.ListItem("Hotel Avenida", "4.6 ★ · $180/night", action="pick_hotel"))``
    """

    group = "layout"
    varargs = "items"
    examples = [{"items": [{"title": "Hotel Avenida", "subtitle": "4.6 ★ · $180/night", "action": "pick_hotel",
                            "data": {"id": "h1"}}]}]

    items: list[ListItem]

    @classmethod
    def declared_actions(cls, props: Mapping[str, Any]) -> list[tuple[str, Optional[dict[str, Any]]]]:
        return [(i["action"], i.get("data")) for i in props.get("items") or [] if isinstance(i, dict) and i.get("action")]
