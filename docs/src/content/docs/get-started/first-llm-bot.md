---
title: Your first LLM bot
description: A travel bot with a custom component, a button handled in Python and a live step.
sidebar:
  order: 3
---

This guide builds a small travel bot that uses everything that makes DyUI different:

- the model renders built-in components;
- the model renders a component you define;
- a button click reaches a Python handler;
- the user approves a booking before it happens;
- a live step shows work in progress.

```bash
pip install "dyui[openai]"     # or dyui[anthropic]; any provider works
export NVIDIA_API_KEY=nvapi-...
```

## The app

```python title="app.py"
import os

import dyui
from dyui import ui

MODEL = os.getenv("DYUI_MODEL", "nvidia/moonshotai/kimi-k2.6")

app = dyui.App(
    title="Travel Bot",
    description="Plans trips and books flights.",
    starters=["Plan a weekend in Lisbon", dyui.Starter("Find flights", "Flights to Tokyo next Friday", icon="plane")],
)


@app.component
class Flight(dyui.Component):
    """A bookable flight option. Use when listing specific flights."""

    airline: str
    depart: str
    price: float

    def render(self):
        return ui.Card(
            self.airline,
            ui.KeyValue({"Departs": self.depart, "Price": f"${self.price:.0f}"}),
            actions=[ui.Button("Book", action="book_flight", data=self.model_dump(), style="primary")],
        )


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    async for part in dyui.llm.stream(
        MODEL,
        chat.history,
        system="You are a calm, expert travel agent. Offer 2–3 concrete flights when asked.",
        components=app.catalog,
    ):
        yield part


@app.on_action("book_flight")
async def book(action: dyui.Action, chat: dyui.Chat):
    flight = action.data
    answer = await chat.ask(ui.Confirm(f"Book {flight['airline']} at {flight['depart']}?",
                                       text=f"${flight['price']:.0f}, charged now.", confirm_label="Book"))
    if not answer.values.get("confirmed"):
        yield "No problem — nothing was booked."
        return
    async with chat.step("Booking the seat", type="tool") as step:
        step.output = {"reference": "TP-7Q4XK2"}          # call your booking API here
    yield ui.Callout("Booked. Your confirmation is on its way.", level="success")
```

Run it with `dyui run app.py`.

## What happens

1. **The prompt grows with your app.** `components=app.catalog` adds a line for every enabled built-in, plus your `flight` component. The class docstring becomes its description and the fields become its props. Run `dyui catalog app.py` to see the exact text.
2. **The model writes a component.** When it offers flights, the model writes `{"ui":"flight","airline":"TAP","depart":"Fri 18:05","price":189}` inside a `dyui` fence. DyUI validates it against `Flight` and calls `render()`. The browser receives the built-in card that `render()` returned.
3. **The click comes back to Python.** **Book** sends the action `book_flight` with the flight as `data`. `@app.on_action("book_flight")` handles it. Without a handler, the click would go to `on_message` as a message for the model; see [Actions](../../concepts/actions/).
4. **The agent waits for a human.** `await chat.ask(ui.Confirm(...))` renders a confirmation and pauses the handler until the user answers.
5. **Work shows progress.** `chat.step(...)` renders a live step. It shows running, then done (or error) with its duration.

## Switch models

Change one string. Any `provider/model` works:

```bash
DYUI_MODEL=nvidia/deepseek-ai/deepseek-v4.1-flash dyui run app.py
DYUI_MODEL=anthropic/claude-sonnet-5-5 dyui run app.py
DYUI_MODEL=ollama/llama3.2 dyui run app.py
```

See [Integrations](../../integrations/openai/) for every provider.
