"""The schema-aware input adapter that makes DyUI plug-and-play for any graph."""

import operator
from typing import Annotated, TypedDict

import pytest
from langgraph.graph import END, START, StateGraph

from dyui import collect_events, emit
from dyui.server import _graph_input_keys, make_smart_input_adapter


def _graph(state_cls, node):
    g = StateGraph(state_cls)
    g.add_node("n", node)
    g.add_edge(START, "n")
    g.add_edge("n", END)
    return g.compile()


class QueryState(TypedDict, total=False):
    query: str
    results: list


class CityState(TypedDict, total=False):
    city: str


class MsgState(TypedDict, total=False):
    messages: Annotated[list, operator.add]


def test_input_keys_discovers_state_fields():
    g = _graph(QueryState, lambda s: {})
    assert _graph_input_keys(g) == {"query", "results"}


def test_string_maps_to_well_known_field():
    g = _graph(QueryState, lambda s: {})
    assert make_smart_input_adapter(g)({"input": "berlin"}) == {"query": "berlin"}


def test_string_maps_to_sole_field():
    # `city` isn't a well-known text field, but it's the only one -> use it.
    g = _graph(CityState, lambda s: {})
    assert make_smart_input_adapter(g)({"input": "Berlin"}) == {"city": "Berlin"}


def test_string_maps_to_messages_shape():
    g = _graph(MsgState, lambda s: {})
    assert make_smart_input_adapter(g)({"input": "hi"}) == {
        "messages": [("user", "hi")]
    }


def test_structured_input_passes_through():
    g = _graph(QueryState, lambda s: {})
    adapter = make_smart_input_adapter(g)
    assert adapter({"input": {"query": "x"}}) == {"query": "x"}
    assert adapter({"input": ["a", "b"]}) == ["a", "b"]
    assert adapter({"input": None}) is None


def test_unknown_graph_falls_back_to_messages():
    # No discoverable keys -> the ubiquitous chat shape.
    adapter = make_smart_input_adapter(object())
    assert adapter({"input": "hello"}) == {"messages": [("user", "hello")]}


def test_smart_adapter_end_to_end_runs_graph():
    def node(state):
        emit("text", {"text": state.get("query", "")})
        return {}

    g = _graph(QueryState, node)
    adapter = make_smart_input_adapter(g)
    events = collect_events(g, adapter({"input": "plug-and-play"}))
    assert events[0]["props"]["text"] == "plug-and-play"
