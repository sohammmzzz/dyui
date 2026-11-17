"""Every way an action reaches your code: chat.ask() waits for an answer,
@app.on_action handles a click, and anything unhandled goes back to on_message.

Save as app.py, then run:  dyui run app.py
"""
import dyui
from dyui import ui

app = dyui.App(title="Account Desk", starters=["Create an account"])


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    if msg.action is not None:  # route 3: an action with no handler arrives as a message
        yield f"You clicked **{msg.action.label}** (`{msg.action.name}`). An LLM bot would see: `{msg.text}`"
        return
    # route 1: render a form and wait for the answer
    answer = await chat.ask(ui.Form(
        ui.Field("email", type="email", required=True),
        ui.Field("plan", type="select", options=["Starter", "Team"]),
        title="Create your account",
    ))
    email, plan = answer.values["email"], answer.values["plan"]
    yield f"Creating a **{plan}** account for `{email}`."
    yield ui.Buttons(
        ui.Button("Delete it again", action="delete_account", data={"email": email}, style="danger"),
        ui.Button("Tell me more", action="more_info"),  # no handler: becomes a message
    )


@app.on_action("delete_account")  # route 2: a Python handler for one action name
async def delete(action: dyui.Action, chat: dyui.Chat):
    answer = await chat.ask(ui.Confirm(f"Delete {action.data['email']}?", danger=True, confirm_label="Delete"))
    if answer.values.get("confirmed"):
        yield ui.Callout("Deleted.", level="success")
    else:
        yield "Kept everything."
