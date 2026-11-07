"""A tolerant parser for *incomplete* JSON (streaming component props).

``parse_partial('{"label": "Reve')`` → ``{"label": "Reve"}``. Open strings,
arrays and objects are closed; incomplete numbers, literals and keys are
dropped. Unterminated strings come back as :class:`PartialStr` (a ``str``
subclass) so callers can tell a value is still streaming.
"""
from __future__ import annotations

from typing import Any

__all__ = ["parse_partial", "PartialStr", "JSONObject", "PartialJSONError", "MISSING", "scan_depth", "ScanState"]


class PartialJSONError(ValueError):
    """Raised when the prefix can never become valid JSON."""


class PartialStr(str):
    """A string value whose closing quote hasn't arrived yet."""


class JSONObject(dict):
    """A decoded object that remembers the order its keys completed in."""

    __slots__ = ("key_order",)

    def __init__(self) -> None:
        super().__init__()
        self.key_order: list[str] = []


class _Missing:
    def __repr__(self) -> str:
        return "MISSING"


MISSING: Any = _Missing()
"""Sentinel: no complete value at this position yet."""

_WS = " \t\r\n"
_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}
_NUM_CHARS = set("+-0123456789.eE")


class _Parser:
    def __init__(self, text: str) -> None:
        self.s = text
        self.n = len(text)
        self.i = 0

    def ws(self) -> None:
        while self.i < self.n and self.s[self.i] in _WS:
            self.i += 1

    def eof(self) -> bool:
        return self.i >= self.n

    def value(self) -> Any:
        self.ws()
        if self.eof():
            return MISSING
        ch = self.s[self.i]
        if ch == "{":
            return self.obj()
        if ch == "[":
            return self.arr()
        if ch == '"':
            return self.string()
        if ch in "-0123456789":
            return self.number()
        for lit, val in (("true", True), ("false", False), ("null", None)):
            if self.s.startswith(lit, self.i):
                self.i += len(lit)
                return val
            rest = self.s[self.i :]
            if lit.startswith(rest):
                self.i = self.n
                return MISSING
        raise PartialJSONError(f"unexpected character {ch!r} at {self.i}")

    def string(self) -> Any:
        self.i += 1  # opening quote
        out: list[str] = []
        while self.i < self.n:
            ch = self.s[self.i]
            if ch == '"':
                self.i += 1
                return "".join(out)
            if ch == "\\":
                if self.i + 1 >= self.n:
                    self.i = self.n
                    break
                esc = self.s[self.i + 1]
                if esc == "u":
                    hex_ = self.s[self.i + 2 : self.i + 6]
                    if len(hex_) < 4:
                        self.i = self.n
                        break
                    try:
                        code = int(hex_, 16)
                    except ValueError:
                        raise PartialJSONError("bad unicode escape") from None
                    self.i += 6
                    if 0xD800 <= code <= 0xDBFF:  # surrogate pair
                        if self.s.startswith("\\u", self.i) and len(self.s) >= self.i + 6:
                            try:
                                low = int(self.s[self.i + 2 : self.i + 6], 16)
                            except ValueError:
                                raise PartialJSONError("bad unicode escape") from None
                            self.i += 6
                            code = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)
                        elif self.i >= self.n or self.n - self.i < 6:
                            self.i = self.n
                            break
                    out.append(chr(code))
                    continue
                if esc not in _ESCAPES:
                    raise PartialJSONError("bad escape")
                out.append(_ESCAPES[esc])
                self.i += 2
                continue
            out.append(ch)
            self.i += 1
        return PartialStr("".join(out))

    def number(self) -> Any:
        start = self.i
        while self.i < self.n and self.s[self.i] in _NUM_CHARS:
            self.i += 1
        if self.i >= self.n:
            return MISSING  # may continue (e.g. "12" → "125")
        text = self.s[start : self.i]
        try:
            if any(c in text for c in ".eE"):
                return float(text)
            return int(text)
        except ValueError:
            raise PartialJSONError(f"bad number {text!r}") from None

    def arr(self) -> Any:
        self.i += 1
        out: list[Any] = []
        while True:
            self.ws()
            if self.eof():
                return out
            if self.s[self.i] == "]":
                self.i += 1
                return out
            item = self.value()
            if item is MISSING:
                return out
            out.append(item)
            if isinstance(item, PartialStr):
                return out
            self.ws()
            if self.eof():
                return out
            ch = self.s[self.i]
            if ch == ",":
                self.i += 1
            elif ch == "]":
                self.i += 1
                return out
            else:
                raise PartialJSONError(f"expected , or ] at {self.i}")

    def obj(self) -> Any:
        self.i += 1
        out = JSONObject()
        while True:
            self.ws()
            if self.eof():
                return out
            ch = self.s[self.i]
            if ch == "}":
                self.i += 1
                return out
            if ch != '"':
                raise PartialJSONError(f"expected key at {self.i}")
            key = self.string()
            if isinstance(key, PartialStr):
                return out
            self.ws()
            if self.eof():
                return out
            if self.s[self.i] != ":":
                raise PartialJSONError(f"expected : at {self.i}")
            self.i += 1
            val = self.value()
            if val is MISSING:
                return out
            out[key] = val
            if not isinstance(val, PartialStr):
                out.key_order.append(key)
            else:
                return out
            self.ws()
            if self.eof():
                return out
            ch = self.s[self.i]
            if ch == ",":
                self.i += 1
            elif ch == "}":
                self.i += 1
                return out
            else:
                raise PartialJSONError(f"expected , or }} at {self.i}")


def parse_partial(text: str) -> Any:
    """Parse a possibly-incomplete JSON document.

    Args:
        text: A JSON prefix.

    Returns:
        The decoded value with open containers closed, or :data:`MISSING`
        when nothing complete is available yet.

    Raises:
        PartialJSONError: If the prefix is malformed (can never become valid).
    """
    p = _Parser(text)
    value = p.value()
    return value


def scan_depth(text: str) -> tuple[int, bool]:
    """Return ``(bracket depth, inside string)`` at the end of ``text``."""
    state = ScanState()
    state.feed(text)
    return state.depth, state.in_str


class ScanState:
    """Incremental bracket-depth / string scanner for streamed JSON.

    Feeding text chunk by chunk costs O(len(chunk)), so callers never need to
    rescan what they already saw (the parser used to rescan the whole growing
    component on every line, which made long components quadratic).
    """

    __slots__ = ("depth", "in_str", "esc", "max_depth")

    def __init__(self) -> None:
        self.depth = 0
        self.in_str = False
        self.esc = False
        self.max_depth = 0

    def copy(self) -> "ScanState":
        other = ScanState()
        other.depth, other.in_str, other.esc, other.max_depth = self.depth, self.in_str, self.esc, self.max_depth
        return other

    def feed(self, text: str) -> None:
        depth, in_str, esc, max_depth = self.depth, self.in_str, self.esc, self.max_depth
        for ch in text:
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch in "{[":
                depth += 1
                if depth > max_depth:
                    max_depth = depth
            elif ch in "}]":
                depth -= 1
        self.depth, self.in_str, self.esc, self.max_depth = depth, in_str, esc, max_depth
