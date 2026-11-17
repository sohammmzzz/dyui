"""Live steps (context manager and decorator), a reasoning block and a live plan.

Save as app.py, then run:  dyui run app.py
"""
import asyncio

import dyui
from dyui import ui

app = dyui.App(title="Trip Planner", starters=["Plan a weekend in Lisbon"])

FLIGHTS = [["TAP", "Fri 18:05", "$189"], ["easyJet", "Fri 06:50", "$142"]]


async def search_flights(origin: str, dest: str) -> list[list[str]]:
    await asyncio.sleep(0.3)  # call a real API here
    return FLIGHTS


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    items = [ui.PlanItem("Find flights", "active"), ui.PlanItem("Pick the best one"), ui.PlanItem("Build itinerary")]
    yield ui.Plan(*items, title="Planning your trip", id="plan")

    async with chat.step("Searching flights", type="search") as step:
        step.input = {"from": "LHR", "to": "LIS"}
        await step.log("Querying 2 airlines")
        step.output = await search_flights("LHR", "LIS")
    yield ui.Table(["Airline", "Depart", "Price"], step.output)

    items[0].status, items[1].status = "done", "active"
    yield ui.Plan(*items, title="Planning your trip", id="plan")  # same id: updated in place

    yield dyui.Reasoning("Comparing departure times… ")
    yield dyui.Reasoning("Friday evening keeps Saturday free.")

    @chat.step("Geocode city", type="tool")  # the decorator form: args become input, return the output
    async def geocode(city: str) -> dict:
        await asyncio.sleep(0.1)
        return {"city": city, "lat": 38.72, "lon": -9.14}

    await geocode("Lisbon")
    items[1].status, items[2].status = "done", "done"
    yield ui.Plan(*items, title="Planning your trip", id="plan")
    yield "TAP at 18:05 is the best fit."
