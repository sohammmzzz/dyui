"""JSON safety helpers: strict JSON (RFC 8259) has no ``NaN`` / ``Infinity``.

Python's ``json`` happily reads and writes them, but browsers' ``JSON.parse`` and
Starlette's ``JSONResponse`` do not — one ``NaN`` in a stored message would make
the whole conversation unloadable. Everything DyUI streams or stores goes through
:func:`finite` first.
"""
from __future__ import annotations

import math
from typing import Any

__all__ = ["finite", "has_nonfinite", "too_deep", "MAX_DEPTH"]

#: Deepest JSON nesting (objects + arrays) accepted from a model. A card inside a
#: grid inside tabs is ~10 levels; 48 leaves ample room while keeping every
#: recursive walker (validation, history, the client's renderer) far from
#: Python's recursion limit.
MAX_DEPTH = 48


def too_deep(value: Any, limit: int = MAX_DEPTH) -> bool:
    """True if ``value`` nests dicts/lists more than ``limit`` levels (iterative, never recurses)."""
    stack: list[tuple[Any, int]] = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        if isinstance(item, dict):
            children = item.values()
        elif isinstance(item, (list, tuple)):
            children = item
        else:
            continue
        if depth > limit:
            return True
        stack.extend((child, depth + 1) for child in children if isinstance(child, (dict, list, tuple)))
    return False


def has_nonfinite(value: Any) -> bool:
    """True if ``value`` contains a ``NaN`` / ``±Infinity`` float anywhere."""
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, dict):
        return any(has_nonfinite(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(has_nonfinite(v) for v in value)
    return False


def finite(value: Any) -> Any:
    """Return ``value`` with every non-finite float replaced by ``None``.

    Returns the same object when nothing needs replacing (cheap common case).
    """
    if not has_nonfinite(value):
        return value
    if isinstance(value, float):
        return None
    if isinstance(value, dict):
        return {k: finite(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [finite(v) for v in value]
    if isinstance(value, list):
        return [finite(v) for v in value]
    return value  # pragma: no cover
