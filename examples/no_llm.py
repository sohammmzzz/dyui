"""A bot with no LLM: scripted components, actions, steps and human-in-the-loop."""
import asyncio

import dyui
from dyui import ui

app = dyui.App(
    title="Pizza Desk",
    description="A scripted bot - no API key needed.",
    starters=["Show the menu", "Order a pizza"],
)


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    text = msg.text.lower()
    if "menu" in text:
        yield "Here is today's menu."
        yield ui.Table(
            columns=["Pizza", "Size", "Price"],
            rows=[["Margherita", "M", "$11"], ["Diavola", "M", "$13"], ["Funghi", "M", "$12"]],
        )
        yield ui.QuickReplies(["Order a pizza"])
    elif "order" in text:
        yield ui.Choice("Which pizza?", ["Margherita", "Diavola", "Funghi"])
    else:
        yield "I can show the **menu** or take an **order**."


@app.on_action("choice")
async def chosen(action: dyui.Action, chat: dyui.Chat):
    pizza = action.values["selected"][0]
    answer = await chat.ask(ui.Confirm(f"Order a {pizza}?", text="Total: $12"))
    if not answer.values.get("confirmed"):
        yield "No problem, cancelled."
        return
    async with chat.step("Sending to the kitchen", type="tool"):
        await asyncio.sleep(1)
    yield ui.Plan(title="Your order", items=[
        {"title": "Order received", "status": "done"},
        {"title": "In the oven", "status": "active"},
        {"title": "Out for delivery", "status": "pending"},
    ])
