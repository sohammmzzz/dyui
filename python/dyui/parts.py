"""Small value types shared across dyui modules (handler yield values)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Reasoning:
    """A delta of model "thinking" text. Yield it from a handler (or receive it
    from ``dyui.llm.stream``) to render a collapsible reasoning block."""

    text: str
