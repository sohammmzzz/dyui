"""Strict JSON Schemas for components (SPEC §5.0, structured / tool mode).

Strict mode follows the common denominator of OpenAI ``strict: true`` and
Anthropic strict tool use: every object has ``additionalProperties: false``,
every property is listed in ``required`` (optionals become nullable), and no
``default``/``format`` keywords are emitted. Arbitrary JSON (``data``, ``input``)
and child components (which are recursive and open-ended) can't be expressed
strictly, so they are encoded as JSON *strings*; validation decodes them.
"""
from __future__ import annotations

import inspect
import json
from typing import Any, Literal, get_args, get_origin

from pydantic import BaseModel

from .signature import is_union, prompt_fields, split_annotated
from .types import ChildList, FreeJson

__all__ = ["component_schema", "model_schema", "CHILD_HINT"]

_NoneType = type(None)

CHILD_HINT = (
    'One child component as a JSON object string, e.g. "{\\"ui\\":\\"stat\\",\\"label\\":\\"Users\\",'
    '\\"value\\":1200}".'
)


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    t = schema.get("type")
    if t == "null" or (isinstance(t, list) and "null" in t):
        return schema
    if "anyOf" in schema:
        if any(s.get("type") == "null" for s in schema["anyOf"]):
            return schema
        return {**schema, "anyOf": [*schema["anyOf"], {"type": "null"}]}
    if isinstance(t, str) and set(schema) <= {"type", "description"}:
        return {**schema, "type": [t, "null"]}
    if isinstance(t, list) and set(schema) <= {"type", "description"}:
        return {**schema, "type": [*t, "null"]}
    desc = schema.get("description")
    inner = {k: v for k, v in schema.items() if k != "description"}
    out: dict[str, Any] = {"anyOf": [inner, {"type": "null"}]}
    if desc:
        out["description"] = desc
    return out


def _type_schema(tp: Any, meta: list[Any], strict: bool) -> dict[str, Any]:
    tp, extra = split_annotated(tp, meta)
    if any(isinstance(m, ChildList) for m in extra):
        item = {"type": "string", "description": CHILD_HINT} if strict else {"type": "object", "description": "A component object {\"ui\": name, ...props}."}
        return {"type": "array", "items": item}
    if any(isinstance(m, FreeJson) for m in extra):
        if strict:
            return {"type": "string", "description": "JSON-encoded value."}
        return {}
    if tp is str:
        return {"type": "string"}
    if tp is bool:
        return {"type": "boolean"}
    if tp is int:
        return {"type": "integer"}
    if tp is float:
        return {"type": "number"}
    if tp is _NoneType:
        return {"type": "null"}
    if tp is Any or tp is object:
        return {"type": "string", "description": "JSON-encoded value."} if strict else {}
    origin = get_origin(tp)
    if origin is Literal:
        values = list(get_args(tp))
        if all(isinstance(v, str) for v in values):
            return {"type": "string", "enum": values}
        return {"enum": values}
    if is_union(tp):
        members: list[dict[str, Any]] = []
        for arg in get_args(tp):
            s = _type_schema(arg, [], strict)
            if s not in members:
                members.append(s)
        simple = [m.get("type") for m in members if set(m) == {"type"} and isinstance(m.get("type"), str)]
        if len(simple) == len(members):
            types_: list[str] = []
            for t in simple:
                if t == "integer" and "number" in simple:
                    continue
                if t not in types_:
                    types_.append(t)
            return {"type": types_[0] if len(types_) == 1 else types_}
        return {"anyOf": members}
    if origin in (list, tuple, set, frozenset):
        args = [a for a in get_args(tp) if a is not Ellipsis]
        if not args:
            items: dict[str, Any] = {"type": "string"} if strict else {}
        elif len(set(map(repr, args))) == 1:
            items = _type_schema(args[0], [], strict)
        else:
            items = {"anyOf": [_type_schema(a, [], strict) for a in args]}
        return {"type": "array", "items": items}
    if origin is dict or tp is dict:
        return {"type": "string", "description": "JSON-encoded object."} if strict else {"type": "object"}
    if inspect.isclass(tp) and issubclass(tp, BaseModel):
        return model_schema(tp, strict=strict)
    return {"type": "string"} if strict else {}


def _default_note(field: Any) -> str:
    default = field.default
    if default is None or callable(default) or default == [] or repr(default) == "PydanticUndefined":
        return "Optional."
    try:
        return f"Optional; default {json.dumps(default)}."
    except (TypeError, ValueError):
        return "Optional."


def model_schema(model: type[BaseModel], *, strict: bool = True) -> dict[str, Any]:
    """Return the JSON Schema of a pydantic model's LLM-visible fields.

    Args:
        model: A component class or nested prop model.
        strict: Strict-mode output (see module docs).
    """
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, field in prompt_fields(model):
        schema = _type_schema(field.annotation, list(field.metadata), strict)
        if field.is_required():
            required.append(name)
        elif strict:
            note = _default_note(field)
            desc = schema.get("description")
            schema = _nullable({**schema, "description": f"{desc} {note}".strip() if desc else note})
            required.append(name)
        if field.description and "description" not in schema:
            schema = {**schema, "description": field.description}
        properties[name] = schema
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def component_schema(cls: type[BaseModel], *, strict: bool = True) -> dict[str, Any]:
    """Return the props schema for a component class, with its description."""
    schema = model_schema(cls, strict=strict)
    info = getattr(cls, "__dyui__", None)
    if info is not None and info.description:
        schema = {"type": "object", "description": info.description, **{k: v for k, v in schema.items() if k != "type"}}
    return schema
