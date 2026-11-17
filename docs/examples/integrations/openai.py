"""An OpenAI model that answers with DyUI components.

Needs:  pip install "dyui[openai]"   and OPENAI_API_KEY in a .env file next to this one.
Save as app.py, then run:  dyui run app.py
Try structured mode with:  DYUI_UI_MODE=tools dyui run app.py
"""
import os

import dyui

MODEL = os.getenv("DYUI_MODEL", "openai/gpt-5")
UI_MODE = os.getenv("DYUI_UI_MODE", "fence")  # "tools" = one strict render_<name> tool per component

app = dyui.App(title="Analyst", starters=["Compare three cloud providers in a table"])


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    async for part in dyui.llm.stream(
        MODEL,
        chat.history,
        system="You are a helpful analyst.",
        components=app.catalog,
        ui_mode=UI_MODE,
    ):
        yield part
