"""Generative UI: catalog, prompt, streaming fence parser, validation, history.

- :class:`Catalog` / :func:`catalog` — which components the LLM may use, the
  prompt that teaches them (``prompt(mode="fence"|"tools")``), strict JSON
  Schemas and ``render_<name>`` tool definitions.
- :class:`FenceParser` — incremental parser for ```dyui blocks in streamed text.
- :func:`serialize_history` — stored messages → LLM history.
- :func:`repair_message` — compact validation-error hint for the model.
"""
from __future__ import annotations

from .catalog import TOKEN_WARN_LIMIT, Catalog, catalog
from .history import action_text, node_source, serialize_history
from .parser import (
    ComponentEnd,
    ComponentError,
    ComponentStart,
    ComponentUpdate,
    FenceParser,
    ParserEvent,
    TextDelta,
    parse_text,
)
from .partial_json import PartialStr, parse_partial
from .validate import ValidationFailure, partial_node, repair_message, validate_node

__all__ = [
    "Catalog",
    "catalog",
    "TOKEN_WARN_LIMIT",
    "FenceParser",
    "ParserEvent",
    "TextDelta",
    "ComponentStart",
    "ComponentUpdate",
    "ComponentEnd",
    "ComponentError",
    "parse_text",
    "parse_partial",
    "PartialStr",
    "validate_node",
    "partial_node",
    "repair_message",
    "ValidationFailure",
    "serialize_history",
    "action_text",
    "node_source",
]
