"""The smallest model-backed DyUI app. Works with every provider prefix.

Needs:  pip install "dyui[openai]"   and NVIDIA_API_KEY in a .env file next to this one
(or another provider's key plus DYUI_MODEL, e.g. DYUI_MODEL=openai/gpt-5).
Save as app.py, then run:  dyui run app.py
"""
import os

import dyui

MODEL = os.getenv("DYUI_MODEL", "nvidia/moonshotai/kimi-k2.6")

app = dyui.App(title="Assistant", starters=["Compare three programming languages in a table"])


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    async for part in dyui.llm.stream(
        MODEL,
        chat.history,
        system="You are a concise, friendly assistant.",
        components=app.catalog,
    ):
        yield part
    if not chat.session.get("titled"):
        # dyui.llm.complete returns the whole reply as one string: handy for titles and summaries
        prompt = [{"role": "user", "content": f"A title of at most five words for: {msg.text}"}]
        await chat.set_title((await dyui.llm.complete(MODEL, prompt)).strip().strip('"')[:60] or "New chat")
        chat.session["titled"] = True
