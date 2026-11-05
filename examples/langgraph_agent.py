"""A LangGraph agent whose tool emits DyUI components while the model streams text."""
import os

import dyui
from dyui import ui
from dyui.integrations.langgraph import emit, stream as lg_stream
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import ToolRuntime, create_react_agent

MODEL = os.getenv("DYUI_LANGCHAIN_MODEL", "openai:gpt-5")

app = dyui.App(title="Weather Agent", starters=["Compare the weather in Paris and Rome"])


@tool
def forecast(city: str, runtime: ToolRuntime) -> str:
    """Get a 3-day temperature forecast for a city."""
    temps = {"paris": [18, 20, 17], "rome": [24, 26, 25]}.get(city.lower(), [20, 20, 20])
    emit(ui.Chart(kind="line", title=f"{city}: next 3 days", unit="C",
                  labels=["Mon", "Tue", "Wed"], series=[{"name": city, "data": temps}]),
         writer=runtime)  # the injected ToolRuntime (portable to Python 3.10)
    return f"{city}: {temps} C"


graph = create_react_agent(MODEL, tools=[forecast], checkpointer=InMemorySaver(),
                           prompt="You are a weather assistant. Be brief.")


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    config = {"configurable": {"thread_id": chat.thread_id}}
    async for part in lg_stream(graph, {"messages": [{"role": "user", "content": msg.text}]}, config=config):
        yield part
