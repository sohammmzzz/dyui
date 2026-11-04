"""Travel agent: an LLM that renders custom Flight / Hotel components and books with confirmation."""
import os

import dyui
from dyui import ui

MODEL = os.getenv("DYUI_MODEL", "openai/gpt-5")

app = dyui.App(
    title="Travel Bot",
    description="Plans trips and books flights.",
    starters=["Plan a weekend in Lisbon", "Find flights from Berlin to Tokyo"],
)


@app.component
class Flight(dyui.Component):
    """A bookable flight option. Use when listing specific flights."""

    airline: str
    depart: str
    arrive: str | None = None
    price: float

    examples = [{"airline": "TAP", "depart": "Fri 18:05", "price": 189}]

    def render(self):
        return ui.Card(
            self.airline,
            ui.Stat("Departs", self.depart),
            ui.Stat("Price", f"${self.price:.0f}"),
            actions=[ui.Button("Book", action="book_flight", data=self.model_dump())],
        )


@app.component
class Hotel(dyui.Component):
    """A hotel option with nightly price and rating. Use when suggesting places to stay."""

    name: str
    area: str | None = None
    price_per_night: float
    rating: float | None = None

    examples = [{"name": "Casa Alfama", "area": "Alfama", "price_per_night": 120, "rating": 4.6}]

    def render(self):
        return ui.Card(
            self.name,
            ui.Stat("Per night", f"${self.price_per_night:.0f}"),
            subtitle=self.area,
            actions=[ui.Button("Reserve", action="book_hotel", data=self.model_dump(), style="secondary")],
        )


SYSTEM = """You are a friendly travel agent. Suggest realistic options (invent plausible
prices and times). Show flights with the flight component and stays with the hotel
component, then offer quick replies for next steps."""


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    async for part in dyui.llm.stream(MODEL, chat.history, system=SYSTEM, components=app.catalog):
        yield part


@app.on_action("book_flight")
async def book_flight(action: dyui.Action, chat: dyui.Chat):
    f = action.data
    # Human in the loop: render a confirmation and wait for the click.
    answer = await chat.ask(ui.Confirm(
        f"Book {f['airline']} {f['depart']}?", text=f"Total ${f['price']:.0f}", confirm_label="Book it",
    ))
    if answer.values.get("confirmed"):
        async with chat.step("Booking flight", type="tool"):
            pass  # call your booking API here
        yield ui.Callout(f"Booked {f['airline']}, {f['depart']}.", level="success", title="Confirmed")
        yield ui.QuickReplies(["Find me a hotel too"])
    else:
        yield "Okay, I have not booked anything."


@app.on_action("book_hotel")
async def book_hotel(action: dyui.Action, chat: dyui.Chat):
    yield ui.Callout(f"Reserved {action.data['name']}.", level="success")
