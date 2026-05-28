"""Emit/decorator behaviour, both outside a run and inside a real graph."""

import pytest

from dyui import Card, UIEvent, collect_events, emit, ui_tool, update
from langgraph.graph import END, START, StateGraph


def test_emit_outside_run_is_graceful():
    # No active LangGraph run -> nothing is written, but we still get the event.
    ev = emit("stat", {"value": 1})
    assert isinstance(ev, UIEvent)
    assert ev.component == "stat"


def test_update_from_event_reuses_id():
    ev = emit("table", {}, status="pending")
    updated = update(ev, {"rows": [[1]]}, status="done")
    assert updated.id == ev.id
    assert updated.status == "done"
    assert updated.props == {"rows": [[1]]}


def test_update_from_id_requires_component():
    with pytest.raises(ValueError):
        update("someid", {"x": 1})


# --- Inside a real one-node graph -------------------------------------------
def _run_single_node(node):
    g = StateGraph(dict)
    g.add_node("n", node)
    g.add_edge(START, "n")
    g.add_edge("n", END)
    return collect_events(g.compile(), {})


def test_emit_inside_graph_streams_event():
    def node(state):
        emit("text", {"text": "hi"}, title="Greeting")
        return {}

    events = _run_single_node(node)
    assert len(events) == 1
    assert events[0]["component"] == "text"
    assert events[0]["props"] == {"text": "hi"}
    assert events[0]["title"] == "Greeting"


def test_ui_tool_emits_pending_then_done():
    @ui_tool("table", title="Search")
    def search(q):
        return {"columns": ["a"], "rows": [[1]]}

    def node(state):
        search("x")
        return {}

    events = _run_single_node(node)
    assert [e["status"] for e in events] == ["pending", "done"]
    # Both events share an id so the frontend updates one card in place.
    assert events[0]["id"] == events[1]["id"]
    assert events[1]["props"]["rows"] == [[1]]


def test_ui_tool_emits_error_and_reraises():
    @ui_tool("text")
    def boom():
        raise RuntimeError("kaboom")

    def node(state):
        try:
            boom()
        except RuntimeError:
            pass
        return {}

    events = _run_single_node(node)
    assert [e["status"] for e in events] == ["pending", "error"]
    assert "kaboom" in events[1]["error"]


def test_card_context_manager_done():
    def node(state):
        with Card("progress", title="P") as card:
            card.progress({"value": 1, "max": 2})
            card.done({"value": 2, "max": 2})
        return {}

    events = _run_single_node(node)
    assert [e["status"] for e in events] == ["pending", "active", "done"]
    assert len({e["id"] for e in events}) == 1  # all the same card


def test_card_context_manager_auto_error():
    def node(state):
        try:
            with Card("text"):
                raise ValueError("nope")
        except ValueError:
            pass
        return {}

    events = _run_single_node(node)
    assert events[-1]["status"] == "error"
    assert "nope" in events[-1]["error"]
