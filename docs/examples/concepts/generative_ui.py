"""A model that answers with a chosen set of components, placed in the prompt with
{dyui_components}, plus a custom component of your own.

Needs:  pip install "dyui[openai]"   and NVIDIA_API_KEY in a .env file next to this one.
Save as app.py, then run:  dyui run app.py      (dyui catalog app.py prints the prompt)
"""
import os

import dyui
from dyui import ui

MODEL = os.getenv("DYUI_MODEL", "nvidia/moonshotai/kimi-k2.6")
UI_MODE = os.getenv("DYUI_UI_MODE", "fence")  # "tools" = schema-guaranteed (OpenAI, Anthropic)

app = dyui.App(
    title="Market Brief",
    components=["stat", "stats", "table", "chart", "callout", "quick_replies"],
    starters=["How did the big tech stocks do this quarter?"],
)


@app.component
class Ticker(dyui.Component):
    """One stock with its price and daily move. Use when the user asks about a single stock."""

    symbol: str
    price: float
    change_pct: float

    examples = [{"symbol": "ACME", "price": 182.4, "change_pct": 1.8}]

    def render(self):
        trend = "up" if self.change_pct >= 0 else "down"
        return ui.Stat(self.symbol, f"${self.price:,.2f}", delta=f"{self.change_pct:+.1f}%", trend=trend)


SYSTEM = """You are a markets analyst. Use made-up but plausible numbers and say so.

{dyui_components}

Prefer a `ticker` for one stock, `stats` for a few headline numbers and a `chart` for trends."""


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    async for part in dyui.llm.stream(MODEL, chat.history, system=SYSTEM, components=app.catalog, ui_mode=UI_MODE):
        yield part
