"""Single source of truth for the DyUI eval dataset.

Everything about the language (component names, props, required/optional, enums, signatures)
is read from the installed ``dyui`` package: ``dyui.catalog()`` and every class's
``model_json_schema()``.  Nothing is hand-copied.  What *is* written by hand here is only
what the spec in MODEL_EVAL.md defines outside the code: the wrong-name blocklist (section N),
the decision-policy rows, category shares and header grammar.

Usage::

    from spec import SPEC
    SPEC.components["chart"].enums        # {"kind": [...], ...}
    SPEC.hash                              # stable sha256 over the whole spec
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional

import dyui

DYUI_VERSION: str = dyui.__version__

# ---------------------------------------------------------------------------------------------
# Hand-written parts of the spec (MODEL_EVAL.md)
# ---------------------------------------------------------------------------------------------

#: Category shares (of the whole set).  Sum is 1.0.
CATEGORY_SHARES: dict[str, float] = {
    "A": 0.20, "B": 0.12, "C": 0.10, "D": 0.09, "E": 0.09, "F": 0.07, "G": 0.08,
    "H": 0.04, "I": 0.04, "J": 0.07, "K": 0.03, "L": 0.02, "N": 0.03, "S": 0.02,
}
CATEGORY_NAMES: dict[str, str] = {
    "A": "single component", "B": "intent -> component selection", "C": "several components",
    "D": "nested layouts", "E": "interactive flows", "F": "follow-up edits", "G": "grounded in tool results",
    "H": "restricted set / dyui off", "I": "custom components", "J": "plain text", "K": "guardrails",
    "L": "agent components", "N": "wrong-name traps", "S": "self-knowledge",
}

#: Decision-policy rows (MODEL_EVAL.md "The decision policy"), slug -> (user need, correct component).
POLICY: dict[str, tuple[str, str]] = {
    "headline_number": ("One headline number", "stat"),
    "headline_numbers": ("2-6 headline numbers", "stats"),
    "trend": ("Values over time", "chart line/area"),
    "compare": ("Compare categories", "chart bar (stacked for parts within categories)"),
    "shares": ("Shares of a whole (<= 6)", "chart donut/pie"),
    "relationship": ("x/y relationship", "chart scatter"),
    "records_table": (">= 3 records x >= 2 fields", "table"),
    "entity_facts": ("Facts about one entity", "keyvalue"),
    "events": ("Ordered events", "timeline"),
    "work_sequence": ("Sequence of work with statuses", "plan"),
    "goal_progress": ("One goal's progress", "progress"),
    "code": ("Code, command or config", "code with language"),
    "note": ("Tip, warning, error or success", "callout with level"),
    "variants": ("Same thing in variants", "tabs"),
    "faq": ("FAQ or optional depth", "accordion"),
    "comparable_items": ("Comparable items", "carousel/grid of cards; list when compact"),
    "structured_input": ("Assistant needs structured input", "form"),
    "single_choice": ("One question, fixed options", "choice"),
    "irreversible_action": ("Irreversible or outward action", "confirm (danger when destructive)"),
    "next_actions": ("Things the user can do next", "buttons"),
    "next_questions": ("Things the user might ask next", "quick_replies (<= 4)"),
    "citing_sources": ("Citing given sources", "sources (URLs from context only)"),
    "media": ("Media from given URLs", "image/gallery/video/audio/file/link_preview"),
    "no_component": ("Small talk, definitions, one-line facts, opinions, rewriting", "no component"),
}

#: Wrong-name traps (MODEL_EVAL.md section N).  Also the hallucination blocklist used by the scorer.
#: ``says`` = names a user (or a model) tends to use; ``correct`` = the real component(s).
WRONG_NAME_TABLE: list[dict[str, Any]] = [
    {"says": ["alert", "banner", "notice", "toast"], "correct": ["callout"], "hint": "callout + level", "row": "note"},
    {"says": ["KPI", "metric", "number card"], "correct": ["stat", "stats"], "hint": "stat / stats", "row": "headline_number"},
    {"says": ["bar chart", "line graph", "histogram", "pie"], "correct": ["chart"], "hint": "chart + kind (histogram = bar)", "row": "compare"},
    {"says": ["stepper", "steps", "checklist", "todo"], "correct": ["plan", "timeline"], "hint": "plan or timeline", "row": "work_sequence"},
    {"says": ["dropdown", "select", "radio", "checkbox"], "correct": ["choice", "form"], "hint": "choice, or a form field type", "row": "single_choice"},
    {"says": ["button", "CTA"], "correct": ["buttons"], "hint": "buttons with items", "row": "next_actions"},
    {"says": ["chips", "suggestions"], "correct": ["quick_replies"], "hint": "quick_replies with options", "row": "next_questions"},
    {"says": ["modal", "dialog", "are you sure"], "correct": ["confirm"], "hint": "confirm", "row": "irreversible_action"},
    {"says": ["collapsible", "FAQ", "expander"], "correct": ["accordion"], "hint": "accordion", "row": "faq"},
    {"says": ["slider", "swiper", "cards row"], "correct": ["carousel"], "hint": "carousel", "row": "comparable_items"},
    {"says": ["tag", "label", "pill"], "correct": ["badges"], "hint": "badges", "row": "note"},
    {"says": ["code block", "snippet"], "correct": ["code"], "hint": "code + language", "row": "code"},
    {"says": ["citation", "references"], "correct": ["sources"], "hint": "sources", "row": "citing_sources"},
    {"says": ["spreadsheet", "grid of data"], "correct": ["table"], "hint": "table (grid is layout only)", "row": "records_table"},
]

#: Names that must never appear as a ``"ui"`` value (hallucinated components).  Built from the table
#: above (snake_case) plus common variants.  A name that is a real component is removed.
_EXTRA_WRONG_NAMES = [
    "bar_chart", "line_chart", "line_graph", "pie_chart", "donut_chart", "area_chart", "histogram", "pie", "graph",
    "alert", "banner", "notice", "toast", "kpi", "metric", "metrics", "number_card", "stat_card", "kpi_card",
    "stepper", "steps", "checklist", "todo", "todo_list", "dropdown", "select", "radio", "radio_group", "checkbox",
    "checkboxes", "button", "cta", "chips", "chip", "suggestions", "modal", "dialog", "popup", "collapsible", "faq",
    "expander", "slider", "swiper", "cards_row", "card_row", "tag", "tags", "label", "pill", "pills", "code_block",
    "snippet", "citation", "citations", "references", "spreadsheet", "data_grid", "datagrid", "text", "paragraph",
    "heading", "title", "html", "div", "input", "textfield", "text_input", "text_area", "textarea", "date_picker",
    "datepicker", "image_gallery", "map", "tooltip", "avatar", "navbar", "sidebar", "menu", "breadcrumb",
    "pagination", "stepper_form", "wizard", "toggle", "switch", "icon", "banner_alert",
]

#: Wrong prop -> right prop, per component (MODEL_EVAL.md "Prop-name traps").
WRONG_PROPS: dict[str, dict[str, str]] = {
    "table": {"headers": "columns", "header": "columns", "data": "rows"},
    "chart": {"type": "kind", "chart": "kind", "data": "series[].data", "values": "series[].data"},
    "callout": {"type": "level", "variant": "level", "severity": "level", "message": "text", "body": "text"},
    "quick_replies": {"items": "options", "replies": "options", "suggestions": "options"},
    "buttons": {"buttons": "items", "options": "items", "actions": "items"},
    "tabs": {"items": "tabs"},
    "stat": {"title": "label", "name": "label"},
}

#: Phrases a reference reply must never contain (filler).
FILLER_PHRASES = [
    "feel free", "let me know", "hope this helps", "i hope", "don't hesitate", "do not hesitate", "happy to help",
    "is there anything else", "anything else you", "if you have any", "if you need anything", "as an ai",
    "great question", "i'd be happy", "i would be happy", "glad to help", "reach out", "have a great day", "just ask",
    "no hay de qué dudar", "n'hésitez pas", "zögern sie nicht", "não hesite", "non esitare", "no dudes en",
    "no dudes", "háganos saber", "fais-moi savoir", "sag mir bescheid", "avise-me", "fammi sapere",
]

#: Phrases that betray the header restriction (must not appear in H replies).
RESTRICTION_LEAKS = [
    "dyui", "component", "restrict", "not available", "isn't available", "is not available", "unavailable",
    "can't render", "cannot render", "can't use", "cannot use", "not allowed", "allowed list", "only have",
    "i don't have a chart", "no chart component", "markdown only", "plain text only",
]

# Header grammar -----------------------------------------------------------------------------
HEADER_KINDS = ("none", "restricted", "custom", "restricted_custom", "off")

# ---------------------------------------------------------------------------------------------
# Schema walker
# ---------------------------------------------------------------------------------------------

@dataclass
class Prop:
    name: str
    required: bool
    types: tuple[str, ...] = ()           # json-schema primitive types seen
    enum: Optional[list[str]] = None
    obj: Optional["Obj"] = None            # nested object (or items object of an array)
    is_array: bool = False
    children: bool = False                 # array of component nodes
    free: bool = False                     # free-form JSON (data / input / output)


@dataclass
class Obj:
    props: dict[str, Prop] = field(default_factory=dict)

    @property
    def required(self) -> list[str]:
        return [n for n, p in self.props.items() if p.required]

    @property
    def optional(self) -> list[str]:
        return [n for n, p in self.props.items() if not p.required]


def _deref(s: dict, defs: dict) -> dict:
    while isinstance(s, dict) and "$ref" in s:
        s = defs[s["$ref"].split("/")[-1]]
    return s


def _variants(s: dict, defs: dict) -> list[dict]:
    s = _deref(s, defs)
    if "anyOf" in s:
        out: list[dict] = []
        for v in s["anyOf"]:
            out.extend(_variants(v, defs))
        return out
    return [s]


def _prop(name: str, s: dict, required: bool, defs: dict) -> Prop:
    vs = [v for v in _variants(s, defs) if v.get("type") != "null"]
    p = Prop(name=name, required=required)
    types: list[str] = []
    for v in vs:
        t = v.get("type")
        if "enum" in v:
            p.enum = list(v["enum"])
        if t:
            types.append(t)
        if t == "array":
            p.is_array = True
            items = v.get("items", {})
            if items == {}:
                p.children = True
            else:
                for iv in _variants(items, defs):
                    if "properties" in iv:
                        p.obj = _obj(iv, defs)
        elif t == "object" or "properties" in v:
            if "properties" in v:
                p.obj = _obj(v, defs)
            else:
                p.free = True
        elif not t and "enum" not in v:
            p.free = True  # untyped (json.data, step.input)
    p.types = tuple(dict.fromkeys(types))
    return p


def _obj(s: dict, defs: dict) -> Obj:
    s = _deref(s, defs)
    req = set(s.get("required", []))
    o = Obj()
    for name, ps in s.get("properties", {}).items():
        o.props[name] = _prop(name, ps, name in req, defs)
    return o


def schema_to_obj(schema: dict) -> Obj:
    return _obj(schema, schema.get("$defs", {}))


@dataclass
class ComponentSpec:
    name: str
    group: str
    cls: Any
    signature: str          # full line from DyUI (with description)
    header_signature: str   # without " - description"
    schema: dict
    obj: Obj
    builtin: bool

    @property
    def required(self) -> list[str]:
        return self.obj.required

    @property
    def optional(self) -> list[str]:
        return self.obj.optional

    @property
    def enums(self) -> dict[str, list[str]]:
        """Enum paths (``kind``, ``items[].color``, ``fields[].type``) -> values."""
        out: dict[str, list[str]] = {}
        _collect_enums(self.obj, "", out)
        return out

    @property
    def has_children(self) -> bool:
        return _has_children(self.obj)


def _collect_enums(o: Obj, prefix: str, out: dict[str, list[str]]) -> None:
    for n, p in o.props.items():
        path = f"{prefix}{n}"
        if p.enum:
            out[path] = list(p.enum)
        if p.obj:
            _collect_enums(p.obj, path + ("[]." if p.is_array else "."), out)


def _has_children(o: Obj) -> bool:
    return any(p.children or (p.obj and _has_children(p.obj)) for p in o.props.values())


def header_signature(cls: Any) -> str:
    """The ``name(prop: type, opt?: type)`` form used in headers (DyUI's own, minus description)."""
    sig = cls.signature()
    return sig.split(" — ")[0].split(" � ")[0].rstrip()


def make_component_spec(cls: Any) -> ComponentSpec:
    info = cls.__dyui__
    schema = cls.model_json_schema()
    return ComponentSpec(
        name=info.name, group=info.group, cls=cls, signature=cls.signature(),
        header_signature=header_signature(cls), schema=schema, obj=schema_to_obj(schema), builtin=info.builtin,
    )


class Spec:
    def __init__(self) -> None:
        cat = dyui.catalog()
        self.catalog = cat
        self.names: list[str] = cat.names
        self.components: dict[str, ComponentSpec] = {c.__dyui__.name: make_component_spec(c) for c in cat}
        self.groups: dict[str, list[str]] = {}
        for n, c in self.components.items():
            self.groups.setdefault(c.group, []).append(n)
        self.blocklist: set[str] = (
            set(_EXTRA_WRONG_NAMES)
            | {w.lower().replace(" ", "_") for row in WRONG_NAME_TABLE for w in row["says"]}
        ) - set(self.names)
        self.wrong_props = WRONG_PROPS
        self.layouts = [n for n in ("card", "grid", "tabs", "accordion", "carousel") if n in self.components]

    # -- convenience -------------------------------------------------------------------------
    def enum_cells(self) -> list[tuple[str, str, str]]:
        """Every (component, enum path, value) in the built-in spec."""
        out = []
        for n, c in self.components.items():
            for path, vals in c.enums.items():
                out.extend((n, path, v) for v in vals)
        return out

    def optional_props(self) -> list[tuple[str, str]]:
        return [(n, p) for n, c in self.components.items() for p in c.optional]

    def group_of(self, name: str) -> str:
        return self.components[name].group

    @property
    def hash(self) -> str:
        payload = {
            "dyui": DYUI_VERSION,
            "components": {n: {"signature": c.signature, "schema": c.schema} for n, c in self.components.items()},
            "blocklist": sorted(self.blocklist),
            "wrong_props": WRONG_PROPS,
            "wrong_name_table": WRONG_NAME_TABLE,
            "policy": POLICY,
            "shares": CATEGORY_SHARES,
        }
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()


SPEC = Spec()


if __name__ == "__main__":
    print(f"dyui {DYUI_VERSION}  spec hash {SPEC.hash[:16]}  {len(SPEC.names)} components")
    for n, c in SPEC.components.items():
        print(f"{n:14s} req={c.required} opt={c.optional} enums={ {k: len(v) for k, v in c.enums.items()} }")
    print(len(SPEC.blocklist), "blocklisted names")
