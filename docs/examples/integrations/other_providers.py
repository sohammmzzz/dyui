"""One app, any provider: pick it with DYUI_MODEL.

Needs:  pip install "dyui[openai]"   and the key for your provider in a .env file next to this one,
e.g. GROQ_API_KEY for groq/..., OPENROUTER_API_KEY for openrouter/..., GEMINI_API_KEY for gemini/...
Save as app.py, then run:  dyui run app.py
"""
import os

import dyui

MODEL = os.getenv("DYUI_MODEL", "groq/llama-3.3-70b-versatile")

app = dyui.App(title="Any Model", description=f"Answering with {MODEL}.", starters=["Show a bar chart of planet sizes"])

# Free tiers limit tokens per minute: a short catalog keeps every request small.
CATALOG = app.catalog.only("table", "stats", "stat", "chart", "callout", "quick_replies")


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    async for part in dyui.llm.stream(
        MODEL,
        chat.history[-12:],  # cap the history you resend
        system="You are a concise assistant.",
        components=CATALOG,
    ):
        yield part
