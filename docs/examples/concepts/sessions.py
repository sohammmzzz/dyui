"""Per-conversation state with chat.session, stored in SQLite.

Save as app.py, then run:  dyui run app.py
Conversations are kept in ./chats.db; restart the app and they are still there.
"""
import dyui
from dyui import ui

app = dyui.App(title="Counter", persist="chats.db", starters=["Count this"])


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    count = chat.session.get("turns", 0) + 1
    chat.session["turns"] = count  # saved when the handler finishes; values must be JSON
    chat.session.setdefault("words", []).append(msg.text)
    yield f"This is message {count} in this conversation."
    yield ui.KeyValue({"Thread": chat.thread_id, "Browser": chat.user_id[:8] + "…", "Turns": count})
