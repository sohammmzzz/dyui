"""LangGraph adapter: ``emit()`` components from nodes, ``stream()`` a graph run."""
from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from dyui.parts import Reasoning

log = logging.getLogger("dyui")

__all__ = ["emit", "stream"]

_KEY = "__dyui__"


_HINT = ("On Python 3.10 pass the run explicitly: emit(item, config=config) in a node that takes "
         "`config: RunnableConfig`, or emit(item, writer=runtime) in a tool that takes "
         "`runtime: ToolRuntime`.")


def emit(item: Any, writer: Any = None, *, config: Any = None) -> None:
    """Send a component (or ``{"ui": ...}`` dict) to the chat from inside a node or tool.

    On Python 3.11+ ``emit(item)`` finds the current LangGraph run by itself. On
    **Python 3.10** LangGraph can't propagate its run context into nodes, so pass the run
    explicitly; these forms work on every version::

        from langchain_core.runnables import RunnableConfig
        from langgraph.prebuilt import ToolRuntime

        async def search(state, config: RunnableConfig):          # a graph node
            emit(ui.Table(...), config=config)

        @tool
        def forecast(city: str, runtime: ToolRuntime) -> str:     # a tool
            emit(ui.Chart(...), writer=runtime)

    Args:
        item: A ``ui.*`` component instance or a ``{"ui": ...}`` dict.
        writer: A LangGraph ``StreamWriter``, or a ``Runtime`` / ``ToolRuntime`` (its
            ``stream_writer`` and ``config`` are used).
        config: The node's ``RunnableConfig``; makes the writer usable on Python 3.10.
    """
    if writer is not None and not callable(writer):  # Runtime / ToolRuntime
        runtime = writer
        writer = getattr(runtime, "stream_writer", None)
        if config is None:
            config = getattr(runtime, "config", None)
    try:
        from langgraph.config import get_stream_writer
    except ImportError:
        log.warning('dyui emit(): langgraph is not installed (pip install "dyui[langgraph]").')
        return

    token = None
    var = None
    if config is not None:
        from langchain_core.runnables.config import var_child_runnable_config as var

        token = var.set(config)
    try:
        if writer is None:
            try:
                writer = get_stream_writer()
            except Exception:
                writer = None
        if writer is None or not callable(writer):
            log.warning("dyui emit() was called outside a LangGraph run; the component was dropped. %s", _HINT)
            return
        try:
            writer({_KEY: item})
        except RuntimeError as exc:  # LangGraph's writer needs the run context (Python 3.10)
            log.warning("dyui emit(): LangGraph couldn't find the current run (%s); the component "
                        "was dropped. %s", exc, _HINT)
    finally:
        if token is not None and var is not None:
            var.reset(token)


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
