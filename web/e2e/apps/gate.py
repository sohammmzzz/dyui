"""E2E fixture app: a password-gated bot."""
import dyui

app = dyui.App(title="Gated", password="letmein", persist=False)


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    yield f"Inside the gate: {msg.text}"
