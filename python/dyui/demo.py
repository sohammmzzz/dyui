"""A self-contained demo agent that ships *inside* the package.

It needs **no API key and no LLM** -- it is a plain LangGraph ``StateGraph`` whose
nodes emit one of every built-in DyUI card. ``dyui demo`` serves it so anyone can
see a working, animated dynamic UI in a single command::

    pip install "dyui[server]"
    dyui demo

This is both an instant "wow" first-run experience and a living catalogue of the
card types you can emit from your own agent.
"""

from __future__ import annotations

import time
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .emit import Card, emit, ui_tool


class State(TypedDict, total=False):
    query: str


@ui_tool("table", title="Search results", icon="search", accent="cyan")
def _search(query: str) -> dict[str, Any]:
    time.sleep(0.25)  # simulate latency so the loading skeleton is visible
    rows = [
        [f"{query}-doc-{i}", f"{round(0.95 - i * 0.12, 2)}", "indexed"]
        for i in range(1, 5)
    ]
    return {"columns": ["title", "relevance", "status"], "rows": rows}


def _plan(state: State) -> State:
    q = state.get("query", "your topic")
    emit(
        "markdown",
        {"text": f"### Researching **{q}**\n"
                 "1. Search the corpus\n2. Score the sources\n3. Summarise"},
        title="Plan", icon="list", accent="violet",
    )
    return {}


def _do_search(state: State) -> State:
    _search(state.get("query", "demo"))
    return {}


def _work(state: State) -> State:
    with Card("progress", title="Summarising", icon="sparkles", accent="emerald") as card:
        for i in range(1, 4):
            time.sleep(0.18)
            card.progress({"value": i, "max": 3, "label": f"chunk {i}/3"})
        card.done({"value": 3, "max": 3, "label": "Summary ready"})
    return {}


def _showcase(state: State) -> State:
    q = state.get("query", "your topic")
    emit("stat", {"label": "Sources analysed", "value": 4, "unit": "docs", "delta": "+4"},
         title="Result", icon="check", accent="emerald")
    emit("list", {"items": [
        {"title": "Relevance scoring", "badge": "done"},
        {"title": "Dedup + ranking", "badge": "done"},
        {"title": "Citations", "badge": "3"},
    ]}, title="Pipeline", icon="list", accent="cyan")
    emit("keyvalue", {"data": {"topic": q, "sources": 4, "confidence": "high"}},
         title="Metadata", accent="violet")
    emit("alert", {"level": "success", "title": "All set",
                   "text": "This entire screen was streamed from one Python file."},
         title="Notice", accent="emerald")
    emit("html",
         {"html": f"<div style='font:600 14px system-ui;color:#34d399'>"
                  f"Finished researching &ldquo;{q}&rdquo; across 4 sources.</div>"},
         title="Custom HTML card", accent="emerald")
    return {}


def build_graph():
    g = StateGraph(State)
    g.add_node("plan", _plan)
    g.add_node("search", _do_search)
    g.add_node("work", _work)
    g.add_node("showcase", _showcase)
    g.add_edge(START, "plan")
    g.add_edge("plan", "search")
    g.add_edge("search", "work")
    g.add_edge("work", "showcase")
    g.add_edge("showcase", END)
    return g.compile()


graph = build_graph()


def build_app() -> Any:
    from .server import create_dyui_app

    return create_dyui_app(
        graph,
        serve_ui=True,
        ui_title="DyUI Demo",
        ui_auto_input="generative UI",  # run once on load for instant cards
    )
