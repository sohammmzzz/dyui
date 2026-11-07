"""Validation of LLM-supplied component objects (SPEC §5.1).

Turns ``{"ui": name, ...props}`` dicts into ``UINode`` dicts — or ``invalid``
nodes — and builds best-effort *partial* nodes for streaming previews.
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Mapping, Optional

from pydantic import ValidationError

from .._jsonsafe import MAX_DEPTH, finite, has_nonfinite, too_deep
from ..ui.base import Component, format_errors, invalid_node, validate_component
from ..ui.types import is_safe_url, to_json_text
from .partial_json import JSONObject, PartialStr

if TYPE_CHECKING:  # pragma: no cover
    from .catalog import Catalog

__all__ = [
    "validate_node",
    "validate_instance",
    "render_instance",
    "component_source",
    "failure_node",
    "partial_node",
    "repair_message",
    "ValidationFailure",
]

log = logging.getLogger("dyui")

_URL_KEYS = frozenset({"url", "src", "image", "poster", "href"})


class ValidationFailure(Exception):
    """A component object that couldn't be validated.

    Attributes:
        component: The ``ui`` name (if known).
        path: Dotted path of the first failing prop (``""`` for the whole object).
        message: Human-readable error.
        raw: The raw JSON text.
    """

    def __init__(self, message: str, *, component: Optional[str] = None, path: str = "", raw: str = "") -> None:
        super().__init__(message)
        self.component = component
        self.path = path
        self.message = message
        self.raw = raw


def _check(obj: Any, catalog: "Catalog") -> tuple[type[Component], dict[str, Any]]:
    if not isinstance(obj, Mapping):
        raise ValidationFailure("expected a JSON object like {\"ui\": \"<name>\", ...}", raw=to_json_text(obj))
    name = obj.get("ui")
    if not isinstance(name, str) or not name:
        raise ValidationFailure('missing "ui" component name', path="ui", raw=to_json_text(obj))
    cls = catalog.get(name)
    if cls is None:
        raise ValidationFailure(f"unknown component {name!r}", component=name, path="ui", raw=to_json_text(obj))
    return cls, dict(obj)


def _shallow_raw(obj: Any) -> str:
    """A short, non-recursive description of an over-deep object for the invalid chip."""
    if isinstance(obj, Mapping):
        return "{" + ", ".join(f'"{k}": …' for k in list(obj)[:8]) + "}"
    return "[…]" if isinstance(obj, (list, tuple)) else repr(obj)[:200]


def validate_instance(obj: Any, catalog: "Catalog") -> Component:
    """Validate one LLM component object and return the component instance.

    Raises:
        ValidationFailure: If the object is not a valid component.
    """
    if too_deep(obj):
        name = obj.get("ui") if isinstance(obj, Mapping) and isinstance(obj.get("ui"), str) else None
        raise ValidationFailure(f"component is nested too deeply (more than {MAX_DEPTH} levels)",
                                component=name, raw=_shallow_raw(obj))
    cls, data = _check(obj, catalog)
    if has_nonfinite(data):
        raise ValidationFailure("numbers must be finite (NaN / Infinity aren't valid JSON)",
                                component=cls.__dyui__.name, raw=to_json_text(finite(obj)))
    try:
        return validate_component(cls, data, {"catalog": catalog})
    except RecursionError:  # pragma: no cover - guarded by too_deep(); belt and braces
        raise ValidationFailure("component is nested too deeply", component=cls.__dyui__.name) from None
    except ValidationError as exc:
        err = exc.errors(include_url=False)
        path = ".".join(str(p) for p in err[0].get("loc", ())) if err else ""
        raise ValidationFailure(format_errors(exc), component=cls.__dyui__.name, path=path, raw=to_json_text(obj)) from None


def render_instance(instance: Component, node_id: str, raw: Any = None) -> dict[str, Any]:
    """Render a validated instance to its node, wrapping ``render()`` failures.

    Raises:
        ValidationFailure: If a custom component's ``render()`` raised.
    """
    try:
        return instance._node(node_id)
    except Exception as exc:  # render() of a custom component failed
        log.exception("render() of component %r failed", type(instance).__dyui__.name)
        raise ValidationFailure(
            f"render() failed: {type(exc).__name__}",
            component=type(instance).__dyui__.name,
            raw=to_json_text(raw if raw is not None else instance.model_dump(mode="json", exclude_none=True)),
        ) from None


def component_source(instance: Component) -> Optional[dict[str, Any]]:
    """For a custom component, its LLM-form ``{"ui": name, ...props}`` (else ``None``).

    Stored next to the expanded node so history shows the model what it wrote.
    """
    info = type(instance).__dyui__
    if not info.custom:
        return None
    try:
        props = instance.model_dump(mode="json", exclude_none=True)
    except Exception:  # pragma: no cover - exotic field types
        return None
    return {"ui": info.name, **props}


def validate_node(obj: Any, catalog: "Catalog", node_id: str) -> dict[str, Any]:
    """Validate one LLM component object and return its ``UINode``.

    Args:
        obj: The decoded ``{"ui": ..., ...props}`` object.
        catalog: The catalog restricting which components are allowed.
        node_id: The id for the resulting node.

    Raises:
        ValidationFailure: If the object is not a valid component.
    """
    return render_instance(validate_instance(obj, catalog), node_id, obj)


def failure_node(node_id: str, failure: ValidationFailure) -> dict[str, Any]:
    """Return the ``invalid`` node for a failure."""
    return invalid_node(node_id, failure.raw, failure.message)


def _clean_partial(value: Any, key: str | None = None) -> Any:
    if isinstance(value, PartialStr):
        if key in _URL_KEYS:
            return None
        return str(value)
    if isinstance(value, str):
        if key in _URL_KEYS and not is_safe_url(value):
            return None
        return value
    if isinstance(value, list):
        return [v for v in (_clean_partial(v) for v in value) if v is not None]
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if not isinstance(k, str) or k.startswith("__"):
                continue
            cv = _clean_partial(v, k)
            if cv is not None:
                out[k] = cv
        return out
    return value


def _partial_children(items: Any, parent: str, catalog: "Catalog") -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return out
    for i, child in enumerate(items):
        cid = f"{parent}-{i}"
        if isinstance(child, str):
            out.append({"id": cid, "ui": "markdown", "props": {"text": str(child)}, "status": "streaming"})
            continue
        node = partial_node(child, catalog, cid)
        if node is None:
            break
        out.append(node)
    return out


def partial_node(obj: Any, catalog: "Catalog", node_id: str) -> Optional[dict[str, Any]]:
    """Build a streaming preview node from partially parsed props.

    Tries full validation first (so normalization and sanitization apply);
    otherwise keeps only declared props with URLs sanitized and unfinished
    URLs dropped. Custom components preview as an empty streaming card.

    Returns:
        A node with ``status: "streaming"``, or ``None`` if the ``ui`` name is
        not known yet (or not in the catalog).
    """
    if not isinstance(obj, Mapping):
        return None
    name = obj.get("ui")
    if not isinstance(name, str) or isinstance(name, PartialStr) or (
        isinstance(obj, JSONObject) and "ui" not in obj.key_order
    ):
        return None
    cls = catalog.get(name)
    if cls is None:
        return None
    info = cls.__dyui__
    if info.custom:
        return {"id": node_id, "ui": "card", "props": {"__component__": name}, "children": [], "status": "streaming"}
    clean = _clean_partial(dict(obj))
    try:
        node = validate_component(cls, clean, {"catalog": catalog})._node(node_id)
        node["status"] = "streaming"
        return node
    except Exception:
        pass
    fields = cls.model_fields
    props: dict[str, Any] = {}
    children: Optional[list[dict[str, Any]]] = None
    for key, value in clean.items():
        if key not in fields:
            continue
        if key == "children":
            children = _partial_children(value, node_id, catalog)
        elif key in ("tabs", "items") and isinstance(value, list) and any(
            isinstance(v, dict) and "children" in v for v in value
        ):
            nested = []
            for i, entry in enumerate(value):
                if isinstance(entry, dict):
                    entry = dict(entry)
                    if "children" in entry:
                        entry["children"] = _partial_children(entry["children"], f"{node_id}-{key}-{i}", catalog)
                    nested.append(entry)
            props[key] = nested
        else:
            props[key] = value
    node: dict[str, Any] = {"id": node_id, "ui": info.render_as, "props": props}
    if children is not None or "children" in fields:
        node["children"] = children or []
    node["status"] = "streaming"
    return node


def repair_message(error: Any, *, component: Optional[str] = None) -> str:
    """Build the compact repair hint sent back to a model after a failed component.

    Accepts a :class:`ValidationFailure`, a parser ``ComponentError``, a pydantic
    ``ValidationError`` or an ``invalid`` node dict.

    Args:
        error: The failure.
        component: The component name, if not carried by ``error``.

    Returns:
        JSON text: ``{"error":"VALIDATION_FAILED","component":...,"path":...,"message":...}``.
    """
    path = ""
    message = str(error)
    if isinstance(error, ValidationFailure):
        component = component or error.component
        path, message = error.path, error.message
    elif isinstance(error, ValidationError):
        errs = error.errors(include_url=False)
        if errs:
            path = ".".join(str(p) for p in errs[0].get("loc", ()))
            message = str(errs[0].get("msg", message))
        component = component or getattr(error, "title", None)
    elif isinstance(error, Mapping):
        props = error.get("props") if isinstance(error.get("props"), Mapping) else error
        message = str(props.get("error") or error.get("error") or "invalid component")
        raw = props.get("raw")
        if component is None and isinstance(raw, str):
            try:
                decoded = json.loads(raw)
                if isinstance(decoded, dict) and isinstance(decoded.get("ui"), str):
                    component = decoded["ui"]
            except ValueError:
                pass
    else:
        component = component or getattr(error, "component", None)
        path = getattr(error, "path", "") or ""
        message = str(getattr(error, "error", None) or message)
    payload = {"error": "VALIDATION_FAILED", "component": component, "path": path, "message": message}
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
