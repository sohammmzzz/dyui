"""``dyui demo`` — a guided tour that needs no API key.

It *simulates* an LLM: replies stream token by token and contain ```dyui blocks, so
everything goes through the same parser, validation and rendering a real model uses.
"""
from __future__ import annotations

import asyncio
import json
import random

import dyui
from dyui import ui

app = dyui.App(
    title="DyUI",
    description="A short tour of chat that answers in interfaces.",
    welcome="Ask me anything — I answer in interfaces.",
    starters=[
        dyui.Starter("Show me what you can do", icon="sparkles"),
        dyui.Starter("Analyze Q3 sales", icon="chart"),
        dyui.Starter("Plan a weekend in Lisbon", icon="plane"),
        dyui.Starter("File a support ticket", icon="life-buoy"),
    ],
    persist=False,
)


@app.component
class Flight(dyui.Component):
    """A bookable flight option. Use when listing specific flights."""

    airline: str
    route: str
    depart: str
    duration: str
    price: float

    def render(self):
        return ui.Card(
            title=self.airline,
            subtitle=f"{self.route} · {self.depart}",
            children=[ui.KeyValue(items=[{"key": "Duration", "value": self.duration},
                                         {"key": "Price", "value": f"€{self.price:.0f}"}])],
            actions=[ui.Button(label="Book", action="book_flight", data=self.model_dump(), style="primary")],
        )


async def type_out(text: str):
    """Stream text the way a model would: small chunks, uneven pacing."""
    i = 0
    while i < len(text):
        n = random.randint(2, 7)
        yield text[i:i + n]
        i += n
        await asyncio.sleep(random.uniform(0.012, 0.03))


def block(*components: dict) -> str:
    return "\n```dyui\n" + "\n".join(json.dumps(c) for c in components) + "\n```\n"


async def tour(chat: dyui.Chat):
    yield dyui.Reasoning("The user wants a tour. Show a few component families, briefly, then offer next steps.")
    await asyncio.sleep(0.4)
    text = (
        "Here's the idea: instead of describing things, I **show** them. A few examples —\n"
        + block(
            {"ui": "stats", "items": [
                {"label": "Components", "value": 39},
                {"label": "Providers", "value": 10},
                {"label": "Frontend code", "value": "0 lines"}]},
        )
        + "Data becomes charts:\n"
        + block({"ui": "chart", "kind": "area", "title": "Weekly active users", "labels": ["W1", "W2", "W3", "W4", "W5", "W6"],
                 "series": [{"name": "Users", "data": [120, 180, 260, 310, 420, 515]}]})
        + "and steps become live plans:\n"
        + block({"ui": "plan", "title": "Launch checklist", "items": [
            {"title": "Write app.py", "status": "done"},
            {"title": "Teach the LLM your components", "status": "done"},
            {"title": "dyui run app.py", "status": "active"},
            {"title": "Ship it", "status": "pending"}]})
        + "Where to next?\n"
        + block({"ui": "quick_replies", "options": ["Analyze Q3 sales", "Plan a weekend in Lisbon", "File a support ticket"]})
    )
    async for chunk in type_out(text):
        yield chunk


async def sales(chat: dyui.Chat):
    async with chat.step("Querying the sales warehouse", type="search") as s:
        await asyncio.sleep(0.9)
        s.input = {"quarter": "Q3", "regions": 4}
        s.output = "4 regions · 12,480 orders"
    yield dyui.Reasoning("EMEA grew fastest; lead with the headline numbers, then the regional chart and table.")
    await asyncio.sleep(0.3)
    text = (
        "Q3 closed strong — revenue is up **14%** quarter over quarter, led by EMEA.\n"
        + block({"ui": "stats", "items": [
            {"label": "Revenue", "value": "$4.82M", "delta": "+14%", "trend": "up"},
            {"label": "Orders", "value": "12,480", "delta": "+9%", "trend": "up"},
            {"label": "Refund rate", "value": "1.8%", "delta": "-0.4pt", "trend": "down"}]})
        + block({"ui": "chart", "kind": "bar", "title": "Revenue by region ($k)", "labels": ["NA", "EMEA", "APAC", "LATAM"],
                 "series": [{"name": "Q2", "data": [1620, 1180, 980, 450]}, {"name": "Q3", "data": [1710, 1460, 1090, 560]}]})
        + block({"ui": "table", "caption": "Top products", "columns": ["Product", "Units", "Revenue", "QoQ"],
                 "rows": [["Atlas Pro", 3120, "$1.21M", "+18%"], ["Atlas Lite", 4410, "$0.88M", "+7%"],
                          ["Nimbus", 1980, "$0.74M", "+22%"], ["Orbit", 1270, "$0.41M", "-3%"]]})
        + block({"ui": "callout", "level": "info", "title": "Worth a look",
                 "text": "Orbit is the only product that shrank. Its refunds doubled after the July price change."})
    )
    async for chunk in type_out(text):
        yield chunk


async def lisbon(chat: dyui.Chat):
    async with chat.step("Searching flights · LHR → LIS", type="search") as s:
        await asyncio.sleep(1.0)
        s.output = "14 options · 3 shown"
    text = (
        "Lisbon in early autumn is lovely — warm, quieter, golden light. Here are the best flights for Friday:\n"
        + block(
            {"ui": "flight", "airline": "TAP Air Portugal", "route": "LHR → LIS", "depart": "Fri 18:05", "duration": "2h 45m", "price": 189},
            {"ui": "flight", "airline": "British Airways", "route": "LHR → LIS", "depart": "Fri 07:20", "duration": "2h 50m", "price": 214},
        )
        + "And a rough shape for the weekend:\n"
        + block({"ui": "timeline", "items": [
            {"time": "Fri evening", "title": "Arrive · dinner in Alfama", "status": "pending"},
            {"time": "Sat", "title": "Belém, pastéis, LX Factory", "status": "pending"},
            {"time": "Sun", "title": "Sintra day trip", "status": "pending"}]})
        + block({"ui": "quick_replies", "options": ["Show hotels in Alfama", "Make it cheaper"]})
    )
    async for chunk in type_out(text):
        yield chunk


@app.on_action("book_flight")
async def book(action: dyui.Action, chat: dyui.Chat):
    f = action.data
    async for chunk in type_out(f"Great choice — **{f.get('airline')}**, {f.get('depart')}. One last check:"):
        yield chunk
    answer = await chat.ask(ui.Confirm(title=f"Book {f.get('airline')} for €{float(f.get('price', 0)):.0f}?",
                                       text="Your card on file will be charged.",
                                       confirm_label="Book flight", action="confirm_booking"))
    if answer.values.get("confirmed", True):
        async with chat.step("Booking", type="tool") as s:
            await asyncio.sleep(0.8)
            s.output = "PNR · LX7Q2D"
        yield ui.Callout(text="Booked. Confirmation LX7Q2D is on its way to your inbox.", level="success", title="You're going to Lisbon")
    else:
        yield ui.Callout(text="No problem — nothing was booked.", level="info")


async def support(chat: dyui.Chat):
    text = (
        "Sorry you're having trouble. Tell me a little more and I'll route it to the right team:\n"
        + block({"ui": "form", "title": "New support ticket", "action": "submit_ticket", "submit_label": "Create ticket",
                 "fields": [
                     {"name": "subject", "label": "Subject", "type": "text", "required": True, "placeholder": "Can't export reports"},
                     {"name": "area", "label": "Area", "type": "select", "options": ["Billing", "Exports", "Login", "Other"]},
                     {"name": "urgency", "label": "Urgency", "type": "slider", "min": 1, "max": 5, "default": 3},
                     {"name": "details", "label": "Details", "type": "textarea"}]})
    )
    async for chunk in type_out(text):
        yield chunk


@app.on_action("submit_ticket")
async def ticket(action: dyui.Action, chat: dyui.Chat):
    v = action.values
    async with chat.step("Creating ticket", type="tool") as s:
        await asyncio.sleep(0.7)
        s.output = "#4821"
    text = (
        f"Ticket **#4821** is open: *{v.get('subject') or 'Untitled'}*. Here's what happens next:\n"
        + block({"ui": "plan", "items": [
            {"title": "Ticket created", "status": "done"},
            {"title": f"Routed to {v.get('area') or 'Support'}", "status": "done"},
            {"title": "First response (usually < 2h)", "status": "active"},
            {"title": "Resolution", "status": "pending"}]})
        + block({"ui": "rating", "label": "How was this experience?", "style": "stars"})
    )
    async for chunk in type_out(text):
        yield chunk


ROUTES = [
    (("what can you do", "show me", "tour", "hello", "hi"), tour),
    (("sales", "revenue", "q3", "analy"), sales),
    (("lisbon", "flight", "trip", "travel", "weekend", "hotel", "cheaper"), lisbon),
    (("support", "ticket", "help", "issue", "problem"), support),
]


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    text = msg.text.lower()
    if msg.action is not None:
        text = f"{msg.action.name} {msg.action.label}".lower()
    for keys, flow in ROUTES:
        if any(k in text for k in keys):
            async for part in flow(chat):
                yield part
            return
    fallback = (
        "I'm the DyUI demo, so I only know a few tricks — but each one answers in an interface. Try one:\n"
        + block({"ui": "quick_replies", "options": ["Show me what you can do", "Analyze Q3 sales",
                                                    "Plan a weekend in Lisbon", "File a support ticket"]})
    )
    async for chunk in type_out(fallback):
        yield chunk
