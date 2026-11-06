"""Generate docs/src/data/components.json from the live dyui component registry.

Every Python example is *executed* against the installed package, so the docs
can never show a constructor call that doesn't work.

Usage:  python docs/scripts/gen_components.py
"""
from __future__ import annotations

import inspect
import json
import re
import sys
from pathlib import Path

import dyui
from dyui import ui
from dyui.ui.registry import BUILTINS
from dyui.ui.signature import prompt_fields, ts_type

OUT = Path(__file__).resolve().parent.parent / "src" / "data" / "components.json"

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
    "html":'ui.Html("<b>Boarding pass</b> · Gate B32", height=120)',
    "invalid": 'ui.Invalid(raw=\'{"ui":"chart","kind":"radar"}\', error="Unknown chart kind")',
}

EXAMPLE_RE = re.compile(r"``(ui\.[A-Za-z]+\(.*?\))``", re.S)


def _doc(cls: type) -> str:
    return inspect.cleandoc(cls.__doc__ or "")


# Examples that replace the docstring's. ui.Html(template=...) currently renders the
# template *path* rather than the file, so the html page shows the raw-HTML form and
# the docs point to dyui.html_template(...) for files.
OVERRIDE = {
    "html": 'ui.Html("<b>Boarding pass</b> · Gate B32 · Boards 17:35", height=120)',
}


def _examples(cls: type, name: str) -> list[str]:
    if name in OVERRIDE:
        return _verified(name, [OVERRIDE[name]])
    found = [" ".join(m.split()) for m in EXAMPLE_RE.findall(_doc(cls))]
    # keep only examples that construct this component (not a sub-model on its own)
    found = [e for e in found if e.startswith(f"ui.{cls.__name__}(")]
    # docstring examples with "..." placeholders are fine in a docstring, poor on a docs page
    concrete = [e for e in found if "..." not in e]
    if concrete:
        found = concrete
    elif name in FALLBACK:
        found = [FALLBACK[name]]
    return _verified(name, found)


def _verified(name: str, found: list[str]) -> list[str]:
    good = []
    for code in found:
        try:
            obj = eval(code, {"ui": ui, "dyui": dyui})  # noqa: S307 - our own docstrings
            obj.to_node()
            good.append(code)
        except Exception as exc:  # surfaced in the build log
            print(f"gen_components: example for {name} failed: {code!r}: {exc}", file=sys.stderr)
    if not good:
        raise SystemExit(f"gen_components: no working Python example for {name!r}")
    return good


def _default(field) -> object:
    if field.is_required():
        return None
    d = field.get_default(call_default_factory=True)
    try:
        json.dumps(d)
    except TypeError:
        return repr(d)
    return d


def _fields(cls: type) -> list[dict]:
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


RST_CODE = re.compile(r"``([^`]+)``")
RST_ROLE = re.compile(r":(?:class|func|meth|data|attr|mod|obj):`~?([^`]+)`")


def _md(text: str) -> str:
    """RST inline markup → Markdown-style single backticks (rendered as <code> by the site)."""
    return RST_CODE.sub(r"`\1`", RST_ROLE.sub(r"`\1`", text))


def _body(cls: type) -> str:
    """Docstring minus the first paragraph and any Example: section."""
    parts = _doc(cls).split("\n\n")[1:]
    keep = [p for p in parts if not p.strip().startswith(("Example:", "Examples:"))]
    return _md("\n\n".join(" ".join(p.split()) for p in keep).strip())


def main() -> int:
    comps = []
    for cls in BUILTINS:
        info = cls.__dyui__
        comps.append({
            "name": info.name,
            "class": cls.__name__,
            "group": info.group,
            "llm": info.llm,
            "description": _md(info.description),
            "details": _body(cls),
            "signature": cls.signature(),
            "positional": list(info.positional),
            "varargs": info.varargs,
            "fields": _fields(cls),
            "python": _examples(cls, info.name),
            "llm_examples": [dict(e) for e in info.examples],
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = {"version": dyui.__version__, "components": comps}
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"gen_components: wrote {len(comps)} components -> {OUT.relative_to(OUT.parents[2])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
