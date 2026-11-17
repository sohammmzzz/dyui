"""Travel Bot: built-in and custom components, a button handled in Python,
an approval before booking, and a live step.

Needs:  pip install "dyui[openai]"   and NVIDIA_API_KEY in a .env file next to this one.
Save as app.py, then run:  dyui run app.py
"""
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

    examples = [{"airline": "TAP", "depart": "Fri 18:05", "price": 189}]  # validated at import

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
        system="You are a calm, expert travel agent. Offer 2-3 concrete flights when asked.",
        components=app.catalog,
    ):
        yield part


@app.on_action("book_flight")
async def book(action: dyui.Action, chat: dyui.Chat):
    flight = action.data
    answer = await chat.ask(ui.Confirm(
        f"Book {flight['airline']} at {flight['depart']}?",
        text=f"${flight['price']:.0f}, charged now.",
        confirm_label="Book",
    ))
    if not answer.values.get("confirmed"):
        yield "No problem — nothing was booked."
        return
    async with chat.step("Booking the seat", type="tool") as step:
        step.output = {"reference": "TP-7Q4XK2"}  # call your booking API here
    yield ui.Callout("Booked. Your confirmation is on its way.", level="success")
