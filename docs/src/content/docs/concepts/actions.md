---
title: Actions & human-in-the-loop
description: How buttons, forms and approvals reach your code — through chat.ask, @app.on_action or the model.
sidebar:
  order: 5
---

Interactive components (`buttons`, `choice`, `form`, `confirm`, `rating`, card `actions`, and `list` rows with an `action`) send an **action** when the user responds. An action carries:

| Field | Meaning |
|---|---|
| `name` | The action name declared by the component, e.g. `"book_flight"`, `"form_submit"`, `"confirm"` |
| `data` | Static data declared next to the action (a button's `data`) |
| `values` | What the user entered or chose. See below. |
| `label` | What the user clicked, e.g. `"Book"` or `"Approve"` |
| `message_id`, `component_id` | Where it came from |

| Component | Default action | `values` |
|---|---|---|
| `buttons`, card `actions`, `list` rows | the button's / row's own `action` | `{}` |
| `choice` | `choice` | `{"selected": [...], "other": "..."}` |
| `form` | `form_submit` | `{"<field name>": value, ...}` |
| `confirm` | `confirm` | `{"confirmed": true \| false}` |
| `rating` | `rating` | `{"rating": n}` (thumbs: `1` or `-1`) |

`quick_replies` are different: tapping one sends its text as a normal user message.

## Routing

When an action arrives, DyUI first checks that the component exists in that message and declared that action name; forged actions get a `400`. It then tries three routes, in order:

### 1. `chat.ask()` — wait for an answer

`await chat.ask(component)` renders an interactive component and **pauses your handler** until the user responds, then returns the `Action`. This is the human-in-the-loop primitive:

```python
@app.on_message
async def reply(msg, chat):
    answer = await chat.ask(ui.Confirm("Delete 14 conversations?", danger=True, confirm_label="Delete"))
    if answer.values.get("confirmed"):
        yield ui.Callout("Deleted.", level="success")
    else:
        yield "Kept everything."
```

Pass `timeout=` (seconds) to stop waiting; `asyncio.TimeoutError` is raised when it runs out. `ask()` also works with forms, choices, buttons and ratings:

```python
answer = await chat.ask(ui.Form(
    ui.Field("email", type="email", required=True),
    ui.Field("plan", type="select", options=["Starter", "Team"]),
    title="Create your account",
))
email = answer.values["email"]
```

### 2. `@app.on_action(name)` — handle it in Python

```python
@app.on_action("book_flight")
async def book(action: dyui.Action, chat: dyui.Chat):
    yield f"Booking {action.data['airline']}…"
```

An action handler has the same shapes and yield rules as `on_message`. If it yields, its output becomes a new assistant reply.

### 3. Back to the model

With no waiting `ask()` and no handler, the action becomes a **user turn**. The user sees the label (for example "Book"), and `on_message` receives an LLM-friendly text with `msg.action` set:

```text
[action:book_flight] {"data":{"airline":"TAP","depart":"Fri 18:05","price":189}}
```

An LLM bot therefore needs no action code at all: the model reads what was clicked and carries on.

## Resolved state

After an interactive component is used, it becomes **resolved**: the client shows the choice inline (for example a check and "Approved") and disables the control. The resolution is stored in the message as `props.__resolved__`, so it survives a reload. Only components in the latest assistant message are interactive.
