"""Render component classes as compact TS-like prompt signatures.

``stat(label: string, value: string|number, unit?: string, ...) — One headline number.``
"""
from __future__ import annotations

import inspect
import json
import types
from typing import Annotated, Any, Iterable, Literal, Union, get_args, get_origin

from pydantic import BaseModel

from .types import TS, PyOnly

__all__ = ["render_signature", "ts_type", "split_annotated", "is_union", "prompt_fields"]

_NoneType = type(None)


def split_annotated(tp: Any, meta: Iterable[Any] = ()) -> tuple[Any, list[Any]]:
    """Strip (nested) ``Annotated`` wrappers, returning ``(type, metadata)``."""
    extra = list(meta)
    while get_origin(tp) is Annotated:
        args = get_args(tp)
        tp = args[0]
        extra = list(args[1:]) + extra
    return tp, extra


def is_union(tp: Any) -> bool:
    """True for ``Union[...]``/``Optional[...]`` and PEP 604 ``X | Y``."""
    origin = get_origin(tp)
    return origin is Union or (hasattr(types, "UnionType") and origin is getattr(types, "UnionType"))


def prompt_fields(model: type[BaseModel]) -> list[tuple[str, Any]]:
    """Return ``(name, FieldInfo)`` pairs visible to the LLM (skips Python-only props)."""
    out = []
    for name, field in model.model_fields.items():
        if any(isinstance(m, PyOnly) for m in field.metadata):
            continue
        out.append((name, field))
    return out


def _wrap(text: str) -> str:
    depth = 0
    for ch in text:
        if ch in "{([":
            depth += 1
        elif ch in "})]":
            depth -= 1
        elif ch == "|" and depth == 0:
            return f"({text})"
    return text


def ts_type(tp: Any, meta: Iterable[Any] = (), *, drop_null: bool = False) -> str:
    """Render a Python/pydantic annotation as a compact TypeScript-like type."""
    tp, extra = split_annotated(tp, meta)
    for m in extra:
        if isinstance(m, TS):
            return m.text
    if tp is Any or tp is object:
        return "any"
    if tp is str:
        return "string"
    if tp is bool:
        return "boolean"
    if tp in (int, float):
        return "number"
    if tp is _NoneType:
        return "null"
    origin = get_origin(tp)
    if origin is Literal:
        return "|".join(json.dumps(a) for a in get_args(tp))
    if is_union(tp):
        parts: list[str] = []
        for arg in get_args(tp):
            if arg is _NoneType and drop_null:
                continue
            text = ts_type(arg)
            if text not in parts:
                parts.append(text)
        return "|".join(parts)
    if origin in (list, tuple, set, frozenset):
        args = get_args(tp)
        if origin is tuple and args and args[-1] is not Ellipsis:
            return "[" + ", ".join(ts_type(a) for a in args) + "]"
        inner = ts_type(args[0]) if args else "any"
        return f"{_wrap(inner)}[]"
    if origin is dict or tp is dict:
        return "object"
    if inspect.isclass(tp) and issubclass(tp, BaseModel):
        override = getattr(tp, "__ts__", None)
        if isinstance(override, str):
            return override
        fields = []
        for name, field in prompt_fields(tp):
            opt = "" if field.is_required() else "?"
            fields.append(f"{name}{opt}: {ts_type(field.annotation, field.metadata, drop_null=not field.is_required())}")
        return "{" + ", ".join(fields) + "}"
    return "any"


def render_signature(cls: type[BaseModel]) -> str:
    """Render ``name(prop: type, opt?: type) — description`` for a component class."""
    info = cls.__dyui__  # type: ignore[attr-defined]
    params = []
    for name, field in prompt_fields(cls):
        opt = "" if field.is_required() else "?"
        params.append(f"{name}{opt}: {ts_type(field.annotation, field.metadata, drop_null=not field.is_required())}")
    line = f"{info.name}({', '.join(params)})"
    if info.description:
        line += f" — {info.description}"
    return line
