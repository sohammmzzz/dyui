"""A custom Flight component: defined in Python, yielded by your code, and offered
to the model too (switch reply() to dyui.llm.stream with components=app.catalog).

Save as app.py, then run:  dyui run app.py      (dyui catalog app.py shows its prompt line)
"""
import dyui
from dyui import ui

app = dyui.App(title="Flight Finder", starters=["Flights to Lisbon"])


@app.component
class Flight(dyui.Component):
    """A bookable flight option. Use when listing specific flights."""

    airline: str
    depart: str
    arrive: str | None = None
    price: float

    examples = [{"airline": "TAP", "depart": "Fri 18:05", "price": 189}]
    positional = ("airline", "depart")

    def render(self):
        return ui.Card(
            self.airline,
            ui.KeyValue({"Departs": self.depart, "Arrives": self.arrive or "—", "Price": f"${self.price:.0f}"}),
            actions=[ui.Button("Book", action="book_flight", data=self.model_dump(), style="primary")],
        )


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    yield "Two options for Friday:"
    yield Flight("TAP", "Fri 18:05", arrive="20:10", price=189)
    yield Flight("easyJet", "Fri 06:50", price=142)


@app.on_action("book_flight")
async def book(action: dyui.Action, chat: dyui.Chat):
    # action.data is the server's copy of the button's data, so the price can be trusted
    yield ui.Callout(f"Booked {action.data['airline']} at {action.data['depart']} for ${action.data['price']:.0f}.",
                     level="success")
