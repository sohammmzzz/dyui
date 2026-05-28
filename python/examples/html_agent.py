"""Zero-frontend example: a LangGraph agent + a folder of HTML card templates.

This is the answer to "I have one Python agent and some HTML card templates --
can DyUI give me a dynamic UI with no frontend code?". Yes:

    uvicorn examples.html_agent:app --port 8010   # then open http://localhost:8010

The server hosts the built-in UI at ``/`` and streams cards rendered from the
``examples/cards/*.html`` templates. No npm, no React, no frontend files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from dyui import HtmlTemplates, emit

# Point the loader at your folder of HTML card templates.
cards = HtmlTemplates(Path(__file__).parent / "cards")


class State(TypedDict, total=False):
    city: str


def respond(state: State) -> State:
    city = state.get("city", "Berlin")

    emit("markdown", {"text": f"### Report for **{city}**"}, title="Summary", accent="violet")

    # Each call fills an HTML template and emits it as a card -- no frontend code.
    # Template placeholder values go in the dict; card config (title/accent/...)
    # are keyword args.
    cards.emit(
        "weather",
        {"emoji": "&#9925;", "city": city, "temp": 21, "summary": "Light rain, breezy"},
        title="Weather",
        accent="cyan",
    )
    cards.emit(
        "invoice",
        {
            "number": 1042,
            "date": "2026-05-29",
            "customer": f"{city} Books Ltd",
            "total": "$1,284.00",
            "items": 7,
            "status": "Paid",  # template placeholder, not card status
        },
        title="Latest invoice",
        accent="emerald",
    )
    return {}


def build_graph():
    g = StateGraph(State)
    g.add_node("respond", respond)
    g.add_edge(START, "respond")
    g.add_edge("respond", END)
    return g.compile()


graph = build_graph()


def _input_adapter(body: dict[str, Any]) -> dict[str, Any]:
    text = body.get("input")
    return text if isinstance(text, dict) else {"city": str(text or "Berlin")}


def make_app() -> Any:
    from dyui.server import create_dyui_app

    return create_dyui_app(
        graph,
        input_adapter=_input_adapter,
        stream_tokens=False,
        serve_ui=True,               # <-- hosts the UI at GET /
        ui_title="DyUI · HTML templates",
        ui_auto_input="Berlin",      # run once on page load for instant cards
    )


try:
    app = make_app()
except Exception:  # pragma: no cover
    app = None


if __name__ == "__main__":
    from dyui import collect_events

    for ev in collect_events(graph, {"city": "Berlin"}):
        print(ev["component"], "->", str(ev["props"])[:80])
