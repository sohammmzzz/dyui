"""Support bot: collects details with a form, shows a plan, cites sources, and reports live steps."""
import asyncio

import dyui
from dyui import ui

app = dyui.App(
    title="Support Desk",
    description="Tell us what is wrong and we will sort it out.",
    starters=["My order has not arrived", "I want a refund"],
)


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    yield "Sorry about that. I need a few details first."
    yield ui.Form(
        title="Order details",
        fields=[
            {"name": "order_id", "label": "Order number", "type": "text", "required": True, "placeholder": "A-1042"},
            {"name": "issue", "label": "What happened?", "type": "select",
             "options": ["Late delivery", "Damaged item", "Wrong item"]},
            {"name": "notes", "label": "Anything else?", "type": "textarea"},
        ],
        submit_label="Open ticket",
        action="open_ticket",
    )


@app.on_action("open_ticket")
async def open_ticket(action: dyui.Action, chat: dyui.Chat):
    order = action.values.get("order_id", "?")
    async with chat.step("Looking up order", type="search") as s:
        s.input = {"order_id": order}
        await asyncio.sleep(0.8)
        s.output = {"status": "in transit", "eta": "2 days"}
    async with chat.step("Checking carrier status", type="tool"):
        await asyncio.sleep(0.8)
    yield f"Order **{order}** is in transit and should arrive in two days. Here is what happens next."
    yield ui.Plan(title="Resolution plan", items=[
        {"title": "Ticket opened", "status": "done"},
        {"title": "Carrier contacted", "status": "active"},
        {"title": "Refund if not delivered by Friday", "status": "pending"},
    ])
    yield ui.Sources(items=[
        {"title": "Shipping policy", "url": "https://example.com/shipping", "snippet": "Delivery takes 3-7 days."},
        {"title": "Refund policy", "url": "https://example.com/refunds"},
    ])
