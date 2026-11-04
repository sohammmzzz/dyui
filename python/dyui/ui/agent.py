"""Agent components: step, reasoning, plan."""
from __future__ import annotations

from typing import Optional

from .base import Component, Model
from .types import JsonValue, lax_enum

__all__ = ["Step", "Reasoning", "PlanItem", "Plan"]

StepStatus = lax_enum(
    "pending", "running", "done", "error",
    aliases={"complete": "done", "completed": "done", "success": "done", "failed": "error", "active": "running"},
)
PlanStatus = lax_enum(
    "pending", "active", "done", "error", "skipped",
    aliases={"complete": "done", "completed": "done", "running": "active", "in_progress": "active",
             "todo": "pending", "failed": "error", "skip": "skipped"},
)


class Step(Component):
    """A tool or agent step with a status.

    Usually produced by ``chat.step(...)``; usable directly too.

    Example:
        ``ui.Step("Search flights", "done", type="search", duration_ms=840)``
    """

    group = "agent"
    positional = ("title", "status")

    title: str
    status: StepStatus = "done"
    type: Optional[str] = None
    input: JsonValue = None
    output: JsonValue = None
    duration_ms: Optional[int] = None


class Reasoning(Component):
    """A collapsible block of reasoning.

    Usually produced by yielding ``dyui.Reasoning`` deltas.

    Example:
        ``ui.Reasoning("Comparing the two fares...", duration_ms=1200)``
    """

    group = "agent"
    positional = ("text",)

    text: str
    duration_ms: Optional[int] = None


class PlanItem(Model):
    """One plan entry: ``title`` and ``status``."""

    __positional__ = ("title", "status")
    __str_field__ = "title"

    title: str
    status: PlanStatus = "pending"


class Plan(Component):
    """A live checklist plan with per-item status.

    Example:
        ``ui.Plan(ui.PlanItem("Find flights", "done"), ui.PlanItem("Book hotel", "active"), title="Trip plan")``
    """

    group = "agent"
    varargs = "items"
    examples = [{"title": "Plan", "items": [{"title": "Find flights", "status": "done"},
                                             {"title": "Book hotel", "status": "active"}]}]

    title: Optional[str] = None
    items: list[PlanItem]
