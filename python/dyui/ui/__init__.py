"""DyUI components.

Every built-in component is a pydantic model with a snake_case LLM name::

    from dyui import ui

    ui.Stat("Revenue", "$48k", delta="+12%")
    ui.Table(["City", "Temp"], [["Lisbon", 24]])
    ui.Card("Title", ui.Stat("Users", 1200), actions=[ui.Button("Open", action="open")])
    ui.Buttons(ui.Button("Book", action="book"))

Subclass :class:`Component` to make your own (see ``@app.component``).
"""
from __future__ import annotations

from .agent import Plan, PlanItem, Reasoning, Step
from .base import Component, ComponentInfo, Model, new_id
from .content import Badge, Badges, Callout, Code, Divider, Markdown, Quote, Source, Sources
from .data import (
    Chart,
    Json,
    KeyValue,
    KeyValueItem,
    Progress,
    Series,
    Stat,
    StatItem,
    Stats,
    Table,
    Timeline,
    TimelineItem,
)
from .developer import Html, Invalid
from .interactive import Button, Buttons, Choice, Confirm, Field, Form, QuickReplies, Rating
from .layout import Accordion, AccordionItem, Card, Carousel, Grid, List, ListItem, Tab, Tabs
from .media import Audio, File, Gallery, GalleryImage, Image, LinkPreview, Video
from .registry import BUILTINS, GROUPS, LLM_BUILTINS, builtin, builtins_in
from .types import is_safe_url

__all__ = [
    "Component",
    "ComponentInfo",
    "Model",
    "new_id",
    "is_safe_url",
    "BUILTINS",
    "LLM_BUILTINS",
    "GROUPS",
    "builtin",
    "builtins_in",
    # content
    "Markdown", "Callout", "Code", "Quote", "Source", "Sources", "Badge", "Badges", "Divider",
    # data
    "Table", "Stat", "StatItem", "Stats", "KeyValue", "KeyValueItem", "Chart", "Series", "Progress",
    "Timeline", "TimelineItem", "Json",
    # media
    "Image", "GalleryImage", "Gallery", "Video", "Audio", "File", "LinkPreview",
    # interactive
    "Button", "Buttons", "QuickReplies", "Choice", "Field", "Form", "Confirm", "Rating",
    # layout
    "Card", "Grid", "Tab", "Tabs", "AccordionItem", "Accordion", "Carousel", "ListItem", "List",
    # agent
    "Step", "Reasoning", "PlanItem", "Plan",
    # developer
    "Html", "Invalid",
]
