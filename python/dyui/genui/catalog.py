"""The component :class:`Catalog`: what the LLM may render, and how it's told."""
from __future__ import annotations

import logging
import re
from typing import Any, Iterable, Iterator, Literal, Optional, Sequence, Union

from ..ui.base import Component, new_id
from ..ui.registry import LLM_BUILTINS, builtins_in
from .validate import ValidationFailure, failure_node, validate_node

__all__ = ["Catalog", "catalog", "TOKEN_WARN_LIMIT"]

log = logging.getLogger("dyui")

TOKEN_WARN_LIMIT = 1800
"""``prompt()`` logs a warning above this many estimated tokens."""

Ref = Union[str, type[Component]]


def _tool_name(name: str) -> str:
    return "render_" + re.sub(r"[^a-zA-Z0-9_-]", "_", name)[:57]


class Catalog:
    """An ordered set of component classes offered to the LLM.

    Built-ins come first in spec order, then custom components in registration
    order, so the generated prompt is deterministic (prompt caching friendly).

    Example:
        >>> import dyui
        >>> cat = dyui.catalog("data", "interactive")
        >>> "stat" in cat.names
        True
    """

    def __init__(self, components: Iterable[type[Component]] = ()) -> None:
        self._items: dict[str, type[Component]] = {}
        for cls in components:
            if not (isinstance(cls, type) and issubclass(cls, Component)):
                raise TypeError(f"not a component class: {cls!r}")
            self._items[cls.__dyui__.name] = cls

    # ----------------------------------------------------------- collection
    @property
    def names(self) -> list[str]:
        """Component names in prompt order."""
        return list(self._items)

    @property
    def components(self) -> list[type[Component]]:
        """Component classes in prompt order."""
        return list(self._items.values())

    def get(self, name: str) -> Optional[type[Component]]:
        """Return the component class for ``name`` (or ``None``)."""
        return self._items.get(name)

    def __contains__(self, item: object) -> bool:
        if isinstance(item, str):
            return item in self._items
        return item in self._items.values()

    def __iter__(self) -> Iterator[type[Component]]:
        return iter(self._items.values())

    def __len__(self) -> int:
        return len(self._items)

    def __repr__(self) -> str:
        return f"Catalog({', '.join(self._items)})"

    def _resolve(self, refs: Sequence[Ref]) -> set[str]:
        names: set[str] = set()
        for ref in refs:
            if isinstance(ref, str):
                if ref not in self._items:
                    raise KeyError(f"component {ref!r} is not in this catalog ({', '.join(self._items)})")
                names.add(ref)
            elif isinstance(ref, type) and issubclass(ref, Component):
                names.add(ref.__dyui__.name)
            else:
                raise TypeError(f"expected a component name or class, got {ref!r}")
        return names

    def only(self, *refs: Ref) -> "Catalog":
        """Return a new catalog containing only the given components (names or classes)."""
        keep = self._resolve(refs)
        return Catalog(c for n, c in self._items.items() if n in keep)

    def without(self, *refs: Ref) -> "Catalog":
        """Return a new catalog without the given components."""
        drop = self._resolve(refs)
        return Catalog(c for n, c in self._items.items() if n not in drop)

    def __add__(self, other: "Catalog") -> "Catalog":
        return Catalog([*self, *(c for c in other if c.__dyui__.name not in self._items)])

    # -------------------------------------------------------------- prompts
    def prompt(self, mode: Literal["fence", "tools"] = "fence") -> str:
        """Return the "UI components" section to add to a system prompt.

        Args:
            mode: ``"fence"`` (default) teaches the fenced ```dyui block format;
                ``"tools"`` tells the model to call ``render_*`` tools instead.
        """
        from .prompt import build_prompt

        text = build_prompt(self, mode)
        tokens = (len(text) + 3) // 4
        if tokens > TOKEN_WARN_LIMIT:
            log.warning(
                "UI prompt is ~%d tokens (> %d); consider catalog.only(...) to trim it", tokens, TOKEN_WARN_LIMIT
            )
        return text

    def token_estimate(self, mode: Literal["fence", "tools"] = "fence") -> int:
        """Rough token count of :meth:`prompt` (characters / 4)."""
        from .prompt import build_prompt

        return (len(build_prompt(self, mode)) + 3) // 4

    # ------------------------------------------------------ structured mode
    def json_schema(self, strict: bool = True) -> dict[str, dict[str, Any]]:
        """Return ``{name: props JSON Schema}`` for every component."""
        return {name: cls.json_schema(strict=strict) for name, cls in self._items.items()}

    def tool_name(self, name: str) -> str:
        """Return the tool name for a component (``render_<name>``)."""
        return _tool_name(name)

    def component_for_tool(self, tool_name: str) -> Optional[str]:
        """Map a ``render_<name>`` tool name back to its component name."""
        for name in self._items:
            if _tool_name(name) == tool_name:
                return name
        return None

    def tool_schemas(self, provider: Literal["openai", "anthropic"] = "openai") -> list[dict[str, Any]]:
        """Return ready-to-send tool definitions, one ``render_<name>`` per component.

        Args:
            provider: ``"openai"`` → ``{"type": "function", "function": {...,
                "strict": true}}``; ``"anthropic"`` → ``{"name", "description",
                "input_schema", "strict": true}``.

        Raises:
            ValueError: For an unknown provider.
        """
        from .prompt import usage_hint

        tools: list[dict[str, Any]] = []
        for name, cls in self._items.items():
            schema = cls.json_schema(strict=True)
            schema.pop("description", None)
            desc = " ".join(p for p in (cls.__dyui__.description, usage_hint(cls)) if p)
            if provider == "openai":
                tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": _tool_name(name),
                            "description": desc,
                            "parameters": schema,
                            "strict": True,
                        },
                    }
                )
            elif provider == "anthropic":
                tools.append({"name": _tool_name(name), "description": desc, "input_schema": schema, "strict": True})
            else:
                raise ValueError(f"unknown provider {provider!r}; expected 'openai' or 'anthropic'")
        return tools

    # ----------------------------------------------------------- validation
    def validate(self, obj: Any, *, id: Optional[str] = None) -> dict[str, Any]:
        """Validate an LLM component object (or tool-call args with ``"ui"``).

        Explicit ``null`` for optional props counts as "not provided".

        Args:
            obj: ``{"ui": name, ...props}``.
            id: Node id (default: fresh ``c_<8hex>``).

        Returns:
            The ``UINode``; an ``invalid`` node (status ``error``) on failure.
        """
        nid = id or new_id()
        try:
            return validate_node(obj, self, nid)
        except ValidationFailure as failure:
            return failure_node(nid, failure)


def catalog(*groups: str) -> Catalog:
    """Return a catalog of built-in components, optionally limited to groups.

    Args:
        *groups: Any of ``content``, ``data``, ``media``, ``interactive``,
            ``layout``, ``agent``. None → every LLM built-in.

    Example:
        ``dyui.catalog("data", "interactive").prompt()``
    """
    if not groups:
        return Catalog(LLM_BUILTINS)
    return Catalog(builtins_in(*groups))
