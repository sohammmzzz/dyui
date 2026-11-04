"""The :class:`Component` base class, component metadata and node conversion.

Every DyUI component — built-in or custom — is a pydantic model. The class
carries metadata (LLM ``name``, ``group``, prompt ``description``,
``examples``) and knows how to turn itself into a ``UINode`` dict (SPEC §4)
with :meth:`Component.to_node`.
"""
from __future__ import annotations

import inspect
import json
import re
import secrets
from dataclasses import dataclass
from typing import Any, ClassVar, Iterable, Mapping, Optional

from pydantic import BaseModel, ConfigDict, PrivateAttr, ValidationError, model_validator
from pydantic.errors import PydanticUserError
from pydantic_core import to_jsonable_python

from .types import to_json_text

__all__ = [
    "Component",
    "ComponentInfo",
    "Model",
    "new_id",
    "snake_case",
    "coerce_child",
    "validate_component",
    "format_errors",
    "invalid_node",
    "registry",
    "lookup",
]

_MODEL_CONFIG = ConfigDict(
    extra="ignore",
    coerce_numbers_to_str=True,
    populate_by_name=True,
    validate_assignment=False,
    protected_namespaces=(),
)

_CONFIG_KEYS = ("name", "group", "description", "examples", "llm", "positional", "varargs", "hint")

_REGISTRY: dict[str, type["Component"]] = {}


def new_id(prefix: str = "c") -> str:
    """Return a fresh random id like ``c_1a2b3c4d``.

    Args:
        prefix: Id prefix (``c`` components, ``m`` messages, ``s`` steps...).
    """
    return f"{prefix}_{secrets.token_hex(4)}"


def snake_case(name: str) -> str:
    """Convert ``PascalCase`` to ``snake_case`` (``LinkPreview`` → ``link_preview``)."""
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", name)
    return s.lower()


def _first_paragraph(doc: str | None) -> str:
    if not doc:
        return ""
    text = inspect.cleandoc(doc).strip()
    para = text.split("\n\n", 1)[0]
    return " ".join(para.split())


@dataclass(frozen=True)
class ComponentInfo:
    """Static metadata about a component class.

    Attributes:
        name: The LLM-facing name (snake_case), e.g. ``"stat"``.
        group: Catalog group (``content``, ``data``, ``media``, ``interactive``,
            ``layout``, ``agent``, ``developer`` or ``custom``).
        description: One-line prompt description (first docstring paragraph).
        examples: Example prop dicts (validated at class creation).
        llm: Whether the component may appear in an LLM catalog.
        builtin: True for DyUI's own components.
        custom: True when the class defines ``render()`` (expanded server-side).
        render_as: The built-in ``ui`` name nodes are emitted as.
        positional: Prop names bound to leading positional constructor args.
        varargs: Prop that collects remaining positional args (e.g. ``children``).
        hint: Extra usage hint appended to tool descriptions (structured mode).
    """

    name: str
    group: str
    description: str
    examples: tuple[dict[str, Any], ...]
    llm: bool
    builtin: bool
    custom: bool
    render_as: str
    positional: tuple[str, ...]
    varargs: Optional[str]
    hint: str = ""


def _namespace_annotations(namespace: Mapping[str, Any]) -> dict[str, Any]:
    anns = namespace.get("__annotations__")
    if isinstance(anns, dict):
        return anns
    annotate = namespace.get("__annotate__") or namespace.get("__annotate_func__")
    if annotate is not None:  # pragma: no cover - Python 3.14+ lazy annotations
        try:
            import annotationlib  # type: ignore[import-not-found]

            return dict(annotationlib.call_annotate_function(annotate, annotationlib.Format.FORWARDREF))
        except Exception:
            return {}
    return {}


def _meta_property(key: str) -> property:
    def getter(cls: type) -> Any:
        if key in cls.__dict__:  # a field default being collected by pydantic
            return cls.__dict__[key]
        info = cls.__dict__.get("__dyui__")
        if info is None or not info.name or key in (getattr(cls, "__pydantic_fields__", None) or {}):
            raise AttributeError(key)
        return getattr(info, key)

    getter.__name__ = key
    getter.__doc__ = f"The component's ``{key}`` (see :class:`ComponentInfo`)."
    return property(getter)


class ComponentMeta(type(BaseModel)):  # type: ignore[misc]
    """Metaclass that lifts DyUI class-level config out of the pydantic namespace.

    ``name = "flight"``, ``group``, ``description``, ``examples``, ``llm``,
    ``positional`` and ``varargs`` may be written as plain class attributes on a
    component; they are read here and never become pydantic fields, so a
    component can still have a *prop* called ``name`` or ``description``.
    """

    def __new__(mcs, cls_name: str, bases: tuple[type, ...], namespace: dict[str, Any], **kwargs: Any):
        anns = _namespace_annotations(namespace)
        config: dict[str, Any] = {}
        for key in _CONFIG_KEYS:
            if key in namespace:
                ann = anns.get(key)
                if ann is None or "ClassVar" in str(ann):
                    config[key] = namespace.pop(key)
        cls = super().__new__(mcs, cls_name, bases, namespace, **kwargs)
        info = _build_info(cls, bases, config)
        type.__setattr__(cls, "__dyui__", info)
        if info.name:
            if "ui" in cls.__pydantic_fields__:
                raise TypeError(f"{cls_name}: 'ui' is reserved and cannot be a prop name")
            if info.builtin or info.name not in _REGISTRY or not _REGISTRY[info.name].__dyui__.builtin:
                _REGISTRY[info.name] = cls
            _check_examples(cls, info)
        return cls

    name = _meta_property("name")
    group = _meta_property("group")
    description = _meta_property("description")
    examples = _meta_property("examples")
    llm = _meta_property("llm")


def _parent_info(bases: Iterable[type]) -> ComponentInfo | None:
    for base in bases:
        info = getattr(base, "__dyui__", None)
        if isinstance(info, ComponentInfo):
            return info
    return None


def _build_info(cls: type, bases: tuple[type, ...], config: dict[str, Any]) -> ComponentInfo:
    parent = _parent_info(bases)
    if parent is None:  # the abstract Component base itself
        return ComponentInfo("", "custom", "", (), False, False, False, "", (), None)
    builtin = cls.__module__.startswith("dyui.ui.")
    name = str(config.get("name") or snake_case(cls.__name__))
    custom = (not builtin) and cls.render is not Component.render  # type: ignore[attr-defined]
    if builtin or custom:
        render_as = name
    else:
        render_as = parent.render_as  # subclass of a built-in without render()
    examples = config.get("examples") or ()
    if isinstance(examples, Mapping):
        examples = (examples,)
    if config.get("group"):
        group = str(config["group"])
    elif custom:
        group = "custom"
    elif parent.name:
        group = parent.group
    else:
        group = "content" if builtin else "custom"
    return ComponentInfo(
        name=name,
        group=group,
        description=" ".join(str(config.get("description") or _first_paragraph(cls.__doc__)).split()),
        examples=tuple(dict(e) for e in examples),
        llm=bool(config.get("llm", parent.llm if parent.name else True)),
        builtin=builtin,
        custom=custom,
        render_as=render_as,
        positional=tuple(config.get("positional", parent.positional if parent.name else ())),
        varargs=config.get("varargs", parent.varargs if parent.name else None),
        hint=" ".join(str(config.get("hint") or "").split()),
    )


def _check_examples(cls: type, info: ComponentInfo) -> None:
    for i, example in enumerate(info.examples):
        try:
            cls.model_validate(example)  # type: ignore[attr-defined]
        except PydanticUserError:  # forward refs not resolvable yet — skip
            return
        except ValidationError as exc:
            raise TypeError(f"{cls.__name__}.examples[{i}] is invalid: {format_errors(exc)}") from None


def _is_child_like(value: Any) -> bool:
    return isinstance(value, (BaseModel, Mapping, list, tuple))


def bind_positional(
    owner: str,
    positional: tuple[str, ...],
    varargs: str | None,
    args: tuple[Any, ...],
    data: dict[str, Any],
) -> dict[str, Any]:
    """Map positional constructor arguments onto prop names.

    Scalars fill ``positional`` slots in order; component-like values (models,
    dicts, lists) — and anything once the slots are full — go to ``varargs``.

    Raises:
        TypeError: On duplicate or surplus arguments.
    """
    out = dict(data)
    slots = list(positional)
    extra: list[Any] = []
    for arg in args:
        if varargs and (extra or not slots or (_is_child_like(arg) and slots[0] != varargs)):
            extra.append(arg)
        elif slots:
            key = slots.pop(0)
            if key in out:
                raise TypeError(f"{owner}() got multiple values for argument {key!r}")
            out[key] = arg
        else:
            raise TypeError(f"{owner}() takes {len(positional)} positional argument(s) but {len(args)} were given")
    if extra:
        if varargs in out:
            raise TypeError(f"{owner}() got multiple values for argument {varargs!r}")
        if len(extra) == 1 and isinstance(extra[0], (list, tuple)):
            out[varargs] = list(extra[0])  # type: ignore[index]
        else:
            out[varargs] = extra  # type: ignore[index]
    return out


class Model(BaseModel):
    """Base for nested prop models (``Button``, ``Field``, ``Tab``...).

    Supports positional construction like components, and building from a bare
    string via ``__str_field__`` (e.g. a badge from ``"beta"``).
    """

    model_config = _MODEL_CONFIG
    __positional__: ClassVar[tuple[str, ...]] = ()
    __varargs__: ClassVar[Optional[str]] = None
    __str_field__: ClassVar[Optional[str]] = None

    def __init__(self, *args: Any, **data: Any) -> None:
        if args:
            data = bind_positional(type(self).__name__, self.__positional__, self.__varargs__, args, data)
        super().__init__(**data)

    @model_validator(mode="before")
    @classmethod
    def _from_scalar(cls, data: Any) -> Any:
        if isinstance(data, (str, int, float)) and not isinstance(data, bool) and cls.__str_field__:
            return {cls.__str_field__: data}
        return _strip_nulls(cls, data)


def _strip_nulls(cls: type[BaseModel], data: Any) -> Any:
    """Treat explicit ``null`` for optional props as "not provided" (tool-call args)."""
    if isinstance(data, dict) and any(v is None for v in data.values()):
        fields = cls.model_fields
        return {k: v for k, v in data.items() if v is not None or (k in fields and fields[k].is_required())}
    return data


class Component(BaseModel, metaclass=ComponentMeta):
    """Base class for every DyUI component.

    Subclass it (and register with ``@app.component``) to define a custom
    component. The class docstring becomes the prompt description, the fields
    become props, and :meth:`render` returns a tree of built-in components::

        @app.component
        class Flight(dyui.Component):
            \"\"\"A bookable flight option. Use when listing specific flights.\"\"\"
            airline: str
            depart: str
            price: float

            examples = [{"airline": "TAP", "depart": "Fri 18:05", "price": 189}]

            def render(self):
                return ui.Card(self.airline, ui.Stat("Price", f"${self.price:.0f}"))

    Class-level options (plain class attributes): ``name`` (LLM name; default
    snake_case of the class name), ``description`` (default: first docstring
    paragraph), ``examples``, ``group``, ``llm`` (False hides it from the LLM),
    ``positional`` (prop names accepted positionally).

    Pass ``id="..."`` to the constructor to give the rendered node a stable id;
    yielding another component with the same id replaces it in place.
    """

    model_config = _MODEL_CONFIG
    __dyui__: ClassVar[ComponentInfo]
    _node_id: Optional[str] = PrivateAttr(default=None)

    def __init__(self, *args: Any, **data: Any) -> None:
        info = type(self).__dyui__
        if args:
            data = bind_positional(type(self).__name__, info.positional, info.varargs, args, data)
        node_id = None
        if "id" in data and "id" not in type(self).model_fields:
            node_id = data.pop("id")
        super().__init__(**data)
        if node_id is not None:
            self._node_id = str(node_id)

    @model_validator(mode="before")
    @classmethod
    def _null_is_missing(cls, data: Any) -> Any:
        return _strip_nulls(cls, data)

    # ------------------------------------------------------------------ API
    def render(self) -> Any:
        """Return the built-in component tree for a custom component.

        Built-ins don't override this. Custom components must, returning a
        component (or a list of components, wrapped in a card, or a string,
        rendered as markdown).
        """
        raise NotImplementedError(f"{type(self).__name__} must define render()")

    def to_node(self, id: str | None = None) -> dict[str, Any]:
        """Serialize to a ``UINode`` dict (SPEC §4).

        Custom components are expanded via :meth:`render`; the outer node keeps
        the custom name in ``props.__component__``. Child ids derive from the
        parent id (``<id>-0``, ``<id>-tabs-1-0``...), so they are stable.

        Args:
            id: Node id; defaults to the constructor ``id=`` or a fresh ``c_<8hex>``.

        Returns:
            The node dict ``{id, ui, props, children?, status}``.
        """
        return self._node(id or self._node_id or new_id())

    @classmethod
    def signature(cls) -> str:
        """Return the compact TS-like prompt line, e.g.
        ``stat(label: string, value: string|number, ...) — One headline number.``"""
        from .signature import render_signature

        return render_signature(cls)

    @classmethod
    def json_schema(cls, strict: bool = True) -> dict[str, Any]:
        """Return the JSON Schema of this component's props (SPEC §5.0).

        Args:
            strict: Produce a provider strict-mode compatible schema
                (``additionalProperties: false`` everywhere, every property
                required, optionals nullable, free-form JSON and child
                components encoded as JSON strings, no ``default``).

        Returns:
            A JSON Schema ``object`` dict (no ``"ui"`` key — the tool name
            identifies the component).
        """
        from .schema import component_schema

        return component_schema(cls, strict=strict)

    @classmethod
    def declared_actions(cls, props: Mapping[str, Any]) -> list[tuple[str, Optional[dict[str, Any]]]]:
        """Actions a rendered node of this class may send, as ``(name, data)``.

        Used by the server to reject forged actions. ``data`` is the static data
        declared alongside the action (``None`` when not applicable).
        """
        return []

    # ------------------------------------------------------------- internal
    def _node(self, nid: str) -> dict[str, Any]:
        info = type(self).__dyui__
        if info.custom:
            child = _normalize_render(self.render(), type(self).__name__)
            node = child._node(nid)
            node.setdefault("props", {})["__component__"] = info.name
            return node
        props: dict[str, Any] = {}
        children: list[Any] | None = None
        for fname in type(self).model_fields:
            value = getattr(self, fname)
            if value is None:
                continue
            if fname == "children":
                children = [_dump(c, nid, (str(i),)) for i, c in enumerate(value)]
                continue
            props[fname] = _dump(value, nid, (fname,))
        node: dict[str, Any] = {"id": nid, "ui": info.render_as, "props": props}
        if children is not None:
            node["children"] = children
        node["status"] = "done"
        return self._finish_node(node)

    def _finish_node(self, node: dict[str, Any]) -> dict[str, Any]:
        return node


def _normalize_render(out: Any, owner: str) -> Component:
    if isinstance(out, Component):
        return out
    if isinstance(out, str):
        from .content import Markdown

        return Markdown(text=out)
    if isinstance(out, (list, tuple)):
        from .layout import Card

        return Card(children=list(out))
    if isinstance(out, Mapping) and "ui" in out:
        return coerce_child(dict(out), None)
    raise TypeError(f"{owner}.render() must return a component, got {type(out).__name__}")


def _dump(value: Any, root: str, path: tuple[str, ...]) -> Any:
    if isinstance(value, Component):
        suffix = "-".join(p for p in path if p != "children")
        return value._node(f"{root}-{suffix}" if suffix else root)
    if isinstance(value, BaseModel):
        out: dict[str, Any] = {}
        for k in type(value).model_fields:
            v = getattr(value, k)
            if v is not None:
                out[k] = _dump(v, root, path + (k,))
        return out
    if isinstance(value, (list, tuple)):
        return [_dump(v, root, path + (str(i),)) for i, v in enumerate(value)]
    if isinstance(value, Mapping):
        return {str(k): _dump(v, root, path + (str(k),)) for k, v in value.items()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return to_jsonable_python(value, fallback=str)


# ----------------------------------------------------------------- validation
def registry() -> dict[str, type[Component]]:
    """Return a snapshot of every known component class keyed by LLM name."""
    return dict(_REGISTRY)


def lookup(name: str, context: Mapping[str, Any] | None = None) -> type[Component] | None:
    """Resolve a component class by name, restricted to ``context["catalog"]`` if given."""
    catalog = (context or {}).get("catalog") if context else None
    if catalog is not None:
        return catalog.get(name)
    return _REGISTRY.get(name)


def format_errors(exc: ValidationError, limit: int = 3) -> str:
    """Summarize a pydantic ``ValidationError`` in one short line."""
    errors = exc.errors(include_url=False)
    parts = []
    for err in errors[:limit]:
        loc = ".".join(str(p) for p in err.get("loc", ()))
        msg = str(err.get("msg", "invalid value"))
        parts.append(f"{loc}: {msg}" if loc else msg)
    if len(errors) > limit:
        parts.append(f"(+{len(errors) - limit} more)")
    return "; ".join(parts)[:400]


def _drop_invalid(cls: type[BaseModel], payload: dict[str, Any], exc: ValidationError) -> bool:
    fields = cls.model_fields
    aliases = {f.alias: n for n, f in fields.items() if f.alias}
    changed = False
    drop_items: dict[str, set[int]] = {}
    for err in exc.errors(include_url=False):
        loc = err.get("loc") or ()
        if not loc or not isinstance(loc[0], str) or loc[0] not in payload:
            continue
        key = loc[0]
        fname = aliases.get(key, key)
        field = fields.get(fname)
        if field is None:
            continue
        if len(loc) >= 2 and isinstance(loc[1], int) and isinstance(payload[key], list):
            drop_items.setdefault(key, set()).add(loc[1])
        elif not field.is_required():
            payload.pop(key, None)
            changed = True
    for key, idxs in drop_items.items():
        if key in payload:
            payload[key] = [v for i, v in enumerate(payload[key]) if i not in idxs]
            changed = True
    return changed


def validate_component(
    cls: type[Component], data: Mapping[str, Any], context: Mapping[str, Any] | None = None
) -> Component:
    """Validate LLM-style props leniently.

    Unknown and ``__dunder`` props are dropped, values are coerced in lax mode,
    invalid *optional* props and invalid list items are dropped and validation
    retried. Only errors in required props fail.

    Args:
        cls: The component class.
        data: Props (may include ``"ui"``/``"id"``, which are ignored).
        context: Validation context; ``{"catalog": Catalog}`` restricts children.

    Raises:
        pydantic.ValidationError: If required props are missing or invalid.
    """
    fields = cls.model_fields
    payload = {
        k: v
        for k, v in data.items()
        if isinstance(k, str) and k != "ui" and not k.startswith("__") and (k != "id" or "id" in fields)
    }
    last: ValidationError | None = None
    for _ in range(6):
        try:
            return cls.model_validate(payload, context=dict(context) if context else None)
        except ValidationError as exc:
            last = exc
            if not _drop_invalid(cls, payload, exc):
                break
    assert last is not None
    raise last


def coerce_child(value: Any, context: Mapping[str, Any] | None) -> Component:
    """Turn a child value (component, dict, string) into a component instance.

    Never raises: unknown or invalid children become :class:`~dyui.ui.Invalid`.
    """
    from .content import Markdown
    from .developer import Invalid

    if isinstance(value, Component):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{") and text.endswith("}") and '"ui"' in text:
            try:  # strict tool schemas carry children as JSON text
                decoded = json.loads(text)
            except ValueError:
                decoded = None
            if isinstance(decoded, dict) and "ui" in decoded:
                return coerce_child(decoded, context)
        return Markdown(text=value)
    if isinstance(value, Mapping):
        name = value.get("ui")
        if not isinstance(name, str) or not name:
            return Invalid(raw=to_json_text(value), error='missing "ui" component name')
        cls = lookup(name, context)
        if cls is None or (context and not cls.__dyui__.llm):
            return Invalid(raw=to_json_text(value), error=f"unknown component {name!r}")
        try:
            return validate_component(cls, value, context)
        except ValidationError as exc:
            return Invalid(raw=to_json_text(value), error=format_errors(exc))
    return Invalid(raw=to_json_text(value), error="not a component")


def invalid_node(nid: str, raw: str, error: str) -> dict[str, Any]:
    """Build the ``invalid`` node shown for components that failed validation."""
    return {
        "id": nid,
        "ui": "invalid",
        "props": {"raw": raw[:4000], "error": error},
        "status": "error",
        "error": error,
    }


def node_json(node: Mapping[str, Any]) -> str:
    """Compact JSON for a node (used in tests and logs)."""
    return json.dumps(node, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
