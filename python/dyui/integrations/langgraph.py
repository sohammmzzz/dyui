"""LangGraph adapter: ``emit()`` components from nodes, ``stream()`` a graph run."""
from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from dyui.parts import Reasoning

log = logging.getLogger("dyui")

__all__ = ["emit", "stream"]

_KEY = "__dyui__"


def emit(item: Any) -> None:
    """Send a component (or ``{"ui": ...}`` dict) to the chat from inside a node/tool."""
    try:
        from langgraph.config import get_stream_writer
    except ImportError:
        log.warning('dyui emit(): langgraph is not installed (pip install "dyui[langgraph]").')
        return
    try:
        writer = get_stream_writer()
    except Exception:
        log.warning("dyui emit() was called outside a LangGraph run; the component was dropped.")
        return
    writer({_KEY: item})



def _parts_of(content: Any) -> list[str | Reasoning]:
    """Text / reasoning parts of an AI message (chunk) ``content``."""
    if isinstance(content, str):
        return [content] if content else []
    out: list[str | Reasoning] = []
    if isinstance(content, list):
        for b in content:
            if isinstance(b, str):
                if b:
                    out.append(b)
            elif isinstance(b, dict):
                t = b.get("type")
                if t in ("text", "text_delta") and b.get("text"):
                    out.append(b["text"])
                elif t in ("thinking", "reasoning") and (b.get("thinking") or b.get("reasoning")):
                    out.append(Reasoning(b.get("thinking") or b.get("reasoning")))
    return out


async def stream(graph: Any, input: Any, config: Any = None, **kwargs: Any) -> AsyncIterator[Any]:
    """Run ``graph`` and yield text deltas, ``Reasoning`` deltas and emitted components."""
    seen: set[str] = set()
    async for item in graph.astream(input, config, stream_mode=["messages", "custom"], **kwargs):
        mode, payload = item
        if mode == "custom":
            if isinstance(payload, dict) and _KEY in payload:
                yield payload[_KEY]
            continue
        if mode != "messages":
            continue
        chunk = payload[0] if isinstance(payload, (tuple, list)) else payload
        ctype = getattr(chunk, "type", None)
        if ctype not in ("AIMessageChunk", "ai"):
            continue
        mid = getattr(chunk, "id", None)
        is_chunk = ctype == "AIMessageChunk" or type(chunk).__name__.endswith("Chunk")
        if not is_chunk:
            # A complete AIMessage: only surface it if we never streamed it.
            if mid is not None and mid in seen:
                continue
        elif mid is not None:
            seen.add(mid)
        if getattr(chunk, "tool_call_chunks", None) and not _parts_of(chunk.content):
            continue
        for part in _parts_of(chunk.content):
            yield part
