"""Weather Desk, answered by a model that renders DyUI components.

Needs:  pip install "dyui[openai]"   and NVIDIA_API_KEY in a .env file next to this one.
Save as app.py, then run:  dyui run app.py
"""
import os

import dyui

# Any "provider/model" string works; change it here or with the DYUI_MODEL variable.
MODEL = os.getenv("DYUI_MODEL", "nvidia/moonshotai/kimi-k2.6")

app = dyui.App(
    title="Weather Desk",
    description="Ask about the weather in any city.",
    starters=["Weather in Lisbon", dyui.Starter("Compare two cities", "Compare Lisbon and Porto", icon="map")],
)


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    async for part in dyui.llm.stream(
        MODEL,
        chat.history,
        system="You are a concise weather assistant.",
        components=app.catalog,  # teaches the model DyUI's components
    ):
        yield part
