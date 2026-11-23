"""Hard gates for the DyUI eval dataset (MODEL_EVAL.md "Hard gates").

``check(record)`` returns a list of :class:`Failure`; an empty list means the record's
``reference`` passes every gate.  ``check(record, reply=...)`` runs the same
*reply-quality* gates on any other reply (e.g. a model output); the gates that compare a
reply to the record's expectations (components_any_of, grounding_values, F byte-identity,
E action payloads) apply to both.

Gate names (stable, used in stats):
    structure, parse, strict, blocklist, allowed, prose, filler, single_line, html, grounding,
    expect, header_leak, edit, action, limits, off
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional

import dyui
from dyui.genui.catalog import Catalog
from dyui.genui.history import action_text
from dyui.genui.parser import ComponentError, parse_text
from dyui.ui.registry import LLM_BUILTINS
from dyui.ui.types import is_safe_url

from spec import FILLER_PHRASES, RESTRICTION_LEAKS, SPEC, Obj, make_component_spec

GATE_NAMES = ["structure", "parse", "strict", "blocklist", "allowed", "prose", "filler", "single_line", "html",
              "grounding", "expect", "header_leak", "edit", "action", "limits", "off"]


@dataclass
class Failure:
    gate: str
    msg: str

    def __str__(self) -> str:
        return f"[{self.gate}] {self.msg}"


# ----------------------------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------------------------

def compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


_OPEN = re.compile(r"^```dyui\s*$")
_CLOSE = re.compile(r"^```\s*$")
_ANY_FENCE = re.compile(r"^(```|~~~)")
_HTML = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>|<!--|&lt;script")
_NUM = re.compile(r"(?<![A-Za-z0-9_.\-])-?\d[\d,]*(?:\.\d+)?|(?<![A-Za-z0-9_.\d])\.\d+")
_URL = re.compile(r"https?://[^\s\"'<>)\]]+", re.I)


@dataclass
class Parsed:
    prose: list[str]            # prose segments: before first block, between, after last
    blocks: list[list[str]]     # raw lines per dyui block
    other_fence_ui: bool        # a non-dyui fence / bare line carrying {"ui": ...}
    unclosed: bool


def split_reply(reply: str) -> Parsed:
    lines = reply.split("\n")
    prose: list[list[str]] = [[]]
    blocks: list[list[str]] = []
    cur: Optional[list[str]] = None
    other_fence = False
    other_ui = False
    unclosed = False
    in_other = False
    for ln in lines:
        s = ln.strip()
        if cur is not None:
            if _CLOSE.match(s):
                blocks.append(cur)
                cur = None
                prose.append([])
            else:
                cur.append(ln)
            continue
        if in_other:
            if _ANY_FENCE.match(s):
                in_other = False
            elif re.match(r'^\s*\[?\s*\{\s*"ui"\s*:', ln):
                other_ui = True
            prose[-1].append(ln)
            continue
        if _OPEN.match(s):
            cur = []
            continue
        if _ANY_FENCE.match(s):
            in_other = True
            other_fence = True
            prose[-1].append(ln)
            continue
        if re.match(r'^\s*\[?\s*\{\s*"ui"\s*:', ln):
            other_ui = True
        prose[-1].append(ln)
    if cur is not None:
        unclosed = True
        blocks.append(cur)
    _ = other_fence
    return Parsed(["\n".join(p).strip() for p in prose], blocks, other_ui, unclosed)


def iter_components(obj: Any):
    """Yield every component dict (with a ``ui`` key) in an object tree."""
    if isinstance(obj, dict):
        if "ui" in obj and isinstance(obj.get("ui"), str):
            yield obj
        for v in obj.values():
            yield from iter_components(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from iter_components(v)


def numbers_in(text: str) -> set[str]:
    out = set()
    for m in _NUM.finditer(text):
        t = m.group(0).replace(",", "")
        t = t.rstrip(".")
        if t:
            out.add(t)
            if t.startswith("-"):
                out.add(t[1:])
    return out


def norm_num(t: str) -> set[str]:
    """Equivalent spellings of a number token (``3.0`` == ``3``)."""
    out = {t, t.lstrip("-")}
    try:
        f = float(t)
        out.add(repr(f).rstrip("0").rstrip(".") if "." in repr(f) else repr(f))
        if f == int(f):
            out.add(str(int(f)))
    except ValueError:
        pass
    return out


# ---- effective catalog ------------------------------------------------------------------------

_CLASS_CACHE: dict[str, Any] = {}
_HEADER_RE = re.compile(r"^\[dyui(?::\s*([a-z_,\s]*?))?\s*(?:\+(.*))?\]$")


def load_custom_class(source: str) -> Any:
    if source in _CLASS_CACHE:
        return _CLASS_CACHE[source]
    from typing import Literal, Optional as Opt
    import hashlib
    import sys
    import types
    modname = "dyui_custom_" + hashlib.sha1(source.encode()).hexdigest()[:12]
    mod = types.ModuleType(modname)
    sys.modules[modname] = mod
    ns = mod.__dict__
    ns.update({"dyui": dyui, "ui": dyui.ui, "Literal": Literal, "Optional": Opt})
    exec(compile(source, modname, "exec"), ns)  # noqa: S102 - generated by our own generator
    classes = [v for v in ns.values() if isinstance(v, type) and issubclass(v, dyui.Component) and v is not dyui.Component]
    cls = classes[-1]
    # register through the real mechanism (@app.component)
    app = dyui.App("eval", persist=False)
    app.component(cls)
    _CLASS_CACHE[source] = cls
    return cls


def parse_header(header: Optional[str]) -> dict[str, Any]:
    """-> {kind, allowed(list|None), custom_sigs[list[str]]}"""
    if header is None:
        return {"kind": "none", "allowed": None, "custom_sigs": []}
    h = header.strip()
    if h == "[dyui off]":
        return {"kind": "off", "allowed": [], "custom_sigs": []}
    m = _HEADER_RE.match(h)
    if not m:
        raise ValueError(f"bad header {header!r}")
    names = [n.strip() for n in (m.group(1) or "").split(",") if n.strip()]
    custom = []
    if m.group(2):
        custom = [s.strip() for s in re.split(r"\s\+", " " + m.group(2).strip()) if s.strip()]
        custom = [c.lstrip("+").strip() for c in custom]
    return {"kind": "restricted" if m.group(1) is not None else "all", "allowed": names if m.group(1) is not None else None,
            "custom_sigs": custom}


def effective_catalog(record: dict) -> tuple[Catalog, dict[str, Any], dict[str, Any]]:
    """-> (catalog, {name: ComponentSpec}, header_info).  Built-ins restricted by header + custom classes."""
    hdr = parse_header(record.get("header"))
    customs = []
    for c in (record.get("expected") or {}).get("custom_components") or []:
        customs.append(load_custom_class(c["class_source"]))
    builtins = list(LLM_BUILTINS)
    if hdr["allowed"] is not None:
        builtins = [c for c in builtins if c.__dyui__.name in hdr["allowed"]]
    cat = Catalog([*builtins, *customs])
    specs = {n: SPEC.components[n] for n in cat.names if n in SPEC.components and SPEC.components[n].builtin}
    for cls in customs:
        specs[cls.__dyui__.name] = make_component_spec(cls)
    return cat, specs, hdr


# ---- strict structural check (props/enums/types beyond what the lenient parser accepts) -------

_URL_KEYS = {"url", "src", "image", "poster"}


def _type_ok(p, v) -> bool:
    if p.free or not p.types:
        return True
    ok = False
    for t in p.types:
        if t == "string" and isinstance(v, str):
            ok = True
        elif t in ("number", "integer") and isinstance(v, (int, float)) and not isinstance(v, bool):
            ok = True
        elif t == "boolean" and isinstance(v, bool):
            ok = True
        elif t == "array" and isinstance(v, list):
            ok = True
        elif t == "object" and isinstance(v, dict):
            ok = True
    return ok


def _strict_obj(o: Obj, obj: dict, path: str, specs: dict, errs: list[str], builtin: bool, top: bool = False) -> None:
    for k in obj:
        if top and k == "ui":
            continue
        if k not in o.props:
            errs.append(f"{path}: unknown prop {k!r}")
    for n, p in o.props.items():
        if n not in obj:
            if p.required:
                errs.append(f"{path}: missing required {n!r}")
            continue
        v = obj[n]
        if v is None:
            errs.append(f"{path}.{n}: null value (omit the prop instead)")
            continue
        if not _type_ok(p, v):
            errs.append(f"{path}.{n}: wrong type {type(v).__name__}")
            continue
        if p.enum is not None and v not in p.enum:
            errs.append(f"{path}.{n}: {v!r} not in {p.enum}")
        if builtin and n in _URL_KEYS and isinstance(v, str) and not is_safe_url(v):
            errs.append(f"{path}.{n}: unsafe URL {v!r}")
        if p.children:
            for i, ch in enumerate(v):
                if not isinstance(ch, dict):
                    errs.append(f"{path}.{n}[{i}]: child must be a component object")
                else:
                    _strict_comp(ch, specs, f"{path}.{n}[{i}]", errs)
        elif p.obj is not None:
            if p.is_array:
                for i, it in enumerate(v):
                    if isinstance(it, dict):
                        _strict_obj(p.obj, it, f"{path}.{n}[{i}]", specs, errs, builtin)
                    elif not (isinstance(it, str) and builtin):  # a bare string item is lenient-accepted; refuse
                        errs.append(f"{path}.{n}[{i}]: item must be an object")
                    else:
                        errs.append(f"{path}.{n}[{i}]: item must be an object, not a bare string")
            elif isinstance(v, dict):
                _strict_obj(p.obj, v, f"{path}.{n}", specs, errs, builtin)


def _strict_comp(obj: dict, specs: dict, path: str, errs: list[str]) -> None:
    name = obj.get("ui")
    if name not in specs:
        errs.append(f"{path}: component {name!r} not in the effective set")
        return
    cs = specs[name]
    if list(obj)[0] != "ui":
        errs.append(f"{path}: 'ui' must be the first key")
    _strict_obj(cs.obj, obj, f"{path}<{name}>", specs, errs, cs.builtin, top=True)
    # extra data-shape constraints that the lenient models normalise silently
    if name == "table":
        cols = obj.get("columns")
        for i, r in enumerate(obj.get("rows") or []):
            if not isinstance(r, list):
                errs.append(f"{path}.rows[{i}]: rows must be arrays, not objects")
            elif isinstance(cols, list) and len(r) != len(cols):
                errs.append(f"{path}.rows[{i}]: {len(r)} cells for {len(cols)} columns")
    if name == "chart":
        kind = obj.get("kind")
        for i, s in enumerate(obj.get("series") or []):
            data = s.get("data") if isinstance(s, dict) else None
            if not isinstance(data, list):
                continue
            if kind == "scatter":
                if not all(isinstance(p, list) and len(p) == 2 for p in data):
                    errs.append(f"{path}.series[{i}]: scatter needs [x,y] pairs")
            elif any(isinstance(p, list) for p in data):
                errs.append(f"{path}.series[{i}]: only scatter takes [x,y] pairs")
            elif obj.get("labels") is not None and len(obj["labels"]) != len(data):
                errs.append(f"{path}.series[{i}]: {len(data)} values for {len(obj['labels'])} labels")
    if name in ("card", "grid", "carousel") and "children" in obj and not obj["children"]:
        errs.append(f"{path}: empty children")


# ---- grounding -------------------------------------------------------------------------------

_SKIP_COMPONENTS_FOR_NUMBERS = {"form", "rating", "code", "choice", "confirm", "buttons", "quick_replies", "step",
                                "reasoning"}
_SKIP_NUM_KEYS = {"max", "min", "step", "columns", "duration_ms", "default"}


def _leaves(obj: Any, key: str = "", comp: str = ""):
    """Yield (comp, key, value) for scalar leaves (not descending into skipped number keys)."""
    if isinstance(obj, dict):
        c = obj.get("ui", comp) if isinstance(obj.get("ui"), str) else comp
        for k, v in obj.items():
            if k == "ui":
                continue
            yield from _leaves(v, k, c)
    elif isinstance(obj, list):
        for v in obj:
            yield from _leaves(v, key, comp)
    else:
        yield comp, key, obj


def context_text(messages: list[dict]) -> str:
    parts = []
    for m in messages:
        if m["role"] == "system":
            continue
        c = m.get("content")
        if isinstance(c, str):
            parts.append(c)
        for tc in m.get("tool_calls") or []:
            parts.append(tc.get("function", {}).get("arguments", ""))
    return "\n".join(parts)


def _ctx_numbers(text: str) -> set[str]:
    out: set[str] = set()
    for t in numbers_in(text):
        out |= norm_num(t)
    return out


def check_grounding(objs: list[dict], ctx: str, derived: set[str], strict_strings: bool, errs: list[Failure]) -> None:
    ctx_nums = _ctx_numbers(ctx)
    ctx_low = ctx.lower()
    ctx_urls = {u.rstrip(".,") for u in _URL.findall(ctx)}
    derived_n = {"0", "0.0"}
    for d in derived:
        derived_n |= _ctx_numbers(str(d)) | {str(d)}
    for o in objs:
        for comp, key, v in _leaves(o):
            if isinstance(v, bool) or v is None:
                continue
            if isinstance(v, str):
                for u in _URL.findall(v):
                    if u.rstrip(".,") not in ctx_urls:
                        errs.append(Failure("grounding", f"URL not in context: {u}"))
                if key in _URL_KEYS and v.startswith(("http://", "https://")) and v not in ctx_urls and not any(v == u for u in ctx_urls):
                    if v not in ctx:
                        errs.append(Failure("grounding", f"URL prop not in context: {v}"))
                if key in _URL_KEYS and v.startswith("/api/files/") and v not in ctx:
                    errs.append(Failure("grounding", f"file path not in context: {v}"))
                if strict_strings and comp in ("table", "keyvalue", "list", "timeline", "chart", "stats", "stat") and key in (
                        "rows", "value", "title", "labels", "") and v.lower() not in ctx_low and not _is_label_like(v):
                    errs.append(Failure("grounding", f"{comp}.{key} string not in context: {v!r}"))
            if comp in _SKIP_COMPONENTS_FOR_NUMBERS or key in _SKIP_NUM_KEYS:
                continue
            toks = [str(v)] if isinstance(v, (int, float)) else list(numbers_in(v)) if isinstance(v, str) else []
            if isinstance(v, str) and key in _URL_KEYS:
                continue
            for t in (numbers_in(str(v)) if isinstance(v, (int, float)) else set(toks) if isinstance(v, str) else set()):
                if not (norm_num(t) & (ctx_nums | derived_n)):
                    errs.append(Failure("grounding", f"number {t} in {comp}.{key} not in context"))


def _is_label_like(v: str) -> bool:
    return False


# ----------------------------------------------------------------------------------------------
# The main check
# ----------------------------------------------------------------------------------------------

_ACTION_RE = re.compile(r"^\[action:([A-Za-z0-9_.\-]+)\]\s*(\{.*\})\s*$", re.S)


def declared_actions_of(obj: dict, specs: dict) -> list[tuple[str, Optional[dict]]]:
    cs = specs.get(obj.get("ui"))
    if cs is None:
        return []
    props = {k: v for k, v in obj.items() if k != "ui"}
    return list(cs.cls.declared_actions(props))


def _history_components(messages: list[dict]) -> list[dict]:
    out = []
    for m in messages:
        if m["role"] != "assistant" or not isinstance(m.get("content"), str):
            continue
        pr = split_reply(m["content"])
        for b in pr.blocks:
            for ln in b:
                if ln.strip():
                    try:
                        out.append(json.loads(ln))
                    except ValueError:
                        pass
    return out


def check(record: dict, reply: Optional[str] = None) -> list[Failure]:
    errs: list[Failure] = []
    is_ref = reply is None
    reply = record.get("reference") if reply is None else reply
    exp = record.get("expected") or {}
    msgs = record.get("messages") or []
    cat_code = record.get("category")

    # -- structure --
    for k in ("id", "category", "dyui", "header", "messages", "reference", "expected"):
        if k not in record:
            errs.append(Failure("structure", f"missing key {k}"))
    if errs:
        return errs
    if not msgs or msgs[-1]["role"] not in ("user", "tool"):
        errs.append(Failure("structure", "messages must end on the last user (or tool) turn"))
    if not isinstance(reply, str) or not reply.strip():
        errs.append(Failure("structure", "empty reply"))
        return errs
    for k in ("policy_row", "components_any_of", "allowed_components", "must_have_block", "grounding_values", "forbidden"):
        if k not in exp:
            errs.append(Failure("structure", f"expected.{k} missing"))
    if errs:
        return errs

    try:
        cat, specs, hdr = effective_catalog(record)
    except Exception as exc:  # noqa: BLE001
        return [Failure("structure", f"cannot build catalog: {exc}")]
    allowed = set(cat.names) if hdr["allowed"] is None else set(hdr["allowed"]) | {
        c["name"] for c in exp.get("custom_components") or []}
    if hdr["kind"] == "off":
        allowed = set()
    if is_ref:
        # header string must agree with the custom components' real signatures
        for sig, c in zip(hdr["custom_sigs"], exp.get("custom_components") or []):
            real = specs[c["name"]].header_signature
            if sig != real:
                errs.append(Failure("structure", f"header sig {sig!r} != DyUI signature {real!r}"))
        if len(hdr["custom_sigs"]) != len(exp.get("custom_components") or []):
            errs.append(Failure("structure", "header custom sigs vs expected.custom_components mismatch"))

    pr = split_reply(reply)
    if pr.unclosed:
        errs.append(Failure("parse", "unclosed ```dyui block"))

    # -- parse every block line --
    objs: list[dict] = []
    top_objs: list[dict] = []
    for bi, blk in enumerate(pr.blocks):
        lines = [ln for ln in blk if ln.strip()]
        if not lines:
            errs.append(Failure("parse", "empty dyui block"))
        for ln in lines:
            try:
                o = json.loads(ln)
            except ValueError as exc:
                errs.append(Failure("single_line", f"line is not a single complete JSON object: {ln[:60]!r} ({exc})"))
                continue
            if not isinstance(o, dict):
                errs.append(Failure("single_line", "block line is not a JSON object"))
                continue
            if ln != compact(o):
                errs.append(Failure("single_line", f"JSON not compact single-line: {ln[:70]!r}"))
            top_objs.append(o)
    for o in top_objs:
        objs.append(o)

    # -- parse_text against the effective catalog --
    for ev in parse_text(reply, cat):
        if isinstance(ev, ComponentError):
            errs.append(Failure("parse", f"ComponentError {ev.component}: {ev.error[:120]}"))

    # -- off / negative --
    has_blocks = bool(pr.blocks)
    optional = bool(exp.get("block_optional")) and hdr["kind"] != "off"
    if optional and not exp["must_have_block"]:
        pass
    elif (not exp["must_have_block"]) or hdr["kind"] == "off":
        if has_blocks or pr.other_fence_ui:
            errs.append(Failure("off", "a dyui block/component appears where none is allowed"))
    elif not has_blocks and exp["must_have_block"]:
        errs.append(Failure("expect", "must_have_block but no dyui block"))
    if pr.other_fence_ui and has_blocks is False and exp["must_have_block"]:
        errs.append(Failure("parse", "component JSON in a non-dyui fence / bare line"))
    if pr.other_fence_ui and cat_code != "S":
        errs.append(Failure("parse", "component JSON outside a ```dyui block"))
    if cat_code == "S" and pr.other_fence_ui:
        errs.append(Failure("parse", "S: example JSON must be inside a code component, not a bare fence"))

    # -- limits --
    if len(pr.blocks) > 3:
        errs.append(Failure("limits", f"{len(pr.blocks)} blocks (max 3)"))
    if len(top_objs) > 6:
        errs.append(Failure("limits", f"{len(top_objs)} components (max 6)"))
    for o in top_objs:
        for c in iter_components(o):
            if c.get("ui") == "quick_replies" and isinstance(c.get("options"), list) and len(c["options"]) > 4:
                errs.append(Failure("limits", "quick_replies with more than 4 options"))

    # -- allowed / blocklist / strict --
    for o in top_objs:
        for c in iter_components(o):
            n = c.get("ui")
            if n in SPEC.blocklist:
                errs.append(Failure("blocklist", f"blocklisted component name {n!r}"))
            elif n not in allowed:
                errs.append(Failure("allowed", f"component {n!r} not in the allowed set"))
        serr: list[str] = []
        _strict_comp(o, specs, "$", serr)
        for e in serr:
            wrong = re.search(r"unknown prop '(\w+)'", e)
            gate = "strict"
            if wrong:
                comp_m = re.search(r"<(\w+)>", e)
                if comp_m and wrong.group(1) in SPEC.wrong_props.get(comp_m.group(1), {}):
                    gate = "blocklist"
            errs.append(Failure(gate, e))

    # -- prose --
    if has_blocks:
        if len(pr.prose[0]) < 10:
            errs.append(Failure("prose", "no prose before the first block"))
        if len(pr.prose[-1]) < 10:
            errs.append(Failure("prose", "no prose after the last block"))
        for i, seg in enumerate(pr.prose[1:-1], 1):
            if len(seg) < 6:
                errs.append(Failure("prose", f"no prose between blocks {i} and {i + 1}"))
        if len(pr.prose[0]) > 330:
            errs.append(Failure("prose", "intro too long"))
    low = reply.lower()
    for ph in FILLER_PHRASES:
        if ph in low:
            errs.append(Failure("filler", f"filler phrase {ph!r}"))

    # -- html --
    prose_all = "\n".join(pr.prose)
    if _HTML.search(prose_all):
        # prose may contain HTML only when it is inside a (non-dyui) code fence we allow for K/S
        stripped = re.sub(r"```.*?```", "", prose_all, flags=re.S)
        if _HTML.search(stripped):
            errs.append(Failure("html", "HTML in prose"))
    for o in top_objs:
        for comp, key, v in _leaves(o):
            if isinstance(v, str) and _HTML.search(v):
                if comp == "code" and key == "code" and exp.get("allow_html_in_code"):
                    continue
                errs.append(Failure("html", f"HTML in {comp}.{key}"))

    # -- header leak --
    if cat_code == "H" or hdr["kind"] in ("restricted", "restricted_custom", "off"):
        plow = prose_all.lower()
        if cat_code == "H" and any(p in plow for p in RESTRICTION_LEAKS):
            hit = [p for p in RESTRICTION_LEAKS if p in plow]
            errs.append(Failure("header_leak", f"reply mentions the restriction: {hit}"))

    # -- expectations (gold must satisfy its own expected) --
    comps_found = [c.get("ui") for o in top_objs for c in iter_components(o)]
    any_of = exp.get("components_any_of") or []
    if exp.get("callout_level_any_of"):
        lv = [c_.get("level", "info") for o in top_objs for c_ in iter_components(o) if c_.get("ui") == "callout"]
        if not set(lv) & set(exp["callout_level_any_of"]):
            errs.append(Failure("expect", f"callout level {lv} not in {exp['callout_level_any_of']}"))
    if exp.get("max_table_rows"):
        for o in top_objs:
            for c_ in iter_components(o):
                if c_.get("ui") == "table" and len(c_.get("rows", [])) > exp["max_table_rows"]:
                    errs.append(Failure("expect", f"table has more than {exp['max_table_rows']} rows"))
    if exp["must_have_block"] and any_of and not (set(any_of) & set(comps_found)):
        errs.append(Failure("expect", f"none of {any_of} in reply (found {sorted(set(comps_found))})"))
    if exp.get("chart_kind_any_of"):
        kinds = [c.get("kind") for o in top_objs for c in iter_components(o) if c.get("ui") == "chart"]
        if not set(kinds) & set(exp["chart_kind_any_of"]):
            errs.append(Failure("expect", f"chart kind {kinds} not in {exp['chart_kind_any_of']}"))
    if exp.get("allowed_components") is not None:
        allow_decl = set(exp["allowed_components"])
        if hdr["kind"] != "off" and hdr["allowed"] is not None:
            if allow_decl - {c["name"] for c in exp.get("custom_components") or []} != set(hdr["allowed"]):
                errs.append(Failure("expect", "allowed_components disagrees with the header"))
    for want in exp.get("must_contain_components") or []:
        if want not in comps_found:
            errs.append(Failure("expect", f"required component {want} missing"))
    for gv in exp["grounding_values"]:
        if str(gv) not in reply:
            errs.append(Failure("expect", f"grounding value {gv!r} missing from the reply"))
    ctx = context_text(msgs)
    if is_ref:
        for gv in exp["grounding_values"]:
            if exp.get("grounding_in_context", True) and str(gv).replace(",", "") not in ctx.replace(",", ""):
                errs.append(Failure("grounding", f"grounding value {gv!r} not in the context"))


    # -- extra expectation gates (K / S / forbidden) --
    for fc in exp.get("forbidden_components") or []:
        if fc in comps_found:
            errs.append(Failure("expect", f"forbidden component {fc!r} present"))
    for fs in exp.get("forbidden_substrings") or []:
        if fs.lower() in low:
            errs.append(Failure("expect", f"forbidden text {fs!r} present"))
    for ms in exp.get("must_mention") or []:
        if ms.lower() not in low:
            errs.append(Failure("expect", f"reply must mention {ms!r}"))
    if exp.get("form_forbidden_fields"):
        for o in top_objs:
            for c_ in iter_components(o):
                if c_.get("ui") == "form" and any(f.get("name") in exp["form_forbidden_fields"] or f.get("type") in exp["form_forbidden_fields"]
                                                for f in c_.get("fields", [])):
                    errs.append(Failure("expect", "form asks for forbidden field"))
    if cat_code == "S":
        for o in top_objs:
            for c_ in iter_components(o):
                if c_.get("ui") == "code" and (c_.get("language") or "").lower() == "json":
                    for ln in str(c_.get("code", "")).splitlines():
                        ln = ln.strip()
                        if ln.startswith("{") and '"ui"' in ln:
                            try:
                                eo = json.loads(ln)
                            except ValueError:
                                errs.append(Failure("parse", f"S example line is not valid JSON: {ln[:50]}"))
                                continue
                            node = cat.validate(eo, id="c_x")
                            if node.get("status") == "error":
                                errs.append(Failure("parse", f"S example invalid: {node.get('error')}"))
                            serr2: list[str] = []
                            _strict_comp(eo, specs, "$ex", serr2)
                            errs.extend(Failure("strict", e) for e in serr2)

    # -- grounding of every number / URL in blocks, and numbers in prose --
    derived = set(str(d) for d in exp.get("derived_values") or [])
    gerrs: list[Failure] = []
    check_grounding(top_objs, ctx, derived, bool(exp.get("string_grounding")), gerrs)
    seen = set()
    for f in gerrs:
        if f.msg not in seen:
            seen.add(f.msg)
            errs.append(f)
    ctx_nums = _ctx_numbers(ctx)
    derived_n = set()
    for d in derived:
        derived_n |= _ctx_numbers(d)
    prose_for_nums = re.sub(r"```.*?```", "", prose_all, flags=re.S)
    prose_nums = numbers_in(prose_for_nums)
    if cat_code not in ("S", "J"):
        for t in prose_nums:
            if not (norm_num(t) & (ctx_nums | derived_n)):
                errs.append(Failure("grounding", f"number {t} in prose not in context (declare it in derived if computed)"))
    if has_blocks:
        block_nums: set[str] = set()
        for o in top_objs:
            for comp, key, v in _leaves(o):
                if comp in _SKIP_COMPONENTS_FOR_NUMBERS or key in _SKIP_NUM_KEYS:
                    continue
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    block_nums |= numbers_in(str(v))
                elif isinstance(v, str) and key not in _URL_KEYS:
                    block_nums |= numbers_in(v)
        block_nums = {t for t in block_nums if len(t.replace(".", "").replace("-", "")) >= 2}
        repeated = [t for t in prose_nums if t in block_nums and not (t.startswith("0") and "." not in t)]
        if len(block_nums) >= 4 and len(repeated) > 2:
            errs.append(Failure("filler", f"prose repeats block data: {sorted(repeated)}"))

    # -- F: byte-identical history values --
    if exp.get("history_values_unchanged") is not None:
        block_text = "\n".join(compact(o) for o in top_objs)
        hist_text = "\n".join(compact(o) for o in _history_components(msgs))
        for frag in exp["history_values_unchanged"]:
            if frag not in block_text:
                errs.append(Failure("edit", f"history value not preserved byte-for-byte: {frag[:60]}"))
            if is_ref and frag not in hist_text:
                errs.append(Failure("edit", f"history value not in history block (bad expectation): {frag[:60]}"))
        for frag in exp.get("must_change") or []:
            if frag not in block_text:
                errs.append(Failure("edit", f"requested change missing: {frag[:60]}"))
        for frag in exp.get("must_not_contain") or []:
            if frag in block_text:
                errs.append(Failure("edit", f"removed value still present: {frag[:60]}"))

    # -- E: actions --
    act = exp.get("action")
    if act:
        _check_action(record, act, top_objs, specs, msgs, errs, is_ref)

    return errs


def _check_action(record: dict, act: dict, top_objs: list[dict], specs: dict, msgs: list[dict],
                  errs: list[Failure], is_ref: bool) -> None:
    stage = act.get("stage")
    if stage == "emit":
        found = False
        for o in top_objs:
            for c in iter_components(o):
                for name, data in declared_actions_of(c, specs):
                    if name == act["name"] and (act.get("data") is None or (data or {}) == act["data"]):
                        found = c.get("ui") == act["component"] or found
                        found = True
        if not found:
            errs.append(Failure("action", f"reply does not declare action {act['name']!r} with data {act.get('data')}"))
        if act.get("danger") is not None:
            ok = any(c.get("ui") == act["component"] and bool(c.get("danger")) == act["danger"]
                     for o in top_objs for c in iter_components(o))
            if not ok:
                errs.append(Failure("action", f"{act['component']}.danger should be {act['danger']}"))
        return
    last = msgs[-1]["content"] if msgs else ""
    if stage == "respond":
        m = _ACTION_RE.match(last or "")
        if not m:
            errs.append(Failure("action", "last user turn is not an [action:...] message"))
            return
        name, payload = m.group(1), json.loads(m.group(2))
        if is_ref:
            if action_text(name, payload) != last:
                errs.append(Failure("action", "action text is not what action_text() produces"))
            if name != act["name"] or payload != act["payload"]:
                errs.append(Failure("action", "action/payload differs from expected"))
        hist = _history_components(msgs)
        decl: list[tuple[str, Optional[dict]]] = []
        comp_cls = None
        for c in hist:
            ds = declared_actions_of(c, specs)
            if any(n == name for n, _ in ds):
                comp_cls = c
            decl.extend(ds)
        if comp_cls is None:
            errs.append(Failure("action", f"action {name!r} not declared by any history component"))
            return
        ui = comp_cls["ui"]
        if ui == "confirm":
            if not isinstance(payload.get("confirmed"), bool):
                errs.append(Failure("action", "confirm payload needs boolean 'confirmed'"))
            data = comp_cls.get("data") or {}
            if any(payload.get(k) != v for k, v in data.items()):
                errs.append(Failure("action", "confirm payload lost its data"))
        elif ui == "form":
            names = {f["name"] for f in comp_cls["fields"]}
            if not set(payload) <= names:
                errs.append(Failure("action", "form payload has keys that are not form fields"))
        elif ui == "choice":
            sel = payload.get("selected")
            if not isinstance(sel, list) or not set(sel) <= set(comp_cls["options"]) or (
                    "other" in payload and not comp_cls.get("allow_other")):
                errs.append(Failure("action", "choice payload invalid"))
            if len(sel or []) > 1 and not comp_cls.get("multiple"):
                errs.append(Failure("action", "choice: several selections without multiple"))
        elif ui == "rating":
            r = payload.get("rating")
            mx = comp_cls.get("max", 5)
            if comp_cls.get("style") == "thumbs":
                if r not in (1, -1):
                    errs.append(Failure("action", "thumbs rating must be 1 or -1"))
            elif not isinstance(r, int) or not 1 <= r <= mx:
                errs.append(Failure("action", "rating out of range"))
        else:  # buttons / card.actions / list rows -> their data
            data_ok = any((d or {}) == payload for n, d in decl if n == name)
            if not data_ok:
                errs.append(Failure("action", "payload != declared data of the button/row"))
    elif stage == "quick_reply":
        hist = _history_components(msgs)
        opts = [o for c in hist if c.get("ui") == "quick_replies" for o in c.get("options", [])]
        if last not in opts:
            errs.append(Failure("action", "quick-reply tap is not one of the offered options"))
    elif stage == "ignore":
        if _ACTION_RE.match(last or ""):
            errs.append(Failure("action", "ignore-the-widget turn must be plain text"))
        if not _history_components(msgs):
            errs.append(Failure("action", "ignore flow needs a widget in history"))
