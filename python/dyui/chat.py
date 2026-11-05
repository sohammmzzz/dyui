"""Per-conversation runtime objects handed to your handlers.

- :class:`Message` — the user message passed to ``@app.on_message``.
- :class:`Action` — a component interaction passed to ``@app.on_action``.
- :class:`Feedback` — a thumbs up/down passed to ``@app.on_feedback``.
- :class:`File` — an uploaded file.
- :class:`Chat` — the conversation: history, session state, ``send``, ``step``, ``ask``.
- :class:`Step` — a live, timed step ("Searching flights…") rendered in the reply.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable, Optional

from .genui import (
    ComponentEnd,
    ComponentError,
    ComponentStart,
    ComponentUpdate,
    FenceParser,
    TextDelta,
    serialize_history,
)
from ._jsonsafe import finite
from .parts import Reasoning
from .store.base import now_ms
from .ui.base import Component, new_id

if TYPE_CHECKING:  # pragma: no cover
    from .app import App

log = logging.getLogger("dyui")

__all__ = ["Message", "File", "Action", "Feedback", "Starter", "Chat", "Step"]


# --------------------------------------------------------------------- values
@dataclass
class File:
    """An uploaded file attached to a user message."""

    id: str
    name: str
    type: str
    size: int
    path: Path
    url: str

    @classmethod
    def from_record(cls, rec: dict[str, Any]) -> "File":
        return cls(
            id=rec["id"], name=rec.get("name", "file"), type=rec.get("type", "application/octet-stream"),
            size=int(rec.get("size", 0)), path=Path(rec.get("path", "")), url=f"api/files/{rec['id']}",
        )

    def ref(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "type": self.type, "size": self.size, "url": self.url}


@dataclass
class Action:
    """A component interaction (button click, form submit, approval…).

    Attributes:
        name: The action name declared by the component (e.g. ``"book_flight"``).
        data: Static data declared alongside the action.
        values: What the user entered/chose (form fields, ``{"confirmed": bool}``…).
        label: Human-readable label of what was clicked.
        message_id: The assistant message holding the component.
        component_id: The component's node id.
    """

    name: str
    data: dict[str, Any] = field(default_factory=dict)
    values: dict[str, Any] = field(default_factory=dict)
    label: str = ""
    message_id: str = ""
    component_id: str = ""


@dataclass
class Message:
    """The user's message, passed to ``@app.on_message``.

    Attributes:
        id: Message id.
        text: The text to answer. For a turn created from an unhandled action this
            is the LLM-friendly form ``"[action:name] {...}"``.
        files: Uploaded files.
        action: Set when this turn came from an action with no handler.
    """

    id: str
    text: str
    files: list[File] = field(default_factory=list)
    action: Optional[Action] = None


@dataclass
class Feedback:
    """Thumbs up (1), down (-1) or cleared (0) on an assistant message."""

    message_id: str
    value: int
    comment: Optional[str] = None


@dataclass
class Starter:
    """A suggested first message on the welcome screen."""

    label: str
    message: Optional[str] = None
    icon: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "message": self.message or self.label, "icon": self.icon}


# --------------------------------------------------------------------- turn
class Turn:
    """One streamed response: an event queue plus the assistant message being built."""

    def __init__(self, app: "App", thread: dict[str, Any], queue: "asyncio.Queue[Any]") -> None:
        self.app = app
        self.thread = thread
        self.queue = queue
        self.message: Optional[dict[str, Any]] = None
        self._parser: Optional[FenceParser] = None
        self._used_ids: set[str] = set()
        self._started = 0.0
        self._reasoning_started: Optional[float] = None

    # ---- events
    def emit(self, event: str, data: Any) -> None:
        self.queue.put_nowait((event, data))

    # ---- message lifecycle
    def ensure_message(self) -> dict[str, Any]:
        if self.message is None:
            self.message = {"id": new_id("m"), "role": "assistant", "created_at": now_ms(), "parts": [], "status": "streaming"}
            self._started = time.monotonic()
            self._parser = FenceParser(self.app.untrusted_catalog, used_ids=self._used_ids)
            self.emit("message_start", {"id": self.message["id"], "role": "assistant", "created_at": self.message["created_at"]})
        return self.message

    async def persist(self) -> None:
        if self.message is not None:
            await self.app.store.put_message(self.thread["id"], self.message)

    async def end_message(self, status: str = "done") -> None:
        if self.message is None:
            return
        self._flush_parser()
        self._close_reasoning()
        self.message["status"] = status
        await self.persist()
        self.emit("message_end", {"id": self.message["id"], "status": status,
                                  "duration_ms": int((time.monotonic() - self._started) * 1000)})
        self.message = None
        self._parser = None

    # ---- parts
    def _parts(self) -> list[dict[str, Any]]:
        return self.ensure_message()["parts"]

    def _text(self, delta: str) -> None:
        if not delta:
            return
        parts = self._parts()
        if parts and parts[-1]["type"] == "text":
            parts[-1]["text"] += delta
        else:
            parts.append({"type": "text", "text": delta})
        self.emit("text", {"message_id": self.message["id"], "delta": delta})  # type: ignore[index]

    def upsert_node(self, node: dict[str, Any]) -> None:
        node = finite(node)
        parts = self._parts()
        for part in parts:
            if part["type"] == "ui" and part["node"]["id"] == node["id"]:
                part["node"] = node
                break
        else:
            parts.append({"type": "ui", "node": node})
        self.emit("ui", {"message_id": self.message["id"], "node": node})  # type: ignore[index]

    def upsert_step(self, step: dict[str, Any]) -> None:
        step = finite(step)
        parts = self._parts()
        for part in parts:
            if part["type"] == "step" and part["step"]["id"] == step["id"]:
                part["step"] = dict(step)
                break
        else:
            parts.append({"type": "step", "step": dict(step)})
        self.emit("step", {"message_id": self.message["id"], "step": dict(step)})  # type: ignore[index]

    def _reasoning(self, delta: str) -> None:
        if not delta:
            return
        parts = self._parts()
        if not (parts and parts[-1]["type"] == "reasoning"):
            parts.append({"type": "reasoning", "text": ""})
            self._reasoning_started = time.monotonic()
        parts[-1]["text"] += delta
        self.emit("reasoning", {"message_id": self.message["id"], "delta": delta})  # type: ignore[index]

    def _close_reasoning(self) -> None:
        if self._reasoning_started is None or self.message is None:
            return
        for part in reversed(self.message["parts"]):
            if part["type"] == "reasoning" and "duration_ms" not in part:
                part["duration_ms"] = int((time.monotonic() - self._reasoning_started) * 1000)
                break
        self._reasoning_started = None

    # ---- parser
    def _apply(self, events: list[Any]) -> None:
        for ev in events:
            if isinstance(ev, TextDelta):
                self._text(ev.text)
            elif isinstance(ev, (ComponentStart, ComponentUpdate, ComponentEnd)):
                self.upsert_node(ev.node)
            elif isinstance(ev, ComponentError):
                self.upsert_node(ev.node())

    def _flush_parser(self) -> None:
        if self._parser is not None:
            self._apply(self._parser.close())
            self._parser = FenceParser(self.app.untrusted_catalog, used_ids=self._used_ids)

    # ---- items yielded by handlers
    def add(self, item: Any) -> Optional[dict[str, Any]]:
        """Render one yielded item; returns the node for components."""
        if item is None:
            return None
        if isinstance(item, (list, tuple)):
            last = None
            for sub in item:
                last = self.add(sub) or last
            return last
        self.ensure_message()
        if isinstance(item, str):
            if self._reasoning_started is not None:
                self._close_reasoning()
            self._apply(self._parser.feed(item))  # type: ignore[union-attr]
            return None
        if isinstance(item, Reasoning):
            self._reasoning(item.text)
            return None
        self._flush_parser()
        self._close_reasoning()
        if isinstance(item, Component):
            node = item.to_node()
        elif isinstance(item, dict) and "ui" in item:
            node = self.app.untrusted_catalog.validate(item)
        else:
            log.warning("dyui: don't know how to render %r; showing it as text", type(item).__name__)
            self._text(str(item))
            return None
        self._used_ids.add(node["id"])
        self.upsert_node(node)
        return node

    def resolve(self, node_id: str, resolved: dict[str, Any]) -> bool:
        """Mark an interactive node in the live message as resolved."""
        if self.message is None:
            return False
        node = find_node(self.message["parts"], node_id)
        if node is None:
            return False
        node.setdefault("props", {})["__resolved__"] = resolved
        top = top_level_node(self.message["parts"], node_id)
        self.emit("ui", {"message_id": self.message["id"], "node": top})
        return True


def _walk(node: dict[str, Any]):
    yield node
    for child in node.get("children") or []:
        if isinstance(child, dict):
            yield from _walk(child)
    for value in (node.get("props") or {}).values():
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    for child in item.get("children") or []:
                        if isinstance(child, dict) and "ui" in child:
                            yield from _walk(child)


def find_node(parts: list[dict[str, Any]], node_id: str) -> Optional[dict[str, Any]]:
    """Find a (possibly nested) UI node by id in a message's parts."""
    for part in parts:
        if part.get("type") == "ui":
            for node in _walk(part["node"]):
                if node.get("id") == node_id:
                    return node
    return None


def top_level_node(parts: list[dict[str, Any]], node_id: str) -> Optional[dict[str, Any]]:
    """The top-level node of the ui part that contains ``node_id``."""
    for part in parts:
        if part.get("type") == "ui":
            for node in _walk(part["node"]):
                if node.get("id") == node_id:
                    return part["node"]
    return None


_DEFAULT_ACTIONS = {"choice": "choice", "form": "form_submit", "confirm": "confirm", "rating": "rating"}


def declared_action_entries(node: dict[str, Any]) -> list[tuple[str, Optional[dict[str, Any]]]]:
    """Every ``(action, static data)`` pair a rendered node may legitimately send."""
    entries: list[tuple[str, Optional[dict[str, Any]]]] = []

    def scan(value: Any) -> None:
        if isinstance(value, dict):
            act = value.get("action")
            if isinstance(act, str) and act:
                data = value.get("data")
                entries.append((act, data if isinstance(data, dict) else None))
            for v in value.values():
                scan(v)
        elif isinstance(value, list):
            for v in value:
                scan(v)

    props = node.get("props") or {}
    scan(props)
    default = _DEFAULT_ACTIONS.get(str(node.get("ui")))
    if default and not any(name == default for name, _ in entries):
        data = props.get("data")
        entries.append((default, data if isinstance(data, dict) else None))
    return entries


def declared_actions(node: dict[str, Any]) -> set[str]:
    """Every action name a rendered node may legitimately send."""
    return {name for name, _ in declared_action_entries(node)}


_FORGED = object()


def trusted_action_data(node: dict[str, Any], name: str, client_data: Any) -> Any:
    """The server-side static ``data`` for an action, never the client's copy.

    The client echoes the data of the button it clicked; it's only used to tell
    several same-named buttons apart. Returns ``_FORGED`` if ``name`` isn't declared,
    or if the node declares different data for it and the client's matches none.
    """
    options = [data or {} for act, data in declared_action_entries(node) if act == name]
    if not options:
        return _FORGED
    claimed = client_data if isinstance(client_data, dict) else {}
    for data in options:
        if data == claimed:
            return dict(data)
    distinct = {to_key(d) for d in options}
    if len(distinct) == 1:
        return dict(options[0])  # one possible payload: the server's copy wins
    return _FORGED


def to_key(data: dict[str, Any]) -> str:
    import json

    return json.dumps(data, sort_keys=True, default=str)


def is_forged(value: Any) -> bool:
    return value is _FORGED


# --------------------------------------------------------------------- step
class Step:
    """A live step in the assistant reply (use via ``async with chat.step(...)``).

    Attributes:
        title: What's happening ("Searching flights").
        type: A free-form kind (``tool``, ``search``, ``code``…).
        input: Optional input shown when expanded.
        output: Optional output shown when expanded.
    """

    def __init__(self, turn: Turn, title: str, type: str = "tool", parent_id: Optional[str] = None) -> None:
        self._turn = turn
        self.id = new_id("s")
        self.title = title
        self.type = type
        self.input: Any = None
        self.output: Any = None
        self.logs: list[str] = []
        self.parent_id = parent_id
        self._status = "pending"
        self._started = time.monotonic()
        self._started_at = now_ms()
        self._duration: Optional[int] = None

    def _dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"id": self.id, "title": self.title, "type": self.type, "status": self._status,
                             "started_at": self._started_at, "parent_id": self.parent_id, "logs": list(self.logs)}
        if self.input is not None:
            d["input"] = _jsonable(self.input)
        if self.output is not None:
            d["output"] = _jsonable(self.output)
        if self._duration is not None:
            d["duration_ms"] = self._duration
        return d

    def _emit(self) -> None:
        self._turn.upsert_step(self._dict())

    async def log(self, text: str) -> None:
        """Append a log line to the step (shown when expanded)."""
        self.logs.append(str(text))
        self._emit()

    async def __aenter__(self) -> "Step":
        self._turn._flush_parser()
        self._status = "running"
        self._emit()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        self._duration = int((time.monotonic() - self._started) * 1000)
        if exc_type is not None and not issubclass(exc_type, asyncio.CancelledError):
            self._status = "error"
            if self.output is None and exc is not None:
                self.output = f"{exc_type.__name__}: {exc}"
        else:
            self._status = "done" if exc_type is None else "error"
        self._emit()
        return False

    def __call__(self, fn: Callable[..., Any]) -> Callable[..., Any]:  # decorator form
        title, type_ = self.title, self.type
        chat_turn = self._turn

        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with Step(chat_turn, title, type_) as s:
                s.input = {"args": args, "kwargs": kwargs} if (args or kwargs) else None
                result = fn(*args, **kwargs)
                if inspect.isawaitable(result):
                    result = await result
                s.output = result
                return result

        return wrapper


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return str(value)


# --------------------------------------------------------------------- chat
class Chat:
    """The conversation, handed to every handler.

    Attributes:
        thread_id: The conversation id.
        user_id: The anonymous browser identity (``dyui_uid`` cookie).
        session: Per-conversation scratch state, persisted with the thread (JSON-serializable).
    """

    def __init__(self, app: "App", thread: dict[str, Any], turn: Turn, messages: list[dict[str, Any]]) -> None:
        self._app = app
        self._thread = thread
        self._turn = turn
        self._messages = messages
        self.thread_id: str = thread["id"]
        self.user_id: str = thread.get("user_id", "")
        self.session: dict[str, Any] = dict(thread.get("session") or {})

    @property
    def messages(self) -> list[dict[str, Any]]:
        """All persisted messages (protocol ``Message`` dicts, oldest first)."""
        return list(self._messages)

    @property
    def history(self) -> list[dict[str, str]]:
        """OpenAI-style ``[{"role", "content"}]`` history, text only.

        Components the assistant showed are re-serialized as compact ``dyui``
        blocks so the model keeps context of the UI it rendered.
        """
        current = self._turn.message["id"] if self._turn.message else None
        return serialize_history(m for m in self._messages if m.get("id") != current)

    async def send(self, *items: Any) -> None:
        """Append text and/or components to the current assistant reply."""
        for item in items:
            self._turn.add(item)

    def step(self, title: str, type: str = "tool") -> Step:
        """A live step: ``async with chat.step("Searching") as s: s.output = ...``."""
        self._turn.ensure_message()
        return Step(self._turn, title, type)

    async def ask(self, component: Any, timeout: Optional[float] = None) -> Action:
        """Render an interactive component and wait for the user's response.

        Args:
            component: A ``ui.Confirm``, ``ui.Form``, ``ui.Choice``, ``ui.Buttons``…
            timeout: Seconds to wait (``None`` waits until the user answers or leaves).

        Returns:
            The :class:`Action` the user took.

        Raises:
            asyncio.TimeoutError: If ``timeout`` elapses first.
        """
        node = self._turn.add(component)
        if node is None:
            raise TypeError("chat.ask() needs a component")
        await self._turn.persist()
        fut: asyncio.Future[Action] = asyncio.get_running_loop().create_future()
        key = (self.thread_id, node["id"])
        self._app._pending[key] = (fut, self._turn)
        try:
            return await asyncio.wait_for(fut, timeout)
        finally:
            self._app._pending.pop(key, None)

    async def set_title(self, title: str) -> None:
        """Set the conversation title (stops auto-titling)."""
        title = str(title).strip()[:120] or "New chat"
        await self._app.store.update_thread(self.thread_id, title=title, title_locked=True, updated_at=now_ms())
        self._thread["title"] = title
        self._thread["title_locked"] = True
        self._turn.emit("title", {"thread_id": self.thread_id, "title": title})

    async def _save_session(self) -> None:
        await self._app.store.update_thread(self.thread_id, session=self.session)


async def iterate(fn: Callable[..., Any], *args: Any) -> AsyncIterator[Any]:
    """Call a handler of any shape and iterate what it yields/returns."""
    if inspect.isasyncgenfunction(fn):
        async for item in fn(*args):
            yield item
        return
    if inspect.isgeneratorfunction(fn):
        gen = fn(*args)
        done = object()
        while True:
            item = await asyncio.to_thread(next, gen, done)
            if item is done:
                return
            yield item
    if inspect.iscoroutinefunction(fn):
        result = await fn(*args)
    else:
        result = await asyncio.to_thread(fn, *args)
        if inspect.isawaitable(result):
            result = await result
    if inspect.isasyncgen(result):
        async for item in result:
            yield item
    elif result is not None:
        yield result
