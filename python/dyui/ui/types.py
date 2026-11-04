"""Shared field types for component models: safe URLs, lax enums, children.

These are pydantic ``Annotated`` aliases. They keep component definitions short
and encode the security rules from SPEC §5.1 (URL allow-list) in one place.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Annotated, Any, Callable, Literal, Optional, Union
from urllib.parse import urlsplit

from pydantic import BeforeValidator, ValidationInfo


__all__ = [
    "TS",
    "PyOnly",
    "is_safe_url",
    "Url",
    "OptUrl",
    "Cell",
    "Scalar",
    "Children",
    "lax_enum",
]


@dataclass(frozen=True)
class TS:
    """Annotation marker overriding how a field type is rendered in the prompt."""

    text: str


@dataclass(frozen=True)
class PyOnly:
    """Annotation marker: the field is Python-only and never shown to the LLM."""


def is_safe_url(url: Any) -> bool:
    """Return True if ``url`` is allowed in component props.

    Allowed: ``http(s)://host...``, ``mailto:...`` and app-relative
    ``/api/files/...``. Everything else (``javascript:``, ``data:``,
    protocol-relative ``//host``, relative paths) is rejected.

    Args:
        url: The candidate value.

    Returns:
        Whether the value is a safe URL string.
    """
    if not isinstance(url, str):
        return False
    u = url.strip()
    if not u or any(ord(c) < 32 or ord(c) == 127 for c in u):
        return False
    if u.startswith("/api/files/"):
        return ".." not in u and "\\" not in u
    low = u.lower()
    if low.startswith(("http://", "https://")):
        try:
            return bool(urlsplit(u).netloc)
        except ValueError:
            return False
    if low.startswith("mailto:"):
        return len(u) > len("mailto:")
    return False


def _require_url(value: Any) -> Any:
    if value is None:
        return value
    if not is_safe_url(value):
        raise ValueError("unsafe or unsupported URL (use http(s), mailto, or /api/files/...)")
    return value.strip()


def _optional_url(value: Any) -> Any:
    if value is None or not is_safe_url(value):
        return None
    return value.strip()


Url = Annotated[str, BeforeValidator(_require_url), TS("string")]
"""A required URL; unsafe values fail validation."""

OptUrl = Annotated[Optional[str], BeforeValidator(_optional_url), TS("string")]
"""An optional URL; unsafe values are silently dropped (``None``)."""

Cell = Union[str, int, float, bool, None]
"""A table cell."""

Scalar = Union[str, int, float, bool, None]
"""A JSON scalar."""


def lax_enum(*values: str, aliases: dict[str, str] | None = None) -> Any:
    """Build a case-insensitive ``Literal`` type with optional synonyms.

    Args:
        *values: The allowed (lower-case) values.
        aliases: Extra spellings mapped onto allowed values.

    Returns:
        An ``Annotated[Literal[...], BeforeValidator]`` type.
    """
    table = dict(aliases or {})

    def _norm(value: Any) -> Any:
        if isinstance(value, str):
            v = value.strip().lower()
            return table.get(v, v)
        return value

    return Annotated[Literal[values], BeforeValidator(_norm)]  # type: ignore[valid-type]


def _coerce_children(value: Any, info: ValidationInfo) -> list[Any]:
    from .base import coerce_child

    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        value = [value]
    out: list[Any] = []
    for item in value:
        if isinstance(item, (list, tuple)):
            out.extend(coerce_child(v, info.context) for v in item)
        else:
            out.append(coerce_child(item, info.context))
    return out


Children = Annotated[list[Any], BeforeValidator(_coerce_children), TS("component[]")]
"""A list of child components. Dicts are validated by ``"ui"`` name, strings
become ``markdown`` children, and anything invalid becomes an ``invalid`` node."""


def to_json_text(value: Any) -> str:
    """Compact, safe JSON dump used for ``invalid`` raw payloads."""
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        return str(value)


Fn = Callable[..., Any]
