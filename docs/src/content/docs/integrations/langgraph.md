---
title: LangGraph
description: Stream a LangGraph agent into a DyUI reply, and emit components from any node or tool.
sidebar:
  order: 5
---

```bash
pip install "dyui[langgraph]"      # installs langgraph>=1.0
```

`dyui.integrations.langgraph` has two functions:

- **`stream(graph, input, config=None, **kwargs)`** runs the graph with `stream_mode=["messages", "custom"]` and yields what DyUI understands: AI message chunks as text (parsed for `dyui` fences), thinking blocks as `Reasoning`, and components you `emit()`.
- **`emit(item, writer=None, *, config=None)`**, called inside any node or tool, sends a component (or a `{"ui": ...}` dict) straight to the chat.

```python
import dyui
from dyui import ui
from dyui.integrations.langgraph import emit, stream as lg_stream
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, MessagesState, StateGraph

app = dyui.App(title="Research Agent")

async def research(state: MessagesState, config: RunnableConfig):
    emit(ui.Step("Searching sources", "running", id="search"), config=config)
    results = await search(state["messages"][-1].content)
    emit(ui.Step("Searching sources", "done", id="search"), config=config)
    emit(ui.Sources(*[ui.Source(r.title, r.url) for r in results]), config=config)
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

## `emit()` on every Python version

On **Python 3.11+**, `emit(item)` finds the current LangGraph run by itself. On **Python 3.10**, LangGraph can't propagate its run context into nodes, so pass the run explicitly. These forms work on every version, so prefer them in code that others will run:

```python
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime

async def search(state, config: RunnableConfig):        # a graph node
    emit(ui.Table(["Title", "URL"], rows), config=config)

@tool
def forecast(city: str, runtime: ToolRuntime) -> str:     # a tool
    emit(ui.Chart("line", [ui.Series(city, [18, 20, 17])]), writer=runtime)
    return "18–20°C"
```

`writer=` accepts a LangGraph `StreamWriter`, or a `Runtime` / `ToolRuntime` (its stream writer and config are used). If `emit()` can't find a run, for example outside a graph or on 3.10 without `config`/`writer`, it **logs a warning and drops the component** rather than raising. It does the same when `langgraph` isn't installed.

## Notes

- Add `app.catalog.prompt()` to the system prompt of the node that writes the final answer, and the model's components render like any other.
- `chat.history` is a list of `{"role", "content"}` dicts, which LangGraph's `MessagesState` accepts directly. If your graph has a **checkpointer** that already remembers the thread, send only the new message: `{"messages": [{"role": "user", "content": msg.text}]}`.
- An emitted `{"ui": ...}` dict is validated like model output, so it can't be the developer-only `html`. Emit a `ui.Html(...)` instance instead.
- Tool-call chunks without text are skipped. A complete `AIMessage` is only shown if it wasn't already streamed.

See the runnable [`examples/langgraph_agent.py`](https://github.com/sohammmzzz/dyui/blob/main/examples/langgraph_agent.py) and the [`langgraph` template](../../get-started/quickstart/#start-from-a-template), which passes `runtime` to `emit()`.
