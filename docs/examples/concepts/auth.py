"""An internal app behind a shared password.

Put APP_PASSWORD=... in a .env file next to this one (dyui run loads it).
Save as app.py, then run:  dyui run app.py
"""
import os

import dyui
from dyui import ui

app = dyui.App(title="Internal Analyst", password=os.environ["APP_PASSWORD"])


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    yield "You're signed in. Each browser still sees only its own conversations."
    yield ui.KeyValue({"Browser id": chat.user_id[:8] + "…"})
