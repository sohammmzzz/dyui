"""What DyUI knows about its own components, in one place.

The docs site (``docs/scripts/gen_components.py`` → ``components.json``), the MCP server's
``get_component`` tool and the fallback coding-agent skill all read component facts from here,
so they can never disagree. Nothing in this module needs the ``mcp`` package.

Every Python example is *executed* against the installed package before it is returned, so no
caller ever shows a constructor call that does not work.
"""
from __future__ import annotations

import inspect
import json
import re
import sys
from typing import Any, Iterable, Optional

__all__ = [
    "ACTIONS",
    "FALLBACK",
    "OVERRIDE",
    "component_classes",
    "find_component",
    "python_examples",
    "llm_examples",
    "fields",
    "md",
    "details",
    "component_record",
    "component_summary",
    "component_detail",
    "component_markdown",
    "signature_lines",
]

# Fallback Python usage for components whose docstring has no example.
FALLBACK = {
    "markdown": 'ui.Markdown("**Two nights** in Alfama, then a day in Sintra.")',
    "callout": 'ui.Callout("Your refund was approved.", level="success", title="Refunded")',
    "code": 'ui.Code("print(\\"hello\\")", language="python", filename="app.py")',
    "quote": 'ui.Quote("Simplicity is the ultimate sophistication.", author="Clare Boothe Luce")',
    "divider": 'ui.Divider("Return journey")',
    "table": 'ui.Table(["Airline", "Depart", "Price"], [["TAP", "18:05", "$189"], ["easyJet", "06:50", "$142"]])',
    "stat": 'ui.Stat("Revenue", "$48.2k", delta="+12%", trend="up")',
    "progress": 'ui.Progress(68, label="Onboarding")',
    "json": 'ui.Json({"id": "TP-7Q4XK2", "seats": ["14A", "14B"]}, title="Booking")',
    "image": 'ui.Image("https://example.com/lisbon.jpg", alt="Lisbon at dusk", caption="Alfama")',
    "video": 'ui.Video("https://www.youtube.com/watch?v=aqz-KE-bpKQ", caption="Product tour")',
    "audio": 'ui.Audio("https://example.com/memo.mp3", title="Voice memo")',
    "file": 'ui.File("itinerary.pdf", "https://example.com/itinerary.pdf", size=248000)',
    "link_preview": 'ui.LinkPreview("https://www.visitlisboa.com", title="Visit Lisboa")',
    "reasoning": 'ui.Reasoning("Friday departures keep Saturday free, so I prioritised evening flights.")',
    "step": 'ui.Step("Search flights", "done", type="search", duration_ms=1240)',
    "tabs": 'ui.Tabs(ui.Tab("Overview", ui.Markdown("A relaxed long weekend.")), ui.Tab("Budget", ui.Stat("Total", "€1,208")))',
    "accordion": 'ui.Accordion(ui.AccordionItem("Can I change my flight?", ui.Markdown("Yes, free up to **24 hours** before departure.")), ui.AccordionItem("How do refunds work?", ui.Markdown("Refunds arrive in 3–5 business days.")))',
    "html": 'ui.Html("<b>Boarding pass</b> · Gate B32", height=120)',
    "invalid": 'ui.Invalid(raw=\'{"ui":"chart","kind":"radar"}\', error="Unknown chart kind")',
}

# Examples that replace the docstring's. ui.Html(template=...) currently renders the
# template *path* rather than the file, so the html page shows the raw-HTML form and
# the docs point to dyui.html_template(...) for files.
OVERRIDE = {
    "html": 'ui.Html("<b>Boarding pass</b> · Gate B32 · Boards 17:35", height=120)',
}

# Default action names and the ``values`` each interactive component sends
# (web/src/components/dyui/interactive). Mirrors docs/src/pages/components/[name].astro.
ACTIONS: dict[str, dict[str, str]] = {
    "buttons": {"action": "<each button's own action>", "values": "{}"},
    "choice": {"action": "choice", "values": '{"selected": ["…"], "other": "…"}'},
    "form": {"action": "form_submit", "values": '{"<field name>": <value>, …}'},
    "confirm": {"action": "confirm", "values": '{"confirmed": true | false}'},
    "rating": {"action": "rating", "values": '{"rating": 4}  (thumbs: 1 or -1)'},
    "card": {"action": "<each button's own action> (from `actions`)", "values": "{}"},
    "list": {"action": "<each row's own action>", "values": "{}"},
}

_EXAMPLE_RE = re.compile(r"``(ui\.[A-Za-z]+\(.*?\))``", re.S)
_RST_CODE = re.compile(r"``([^`]+)``")
_RST_ROLE = re.compile(r":(?:class|func|meth|data|attr|mod|obj):`~?([^`]+)`")


# ------------------------------------------------------------------ lookup
def component_classes(*, include_developer: bool = True) -> list[type]:
    """Every built-in component class, in spec order."""
    from ..ui.registry import BUILTINS

    return [c for c in BUILTINS if include_developer or c.__dyui__.llm]


def find_component(name: str, extra: Iterable[type] = ()) -> Optional[type]:
    """A component class by LLM name (``"key_value"``-style), class name (``"KeyValue"``) or ``ui.X``."""
    key = name.strip()
    if key.startswith("ui."):
        key = key[3:]
    low = key.lower().replace("-", "_")
    classes = [*extra, *component_classes()]
    for cls in classes:
        if cls.__dyui__.name == low or cls.__name__ == key:
            return cls
    for cls in classes:  # forgiving: "KeyValue" / "key_value" / "keyvalue"
        if cls.__name__.lower() == low.replace("_", "") or cls.__dyui__.name.replace("_", "") == low.replace("_", ""):
            return cls
    return None


# ------------------------------------------------------------------ text helpers
def _doc(cls: type) -> str:
    return inspect.cleandoc(cls.__doc__ or "")


def md(text: str) -> str:
    """RST inline markup → Markdown-style single backticks."""
    return _RST_CODE.sub(r"`\1`", _RST_ROLE.sub(r"`\1`", text))


def details(cls: type) -> str:
    """Docstring minus the first paragraph and any Example: section."""
    parts = _doc(cls).split("\n\n")[1:]
    keep = [p for p in parts if not p.strip().startswith(("Example:", "Examples:"))]
    return md("\n\n".join(" ".join(p.split()) for p in keep).strip())


# ------------------------------------------------------------------ examples
def _verified(name: str, found: list[str], *, strict: bool) -> list[str]:
    from .. import ui
    import dyui

    good = []
    for code in found:
        try:
            obj = eval(code, {"ui": ui, "dyui": dyui})  # noqa: S307 - our own docstrings
            obj.to_node()
            good.append(code)
        except Exception as exc:  # surfaced in the docs build log
            print(f"dyui: Python example for {name} failed: {code!r}: {exc}", file=sys.stderr)
    if not good and strict:
        raise ValueError(f"no working Python example for {name!r}")
    return good


def python_examples(cls: type, *, strict: bool = True) -> list[str]:
    """Working ``ui.X(...)`` constructor calls for a built-in (docstring, else a fallback)."""
    name = cls.__dyui__.name
    if name in OVERRIDE:
        return _verified(name, [OVERRIDE[name]], strict=strict)
    found = [" ".join(m.split()) for m in _EXAMPLE_RE.findall(_doc(cls))]
    # keep only examples that construct this component (not a sub-model on its own)
    found = [e for e in found if e.startswith(f"ui.{cls.__name__}(")]
    # docstring examples with "..." placeholders are fine in a docstring, poor on a docs page
    concrete = [e for e in found if "..." not in e]
    if concrete:
        found = concrete
    elif name in FALLBACK:
        found = [FALLBACK[name]]
    return _verified(name, found, strict=strict)


def llm_examples(cls: type, *, derive: bool = True) -> list[dict[str, Any]]:
    """``{"ui": name, ...props}`` objects the model could write for this component.

    The component's declared ``examples`` come first. With ``derive``, a component that
    declares none gets one derived from its Python example (``model_dump``), kept only if
    it passes the real validator.
    """
    info = cls.__dyui__
    out = [{"ui": info.name, **dict(e)} for e in info.examples]
    if out or not derive or not info.llm:
        return out
    from .. import ui
    import dyui
    from ..genui.catalog import Catalog

    cat = Catalog([cls])
    for code in python_examples(cls, strict=False) if info.builtin else []:
        try:
            obj = eval(code, {"ui": ui, "dyui": dyui})  # noqa: S307 - verified above
            candidate = {"ui": info.name, **obj.model_dump(mode="json", exclude_none=True)}
        except Exception:  # pragma: no cover - python_examples already ran it
            continue
        if cat.validate(candidate).get("status") != "error":
            out.append(candidate)
            break
    return out


# ------------------------------------------------------------------ fields
def _default(field: Any) -> object:
    if field.is_required():
        return None
    d = field.get_default(call_default_factory=True)
    try:
        json.dumps(d)
    except TypeError:
        return repr(d)
    return d


def fields(cls: type) -> list[dict[str, Any]]:
    """The props the model sees: name, TS-like type, required, default, positional, description."""
    from ..ui.signature import prompt_fields, ts_type

    info = cls.__dyui__
    out = []
    for fname, field in prompt_fields(cls):
        out.append({
            "name": fname,
            "type": ts_type(field.annotation, field.metadata, drop_null=not field.is_required()),
            "required": field.is_required(),
            "default": _default(field),
            "positional": fname in info.positional or fname == info.varargs,
            "description": field.description or "",
        })
    return out


def _constructor(cls: type) -> str:
    """``ui.Stat(label, value, *, unit=None, ...)`` — how the Python constructor binds arguments."""
    info = cls.__dyui__
    pos = list(info.positional)
    head = list(pos)
    if info.varargs:
        head.append(f"*{info.varargs}")
    rest = []
    for fname, field in cls.model_fields.items():
        if fname in pos or fname == info.varargs:
            continue
        rest.append(f"{fname}=…" if field.is_required() else f"{fname}={_default(field)!r}")
    if rest and not info.varargs:
        head.append("*")
    return f"ui.{cls.__name__}({', '.join(head + rest)})" if info.builtin else f"{cls.__name__}({', '.join(head + rest)})"


# ------------------------------------------------------------------ records
def component_record(cls: type) -> dict[str, Any]:
    """The docs-site record (``docs/src/data/components.json``) for one built-in."""
    info = cls.__dyui__
    return {
        "name": info.name,
        "class": cls.__name__,
        "group": info.group,
        "llm": info.llm,
        "description": md(info.description),
        "details": details(cls),
        "signature": cls.signature(),
        "positional": list(info.positional),
        "varargs": info.varargs,
        "fields": fields(cls),
        "python": python_examples(cls),
        "llm_examples": [dict(e) for e in info.examples],
    }


def component_summary(cls: type) -> dict[str, Any]:
    info = cls.__dyui__
    return {
        "name": info.name,
        "group": info.group,
        "description": md(info.description),
        "python": f"ui.{cls.__name__}" if info.builtin else cls.__name__,
        "offered_to_model": info.llm,
        "custom": not info.builtin,
    }


def component_detail(cls: type) -> dict[str, Any]:
    """Everything an agent needs to use one component correctly."""
    info = cls.__dyui__
    lines = [json.dumps(e, ensure_ascii=False, separators=(",", ":")) for e in llm_examples(cls)]
    out: dict[str, Any] = {
        **component_summary(cls),
        "details": details(cls),
        "prompt_line": cls.signature(),
        "constructor": _constructor(cls),
        "positional": list(info.positional),
        "varargs": info.varargs,
        "fields": fields(cls),
        "props_schema": cls.json_schema(strict=False),
        "llm_examples": lines,
        "llm_fence": ("```dyui\n" + "\n".join(lines) + "\n```") if lines and info.llm else "",
        "python_examples": python_examples(cls, strict=False) if info.builtin else [],
    }
    if info.hint:
        out["hint"] = info.hint
    if info.name in ACTIONS:
        out["action"] = ACTIONS[info.name]
    return out


def component_markdown(cls: type) -> str:
    """:func:`component_detail` as a compact Markdown page (for the MCP resource)."""
    d = component_detail(cls)
    out = [f"# {d['name']}  (`{d['python']}`, group `{d['group']}`)", "", d["description"]]
    if d["details"]:
        out += ["", d["details"]]
    if not d["offered_to_model"]:
        out += ["", "**Developer-only:** never offered to the model; yield it from Python."]
    out += ["", "## Python", "", "```python", d["constructor"], *d["python_examples"], "```"]
    if d["llm_fence"]:
        out += ["", "## What the model writes", "", d["llm_fence"]]
    if d["offered_to_model"]:
        out += ["", "## Prompt line", "", "```text", d["prompt_line"], "```"]
    out += ["", "## Props", "", "| prop | type | required | default | description |", "|---|---|---|---|---|"]
    for f in d["fields"]:
        default = "" if f["required"] else json.dumps(f["default"], ensure_ascii=False)
        pos = " (positional)" if f["positional"] else ""
        out.append(f"| `{f['name']}`{pos} | `{f['type']}` | {'yes' if f['required'] else ''} | {default} | {f['description']} |")
    if "action" in d:
        out += ["", "## Actions", "",
                f"Sends the action `{d['action']['action']}` (override with the `action` prop) with `values`:",
                "", "```json", d["action"]["values"], "```",
                "Handle it with `@app.on_action(name)`, `await chat.ask(component)`, or let it reach the model."]
    out += ["", "## JSON schema of the props", "", "```json", json.dumps(d["props_schema"], indent=2, ensure_ascii=False), "```"]
    return "\n".join(out) + "\n"


def signature_lines(classes: Optional[Iterable[type]] = None) -> str:
    """One prompt line per component (the ``{{components}}`` section of the fallback skill)."""
    if classes is None:
        from ..genui import catalog

        classes = catalog()
    return "\n".join(cls.signature() for cls in classes)
