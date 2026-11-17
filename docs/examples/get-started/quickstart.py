"""Weather Desk: a DyUI bot with no model and no API key.

Save as app.py, then run:  dyui run app.py
"""
import dyui
from dyui import ui

app = dyui.App(
    title="Weather Desk",
    description="Ask about the weather in any city.",
    starters=["Weather in Lisbon", dyui.Starter("Compare two cities", "Compare Lisbon and Porto", icon="map")],
)


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    yield f"Here's the outlook for **{msg.text}**."
    yield ui.Stats(ui.Stat("Today", "24°C", trend="up", delta="+2°"), ui.Stat("Rain", "10%"))
    yield ui.QuickReplies("Tomorrow?", "Compare with Porto")
