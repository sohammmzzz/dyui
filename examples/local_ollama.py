"""A fully local bot. Start Ollama first:  ollama pull llama3.2  (serves on localhost:11434)."""
import os

import dyui

MODEL = os.getenv("DYUI_MODEL", "ollama/llama3.2")

app = dyui.App(title="Local Bot", description="Runs on your machine via Ollama.", persist=True)


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    # Small local models do best with a narrow catalog, which also keeps the prompt short.
    catalog = app.catalog.only("table", "stat", "callout", "quick_replies")
    async for part in dyui.llm.stream(MODEL, chat.history, system="You are a helpful assistant.",
                                      components=catalog):
        yield part
