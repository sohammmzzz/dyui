"""Emitting UI events from inside a LangGraph agent.

The whole point of DyUI is that *any* node or tool in *any* LangGraph graph can
push a card to the UI with one call, regardless of which LLM (or no LLM) drives
the graph. We do this through LangGraph's first-class ``custom`` stream channel,
obtained via :func:`langgraph.config.get_stream_writer`. That writer is bound to
the currently executing run, so ``emit()`` "just works" inside nodes and tools
without threading any context object around.

If called outside a streaming run (e.g. in a unit test, or with a stream mode
that does not include ``"custom"``), emitting degrades gracefully: the event is
still returned to the caller, it simply is not written anywhere.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Optional

from .events import Status, UIEvent

try:  # LangGraph is an install-time dependency, but keep import defensive.
    from langgraph.config import get_stream_writer as _lg_get_stream_writer
except Exception:  # pragma: no cover - only if langgraph missing/old
    _lg_get_stream_writer = None


def _writer() -> Optional[Callable[[Any], None]]:
    """Return the active LangGraph custom-stream writer, or None if unavailable."""
    if _lg_get_stream_writer is None:
        return None
    try:
        return _lg_get_stream_writer()
    except Exception:
        # Raised when there is no active run / streaming context.
        return None


def emit(
    component: str,
    props: Optional[dict[str, Any]] = None,
    *,
    id: Optional[str] = None,
    status: Status = "done",
    surface: str = "default",
    title: Optional[str] = None,
    icon: Optional[str] = None,
    accent: Optional[str] = None,
    error: Optional[str] = None,
    replace: bool = True,
    ttl_ms: Optional[int] = None,
    meta: Optional[dict[str, Any]] = None,
) -> UIEvent:
    """Emit a single UI card to the frontend.

    Args:
        component: Registry key selecting the React component to render.
        props: JSON-serialisable data for that component.
        id: Reuse an existing card's id to update it in place.
        status: Lifecycle state (``pending`` | ``active`` | ``done`` | ``error``).
        surface / title / icon / accent / ttl_ms / meta: see :class:`UIEvent`.

    Returns:
        The :class:`UIEvent` that was emitted. Capture its ``.id`` to update the
        same card later (or use :func:`update`).
    """
    fields: dict[str, Any] = dict(
        component=component,
        props=props or {},
        status=status,
        surface=surface,
        title=title,
        icon=icon,
        accent=accent,
        error=error,
        replace=replace,
        ttl_ms=ttl_ms,
        meta=meta or {},
    )
    if id is not None:
        fields["id"] = id
    event = UIEvent(**fields)

    writer = _writer()
    if writer is not None:
        writer(event.envelope())
    return event


def update(
    event: "UIEvent | str",
    props: Optional[dict[str, Any]] = None,
    *,
    status: Optional[Status] = None,
    **kwargs: Any,
) -> UIEvent:
    """Re-emit an event under an existing id to update its card.

    Accepts either a :class:`UIEvent` (whose id/component are reused) or a raw
    id string (in which case ``component`` must be supplied via kwargs).
    """
    if isinstance(event, UIEvent):
        base = event.model_dump()
        base.update(kwargs)
        if props is not None:
            base["props"] = props
        if status is not None:
            base["status"] = status
        merged = UIEvent.model_validate(base)
        return emit(
            merged.component,
            id=merged.id,
            props=merged.props,
            status=merged.status,
            surface=merged.surface,
            title=merged.title,
            icon=merged.icon,
            accent=merged.accent,
            error=merged.error,
            replace=merged.replace,
            ttl_ms=merged.ttl_ms,
            meta=merged.meta,
        )
    # event is an id string
    component = kwargs.pop("component", None)
    if component is None:
        raise ValueError("update(id_str, ...) requires a component= keyword")
    return emit(
        component,
        id=event,
        props=props or {},
        status=status or "done",
        **kwargs,
    )


class Card:
    """A handle to a single card, for the common pending -> done pattern.

    Example::

        with Card("table", title="Search results") as card:
            rows = do_search()              # card is showing a skeleton
            card.done({"rows": rows})        # card now renders the table

    If the ``with`` block raises, the card is automatically flipped to ``error``.
    """

    def __init__(
        self,
        component: str,
        *,
        surface: str = "default",
        title: Optional[str] = None,
        icon: Optional[str] = None,
        accent: Optional[str] = None,
        props: Optional[dict[str, Any]] = None,
        ttl_ms: Optional[int] = None,
    ) -> None:
        self.component = component
        self.surface = surface
        self.title = title
        self.icon = icon
        self.accent = accent
        self.ttl_ms = ttl_ms
        self._event = emit(
            component,
            props or {},
            status="pending",
            surface=surface,
            title=title,
            icon=icon,
            accent=accent,
        )

    @property
    def id(self) -> str:
        return self._event.id

    def _reemit(self, status: Status, props: Optional[dict], error: Optional[str]) -> UIEvent:
        self._event = emit(
            self.component,
            props if props is not None else self._event.props,
            id=self._event.id,
            status=status,
            surface=self.surface,
            title=self.title,
            icon=self.icon,
            accent=self.accent,
            error=error,
            ttl_ms=self.ttl_ms,
        )
        return self._event

    def progress(self, props: dict[str, Any]) -> UIEvent:
        """Update an in-flight card while keeping it ``active``."""
        return self._reemit("active", props, None)

    def done(self, props: Optional[dict[str, Any]] = None) -> UIEvent:
        return self._reemit("done", props, None)

    def error(self, message: str, props: Optional[dict[str, Any]] = None) -> UIEvent:
        return self._reemit("error", props or {"error": message}, message)

    def __enter__(self) -> "Card":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is not None:
            self.error(str(exc))
        elif self._event.status == "pending":
            # Block exited cleanly but caller never resolved -> mark done.
            self.done()
        return False  # never suppress exceptions


def _default_props_from(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    return {"value": result}


def ui_tool(
    component: Optional[str] = None,
    *,
    surface: str = "default",
    title: Optional[str] = None,
    icon: Optional[str] = None,
    accent: Optional[str] = None,
    ttl_ms: Optional[int] = None,
    props_from: Optional[Callable[..., dict[str, Any]]] = None,
) -> Callable[[Callable], Callable]:
    """Decorate a node/tool so it auto-emits ``pending`` then ``done``/``error``.

    Works on both sync and async callables — ideal for LangGraph tool functions
    and node functions alike. The card's final props come from ``props_from`` (a
    function of the wrapped callable's return value) or, by default, the return
    value itself when it is a dict.

    Example::

        @ui_tool("stat", title="Weather", icon="cloud", accent="cyan")
        def get_weather(city: str) -> dict:
            return {"label": city, "value": fetch_temp(city), "unit": "°C"}
    """

    def decorator(fn: Callable) -> Callable:
        comp = component or fn.__name__
        derive = props_from or _default_props_from

        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                ev = emit(comp, {}, status="pending", surface=surface,
                          title=title or comp, icon=icon, accent=accent)
                try:
                    result = await fn(*args, **kwargs)
                except Exception as exc:
                    emit(comp, {"error": str(exc)}, id=ev.id, status="error",
                         surface=surface, title=title or comp, icon=icon,
                         accent=accent, error=str(exc))
                    raise
                emit(comp, derive(result), id=ev.id, status="done", surface=surface,
                     title=title or comp, icon=icon, accent=accent, ttl_ms=ttl_ms)
                return result

            return async_wrapper

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            ev = emit(comp, {}, status="pending", surface=surface,
                      title=title or comp, icon=icon, accent=accent)
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                emit(comp, {"error": str(exc)}, id=ev.id, status="error",
                     surface=surface, title=title or comp, icon=icon,
                     accent=accent, error=str(exc))
                raise
            emit(comp, derive(result), id=ev.id, status="done", surface=surface,
                 title=title or comp, icon=icon, accent=accent, ttl_ms=ttl_ms)
            return result

        return sync_wrapper

    return decorator
