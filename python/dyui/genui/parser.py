"""Streaming parser for ```dyui fences in LLM text (SPEC §5).

:class:`FenceParser` is an incremental state machine that accepts text in
arbitrary chunks and emits events::

    parser = FenceParser(catalog)
    for chunk in llm_stream:
        for event in parser.feed(chunk):
            ...
    events = parser.close()

States: ``TEXT`` → (line ```` ```dyui ````) → ``BLOCK`` → (line ```` ``` ````) →
``TEXT``. A ```` ```json ```` fence is treated as ``dyui`` when its first object
has a ``"ui"`` key; a bare ``{"ui": ...}`` line outside any fence is accepted
too. Inside a block, objects may span several lines (pretty-printed JSON) and a
line may hold a JSON array of objects.

The final output (concatenated text + final nodes) is identical however the
input is chunked; only the number of throttled partial updates varies.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Union

from ..ui.base import new_id
from ..ui.types import to_json_text
from .partial_json import JSONObject, PartialJSONError, parse_partial, scan_depth
from .validate import ValidationFailure, component_source, partial_node, render_instance, validate_instance

__all__ = [
    "FenceParser",
    "TextDelta",
    "ComponentStart",
    "ComponentUpdate",
    "ComponentEnd",
    "ComponentError",
    "ParserEvent",
    "parse_text",
]

_DYUI_FENCE = re.compile(r"^`{3,}\s*dyui\s*$", re.I)
_JSON_FENCE = re.compile(r"^`{3,}\s*json\s*$", re.I)
_UI_START = re.compile(r'^\[?\s*\{\s*"ui"\s*:')
_INCOMPLETE = "incomplete component (the reply ended before it was finished)"
_SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")  # LLM-supplied ids end up in the DOM


@dataclass
class TextDelta:
    """Prose text (Markdown) outside of component blocks."""

    text: str


@dataclass
class ComponentStart:
    """A component began streaming; ``node`` is its first (streaming) preview."""

    id: str
    ui: str
    node: dict[str, Any]


@dataclass
class ComponentUpdate:
    """New partial props arrived; ``node`` is the updated streaming preview."""

    id: str
    props: dict[str, Any]
    node: dict[str, Any]


@dataclass
class ComponentEnd:
    """A component finished and validated; ``node`` is final (status ``done``).

    ``source`` is the custom component's LLM form (``None`` for built-ins).
    """

    id: str
    node: dict[str, Any]
    source: Optional[dict[str, Any]] = None


@dataclass
class ComponentError:
    """A component failed to parse or validate."""

    id: str
    error: str
    raw: str
    component: Optional[str] = None
    path: str = ""

    def node(self) -> dict[str, Any]:
        """The ``invalid`` node to render in place of the component."""
        from ..ui.base import invalid_node

        return invalid_node(self.id, self.raw, self.error)


ParserEvent = Union[TextDelta, ComponentStart, ComponentUpdate, ComponentEnd, ComponentError]


@dataclass
class _Slot:
    id: str
    ui: str
    streaming: bool
    last_len: int = 0
    last_t: float = 0.0
    last_json: str = ""


@dataclass
class _Unit:
    text: str = ""
    slots: dict[int, _Slot] = field(default_factory=dict)


class FenceParser:
    """Incremental parser turning LLM text into prose + component events.

    Args:
        catalog: Components the model may use (default: every built-in).
        id_factory: Returns fresh node ids (default ``c_<8hex>``).
        used_ids: Ids already used in the message (kept unique; shared and updated).
        clock: Monotonic clock used for update throttling.
        throttle_chars: Emit a partial update after this many new characters...
        throttle_seconds: ...or after this much time, whichever comes first.
    """

    def __init__(
        self,
        catalog: Any = None,
        *,
        id_factory: Optional[Callable[[], str]] = None,
        used_ids: Optional[set[str]] = None,
        clock: Callable[[], float] = time.monotonic,
        throttle_chars: int = 24,
        throttle_seconds: float = 0.06,
    ) -> None:
        if catalog is None:
            from .catalog import catalog as default_catalog

            catalog = default_catalog()
        self.catalog = catalog
        self._new_id = id_factory or new_id
        self.used_ids: set[str] = used_ids if used_ids is not None else set()
        self._clock = clock
        self._throttle_chars = throttle_chars
        self._throttle_s = throttle_seconds
        self._state = "TEXT"
        self._buf = ""
        self._line_start = True
        self._in_code = False
        self._unit = _Unit()
        self._held: list[str] = []
        self._events: list[ParserEvent] = []
        self._closed = False

    # ------------------------------------------------------------- public
    def feed(self, chunk: str) -> list[ParserEvent]:
        """Consume a chunk of model output and return the events it produced."""
        if self._closed:
            raise RuntimeError("parser is closed")
        if chunk:
            self._buf += chunk
            self._drain()
        return self._take()

    def close(self) -> list[ParserEvent]:
        """Flush at end of stream: finish complete lines, error a partial component."""
        if self._closed:
            return []
        self._closed = True
        if self._state == "TEXT":
            if self._buf:
                s = self._buf.strip()
                if not self._in_code and (_DYUI_FENCE.match(s) or _JSON_FENCE.match(s)):
                    pass  # a dangling opener with no content
                elif not self._in_code and self._is_bare_component(s):
                    self._bare_line(self._buf)
                else:
                    self._text(self._buf)
                self._buf = ""
        elif self._state == "MAYBE":
            rest, self._buf = self._buf, ""
            if rest:
                self._held.append(rest)
            self._decide_maybe(final=True)
        if self._state == "BLOCK":
            if self._buf:
                line, self._buf = self._buf, ""
                self._block_line(line)
            if self._state == "BLOCK" and self._unit.text.strip():
                self._fail_unit(_INCOMPLETE)
            self._state = "TEXT"
        return self._take()

    @property
    def in_block(self) -> bool:
        """True while inside a component block."""
        return self._state != "TEXT"

    # ------------------------------------------------------------ helpers
    def _take(self) -> list[ParserEvent]:
        out, self._events = self._events, []
        return out

    def _text(self, text: str) -> None:
        if not text:
            return
        if self._events and isinstance(self._events[-1], TextDelta):
            self._events[-1].text += text
        else:
            self._events.append(TextDelta(text))

    def _assign_id(self, obj: Any) -> str:
        cand = None
        if isinstance(obj, dict):
            keys = obj.key_order if isinstance(obj, JSONObject) else list(obj)
            if "id" in keys and "ui" in keys and keys.index("id") < keys.index("ui"):
                value = obj.get("id")
                if isinstance(value, str) and _SAFE_ID.fullmatch(value):
                    cand = value
        if cand is None or cand in self.used_ids:
            cand = self._new_id()
            while cand in self.used_ids:
                cand = self._new_id()
        self.used_ids.add(cand)
        return cand

    # ------------------------------------------------------------- driver
    def _drain(self) -> None:
        while self._buf:
            if self._state == "TEXT":
                if not self._text_step():
                    return
            elif self._state == "BLOCK":
                nl = self._buf.find("\n")
                if nl == -1:
                    self._block_partial(self._buf)
                    return
                line, self._buf = self._buf[:nl], self._buf[nl + 1 :]
                self._block_line(line)
            else:  # MAYBE (```json)
                nl = self._buf.find("\n")
                if nl == -1:
                    self._decide_maybe(final=False, pending=self._buf)
                    if self._state == "MAYBE":
                        return
                    continue
                line, self._buf = self._buf[: nl + 1], self._buf[nl + 1 :]
                self._held.append(line)
                self._decide_maybe(final=False)

    # --------------------------------------------------------------- TEXT
    def _could_be_special(self, partial: str) -> bool:
        t = partial.lstrip(" \t")
        if "```".startswith(t) or t.startswith("```"):
            return True
        if self._in_code:
            return False
        if t.startswith("{") or t.startswith("[{"):
            compact = re.sub(r"\s+", "", t)
            return compact.startswith(('{"ui"', '[{"ui"')) or '{"ui"'.startswith(compact) or '[{"ui"'.startswith(compact)
        return False

    def _text_step(self) -> bool:
        buf = self._buf
        if self._line_start:
            nl = buf.find("\n")
            if nl == -1:
                if self._could_be_special(buf):
                    return False
                self._text(buf)
                self._buf = ""
                self._line_start = False
                return False
            line, self._buf = buf[: nl + 1], buf[nl + 1 :]
            self._text_line(line)
            return True
        nl = buf.find("\n")
        if nl == -1:
            self._text(buf)
            self._buf = ""
            return False
        self._text(buf[: nl + 1])
        self._buf = buf[nl + 1 :]
        self._line_start = True
        return True

    def _text_line(self, line: str) -> None:
        s = line.strip()
        self._line_start = True
        if self._in_code:
            if s.startswith("```") and not s.strip("`").strip():
                self._in_code = False
            self._text(line)
            return
        if _DYUI_FENCE.match(s):
            self._state = "BLOCK"
            self._unit = _Unit()
            return
        if _JSON_FENCE.match(s):
            self._state = "MAYBE"
            self._held = [line]
            return
        if s.startswith("```"):
            self._in_code = True
            self._text(line)
            return
        if self._is_bare_component(s):
            self._bare_line(line)
            return
        self._text(line)

    def _is_bare_component(self, s: str) -> bool:
        if not _UI_START.match(s):
            return False
        try:
            value = json.loads(s)
        except ValueError:
            return False
        items = value if isinstance(value, list) else [value]
        return bool(items) and all(isinstance(v, dict) and isinstance(v.get("ui"), str) for v in items)

    def _bare_line(self, line: str) -> None:
        self._unit = _Unit(text=line.strip() + "\n")
        self._finish_unit()

    # -------------------------------------------------------------- MAYBE
    def _decide_maybe(self, *, final: bool, pending: str = "") -> None:
        content = "".join(self._held[1:]) + pending
        last = self._held[-1].strip() if len(self._held) > 1 else ""
        closed = len(self._held) > 1 and last.startswith("```") and not last.strip("`").strip()
        body = content
        if closed:
            body = "".join(self._held[1:-1])
        s = body.strip()
        verdict: Optional[bool] = None
        if s and s[0] not in "{[":
            verdict = False
        elif s and _UI_START.match(s):
            verdict = True
        elif s:
            depth, in_str = scan_depth(s)
            if depth <= 0 and not in_str:
                try:
                    value, _ = json.JSONDecoder().raw_decode(s)
                except ValueError:
                    value = None
                first = value[0] if isinstance(value, list) and value else value
                verdict = isinstance(first, dict) and "ui" in first
        if verdict is None and (closed or final):
            verdict = False
        if verdict is None:
            return
        held, self._held = self._held, []
        if verdict:
            self._state = "BLOCK"
            self._unit = _Unit()
            for line in held[1:]:
                if self._state != "BLOCK":
                    self._buf = line + self._buf
                    continue
                if line.endswith("\n"):
                    self._block_line(line[:-1])
                else:
                    self._buf = line + self._buf
        else:
            self._state = "TEXT"
            self._line_start = True
            self._text("".join(held))
            self._in_code = not closed  # any pending partial line stays in the buffer

    # -------------------------------------------------------------- BLOCK
    def _block_line(self, line: str) -> None:
        s = line.strip()
        unit = self._unit
        if s.startswith("```"):
            if unit.text.strip():
                self._fail_unit("component block closed before the JSON was complete")
            if _DYUI_FENCE.match(s) or _JSON_FENCE.match(s):
                return  # a re-opened block: keep going
            self._state = "TEXT"
            self._line_start = True
            rest = s.lstrip("`").strip()
            if rest:
                self._text(rest + "\n")
            return
        if not unit.text:
            if not s:
                return
            if s[0] not in "{[":
                self._error_new(f"expected a JSON object, got {s[:40]!r}", s)
                return
        elif _UI_START.match(s):
            depth, in_str = scan_depth(unit.text)
            if depth > 0 or in_str:
                self._fail_unit("malformed component JSON")
        self._unit.text += line + "\n"
        depth, in_str = scan_depth(self._unit.text)
        if depth <= 0 and not in_str:
            self._finish_unit()
        else:
            self._update_unit(self._unit.text)

    def _block_partial(self, pending: str) -> None:
        unit = self._unit
        s = pending.strip()
        if not unit.text:
            if not s or "```".startswith(s) or s.startswith("```") or s[0] not in "{[":
                return
        self._update_unit(unit.text + pending)

    def _update_unit(self, text: str) -> None:
        try:
            value = parse_partial(text)
        except PartialJSONError:
            return
        if isinstance(value, JSONObject):
            elements = [(0, value)]
        elif isinstance(value, list):
            elements = [(i, v) for i, v in enumerate(value) if isinstance(v, JSONObject)]
        else:
            return
        unit = self._unit
        now = self._clock()
        for index, obj in elements:
            slot = unit.slots.get(index)
            if slot is None:
                ui = obj.get("ui")
                if not isinstance(ui, str) or "ui" not in obj.key_order:
                    break
                streaming = self.catalog.get(ui) is not None
                slot = _Slot(id=self._assign_id(obj), ui=ui, streaming=streaming, last_len=len(text), last_t=now)
                unit.slots[index] = slot
                if streaming:
                    node = partial_node(obj, self.catalog, slot.id) or {
                        "id": slot.id, "ui": ui, "props": {}, "status": "streaming"}
                    slot.last_json = to_json_text(node)
                    self._events.append(ComponentStart(slot.id, ui, node))
                continue
            if not slot.streaming:
                continue
            if len(text) - slot.last_len < self._throttle_chars and now - slot.last_t < self._throttle_s:
                continue
            node = partial_node(obj, self.catalog, slot.id)
            slot.last_len, slot.last_t = len(text), now
            if node is None:
                continue
            encoded = to_json_text(node)
            if encoded != slot.last_json:
                slot.last_json = encoded
                props = {k: (str(v) if isinstance(v, str) else v) for k, v in obj.items()}
                self._events.append(ComponentUpdate(slot.id, props, node))

    def _decode_unit(self, text: str) -> list[Any]:
        s = text.strip()
        try:
            value = json.loads(s)
            return value if isinstance(value, list) else [value]
        except ValueError:
            pass
        values: list[Any] = []
        decoder = json.JSONDecoder()
        i = 0
        while i < len(s):
            while i < len(s) and s[i] in " \t\r\n,":
                i += 1
            if i >= len(s):
                break
            value, i = decoder.raw_decode(s, i)  # raises ValueError
            values.extend(value if isinstance(value, list) else [value])
        return values

    def _finish_unit(self) -> None:
        unit, self._unit = self._unit, _Unit()
        raw = unit.text.strip()
        try:
            values = self._decode_unit(raw)
        except ValueError as exc:
            self._fail_slots(unit, f"invalid JSON: {exc}", raw)
            return
        if not values:
            self._fail_slots(unit, "empty component", raw)
            return
        for index, value in enumerate(values):
            slot = unit.slots.get(index)
            nid = slot.id if slot else self._assign_id(value if isinstance(value, dict) else {})
            try:
                instance = validate_instance(value, self.catalog)
                node = render_instance(instance, nid, value)
            except ValidationFailure as failure:
                self._events.append(
                    ComponentError(nid, failure.message, failure.raw or to_json_text(value), failure.component, failure.path)
                )
                continue
            self._events.append(ComponentEnd(nid, node, component_source(instance)))
        for index, slot in unit.slots.items():
            if index >= len(values):
                self._events.append(ComponentError(slot.id, "component missing from final JSON", raw, slot.ui))

    def _fail_slots(self, unit: _Unit, error: str, raw: str) -> None:
        if not unit.slots:
            self._error_new(error, raw)
            return
        for slot in unit.slots.values():
            self._events.append(ComponentError(slot.id, error, raw, slot.ui))

    def _fail_unit(self, error: str) -> None:
        unit, self._unit = self._unit, _Unit()
        self._fail_slots(unit, error, unit.text.strip())

    def _error_new(self, error: str, raw: str) -> None:
        nid = self._assign_id({})
        self._events.append(ComponentError(nid, error, raw))


def parse_text(text: str, catalog: Any = None, **kwargs: Any) -> list[ParserEvent]:
    """Parse a complete text in one go (convenience for tests and history)."""
    parser = FenceParser(catalog, **kwargs)
    return parser.feed(text) + parser.close()
