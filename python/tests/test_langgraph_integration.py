from __future__ import annotations

import logging
from typing import Annotated, TypedDict

import pytest

pytest.importorskip("langgraph")
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from dyui.integrations.langgraph import emit, stream
from dyui.parts import Reasoning


class State(TypedDict):
    messages: Annotated[list, add_messages]


def build(reply="Hello from the model", component=None):
    model = GenericFakeChatModel(messages=iter([AIMessage(content=reply)]))

    def prep(state):
        if component is not None:
            emit(component)
        return {}

    async def call(state):
        return {"messages": [await model.ainvoke(state["messages"])]}

    g = StateGraph(State)
    g.add_node("prep", prep)
    g.add_node("llm", call)
    g.add_edge(START, "prep")
    g.add_edge("prep", "llm")
    g.add_edge("llm", END)
    return g.compile()


async def collect(agen):
    return [p async for p in agen]


@pytest.mark.asyncio
async def test_stream_text_and_dict_component():
    comp = {"ui": "stat", "label": "A", "value": 1}
    out = await collect(stream(build(component=comp), {"messages": [HumanMessage("hi")]}))
    assert comp in out
    text = "".join(p for p in out if isinstance(p, str))
    assert text == "Hello from the model"  # nothing from the HumanMessage, no duplicates


@pytest.mark.asyncio
async def test_component_object_passthrough():
    class Thing:  # stand-in for a ui component instance
        pass

    t = Thing()
    out = await collect(stream(build(component=t), {"messages": [HumanMessage("hi")]}))
    assert any(p is t for p in out)


@pytest.mark.asyncio
async def test_order_component_before_text():
    comp = {"ui": "divider"}
    out = await collect(stream(build(component=comp), {"messages": []}))
    assert out.index(comp) == 0


def test_emit_outside_run_warns(caplog):
    with caplog.at_level(logging.WARNING, logger="dyui"):
        emit({"ui": "divider"})
    assert any("outside a LangGraph run" in r.message for r in caplog.records)


def test_parts_of_blocks():
    from dyui.integrations.langgraph import _parts_of

    assert _parts_of([{"type": "thinking", "thinking": "t"}, {"type": "text", "text": "x"},
                      {"type": "tool_use", "id": "1"}]) == [Reasoning("t"), "x"]
