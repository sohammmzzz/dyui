"""Branding from App(...): title, welcome copy, starters, accent, theme and feedback.

Save as app.py, then run:  dyui run app.py
"""
import dyui
from dyui import ui

app = dyui.App(
    title="Acme Support",
    description="Answers about orders, returns and billing.",
    welcome="How can we help today?",
    placeholder="Message {title}…",
    theme="system",  # "system" | "light" | "dark"
    accent="emerald",  # indigo, teal, rose, amber, emerald, slate or any hex like "#0F766E"
    starters=[
        "Where is my order?",
        dyui.Starter("Start a return", "I'd like to return an item", icon="shop"),
    ],
    uploads=False,
)


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    yield "Thanks! Rate this answer with the thumbs below it."
    yield ui.Callout("Returns are free within 30 days.", level="info", title="Returns")


@app.on_feedback
async def feedback(fb: dyui.Feedback, chat: dyui.Chat):
    print("feedback:", fb.message_id, fb.value, fb.comment)  # value: 1, -1 or 0 (cleared)
