"""{{title}} - a DyUI bot driven by a LangGraph agent. Run it with:  dyui run"""
import os

import dyui
from dyui import ui
from dyui.integrations.langgraph import emit, stream as lg_stream
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent

MODEL = os.getenv("DYUI_LANGCHAIN_MODEL", "openai:gpt-5")  # needs langchain-openai (see requirements)

app = dyui.App(title="{{title}}", description="A LangGraph agent that shows its work.")


@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    # emit() sends a DyUI component straight to the chat from inside any node or tool.
    emit(ui.Stat(f"Weather in {city}", "21", unit="C"))
    return f"It is 21C and sunny in {city}."


graph = create_react_agent(
    MODEL,
    tools=[get_weather],
    prompt="You are a helpful assistant.\n\n" + app.catalog.prompt(),
    checkpointer=InMemorySaver(),
)


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    config = {"configurable": {"thread_id": chat.thread_id}}
    # The checkpointer remembers earlier turns, so we only send the new message.
    async for part in lg_stream(graph, {"messages": [{"role": "user", "content": msg.text}]}, config=config):
        yield part
