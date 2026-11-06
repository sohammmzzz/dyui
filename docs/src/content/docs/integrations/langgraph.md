---
title: LangGraph
description: Stream a LangGraph agent into a DyUI reply, and emit components from any node or tool.
sidebar:
  order: 5
---

```bash
pip install "dyui[langgraph]"
```

`dyui.integrations.langgraph` has two functions:

- **`stream(graph, input, config=None, **kwargs)`** runs the graph with `stream_mode=["messages", "custom"]` and yields what DyUI understands: AI message chunks as text (parsed for `dyui` fences), thinking blocks as `Reasoning`, and components you `emit()`.
- **`emit(component)`**, called inside any node or tool, sends a component (or a `{"ui": ...}` dict) straight to the chat.

```python
import dyui
from dyui import ui
from dyui.integrations.langgraph import emit, stream as lg_stream
from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph

app = dyui.App(title="Research Agent")

async def research(state: MessagesState):
    emit(ui.Step("Searching sources", "running", id="search"))
    results = await search(state["messages"][-1].content)
    emit(ui.Step("Searching sources", "done", id="search"))
    emit(ui.Sources(*[ui.Source(r.title, r.url) for r in results]))
    return {"messages": []}

async def answer(state: MessagesState):
    system = SystemMessage("Answer from the sources.\n\n" + app.catalog.prompt())
    return {"messages": [await llm.ainvoke([system, *state["messages"]])]}

builder = StateGraph(MessagesState)
builder.add_node("research", research)
builder.add_node("answer", answer)
builder.add_edge(START, "research")
builder.add_edge("research", "answer")
builder.add_edge("answer", END)
graph = builder.compile()

@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    async for part in lg_stream(graph, {"messages": chat.history},
                                config={"configurable": {"thread_id": chat.thread_id}}):
        yield part
```

- Add `app.catalog.prompt()` to the system prompt of the node that writes the final answer, and the model's components render like any other.
- `chat.history` is a list of `{"role", "content"}` dicts, which LangGraph's `MessagesState` accepts directly. If your graph has a **checkpointer** that already remembers the thread, send only the new message: `{"messages": [{"role": "user", "content": msg.text}]}`.
- `emit()` outside a graph run logs a warning and drops the component. If `langgraph` isn't installed, it logs a warning instead of raising.
- Tool-call chunks without text are skipped. A complete `AIMessage` is only shown if it wasn't already streamed.

See the runnable [`examples/langgraph_agent.py`](https://github.com/sohammmzzz/dyui/blob/main/examples/langgraph_agent.py) and the [`langgraph` template](../../get-started/quickstart/#start-from-a-template).
