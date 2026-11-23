"""Evaluator for the DyUI model-eval dataset (see MODEL_EVAL.md and DATASET_PLAN.md section 8).

Scores model answers (or the dataset's own ``reference`` answers, to self-test the dataset)
against the real DyUI machinery: ``dyui.genui.parser.parse_text`` with the item's effective
catalog (built-ins, restricted by the control header, plus real component classes registered
for custom signatures).

Library use::

    from dataset.evaluator import evaluate_item, evaluate_file
    result = evaluate_item(record, answer)         # -> ItemResult
    report = evaluate_file("eval.jsonl", answers_path="answers.jsonl")

CLI::

    python -m dataset.evaluator --data dataset/data/eval.jsonl --answers answers.jsonl \
        --out results.jsonl --report report.json
    python -m dataset.evaluator --data dataset/data/eval.jsonl --use-reference

Record fields read (all optional except ``id`` and ``messages``): ``category``, ``header``,
``reference``, ``answer`` and an ``expected`` dict with ``allowed_components``,
``must_have_block``, ``components_any_of``, ``components_all_of``, ``forbidden_components``,
``chart_kind_any_of``, ``grounding_values``, ``history_values`` (aliases: ``unchanged_values``,
``preserved_values``, ``preserve``), ``action`` (aliases: ``action_name``, ``required_action``),
``payload`` (aliases: ``data``, ``action_data``, ``action_payload``), ``custom_components``
(signature strings, or dicts with ``signature``). A missing field simply skips its check.

Counting rules: ``components`` in the <= 6 limit are the top-level objects the model wrote in
blocks (nested children are not counted; pass ``count_nested=True`` to count them too).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import typing
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Literal, Optional, Union, get_args, get_origin

import dyui
from dyui.genui.catalog import Catalog
from dyui.genui.parser import ComponentEnd, ComponentError, parse_text
from dyui.ui.base import Component
from dyui.ui.content import Markdown
from dyui.ui.signature import is_union, split_annotated
from dyui.ui.types import is_safe_url
from pydantic import BaseModel, ValidationError

__all__ = [
    "ItemResult",
    "Failure",
    "HeaderSpec",
    "parse_header",
    "build_catalog",
    "evaluate_item",
    "evaluate_records",
    "evaluate_file",
    "aggregate",
    "main",
]

# ---------------------------------------------------------------------------- constants

MAX_BLOCKS = 3
MAX_COMPONENTS = 6
MAX_QUICK_REPLIES = 4

#: Names models tend to invent (MODEL_EVAL.md, section N). Anything not in the catalog is
#: invented; these get a clearer message and are always invented, even if a header listed them.
COMPONENT_BLOCKLIST: dict[str, str] = {
    **dict.fromkeys(["alert", "banner", "notice", "toast"], "callout + level"),
    **dict.fromkeys(["kpi", "metric", "number_card", "metric_card", "stat_card"], "stat / stats"),
    **dict.fromkeys(["bar_chart", "line_chart", "line_graph", "histogram", "pie", "pie_chart",
                     "donut", "graph", "area_chart", "scatter"], "chart + kind"),
    **dict.fromkeys(["stepper", "steps", "checklist", "todo"], "plan or timeline"),
    **dict.fromkeys(["dropdown", "select", "radio", "checkbox"], "choice, or a form field type"),
    **dict.fromkeys(["button", "cta"], "buttons with items"),
    **dict.fromkeys(["chips", "suggestions"], "quick_replies with options"),
    **dict.fromkeys(["modal", "dialog"], "confirm"),
    **dict.fromkeys(["collapsible", "faq", "expander"], "accordion"),
    **dict.fromkeys(["slider", "swiper", "cards"], "carousel"),
    **dict.fromkeys(["tag", "label", "pill"], "badges"),
    **dict.fromkeys(["code_block", "snippet"], "code + language"),
    **dict.fromkeys(["citation", "references"], "sources"),
    **dict.fromkeys(["spreadsheet", "data_grid", "datagrid"], "table"),
    **dict.fromkeys(["text", "paragraph", "heading", "html", "invalid"], "markdown"),
}

#: Prop-name traps: (component, wrong prop) -> right prop.
PROP_BLOCKLIST: dict[tuple[str, str], str] = {
    ("table", "headers"): "columns",
    ("table", "data"): "rows",
    ("chart", "type"): "kind",
    ("chart", "data"): "series[].data",
    ("callout", "type"): "level",
    ("callout", "variant"): "level",
    ("quick_replies", "items"): "options",
    ("buttons", "buttons"): "items",
    ("tabs", "items"): "tabs",
    ("stat", "title"): "label",
}

FILLER_PATTERNS = [
    r"feel free to",
    r"let me know if",
    r"don'?t hesitate",
    r"hope (?:this|that|it) helps",
    r"happy to help",
    r"is there anything else",
    r"anything else (?:i|you)",
    r"if you (?:have|need|want) (?:any|more|further|anything)",
    r"i'?m here (?:to|if|for)",
    r"as an ai\b",
    r"just ask",
    r"reach out",
]
_FILLER_RE = re.compile("|".join(FILLER_PATTERNS), re.I)

_HTML_RE = re.compile(
    r"</?\s*(?:html|head|body|div|span|script|style|iframe|img|a|p|br|hr|h[1-6]|ul|ol|li|table|thead|tbody|"
    r"tr|td|th|button|input|form|label|select|option|textarea|svg|link|meta|center|font|b|i|u|strong|em)"
    r"(?:\s[^<>]*)?/?\s*>",
    re.I,
)

_URL_KEYS = frozenset({"url", "src", "href", "image", "poster", "link"})
_URL_RE = re.compile(r"""(?:https?://|ftp://|javascript:|data:|vbscript:)[^\s"'<>)\]]+""", re.I)
_NUM_RE = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?")
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})[ \t]*([^`]*?)[ \t]*$")
_INLINE_OPEN_RE = re.compile(r"^(.*?\S.*?)(`{3,}|~{3,})[ \t]*dyui[ \t]*$", re.I)
_UI_LINE_RE = re.compile(r'^\[?\s*\{\s*"ui"\s*:')

# ---------------------------------------------------------------------------- results


@dataclass
class Failure:
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass
class ItemResult:
    id: str
    category: str
    passed: bool
    failures: list[Failure] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def codes(self) -> set[str]:
        return {f.code for f in self.failures}

    def has(self, *codes: str) -> bool:
        return bool(self.codes.intersection(codes))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "passed": self.passed,
            "failures": [f.to_dict() for f in self.failures],
            "warnings": self.warnings,
            "stats": self.stats,
        }


# Failure code groups (used by the metrics).
PARSE_CODES = {"PARSE_ERROR", "SCHEMA_STRICT", "SCHEMA_CHILD_INVALID", "UNCLOSED_BLOCK"}
INVENTED_CODES = {"INVENTED_COMPONENT", "INVENTED_PROP"}
HEADER_CODES = {"HEADER_LEAK", "HEADER_OFF_BLOCK"}
PROSE_CODES = {"NO_LEAD_PROSE", "NO_TAIL_PROSE", "FILLER"}
SELECTION_CODES = {"MISSING_BLOCK", "WRONG_COMPONENT", "WRONG_CHART_KIND", "FORBIDDEN_COMPONENT", "OVERUSE"}
GROUNDING_CODES = {"MISSING_GROUNDING", "UNGROUNDED_URL", "UNGROUNDED_NUMBER", "EDIT_CHANGED"}
ACTION_CODES = {"ACTION_MISMATCH", "ACTION_PAYLOAD_MISMATCH"}

# ---------------------------------------------------------------------------- header


@dataclass
class HeaderSpec:
    raw: Optional[str] = None
    off: bool = False
    allowed: Optional[list[str]] = None  # None = all built-ins
    customs: list[str] = field(default_factory=list)  # signature strings

    @property
    def restricting(self) -> bool:
        return self.off or self.allowed is not None


_PLUS_SIG_RE = re.compile(r"\+\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def _balanced_paren_end(text: str, start: int) -> int:
    """Index just past the ``)`` matching the ``(`` at ``start`` (quotes respected), or -1."""
    depth = 0
    in_str = False
    i = start
    while i < len(text):
        ch = text[i]
        if in_str:
            if ch == "\\":
                i += 1
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def parse_header(text: Optional[str]) -> HeaderSpec:
    """Parse ``[dyui ...]`` control headers (all variants in MODEL_EVAL.md)."""
    if not text:
        return HeaderSpec()
    raw = text.strip()
    spec = HeaderSpec(raw=raw)
    s = raw.replace("\\|", "|")
    m = re.match(r"^\[\s*dyui\b", s, re.I)
    if not m:
        return HeaderSpec()
    end = s.rfind("]")
    inner = s[m.end(): end if end > m.end() else len(s)].strip()
    if inner.lower() == "off":
        spec.off = True
        return spec
    first = _PLUS_SIG_RE.search(inner)
    list_part = inner[: first.start()] if first else inner
    list_part = list_part.strip()
    if list_part.startswith(":"):
        names = [n.strip() for n in re.split(r"[,\s]+", list_part[1:]) if n.strip()]
        spec.allowed = names
    pos = 0
    while True:
        m2 = _PLUS_SIG_RE.search(inner, pos)
        if not m2:
            break
        open_idx = m2.end() - 1
        close = _balanced_paren_end(inner, open_idx)
        if close < 0:
            break
        spec.customs.append(inner[m2.start() + 1: close].strip())
        pos = close
    return spec


def _find_header(record: dict[str, Any]) -> HeaderSpec:
    header = record.get("header")
    if isinstance(header, str) and header.strip():
        return parse_header(header)
    for msg in record.get("messages") or []:
        if msg.get("role") == "system":
            content = _content_text(msg)
            m = re.search(r"^[ \t]*(\[dyui\b[^\n]*\])", content, re.I | re.M)
            if m:
                return parse_header(m.group(1))
            break
    return HeaderSpec()


# ---------------------------------------------------------------------------- custom components


def _split_top(text: str, sep: str) -> list[str]:
    out: list[str] = []
    depth = 0
    in_str = False
    cur: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if in_str:
            cur.append(ch)
            if ch == "\\" and i + 1 < len(text):
                cur.append(text[i + 1])
                i += 1
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
            cur.append(ch)
        elif ch in "([{":
            depth += 1
            cur.append(ch)
        elif ch in ")]}":
            depth -= 1
            cur.append(ch)
        elif ch == sep and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    out.append("".join(cur))
    return [p.strip() for p in out]


def _type_from_ts(text: str) -> Any:
    text = text.strip()
    while text.startswith("(") and text.endswith(")") and _balanced_paren_end(text, 0) == len(text):
        text = text[1:-1].strip()
    parts = _split_top(text, "|")
    literals: list[Any] = []
    others: list[Any] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith('"') and part.endswith('"') and len(part) >= 2:
            try:
                literals.append(json.loads(part))
            except ValueError:
                literals.append(part[1:-1])
        elif re.fullmatch(r"-?\d+(?:\.\d+)?", part):
            literals.append(float(part) if "." in part else int(part))
        elif part.endswith("[]"):
            others.append(list[_type_from_ts(part[:-2])])  # type: ignore[misc]
        elif part == "string":
            others.append(str)
        elif part == "number":
            others.append(float)
        elif part == "boolean":
            others.append(bool)
        elif part == "null":
            others.append(type(None))
        elif part in ("object",) or part.startswith("{"):
            others.append(dict[str, Any])
        elif part.startswith("["):
            others.append(list[Any])
        else:  # any / unknown
            others.append(Any)
    members: list[Any] = []
    if literals:
        members.append(Literal[tuple(literals)])  # type: ignore[valid-type]
    members.extend(others)
    if not members:
        return Any
    if len(members) == 1:
        return members[0]
    return Union[tuple(members)]  # type: ignore[return-value]


@dataclass
class CustomSig:
    name: str
    params: list[tuple[str, bool, str]]  # (prop, optional, type text)


def parse_signature(sig: str) -> CustomSig:
    sig = sig.strip().lstrip("+").strip()
    sig = sig.replace("\\|", "|")
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\(", sig)
    if not m:
        raise ValueError(f"not a component signature: {sig[:60]!r}")
    end = _balanced_paren_end(sig, m.end() - 1)
    if end < 0:
        raise ValueError(f"unbalanced parentheses in signature: {sig[:60]!r}")
    body = sig[m.end(): end - 1]
    params: list[tuple[str, bool, str]] = []
    for part in _split_top(body, ","):
        if not part:
            continue
        pm = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)(\?)?\s*:\s*(.*)$", part, re.S)
        if not pm:
            raise ValueError(f"bad parameter {part!r} in {m.group(1)}(...)")
        params.append((pm.group(1), bool(pm.group(2)), pm.group(3)))
    return CustomSig(m.group(1), params)


def _camel(name: str) -> str:
    return "".join(p[:1].upper() + p[1:] for p in name.split("_") if p) or "Custom"


_CUSTOM_CACHE: dict[str, type[Component]] = {}


def build_custom_class(sig: str) -> type[Component]:
    """Register a real pydantic/DyUI component class for a signature string (cached)."""
    key = re.sub(r"\s+", " ", sig.strip().lstrip("+").replace("\\|", "|"))
    cached = _CUSTOM_CACHE.get(key)
    if cached is not None:
        return cached
    parsed = parse_signature(sig)
    if parsed.name in {c.__dyui__.name for c in dyui.catalog()}:
        raise ValueError(f"custom component {parsed.name!r} shadows a built-in")
    annotations: dict[str, Any] = {}
    ns: dict[str, Any] = {}
    for prop, optional, tstr in parsed.params:
        tp = _type_from_ts(tstr)
        if optional:
            annotations[prop] = Optional[tp]
            ns[prop] = None
        else:
            annotations[prop] = tp

    def render(self: Component) -> Any:
        return Markdown(text=f"{type(self).__dyui__.name}")

    def make(with_name: bool) -> type[Component]:
        namespace = {"__module__": "dataset.evaluator._custom", "__annotations__": dict(annotations), "render": render, **ns}
        namespace["__doc__"] = f"Synthetic custom component {parsed.name}."
        if with_name:
            namespace["name"] = parsed.name
        return type(Component)(_camel(parsed.name), (Component,), namespace)  # type: ignore[call-arg]

    cls = make(False)
    if cls.__dyui__.name != parsed.name:
        if any(p == "name" for p, _, _ in parsed.params):
            raise ValueError(f"cannot register custom component {parsed.name!r} (class-name round-trip failed)")
        cls = make(True)
    _CUSTOM_CACHE[key] = cls
    return cls


def _record_customs(record: dict[str, Any], header: HeaderSpec) -> list[str]:
    sigs = list(header.customs)
    exp = record.get("expected") or {}
    for src in (exp.get("custom_components"), exp.get("custom"), exp.get("custom_signatures"),
                record.get("custom_components")):
        if not src:
            continue
        for item in src if isinstance(src, list) else [src]:
            if isinstance(item, dict):
                item = item.get("signature") or item.get("sig")
            if isinstance(item, str) and item.strip():
                sigs.append(item)
    seen: set[str] = set()
    out = []
    for s in sigs:
        k = s.strip().lstrip("+").strip()
        name = k.split("(", 1)[0].strip()
        if name not in seen:
            seen.add(name)
            out.append(k)
    return out


def build_catalog(header: HeaderSpec, custom_sigs: Iterable[str] = (), allowed_fallback: Optional[list[str]] = None
                  ) -> tuple[Catalog, Catalog, list[str]]:
    """Return ``(effective_catalog, full_known_catalog, warnings)``.

    ``effective`` is what the item allows. ``full_known`` holds every built-in plus the item's
    custom classes, to tell "outside the allowed set" apart from "does not exist".
    """
    warnings: list[str] = []
    base = dyui.catalog()
    classes: list[type[Component]] = []
    for sig in custom_sigs:
        try:
            classes.append(build_custom_class(sig))
        except Exception as exc:  # noqa: BLE001 - report, keep going
            warnings.append(f"custom signature not registered ({sig[:50]!r}): {exc}")
    custom_cat = Catalog(classes)
    full = base + custom_cat
    names = header.allowed if header.allowed is not None else allowed_fallback
    if header.off:
        effective = Catalog([])
    elif names is not None:
        keep = [n for n in names if n in base]
        for n in names:
            if n not in base and custom_cat.get(n) is None:
                warnings.append(f"header lists unknown component {n!r}")
        effective = base.only(*keep) + custom_cat if keep else custom_cat
    else:
        effective = full
    return effective, full, warnings


# ---------------------------------------------------------------------------- extraction


@dataclass
class Obj:
    value: Any
    block: int
    line: int  # 1-based line in the answer
    multiline: bool = False
    shared_line: bool = False
    top_index: int = 0


@dataclass
class Block:
    kind: str  # "dyui" | "jsonfence" | "bare"
    start_line: int
    body: str
    closed: bool = True
    inline_open: bool = False
    objects: list[Obj] = field(default_factory=list)
    decode_error: Optional[str] = None


@dataclass
class Extracted:
    blocks: list[Block]
    prose_before: str
    prose_after: str
    prose_all: str  # prose outside any fence, joined
    code_text: str  # text of non-dyui fenced code
    segments: list[tuple[str, Any]]


def _decode_body(body: str, block_idx: int, start_line: int) -> tuple[list[Obj], Optional[str]]:
    dec = json.JSONDecoder()
    i, n = 0, len(body)
    objs: list[Obj] = []
    err: Optional[str] = None
    last_end_line = -1
    while i < n:
        while i < n and body[i] in " \t\r\n,":
            i += 1
        if i >= n:
            break
        try:
            value, j = dec.raw_decode(body, i)
        except ValueError as exc:
            err = f"invalid JSON near line {start_line + 1 + body.count(chr(10), 0, i)}: {exc}"
            break
        span = body[i:j]
        first_line = start_line + 1 + body.count("\n", 0, i)
        items = value if isinstance(value, list) else [value]
        multi = "\n" in span
        for k, item in enumerate(items):
            shared = len(items) > 1 or first_line == last_end_line
            objs.append(Obj(item, block_idx, first_line, multiline=multi, shared_line=shared))
        last_end_line = start_line + 1 + body.count("\n", 0, j)
        i = j
    return objs, err


def extract(answer: str) -> Extracted:
    lines = answer.split("\n")
    blocks: list[Block] = []
    segments: list[tuple[str, Any]] = []
    prose: list[str] = []
    code: list[str] = []

    def flush_prose() -> None:
        if prose:
            segments.append(("prose", "\n".join(prose)))
            prose.clear()

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        s = line.strip()
        fm = _FENCE_RE.match(s)
        inline = _INLINE_OPEN_RE.match(s) if not fm else None
        kind = None
        fence = None
        pre = ""
        if fm:
            info = fm.group(2).strip().lower()
            if info == "dyui":
                kind, fence = "dyui", fm
            elif info == "json":
                kind, fence = "json", fm
            else:
                # ordinary code fence: skip to its end
                j = i + 1
                body: list[str] = [line]
                while j < n:
                    body.append(lines[j])
                    cm = _FENCE_RE.match(lines[j].strip())
                    if cm and not cm.group(2).strip() and cm.group(1)[0] == fm.group(1)[0] and len(cm.group(1)) >= len(fm.group(1)):
                        break
                    j += 1
                code.append("\n".join(body))
                flush_prose()
                segments.append(("code", "\n".join(body)))
                i = j + 1
                continue
        elif inline:
            kind, fence, pre = "dyui", inline, inline.group(1)
        elif _UI_LINE_RE.match(s):
            try:
                v = json.loads(s)
                items = v if isinstance(v, list) else [v]
                ok = bool(items) and all(isinstance(x, dict) and isinstance(x.get("ui"), str) for x in items)
            except ValueError:
                ok = False
            if ok:
                flush_prose()
                b = Block("bare", i + 1, s)
                b.objects, b.decode_error = _decode_body(s, len(blocks), i)
                blocks.append(b)
                segments.append(("block", len(blocks) - 1))
                i += 1
                continue
        if kind is None:
            prose.append(line)
            i += 1
            continue
        # a dyui / json fence
        if pre.strip():
            prose.append(pre)
        marker = fence.group(1) if fm else fence.group(2)  # type: ignore[union-attr]
        j = i + 1
        body_lines: list[str] = []
        closed = False
        while j < n:
            cm = _FENCE_RE.match(lines[j].strip())
            if cm and not cm.group(2).strip() and cm.group(1)[0] == marker[0] and len(cm.group(1)) >= len(marker):
                closed = True
                break
            body_lines.append(lines[j])
            j += 1
        body_text = "\n".join(body_lines)
        if kind == "json":
            objs, err = _decode_body(body_text, len(blocks), i)
            first = objs[0].value if objs else None
            if isinstance(first, dict) and "ui" in first:
                flush_prose()
                b = Block("jsonfence", i + 1, body_text, closed, objects=objs, decode_error=err)
                blocks.append(b)
                segments.append(("block", len(blocks) - 1))
            else:
                flush_prose()
                chunk = "\n".join([line, *body_lines] + ([lines[j]] if closed else []))
                code.append(chunk)
                segments.append(("code", chunk))
            i = j + 1
            continue
        flush_prose()
        b = Block("dyui", i + 1, body_text, closed, inline_open=bool(pre.strip()))
        b.objects, b.decode_error = _decode_body(body_text, len(blocks), i)
        blocks.append(b)
        segments.append(("block", len(blocks) - 1))
        i = j + 1
    flush_prose()

    first_block = next((k for k, (t, _) in enumerate(segments) if t == "block"), None)
    last_block = max((k for k, (t, _) in enumerate(segments) if t == "block"), default=None)
    prose_segments = [(k, v) for k, (t, v) in enumerate(segments) if t == "prose"]
    if first_block is None:
        before, after = "", ""
    else:
        before = "\n".join(v for k, v in prose_segments if k < first_block)
        after = "\n".join(v for k, v in prose_segments if k > (last_block or 0))
    # prose pending in `prose` above was flushed, so segments hold everything
    return Extracted(
        blocks=blocks,
        prose_before=before.strip(),
        prose_after=after.strip(),
        prose_all="\n".join(v for _, v in prose_segments).strip(),
        code_text="\n".join(code),
        segments=segments,
    )


# ---------------------------------------------------------------------------- helpers


def _content_text(msg: dict[str, Any]) -> str:
    content = msg.get("content")
    parts: list[str] = []
    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        for p in content:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict):
                parts.append(str(p.get("text") or p.get("content") or ""))
    elif content is not None:
        parts.append(json.dumps(content, ensure_ascii=False))
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function", tc) if isinstance(tc, dict) else {}
        args = fn.get("arguments") if isinstance(fn, dict) else None
        if args is not None:
            parts.append(args if isinstance(args, str) else json.dumps(args, ensure_ascii=False))
    return "\n".join(parts)


def _context_text(record: dict[str, Any]) -> str:
    return "\n".join(_content_text(m) for m in record.get("messages") or [])


def _norm_numbers(text: str) -> str:
    """Strip thousands separators (4,120 -> 4120)."""
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    return text


def _number_set(text: str) -> set[float]:
    out: set[float] = set()
    for tok in _NUM_RE.findall(_norm_numbers(text)):
        try:
            out.add(float(tok))
        except ValueError:
            pass
    return out


def iter_components(value: Any, path: str = "") -> Iterator[tuple[dict[str, Any], str]]:
    """Yield every dict with a string ``ui`` key (top-level and nested), with a path."""
    if isinstance(value, dict):
        if isinstance(value.get("ui"), str):
            yield value, path
        for k, v in value.items():
            yield from iter_components(v, f"{path}.{k}" if path else str(k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from iter_components(v, f"{path}[{i}]")


def iter_strings(value: Any, key: Optional[str] = None, skip_code: bool = True,
                 comp: Optional[str] = None) -> Iterator[tuple[Optional[str], str, Optional[str]]]:
    """Yield ``(key, string, component)`` for every string in a component tree."""
    if isinstance(value, str):
        yield key, value, comp
    elif isinstance(value, dict):
        name = value.get("ui") if isinstance(value.get("ui"), str) else comp
        for k, v in value.items():
            if k == "ui":
                continue
            if skip_code and name == "code" and k == "code":
                continue
            yield from iter_strings(v, k, skip_code, name)
    elif isinstance(value, list):
        for v in value:
            yield from iter_strings(v, key, skip_code, comp)


def iter_numbers(value: Any, key: Optional[str] = None) -> Iterator[float]:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        yield float(value)
    elif isinstance(value, str):
        yield from _number_set(value)
    elif isinstance(value, dict):
        for k, v in value.items():
            if k in ("ui", "id"):
                continue
            yield from iter_numbers(v, k)
    elif isinstance(value, list):
        for v in value:
            yield from iter_numbers(v, key)


def _models_in(annotation: Any) -> list[type[BaseModel]]:
    tp, _ = split_annotated(annotation)
    if isinstance(tp, type) and issubclass(tp, BaseModel):
        return [] if issubclass(tp, Component) else [tp]
    out: list[type[BaseModel]] = []
    for arg in get_args(tp):
        if arg is Ellipsis:
            continue
        out.extend(_models_in(arg))
    return out


def _unknown_nested(models: list[type[BaseModel]], value: Any, path: str) -> Iterator[tuple[str, str]]:
    """Yield ``(path, key)`` for dict keys not declared by the expected nested model."""
    if isinstance(value, list):
        for i, v in enumerate(value):
            yield from _unknown_nested(models, v, f"{path}[{i}]")
        return
    if not isinstance(value, dict) or not models:
        return
    best = max(models, key=lambda m: len(set(m.model_fields) & set(value)))
    for k, v in value.items():
        if k not in best.model_fields:
            yield path, k
        else:
            yield from _unknown_nested(_models_in(best.model_fields[k].annotation), v, f"{path}.{k}")


def _walk_node(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        if "ui" in node and "props" in node:
            yield node
        for v in node.values():
            yield from _walk_node(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_node(v)


def _fmt_obj(o: Obj) -> str:
    return f"block {o.block + 1} line {o.line}"


# ---------------------------------------------------------------------------- the evaluator


def evaluate_item(record: dict[str, Any], answer: Optional[str], *, strict_numbers: bool = False,
                  count_nested: bool = False) -> ItemResult:
    """Score one answer against one record. Never raises for malformed answers."""
    rid = str(record.get("id", "?"))
    cat = str(record.get("category") or (rid.split("-")[0] if "-" in rid else ""))
    exp: dict[str, Any] = record.get("expected") or {}
    failures: list[Failure] = []
    warnings: list[str] = []

    def fail(code: str, msg: str) -> None:
        failures.append(Failure(code, msg))

    if not isinstance(answer, str) or not answer.strip():
        fail("EMPTY_ANSWER", "the answer is empty")
        return ItemResult(rid, cat, False, failures, warnings, {"n_blocks": 0, "n_components": 0, "components": []})

    header = _find_header(record)
    customs = _record_customs(record, header)
    allowed_fallback = exp.get("allowed_components")
    catalog, full, cat_warn = build_catalog(header, customs, allowed_fallback if isinstance(allowed_fallback, list) else None)
    warnings.extend(cat_warn)
    restricted = header.restricting or isinstance(allowed_fallback, list)

    ex = extract(answer)
    top: list[Obj] = [o for b in ex.blocks for o in b.objects]
    n_blocks = len(ex.blocks)
    block_text = "\n".join(b.body for b in ex.blocks)
    context = _context_text(record)

    # ---- structure / format
    for b in ex.blocks:
        label = f"block {ex.blocks.index(b) + 1}"
        if b.kind == "jsonfence":
            fail("BARE_JSON_FENCE", f"{label}: a ```json fence containing a \"ui\" key (use ```dyui, or put JSON examples inside a code component)")
        elif b.kind == "bare":
            fail("BARE_COMPONENT", f"{label}: component line outside a ```dyui fence")
        if b.inline_open:
            fail("INLINE_FENCE", f"{label}: ```dyui opener is not on its own line")
        if not b.closed:
            fail("UNCLOSED_BLOCK", f"{label}: no closing fence")
        if b.decode_error:
            fail("PARSE_ERROR", f"{label}: {b.decode_error}")
    for o in top:
        if o.multiline:
            fail("MULTILINE_JSON", f"{_fmt_obj(o)}: component JSON spans several lines (must be single-line)")
        elif o.shared_line:
            fail("ONE_PER_LINE", f"{_fmt_obj(o)}: more than one component on a line")

    # ---- per-object name/prop checks and object validity
    obj_ok: list[dict[str, Any]] = []  # {component, ok}
    used: list[str] = []
    chart_kinds: list[str] = []
    seen_leak: set[str] = set()
    seen_inv: set[str] = set()
    for o in top:
        for comp, path in iter_components(o.value):
            name = comp.get("ui")
            used.append(name)
            ok = True
            cls = catalog.get(name)
            where = f"{_fmt_obj(o)}{(' ' + path) if path else ''}"
            if name in COMPONENT_BLOCKLIST and cls is None:
                fail("INVENTED_COMPONENT", f"{where}: {name!r} does not exist (use {COMPONENT_BLOCKLIST[name]})")
                seen_inv.add(name)
                ok = False
            elif cls is None:
                if full.get(name) is not None and (restricted or header.off):
                    if name not in seen_leak:
                        fail("HEADER_LEAK", f"{where}: component {name!r} is outside the allowed set")
                        seen_leak.add(name)
                else:
                    fail("INVENTED_COMPONENT", f"{where}: unknown component {name!r}")
                    seen_inv.add(name)
                ok = False
            else:
                fields = cls.model_fields
                for k in comp:
                    if k in ("ui", "id") or k.startswith("__") or k in fields:
                        continue
                    hint = PROP_BLOCKLIST.get((name, k))
                    fail("INVENTED_PROP", f"{where}: {name} has no prop {k!r}" + (f" (use {hint})" if hint else ""))
                    ok = False
                for k, v in comp.items():
                    if k in fields:
                        for p, bad in _unknown_nested(_models_in(fields[k].annotation), v, f"{k}"):
                            hint = PROP_BLOCKLIST.get((name, bad))
                            fail("INVENTED_PROP", f"{where}: {name}.{p} has no prop {bad!r}" + (f" (use {hint})" if hint else ""))
                            ok = False
                if name == "chart" and isinstance(comp.get("kind"), str):
                    chart_kinds.append(comp["kind"])
            obj_ok.append({"component": name, "ok": ok, "top": path == ""})

    # ---- real parser against the effective catalog
    events = parse_text(answer, catalog if len(catalog) else full)
    comp_events = [e for e in events if isinstance(e, (ComponentEnd, ComponentError))]
    aligned = len(comp_events) == len(top)
    for idx, ev in enumerate(comp_events):
        o = top[idx] if aligned else None
        where = _fmt_obj(o) if o else "component"
        if isinstance(ev, ComponentError):
            if ev.error.startswith("unknown component") and ev.component in (seen_leak | seen_inv):
                continue  # already reported by name (HEADER_LEAK / INVENTED_COMPONENT)
            msg = f"{where}: {ev.component + ': ' if ev.component else ''}{ev.error}"
            if ev.path:
                msg += f" (at {ev.path})"
            fail("PARSE_ERROR", msg)
            if o is not None:
                nm = o.value.get("ui") if isinstance(o.value, dict) else None
                for rec in obj_ok:
                    if rec["top"] and rec["component"] == nm:
                        rec["ok"] = False
                        break
            continue
        # parsed fine: look for silently-dropped children and strict-schema problems
        for node in _walk_node(ev.node):
            if node.get("ui") == "invalid":
                err = str((node.get("props") or {}).get("error", "invalid"))
                if err.startswith("unknown component"):
                    continue
                fail("SCHEMA_CHILD_INVALID", f"{where}: invalid child component: {err}")
        if o is not None and isinstance(o.value, dict):
            cls = catalog.get(o.value.get("ui"))
            if cls is not None:
                payload = {k: v for k, v in o.value.items() if k != "ui" and not k.startswith("__") and (k != "id" or "id" in cls.model_fields)}
                try:
                    cls.model_validate(payload, context={"catalog": catalog})
                except ValidationError as exc:
                    errs = exc.errors(include_url=False)
                    loc = ".".join(str(p) for p in errs[0].get("loc", ())) if errs else ""
                    fail("SCHEMA_STRICT", f"{where}: {o.value.get('ui')}: {errs[0].get('msg') if errs else exc} (at {loc}); DyUI would silently drop it")
                    for rec in obj_ok:
                        if rec["top"] and rec["component"] == o.value.get("ui"):
                            rec["ok"] = False
                            break
                except Exception:  # noqa: BLE001 - strict re-check is best-effort
                    pass
    if not aligned and (top or comp_events):
        warnings.append(f"parser produced {len(comp_events)} components, extractor found {len(top)}")

    # ---- header adherence
    if header.off and (n_blocks or top):
        fail("HEADER_OFF_BLOCK", "a dyui block was written under [dyui off]")
    if header.raw:
        if re.search(r"\[dyui\b|\bdyui\b", ex.prose_all, re.I) and not exp.get("self_knowledge"):
            if cat != "S":
                fail("MENTIONS_RESTRICTION", "the reply mentions the control header / dyui")

    # ---- prose wrap
    if n_blocks:
        if not re.search(r"\w", ex.prose_before):
            fail("NO_LEAD_PROSE", "no prose before the first block")
        if not re.search(r"\w", ex.prose_after):
            fail("NO_TAIL_PROSE", "no prose (takeaway) after the last block")
    mf = _FILLER_RE.search(ex.prose_all)
    if mf:
        fail("FILLER", f"filler phrase: {mf.group(0)!r}")

    # ---- limits
    top_level = [o for o in top if isinstance(o.value, dict)]
    n_comp = len(used) if count_nested else len(top_level)
    if n_blocks > MAX_BLOCKS:
        fail("LIMIT_BLOCKS", f"{n_blocks} blocks (max {MAX_BLOCKS})")
    if n_comp > MAX_COMPONENTS:
        fail("LIMIT_COMPONENTS", f"{n_comp} components (max {MAX_COMPONENTS})")
    for o in top:
        for comp, path in iter_components(o.value):
            if comp.get("ui") == "quick_replies":
                opts = comp.get("options")
                if isinstance(opts, list) and len(opts) > MAX_QUICK_REPLIES:
                    fail("LIMIT_QUICK_REPLIES", f"{_fmt_obj(o)}: quick_replies has {len(opts)} options (max {MAX_QUICK_REPLIES})")

    # ---- HTML / unsafe URLs
    html_hit = None
    prose_clean = re.sub(r"`[^`\n]*`", "", ex.prose_all)
    m = _HTML_RE.search(prose_clean)
    if m:
        html_hit = f"prose: {m.group(0)[:40]!r}"
    for o in top:
        if html_hit:
            break
        for key, s, comp_name in iter_strings(o.value):
            m = _HTML_RE.search(s)
            if m:
                html_hit = f"{_fmt_obj(o)} {comp_name or ''}.{key}: {m.group(0)[:40]!r}"
                break
    if html_hit:
        fail("HTML", f"HTML in the reply ({html_hit})")

    ctx_urls = set(_URL_RE.findall(context))
    for o in top:
        for key, s, comp_name in iter_strings(o.value, skip_code=True):
            cand: list[str] = []
            if key in _URL_KEYS and re.match(r"^[A-Za-z][A-Za-z0-9+.\-]*:|^//", s):
                cand.append(s)
            cand.extend(_URL_RE.findall(s))
            for url in dict.fromkeys(cand):
                if re.match(r"^(javascript|data|vbscript):", url, re.I) and not (url.lower().startswith("data:image/") and url in context):
                    fail("UNSAFE_URL", f"{_fmt_obj(o)}: unsafe URL {url[:60]!r}")
                elif url not in context and url.rstrip("/.,;") not in context:
                    fail("UNGROUNDED_URL", f"{_fmt_obj(o)}: URL not found in the conversation: {url[:80]!r}")

    # ---- selection / over-use
    must = exp.get("must_have_block")
    used_set = set(used)
    any_of = exp.get("components_any_of") or []
    all_of = exp.get("components_all_of") or []
    if must is False and (n_blocks or top):
        fail("OVERUSE", f"a component block was written but none was expected (policy row {exp.get('policy_row')!r}); used {sorted(used_set)}")
    elif must is True and not top:
        fail("MISSING_BLOCK", "a dyui block was expected but the reply has none")
    elif any_of and not top and must is not False:
        fail("MISSING_BLOCK", f"expected one of {any_of} but the reply has no components")
    elif top:
        if any_of and not used_set.intersection(any_of):
            fail("WRONG_COMPONENT", f"expected one of {any_of}, got {sorted(used_set)}")
        missing = [c for c in all_of if c not in used_set]
        if all_of and missing:
            fail("WRONG_COMPONENT", f"missing required components {missing}; got {sorted(used_set)}")
        kinds = exp.get("chart_kind_any_of") or []
        if kinds and "chart" in used_set and not set(chart_kinds).intersection(kinds):
            fail("WRONG_CHART_KIND", f"chart kind {chart_kinds} is not one of {kinds}")
        bad = used_set.intersection(exp.get("forbidden_components") or [])
        if bad:
            fail("FORBIDDEN_COMPONENT", f"forbidden components used: {sorted(bad)}")

    # ---- grounding
    answer_norm = _norm_numbers(answer)
    for gv in exp.get("grounding_values") or []:
        sv = str(gv)
        if sv not in answer and _norm_numbers(sv) not in answer_norm:
            fail("MISSING_GROUNDING", f"grounding value {sv!r} is missing from the reply")
    ctx_nums = _number_set(context)
    ungrounded: list[float] = []
    for o in top:
        for num in iter_numbers(o.value):
            if abs(num) >= 10 and num not in ctx_nums and num not in ungrounded:
                ungrounded.append(num)
    if ungrounded:
        msg = f"numbers not found in the conversation: {ungrounded[:8]}"
        if strict_numbers:
            fail("UNGROUNDED_NUMBER", msg)
        else:
            warnings.append(msg)

    # ---- F edits: history values unchanged byte-for-byte
    for key in ("history_values", "unchanged_values", "preserved_values", "preserve", "unchanged"):
        for hv in exp.get(key) or []:
            frags = {str(hv)} if isinstance(hv, str) else set()
            frags.add(json.dumps(hv, ensure_ascii=False, separators=(",", ":")))
            if not any(f in block_text for f in frags):
                fail("EDIT_CHANGED", f"history value {json.dumps(hv, ensure_ascii=False)[:80]} is missing or changed in the new block")

    # ---- E actions
    want_action = next((exp[k] for k in ("action", "action_name", "required_action") if exp.get(k)), None)
    want_payload = next((exp[k] for k in ("payload", "action_data", "action_payload", "data") if isinstance(exp.get(k), dict)), None)
    if isinstance(want_action, dict):
        # nested form from the dataset generator: {stage, component, name, data, ...}.
        # Only the "emit" stage constrains the answer; respond/quick_reply/ignore describe the user's input.
        nested = want_action
        want_action = nested.get("name") if nested.get("stage") == "emit" else None
        if want_action and want_payload is None and isinstance(nested.get("data"), dict) and nested["data"]:
            want_payload = nested["data"]
    if want_action or want_payload:
        found: list[tuple[str, dict[str, Any]]] = []
        for o in top:
            for comp, path in iter_components(o.value):
                cls = catalog.get(comp.get("ui"))
                default = cls.model_fields["action"].default if cls is not None and "action" in cls.model_fields else None
                if isinstance(comp.get("action"), str):
                    found.append((comp["action"], comp.get("data") if isinstance(comp.get("data"), dict) else {}))
                elif isinstance(default, str):
                    found.append((default, comp.get("data") if isinstance(comp.get("data"), dict) else {}))
            for d in _iter_dicts(o.value):
                if isinstance(d.get("action"), str) and "ui" not in d:  # buttons items, card actions, list items
                    found.append((d["action"], d.get("data") if isinstance(d.get("data"), dict) else {}))
        if want_action and not any(a == want_action for a, _ in found):
            fail("ACTION_MISMATCH", f"expected action {want_action!r}, found {sorted({a for a, _ in found})}")
        elif want_payload is not None:
            cands = [d for a, d in found if not want_action or a == want_action]
            if not any(all(k in d and d[k] == v for k, v in want_payload.items()) for d in cands):
                fail("ACTION_PAYLOAD_MISMATCH", f"expected payload {json.dumps(want_payload)[:80]}, found {[d for d in cands][:3]}")

    stats = {
        "n_blocks": n_blocks,
        "n_components": n_comp,
        "n_components_nested": len(used),
        "components": sorted(used_set),
        "chart_kinds": chart_kinds,
        "header": header.raw,
        "header_restricting": restricted,
        "objects": obj_ok,
        "has_block": bool(top),
    }
    return ItemResult(rid, cat, not failures, failures, warnings, stats)


def _iter_dicts(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from _iter_dicts(v)
    elif isinstance(value, list):
        for v in value:
            yield from _iter_dicts(v)


# ---------------------------------------------------------------------------- aggregation

TARGETS: list[dict[str, Any]] = [
    {"key": "parse_valid", "name": "Parse + schema-valid rate", "target": 0.995, "dir": ">="},
    {"key": "invented", "name": "Invented component or prop names", "target": 0.003, "dir": "<="},
    {"key": "header", "name": "Header adherence (restricted / off leaks)", "target": 0.995, "dir": ">="},
    {"key": "prose", "name": "Prose-wrap rate", "target": 0.98, "dir": ">="},
    {"key": "selection_b", "name": "Selection accuracy on B near-miss pairs", "target": 0.90, "dir": ">="},
    {"key": "overuse_j", "name": "Over-use on J", "target": 0.05, "dir": "<="},
    {"key": "grounding", "name": "Grounding exactness on G, F, I", "target": 0.98, "dir": ">="},
    {"key": "flow_e", "name": "E action flows completed correctly", "target": 0.95, "dir": ">="},
    {"key": "heldout_custom", "name": "Held-out custom components valid and appropriate", "target": 0.90, "dir": ">="},
    {"key": "components_below_98", "name": "Components valid in < 98% of uses (>=10 uses)", "target": 0, "dir": "<=", "count": True},
]


def _is_heldout(rec: dict[str, Any]) -> bool:
    exp = rec.get("expected") or {}
    if any(rec.get(k) or exp.get(k) for k in ("heldout", "held_out", "heldout_custom")):
        return True
    return str(rec.get("split") or exp.get("split") or "").lower() in ("heldout", "held_out", "test_heldout", "heldout_custom")


def aggregate(results: list[ItemResult], records: Optional[dict[str, dict[str, Any]]] = None,
              n_missing: int = 0) -> dict[str, Any]:
    records = records or {}
    n = len(results)

    def rate(num: int, den: int) -> Optional[float]:
        return None if den == 0 else num / den

    m: dict[str, tuple[int, int]] = {}
    with_blocks = [r for r in results if r.stats.get("has_block")]
    m["parse_valid"] = (sum(1 for r in with_blocks if not r.has(*PARSE_CODES)), len(with_blocks))
    inv_items = sum(1 for r in with_blocks if r.has(*INVENTED_CODES))
    m["invented"] = (inv_items, len(with_blocks))
    restricted = [r for r in results if r.stats.get("header_restricting")]
    m["header"] = (sum(1 for r in restricted if not r.has(*HEADER_CODES)), len(restricted))
    m["prose"] = (sum(1 for r in with_blocks if not r.has(*PROSE_CODES)), len(with_blocks))
    b_items = [r for r in results if r.category == "B"]
    m["selection_b"] = (sum(1 for r in b_items if not r.has(*SELECTION_CODES, *PARSE_CODES)), len(b_items))
    j_items = [r for r in results if r.category == "J"]
    m["overuse_j"] = (sum(1 for r in j_items if r.has("OVERUSE")), len(j_items))
    g_items = [r for r in results if r.category in ("G", "F", "I")]
    m["grounding"] = (sum(1 for r in g_items if not r.has(*GROUNDING_CODES)), len(g_items))
    e_items = [r for r in results if r.category == "E"]
    m["flow_e"] = (sum(1 for r in e_items if r.passed), len(e_items))
    i_items = [r for r in results if r.category == "I"]
    held = [r for r in i_items if _is_heldout(records.get(r.id, {}))]
    pool = held or i_items
    m["heldout_custom"] = (sum(1 for r in pool if r.passed), len(pool))

    by_comp: dict[str, dict[str, Any]] = defaultdict(lambda: {"occurrences": 0, "valid": 0, "items": set()})
    for r in results:
        for rec in r.stats.get("objects", []):
            d = by_comp[rec["component"]]
            d["occurrences"] += 1
            d["valid"] += 1 if rec["ok"] else 0
            d["items"].add(r.id)
    comp_report = {
        k: {"occurrences": v["occurrences"], "valid": v["valid"], "valid_rate": v["valid"] / v["occurrences"], "items": len(v["items"])}
        for k, v in sorted(by_comp.items())
    }
    below = [k for k, v in comp_report.items() if v["occurrences"] >= 10 and v["valid_rate"] < 0.98]
    m["components_below_98"] = (len(below), 0)

    metrics = []
    all_met = True
    for t in TARGETS:
        num, den = m[t["key"]]
        value = float(num) if t.get("count") else rate(num, den)
        if t.get("count"):
            ok: Optional[bool] = num <= t["target"]
        elif value is None:
            ok = None
        else:
            ok = value >= t["target"] if t["dir"] == ">=" else value <= t["target"]
        if ok is False:
            all_met = False
        metrics.append({"key": t["key"], "name": t["name"], "value": value, "numerator": num, "denominator": den,
                        "target": t["target"], "direction": t["dir"], "passed": ok,
                        **({"components": below} if t.get("count") else {})})

    by_cat: dict[str, dict[str, Any]] = {}
    for r in results:
        d = by_cat.setdefault(r.category, {"n": 0, "passed": 0, "failure_codes": Counter()})
        d["n"] += 1
        d["passed"] += 1 if r.passed else 0
        d["failure_codes"].update(r.codes)
    for d in by_cat.values():
        d["pass_rate"] = d["passed"] / d["n"]
        d["failure_codes"] = dict(d["failure_codes"].most_common())
    codes = Counter(c for r in results for c in r.codes)

    return {
        "n_items": n,
        "n_passed": sum(1 for r in results if r.passed),
        "pass_rate": rate(sum(1 for r in results if r.passed), n),
        "n_missing_answers": n_missing,
        "all_targets_met": all_met,
        "metrics": metrics,
        "by_category": dict(sorted(by_cat.items())),
        "by_component": comp_report,
        "by_failure_code": dict(codes.most_common()),
    }


def format_report(report: dict[str, Any]) -> str:
    lines = [f"items: {report['n_items']}  passed: {report['n_passed']} ({_pct(report['pass_rate'])})"
             + (f"  missing answers: {report['n_missing_answers']}" if report["n_missing_answers"] else ""),
             "", f"{'metric':<58}{'value':>9}{'target':>10}  result"]
    for mt in report["metrics"]:
        if mt["key"] == "components_below_98":
            val, tgt = str(mt["numerator"]), "0"
        else:
            val = _pct(mt["value"]) if mt["value"] is not None else "n/a"
            tgt = f"{mt['direction']}{mt['target'] * 100:g}%"
        res = "n/a" if mt["passed"] is None else ("PASS" if mt["passed"] else "FAIL")
        den = f" ({mt['numerator']}/{mt['denominator']})" if mt["key"] != "components_below_98" else ""
        lines.append(f"{mt['name']:<58}{val:>9}{tgt:>10}  {res}{den}")
    lines += ["", "by category:"]
    for cat, d in report["by_category"].items():
        top = ", ".join(f"{k}:{v}" for k, v in list(d["failure_codes"].items())[:4])
        lines.append(f"  {cat or '?':<3} {d['passed']:>5}/{d['n']:<5} {_pct(d['pass_rate']):>7}  {top}")
    if report["by_failure_code"]:
        lines += ["", "failure codes: " + ", ".join(f"{k}={v}" for k, v in report["by_failure_code"].items())]
    low = [(k, v) for k, v in report["by_component"].items() if v["valid_rate"] < 1.0]
    if low:
        lines += ["", "components with invalid uses: " + ", ".join(f"{k} {v['valid']}/{v['occurrences']}" for k, v in low[:15])]
    lines.append("")
    lines.append("ALL TARGETS MET" if report["all_targets_met"] else "TARGETS MISSED")
    return "\n".join(lines)


def _pct(x: Optional[float]) -> str:
    return "n/a" if x is None else f"{x * 100:.2f}%"


# ---------------------------------------------------------------------------- IO


def read_jsonl(path: Union[str, Path]) -> list[dict[str, Any]]:
    out = []
    with open(path, encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError as exc:
                raise ValueError(f"{path}:{ln}: invalid JSON: {exc}") from None
    return out


def _answer_of(obj: dict[str, Any]) -> Optional[str]:
    for k in ("answer", "response", "output", "completion", "text"):
        if isinstance(obj.get(k), str):
            return obj[k]
    return None


def evaluate_records(records: list[dict[str, Any]], answers: Optional[dict[str, str]] = None, *,
                     use_reference: bool = False, strict_numbers: bool = False,
                     count_nested: bool = False) -> tuple[list[ItemResult], int]:
    """Evaluate many records. Returns ``(results, n_missing_answers)``."""
    results: list[ItemResult] = []
    missing = 0
    for rec in records:
        rid = str(rec.get("id"))
        if use_reference:
            ans = rec.get("reference")
        elif answers is not None and rid in answers:
            ans = answers[rid]
        else:
            ans = _answer_of(rec)
        if ans is None:
            missing += 1
            results.append(ItemResult(rid, str(rec.get("category") or ""), False, [Failure("NO_ANSWER", "no answer supplied for this id")]))
            continue
        results.append(evaluate_item(rec, ans, strict_numbers=strict_numbers, count_nested=count_nested))
    return results, missing


def evaluate_file(data: Union[str, Path], answers_path: Optional[Union[str, Path]] = None, *,
                  use_reference: bool = False, out: Optional[Union[str, Path]] = None,
                  report_path: Optional[Union[str, Path]] = None, strict_numbers: bool = False,
                  count_nested: bool = False, limit: Optional[int] = None) -> dict[str, Any]:
    """Evaluate a JSONL dataset; write per-item results to ``out`` and the report to ``report_path``."""
    records = read_jsonl(data)
    if limit:
        records = records[:limit]
    answers = None
    if answers_path:
        answers = {}
        for obj in read_jsonl(answers_path):
            a = _answer_of(obj)
            if a is not None and "id" in obj:
                answers[str(obj["id"])] = a
    results, missing = evaluate_records(records, answers, use_reference=use_reference,
                                        strict_numbers=strict_numbers, count_nested=count_nested)
    by_id = {str(r.get("id")): r for r in records}
    graded = [r for r in results if not r.has("NO_ANSWER")]
    report = aggregate(graded, by_id, missing)
    report["n_items"] = len(results)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            for r in results:
                d = r.to_dict()
                d["stats"] = {k: v for k, v in d["stats"].items() if k != "objects"}
                fh.write(json.dumps(d, ensure_ascii=False) + "\n")
    if report_path:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["_results"] = results
    return report


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m dataset.evaluator", description="Score DyUI model answers against the eval dataset.")
    ap.add_argument("--data", required=True, help="eval JSONL (MODEL_EVAL.md record format)")
    ap.add_argument("--answers", help='answers JSONL: {"id": ..., "answer": ...}')
    ap.add_argument("--use-reference", action="store_true", help="grade each record's own `reference` (dataset self-test)")
    ap.add_argument("--out", help="per-item results JSONL (default: <data stem>.results.jsonl next to --report or cwd)")
    ap.add_argument("--report", help="aggregate report JSON (default: <out stem>.report.json)")
    ap.add_argument("--strict-numbers", action="store_true", help="fail (not warn) on numbers in blocks absent from the context")
    ap.add_argument("--count-nested", action="store_true", help="count nested children toward the 6-component limit")
    ap.add_argument("--limit", type=int, help="only the first N records")
    ap.add_argument("--no-fail", action="store_true", help="always exit 0")
    ap.add_argument("--show-failures", type=int, default=0, metavar="N", help="print the first N failing items")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not (args.answers or args.use_reference):
        print("note: no --answers / --use-reference: using the `answer` field of each record", file=sys.stderr)
    out = args.out or (Path.cwd() / (Path(args.data).stem + ".results.jsonl"))
    report_path = args.report or Path(str(out)).with_suffix(".report.json")
    report = evaluate_file(args.data, args.answers, use_reference=args.use_reference, out=out, report_path=report_path,
                           strict_numbers=args.strict_numbers, count_nested=args.count_nested, limit=args.limit)
    results: list[ItemResult] = report.pop("_results")
    print(format_report(report))
    if args.show_failures:
        shown = 0
        for r in results:
            if not r.passed and shown < args.show_failures:
                shown += 1
                print(f"\n{r.id} [{r.category}]")
                for f in r.failures:
                    print(f"  {f.code}: {f.message}")
    print(f"\nresults: {out}\nreport:  {report_path}")
    if args.no_fail:
        return 0
    return 0 if report["all_targets_met"] and report["n_missing_answers"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
