"""{{title}} - a DyUI bot with no LLM. Run it with:  dyui run"""
import dyui
from dyui import ui

app = dyui.App(
    title="{{title}}",
    description="A small bot that answers with interfaces.",
    starters=["Show me a dashboard", "Ask me to confirm something"],
)


@app.on_chat_start
async def greet(chat: dyui.Chat):
    await chat.send("Hi! Try asking for a **dashboard**, or say anything else.")


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    if "dashboard" in msg.text.lower():
        yield "Here is a quick snapshot."
        # Components are plain Python objects - just yield them.
        yield ui.Stats(items=[
            {"label": "Revenue", "value": "$48.2k", "delta": "+12%", "trend": "up"},
            {"label": "Orders", "value": 1284, "delta": "+3%", "trend": "up"},
            {"label": "Refunds", "value": 17, "delta": "-8%", "trend": "down"},
        ])
        yield ui.Table(
            columns=["Product", "Units", "Revenue"],
            rows=[["Notebook", 420, "$8,400"], ["Pen set", 310, "$3,720"], ["Desk lamp", 95, "$5,510"]],
        )
        yield ui.Buttons(ui.Button("Export report", action="export", data={"format": "csv"}))
    else:
        yield f"You said: {msg.text}"
        yield ui.QuickReplies(["Show me a dashboard", "Ask me to confirm something"])


# Runs when a component fires an action you declared (here: the button above).
@app.on_action("export")
async def export(action: dyui.Action, chat: dyui.Chat):
    async with chat.step("Building report", type="tool") as step:
        await step.log(f"format={action.data['format']}")
    yield ui.Callout("Report exported.", level="success")
