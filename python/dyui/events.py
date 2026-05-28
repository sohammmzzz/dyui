"""Core event model for DyUI.

A ``UIEvent`` is the single unit of communication between a LangGraph agent and
the DyUI frontend. The agent emits events; the frontend renders a *card* for
each one, keyed by ``component`` and addressed by ``id`` so that later events
can update a card in place (e.g. ``pending`` -> ``done``).

The model is deliberately transport- and LLM-agnostic: it is just data. The
agent side puts it on LangGraph's ``custom`` stream channel (see ``emit.py``),
and the server side forwards it to the browser (see ``server.py``).
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# Marker key used to tag DyUI payloads on LangGraph's ``custom`` stream so we can
# distinguish them from any other data a graph might write to that channel.
DYUI_KEY = "__dyui__"

# Lifecycle of a card. Mirrors the proven open-scrum lifecycle but generalised:
#   pending -> the work behind the card has started, show a skeleton/loader
#   active  -> long-running work in progress, optionally with progress props
#   done    -> finished successfully, render the result
#   error   -> finished with a failure, render the error
Status = Literal["pending", "active", "done", "error"]


class UIEvent(BaseModel):
    """One dynamic-UI instruction emitted by an agent.

    Attributes:
        id: Stable identifier. Re-emitting with the same ``id`` updates the
            existing card instead of creating a new one. Auto-generated when
            omitted.
        component: Registry key that selects which React component renders this
            card on the frontend (e.g. ``"table"``, ``"stat"``, ``"html"``, or
            any custom component the consumer registered).
        props: Arbitrary JSON-serialisable data handed to that component.
        status: Lifecycle state (see ``Status``).
        surface: Named region/slot on the frontend that should host the card.
            Lets one agent drive several independent areas of a screen.
        title: Optional human-readable label shown in the card header.
        icon: Optional icon hint (a name your registry understands).
        accent: Optional accent-color hint (e.g. ``"cyan"``, ``"violet"``,
            ``"emerald"``, ``"rose"`` or any CSS color).
        error: Human-readable error message when ``status == "error"``.
        replace: When True (default) an event with an existing ``id`` replaces
            that card's props; when False, props are shallow-merged.
        ttl_ms: Optional auto-dismiss timeout in milliseconds. ``None`` keeps the
            card until explicitly replaced/removed; ``0`` also means sticky.
        ts: Emission timestamp (epoch seconds).
        meta: Free-form metadata bag for advanced consumers.
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    component: str
    props: dict[str, Any] = Field(default_factory=dict)
    status: Status = "done"
    surface: str = "default"
    title: Optional[str] = None
    icon: Optional[str] = None
    accent: Optional[str] = None
    error: Optional[str] = None
    replace: bool = True
    ttl_ms: Optional[int] = None
    ts: float = Field(default_factory=time.time)
    meta: dict[str, Any] = Field(default_factory=dict)

    def envelope(self) -> dict[str, Any]:
        """Wrap this event in the ``DYUI_KEY`` marker for the custom stream."""
        return {DYUI_KEY: self.model_dump()}


def is_dyui_payload(chunk: Any) -> bool:
    """True if ``chunk`` is a DyUI envelope coming off the custom stream."""
    return isinstance(chunk, dict) and DYUI_KEY in chunk


def parse_envelope(chunk: dict[str, Any]) -> "UIEvent":
    """Reconstruct a ``UIEvent`` from a custom-stream envelope."""
    return UIEvent.model_validate(chunk[DYUI_KEY])
