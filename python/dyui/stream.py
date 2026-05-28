"""Bridge a LangGraph run into a flat stream of frames the UI understands.

A "frame" is a small ``(type, data)`` tuple:

* ``("ui",    {...UIEvent...})`` -- a dynamic card instruction
* ``("token", {"text": str, "node": str})`` -- an LLM token (optional)
* ``("done",  {})`` -- the run finished

This module is transport-agnostic: it knows nothing about HTTP. The FastAPI
adapter in ``server.py`` is a thin wrapper that serialises these frames as SSE.
Tests can consume the frames directly via :func:`collect`.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Iterable, Optional

from .events import DYUI_KEY, is_dyui_payload

Frame = tuple[str, dict[str, Any]]


def _extract_token(chunk: Any) -> Optional[dict[str, Any]]:
    """Pull display text out of a ``messages``-mode chunk, if any.

    LangGraph yields ``(message_chunk, metadata)`` for ``stream_mode="messages"``.
    The content may be a plain string or a list of content blocks.
    """
    if not isinstance(chunk, tuple) or len(chunk) != 2:
        return None
    msg, meta = chunk
    content = getattr(msg, "content", None)
    text = ""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text += part.get("text", "")
            elif isinstance(part, str):
                text += part
    if not text:
        return None
    node = (meta or {}).get("langgraph_node") if isinstance(meta, dict) else None
    return {"text": text, "node": node}


async def astream_ui(
    graph: Any,
    input: Any,
    *,
    config: Optional[dict[str, Any]] = None,
    stream_tokens: bool = True,
    stream_modes: Optional[Iterable[str]] = None,
) -> AsyncIterator[Frame]:
    """Run ``graph`` and yield normalised UI/token frames.

    Args:
        graph: A compiled LangGraph graph (anything with ``.astream``).
        input: The graph input (state dict, messages, etc.).
        config: Optional LangGraph run config (thread id, etc.).
        stream_tokens: When True, also surface LLM tokens as ``token`` frames.
        stream_modes: Override the LangGraph stream modes. Defaults to
            ``["custom", "messages"]`` (or just ``["custom"]`` when tokens off).
    """
    if stream_modes is None:
        modes = ["custom", "messages"] if stream_tokens else ["custom"]
    else:
        modes = list(stream_modes)

    async for mode, chunk in graph.astream(
        input, config=config or {}, stream_mode=modes
    ):
        if mode == "custom" and is_dyui_payload(chunk):
            yield ("ui", chunk[DYUI_KEY])
        elif mode == "messages" and stream_tokens:
            token = _extract_token(chunk)
            if token:
                yield ("token", token)
    yield ("done", {})


def collect(
    graph: Any,
    input: Any,
    *,
    config: Optional[dict[str, Any]] = None,
    stream_tokens: bool = False,
) -> list[Frame]:
    """Synchronously run a graph and collect all frames. Handy in tests."""

    async def _run() -> list[Frame]:
        return [
            frame
            async for frame in astream_ui(
                graph, input, config=config, stream_tokens=stream_tokens
            )
        ]

    return asyncio.run(_run())


def collect_events(graph: Any, input: Any, *, config: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    """Collect just the UI event payloads from a run (drops tokens/done)."""
    return [data for kind, data in collect(graph, input, config=config) if kind == "ui"]
