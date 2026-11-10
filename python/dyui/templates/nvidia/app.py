"""{{title}} - a DyUI bot. Run it with:  dyui run"""
import os

import dyui

# Any "provider/model" string works: nvidia/..., openai/..., anthropic/..., ollama/...
MODEL = os.getenv("DYUI_MODEL", "nvidia/moonshotai/kimi-k2.6")

app = dyui.App(
    title="{{title}}",
    description="Ask me anything - I answer with tables, charts and cards when they help.",
    starters=["Compare three programming languages in a table", "Show a bar chart of planet sizes"],
)


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    # components=app.catalog adds the UI instructions to the system prompt.
    # Register your own components with @app.component and the prompt updates itself.
    async for part in dyui.llm.stream(
        MODEL,
        chat.history,
        system="You are a concise, friendly assistant. Explain in words as well as components.",
        components=app.catalog,
    ):
        yield part
