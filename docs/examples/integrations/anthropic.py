"""A Claude model that answers with DyUI components, with optional extended thinking.

Needs:  pip install "dyui[anthropic]"   and ANTHROPIC_API_KEY in a .env file next to this one.
Save as app.py, then run:  dyui run app.py
Stream Claude's thinking with:  DYUI_THINKING=1 dyui run app.py
"""
import os

import dyui

MODEL = os.getenv("DYUI_MODEL", "anthropic/claude-sonnet-5-5")
THINKING = os.getenv("DYUI_THINKING") == "1"

app = dyui.App(title="Research Assistant", starters=["Summarise the trade-offs of SQLite vs Postgres"])


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    extra = {"max_tokens": 16000, "thinking": {"type": "enabled", "budget_tokens": 8000}} if THINKING else {}
    async for part in dyui.llm.stream(
        MODEL,
        chat.history,
        system="You are a careful research assistant.",
        components=app.catalog,
        **extra,  # anything else goes to client.messages.stream(...)
    ):
        yield part
