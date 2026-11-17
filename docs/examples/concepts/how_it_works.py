"""One DyUI turn, end to end, with no model: text, a component, a live step,
a button that comes back to Python, and an approval that pauses the handler.

Save as app.py, then run:  dyui run app.py
"""
import asyncio

import dyui
from dyui import ui

app = dyui.App(title="Order Desk", starters=["Where is order 1042?"])


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    # 1. text streams into the reply as Markdown
    yield f"Looking up **{msg.text}**…"
    # 2. a live step shows work in progress, then done with its duration
    async with chat.step("Fetching the order", type="tool") as step:
        await asyncio.sleep(0.3)  # call your API here
        step.output = {"order": 1042, "status": "shipped"}
    # 3. components render inline, where they're yielded
    yield ui.KeyValue({"Order": "1042", "Status": "Shipped", "Carrier": "DHL"})
    # 4. a button sends an action back to Python
    yield ui.Buttons(ui.Button("Cancel order", action="cancel_order", data={"order": 1042}, style="danger"))


@app.on_action("cancel_order")
async def cancel(action: dyui.Action, chat: dyui.Chat):
    # 5. chat.ask() renders a component and waits for the user's answer
    answer = await chat.ask(ui.Confirm(f"Cancel order {action.data['order']}?", danger=True, confirm_label="Cancel it"))
    if answer.values.get("confirmed"):
        yield ui.Callout("Cancelled. The refund is on its way.", level="success")
    else:
        yield "Kept the order as it is."
