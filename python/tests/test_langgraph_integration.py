from __future__ import annotations

import logging
import sys
from typing import Annotated, TypedDict

import pytest

pytest.importorskip("langgraph")
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import StreamWriter
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode, ToolRuntime
from langgraph.runtime import Runtime
from langchain_core.tools import tool

from dyui.integrations.langgraph import emit, stream
from dyui.parts import Reasoning


class State(TypedDict):
    messages: Annotated[list, add_messages]


IMPLICIT_OK = sys.version_info >= (3, 11)
needs_implicit = pytest.mark.skipif(
    not IMPLICIT_OK, reason="get_stream_writer() needs contextvar propagation (Python 3.11+); use writer=")


def build(reply="Hello from the model", component=None, explicit=True):
    model = GenericFakeChatModel(messages=iter([AIMessage(content=reply)]))

    if explicit:
        def prep(state, config: RunnableConfig):  # portable form (works on Python 3.10)
            if component is not None:
                emit(component, config=config)
            return {}
    else:
        def prep(state):  # implicit form (Python 3.11+)
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


@needs_implicit
@pytest.mark.asyncio
async def test_implicit_writer_form():
    comp = {"ui": "stat", "label": "A", "value": 1}
    out = await collect(stream(build(component=comp, explicit=False), {"messages": [HumanMessage("hi")]}))
    assert comp in out


@pytest.mark.asyncio
async def test_async_node_with_runtime():

    comp = {"ui": "divider"}

    async def node(state, runtime: Runtime, config: RunnableConfig):
        emit(comp, writer=runtime, config=config)  # a Runtime is unwrapped to its stream_writer
        return {}

    g = StateGraph(State)
    g.add_node("n", node)
    g.add_edge(START, "n")
    g.add_edge("n", END)
    out = await collect(stream(g.compile(), {"messages": []}))
    assert out == [comp]


@pytest.mark.asyncio
async def test_async_node_with_writer_and_config():
    comp = {"ui": "divider"}

    async def node(state, writer: StreamWriter, config: RunnableConfig):
        emit(comp, writer=writer, config=config)
        return {}

    g = StateGraph(State)
    g.add_node("n", node)
    g.add_edge(START, "n")
    g.add_edge("n", END)
    out = await collect(stream(g.compile(), {"messages": []}))
    assert out == [comp]


@pytest.mark.asyncio
async def test_tool_with_tool_runtime():

    comp = {"ui": "stat", "label": "Temp", "value": 21}

    @tool
    def weather(city: str, runtime: ToolRuntime) -> str:
        """Weather for a city."""
        emit(comp, writer=runtime)
        return "sunny"

    g = StateGraph(State)
    g.add_node("tools", ToolNode([weather]))
    g.add_edge(START, "tools")
    g.add_edge("tools", END)
    call = AIMessage(content="", tool_calls=[{"name": "weather", "args": {"city": "Rome"}, "id": "t1"}])
    out = await collect(stream(g.compile(), {"messages": [call]}))
    assert comp in out


def test_emit_explicit_writer_direct():
    got = []
    emit({"ui": "divider"}, writer=got.append)
    assert got == [{"__dyui__": {"ui": "divider"}}]


def test_emit_bad_writer_warns(caplog):
    with caplog.at_level(logging.WARNING, logger="dyui"):
        emit({"ui": "divider"}, writer=object())
    assert any("config=config" in r.getMessage() for r in caplog.records)


def test_emit_writer_runtime_error_is_caught(caplog):
    def broken(_):
        raise RuntimeError("Called get_config outside of a runnable context")

    with caplog.at_level(logging.WARNING, logger="dyui"):
        emit({"ui": "divider"}, writer=broken)  # must not crash the node
    assert any("couldn't find the current run" in r.getMessage() for r in caplog.records)


def test_emit_outside_run_warns(caplog):
    with caplog.at_level(logging.WARNING, logger="dyui"):
        emit({"ui": "divider"})
    assert any("outside a LangGraph run" in r.message for r in caplog.records)


def test_parts_of_blocks():
    from dyui.integrations.langgraph import _parts_of

    assert _parts_of([{"type": "thinking", "thinking": "t"}, {"type": "text", "text": "x"},
                      {"type": "tool_use", "id": "1"}]) == [Reasoning("t"), "x"]
