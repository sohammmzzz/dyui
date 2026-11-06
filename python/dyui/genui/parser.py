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
from .._jsonsafe import MAX_DEPTH
from .partial_json import JSONObject, PartialJSONError, ScanState, parse_partial, scan_depth
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

_DYUI_FENCE = re.compile(r"^(?:`{3,}|~{3,})\s*dyui\s*$", re.I)
_JSON_FENCE = re.compile(r"^(?:`{3,}|~{3,})\s*json\s*$", re.I)
# CommonMark fence: 3+ backticks or tildes, then an info string (no backticks in it).
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})[ \t]*([^`]*?)[ \t]*$")
# A dyui opener that isn't on its own line ("Here you go ```dyui") — common LLM slip.
_INLINE_OPENER = re.compile(r"^(.*?)(`{3,}|~{3,})[ \t]*dyui[ \t]*$", re.I | re.S)
# The end of a partial line that could still grow into such an opener: hold it back.
_OPENER_TAIL = re.compile(r"(?:`+|~+)[ \t]*(?:d(?:y(?:u(?:i)?)?)?)?[ \t]*$", re.I)


@dataclass(frozen=True)
class _Fence:
    char: str
    size: int
    info: str  # as written

    @property
    def kind(self) -> str:
        return self.info.lower()

    def closes(self, other: Optional["_Fence"]) -> bool:
        """Whether ``other`` (a fence line) closes a block opened by ``self`` (CommonMark)."""
        return other is not None and other.char == self.char and other.size >= self.size


def _fence(s: str) -> Optional[_Fence]:
    m = _FENCE_RE.match(s)
    if not m:
        return None
    return _Fence(m.group(1)[0], len(m.group(1)), m.group(2).strip())


def _could_be_fence(t: str) -> bool:
    """A partial line that is, or could still become, a fence line."""
    if not t or t[0] not in "`~":
        return False
    run = len(t) - len(t.lstrip(t[0]))
    return run >= 3 or run == len(t)


_DEFAULT_FENCE = _Fence("`", 3, "dyui")
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
    text: str = ""                                    # complete lines of the current component
    slots: dict[int, _Slot] = field(default_factory=dict)
    scan: ScanState = field(default_factory=ScanState)        # depth state after ``text``
    pending: list[str] = field(default_factory=list)          # chunks of the in-progress line
    pending_len: int = 0
    pending_scan: Optional[ScanState] = None                  # depth state after text + pending
    parse_len: int = 0                                         # size at the last partial parse...
    parse_t: float = float("-inf")                             # ...when it ran...
    parse_cost: float = 0.0                                    # ...and how long it took
    skipping: bool = False                                     # dropping an oversized component
    head_ok: Optional[bool] = None                             # first line starts like JSON?

    @property
    def size(self) -> int:
        return len(self.text) + self.pending_len

    def take_pending(self) -> str:
        out = "".join(self.pending)
        self.pending, self.pending_len, self.pending_scan, self.head_ok = [], 0, None, None
        return out


#: A component line larger than this fails as "too large" (and the rest of it is skipped).
MAX_COMPONENT_CHARS = 512 * 1024
#: Streaming previews stop above this size; the component still renders when it completes.
MAX_PARTIAL_CHARS = 64 * 1024


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
        self._code_fence: Optional[_Fence] = None   # fence of the open (non-dyui) code block
        self._fence: _Fence = _DEFAULT_FENCE        # fence of the open dyui / json block
        self._after_bare = False                    # previous line was a bare component line
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
                inline = None if self._in_code else _INLINE_OPENER.match(self._buf)
                if not self._in_code and (_DYUI_FENCE.match(s) or _JSON_FENCE.match(s)):
                    pass  # a dangling opener with no content
                elif inline is not None:
                    self._text(inline.group(1))  # dangling inline opener: keep only the prose
                elif not self._in_code and self._line_start and self._is_bare_component(s):
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
            if self._buf or self._unit.pending:
                line = self._unit.take_pending() + self._buf
                self._buf = ""
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
                    # Park the partial line in the unit so later chunks never re-copy or
                    # re-search it (keeps a long component line linear, not quadratic).
                    chunk, self._buf = self._buf, ""
                    self._block_partial(chunk)
                    return
                head, self._buf = self._buf[:nl], self._buf[nl + 1 :]
                self._block_line(self._unit.take_pending() + head)
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
        if len(partial) > MAX_PARTIAL_CHARS:
            return False  # stop holding a huge line back; it streams as prose
        t = partial[:64].lstrip(" \t")
        if _could_be_fence(t):
            return True
        if self._in_code:
            return False
        if _OPENER_TAIL.search(partial[-80:]):
            return True  # prose that may end in an inline ```dyui opener
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
            hold = None if self._in_code or len(buf) > MAX_PARTIAL_CHARS else _OPENER_TAIL.search(buf)
            if hold is not None:
                # the line so far might end in "```dyui": keep that tail back until we know
                self._text(buf[: hold.start()])
                self._buf = buf[hold.start():]
            else:
                self._text(buf)
                self._buf = ""
            return False
        rest_of_line = buf[:nl]
        inline = None if self._in_code else _INLINE_OPENER.match(rest_of_line)
        self._buf = buf[nl + 1 :]
        self._line_start = True
        self._after_bare = False
        if inline is not None:
            self._text(inline.group(1))
            self._open_block(_fence(inline.group(2) + "dyui") or _DEFAULT_FENCE)
            return True
        self._text(buf[: nl + 1])
        return True

    def _open_block(self, fence: _Fence) -> None:
        self._state = "BLOCK"
        self._fence = fence
        self._unit = _Unit()

    def _text_line(self, line: str) -> None:
        s = line.strip()
        self._line_start = True
        after_bare, self._after_bare = self._after_bare, False
        fence = _fence(s)
        if self._in_code:
            if fence is not None and not fence.info and self._code_fence is not None and self._code_fence.closes(fence):
                self._in_code = False
                self._code_fence = None
            self._text(line)
            return
        if fence is not None and fence.kind == "dyui":
            self._open_block(fence)
            return
        if fence is not None and fence.kind == "json":
            self._state = "MAYBE"
            self._fence = fence
            self._held = [line]
            return
        if fence is not None:
            if after_bare and not fence.info:
                return  # stray closing fence after a fenceless component line: swallow it
            self._in_code = True
            self._code_fence = fence
            self._text(line)
            return
        inline = _INLINE_OPENER.match(line.rstrip("\r\n"))
        if inline is not None and inline.group(1).strip():
            self._text(inline.group(1))
            self._open_block(_fence(inline.group(2) + "dyui") or _DEFAULT_FENCE)
            return
        if self._is_bare_component(s):
            self._bare_line(line)
            self._after_bare = True
            return
        self._text(line)

    def _is_bare_component(self, s: str) -> bool:
        if not _UI_START.match(s):
            return False
        try:
            value = json.loads(s)
        except (ValueError, RecursionError):
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
        last_fence = _fence(last) if len(self._held) > 1 else None
        closed = last_fence is not None and not last_fence.info and self._fence.closes(last_fence)
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
                except (ValueError, RecursionError):
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
            self._code_fence = None if closed else self._fence

    # -------------------------------------------------------------- BLOCK
    def _block_line(self, line: str) -> None:
        s = line.strip()
        unit = self._unit
        fence = _fence(s)
        closing = self._fence.closes(fence)
        if unit.skipping:
            # dropping the rest of an oversized / over-deep component until the block ends
            if not closing:
                return
            self._unit = unit = _Unit()
        if closing:
            assert fence is not None
            if unit.text.strip():
                self._fail_unit("component block closed before the JSON was complete")
            if fence.kind in ("dyui", "json"):
                return  # a re-opened block: keep going
            self._state = "TEXT"
            self._line_start = True
            if fence.info:
                self._text(fence.info + "\n")
            return
        if not unit.text:
            if not s:
                return
            if s[0] not in "{[":
                self._error_new(f"expected a JSON object, got {s[:40]!r}", s)
                return
        elif _UI_START.match(s):
            if unit.scan.depth > 0 or unit.scan.in_str:
                self._fail_unit("malformed component JSON")
        unit = self._unit
        unit.text += line + "\n"
        unit.scan.feed(line + "\n")
        if self._over_limits(unit.scan, len(unit.text)):
            return
        if unit.scan.depth <= 0 and not unit.scan.in_str:
            self._finish_unit()
        else:
            self._maybe_update(unit)

    def _block_partial(self, chunk: str) -> None:
        unit = self._unit
        if unit.skipping:
            # keep just enough of the line to recognise a closing fence
            if unit.pending_len < 8:
                unit.pending.append(chunk[: 8 - unit.pending_len])
                unit.pending_len += min(len(chunk), 8 - unit.pending_len)
            return
        unit.pending.append(chunk)
        unit.pending_len += len(chunk)
        if unit.pending_scan is None:
            unit.pending_scan = unit.scan.copy()
        unit.pending_scan.feed(chunk)
        if self._over_limits(unit.pending_scan, unit.size):
            return
        if not unit.text and not self._line_looks_like_json(unit):
            return
        self._maybe_update(unit)

    @staticmethod
    def _line_looks_like_json(unit: _Unit) -> bool:
        """Whether the in-progress first line starts like a JSON value (not a fence).

        Looks at a few leading characters only and caches the verdict, so it stays
        O(1) per chunk however long the line grows.
        """
        if unit.head_ok is not None:
            return unit.head_ok
        head = ""
        for chunk in unit.pending:
            head += chunk.lstrip() if not head else chunk
            if len(head) >= 3:
                break
        if not head or _could_be_fence(head[:3]):
            return False  # undecided yet / a fence line
        unit.head_ok = head[0] in "{["
        return unit.head_ok

    def _over_limits(self, scan: ScanState, size: int) -> bool:
        """Fail the current component if it is too large or nested too deeply."""
        if size > MAX_COMPONENT_CHARS:
            error = f"component is too large (over {MAX_COMPONENT_CHARS // 1024} KB)"
        elif scan.max_depth > MAX_DEPTH:
            error = f"component is nested too deeply (more than {MAX_DEPTH} levels)"
        else:
            return False
        unit = self._unit
        raw = (unit.text + "".join(unit.pending))[:4000]
        self._unit = _Unit()
        self._fail_slots(unit, error, raw)
        self._unit.skipping = True
        return True

    def _maybe_update(self, unit: _Unit) -> None:
        """Re-parse the partial component, but only as often as stays linear overall.

        Each partial parse costs O(size). Parsing again only after the text grew by
        25% (or after a quiet period that is long relative to the last parse's cost)
        bounds the total work to a small multiple of the component's size.
        """
        size = unit.size
        if size > MAX_PARTIAL_CHARS:
            return
        now = self._clock()
        grown = size - unit.parse_len
        if grown <= 0:
            return
        step = max(self._throttle_chars if unit.slots else 1, unit.parse_len // 4)
        quiet = now - unit.parse_t >= max(self._throttle_s, 4 * unit.parse_cost)
        if grown < step and not quiet:
            return
        text = unit.text + "".join(unit.pending)
        started = time.perf_counter()
        self._update_unit(text)
        unit.parse_cost = time.perf_counter() - started
        unit.parse_len, unit.parse_t = size, now

    def _update_unit(self, text: str) -> None:
        try:
            value = parse_partial(text)
        except (PartialJSONError, RecursionError):
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
        except (ValueError, RecursionError):
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
        except (ValueError, RecursionError) as exc:
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
