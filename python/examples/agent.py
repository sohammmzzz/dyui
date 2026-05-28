"""A self-contained LangGraph agent that drives the DyUI frontend.

This needs **no API key and no LLM** -- it is a plain LangGraph ``StateGraph``
whose nodes emit DyUI cards. It exists to prove the whole pipeline end to end
and to serve as a copy-paste starting point. Swap the node bodies for real LLM
calls / tools and the UI keeps working unchanged.

Run the server::

    uvicorn examples.agent:app --reload --port 8008

Then POST to ``/dyui/stream`` with ``{"input": {"query": "berlin"}}`` (the
frontend template does exactly this).
"""

from __future__ import annotations

import time
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from dyui import Card, emit, ui_tool


class State(TypedDict, total=False):
    query: str
    results: list[dict[str, Any]]


# --- A tool that auto-manages its own card via the decorator -----------------
@ui_tool("table", title="Search results", icon="search", accent="cyan")
def search(query: str) -> dict[str, Any]:
    """Pretend to search; the decorator shows a skeleton then this table."""
    time.sleep(0.2)  # simulate latency so the skeleton is visible
    rows = [
        [f"{query}-doc-{i}", f"score {round(0.9 - i * 0.13, 2)}", "indexed"]
        for i in range(1, 5)
    ]
    return {"columns": ["title", "relevance", "status"], "rows": rows}


# --- Graph nodes -------------------------------------------------------------
def plan_node(state: State) -> State:
    """Open with a short markdown plan card."""
    emit(
        "markdown",
        {"text": f"### Researching **{state.get('query', '?')}**\n"
                 "1. Search the corpus\n2. Score sources\n3. Summarise"},
        title="Plan",
        icon="list",
        accent="violet",
    )
    return {}


def search_node(state: State) -> State:
    results = search(state.get("query", ""))  # emits pending -> table
    return {"results": results["rows"]}


def progress_node(state: State) -> State:
    """Show a long-running task updating one card in place (active -> done)."""
    with Card("progress", title="Summarising", icon="sparkles", accent="emerald") as card:
        total = 3
        for i in range(1, total + 1):
            time.sleep(0.15)
            card.progress({"value": i, "max": total, "label": f"chunk {i}/{total}"})
        card.done({"value": total, "max": total, "label": "Summary ready"})
    return {}


def summary_node(state: State) -> State:
    n = len(state.get("results", []))
    emit(
        "stat",
        {"label": "Sources analysed", "value": n, "unit": "docs", "delta": "+all"},
        title="Done",
        icon="check",
        accent="emerald",
        ttl_ms=10000,
    )
    # A custom raw-HTML card -- no React component required on the frontend.
    emit(
        "html",
        {"html": f"<div style='font:600 13px system-ui;color:#34d399'>"
                 f"Finished researching “{state.get('query','')}” "
                 f"across {n} sources.</div>"},
        title="Custom HTML card",
        accent="emerald",
    )
    return {}


def build_graph():
    g = StateGraph(State)
    g.add_node("plan", plan_node)
    g.add_node("search", search_node)
    g.add_node("progress", progress_node)
    g.add_node("summary", summary_node)
    g.add_edge(START, "plan")
    g.add_edge("plan", "search")
    g.add_edge("search", "progress")
    g.add_edge("progress", "summary")
    g.add_edge("summary", END)
    return g.compile()


graph = build_graph()


# Importing FastAPI lazily keeps ``import examples.agent`` cheap for tests that
# only want the graph.
def _make_app():
    from dyui.server import create_dyui_app

    return create_dyui_app(graph)


try:  # expose ``app`` for ``uvicorn examples.agent:app`` when FastAPI is present
    app = _make_app()
except Exception:  # pragma: no cover
    app = None


if __name__ == "__main__":
    # No server needed -- just print the cards the graph produces.
    from dyui import collect_events

    for ev in collect_events(graph, {"query": "berlin"}):
        print(f"[{ev['status']:>7}] {ev['component']:<10} {ev.get('title','')}  {ev['props']}")
