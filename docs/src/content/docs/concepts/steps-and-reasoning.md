---
title: Steps & reasoning
description: Show tools at work with live steps, and stream model thinking into a collapsible block.
sidebar:
  order: 6
---

## Steps

`chat.step()` renders a live step in the reply. It moves from running to done (or error) and shows how long it took.

```python
@app.on_message
async def reply(msg, chat):
    async with chat.step("Searching flights", type="search") as step:
        step.input = {"from": "LHR", "to": "LIS"}
        await step.log("Querying 4 airlines")
        step.output = await search_flights("LHR", "LIS")
    yield ui.Table(["Airline", "Depart", "Price"], to_rows(step.output))
```

| Member | Purpose |
|---|---|
| `title`, `type` | The label and a free-form kind (`tool`, `search`, `code`…) |
| `step.input`, `step.output` | Shown when the step is expanded. Any JSON-serializable value; pydantic models are dumped. |
| `await step.log(text)` | Appends a log line, shown when expanded |

If an exception escapes the block, the step is marked **error**, its message becomes the output, and the exception is re-raised. If the user presses stop while the step runs, it also ends in the error state.

`chat.step` also works as a decorator. The wrapped function's arguments become the input and its return value the output:

```python
async def reply(msg, chat):
    @chat.step("Geocode city", type="tool")
    async def geocode(city: str):
        return await lookup(city)

    coords = await geocode(msg.text)
```

You can also render a step that you control yourself: `ui.Step("Indexing", "running", id="idx")`, then yield it again with the same `id` and `status="done"`.

## Reasoning

Yield `dyui.Reasoning(text)` deltas, and DyUI collects them into a collapsible "thinking" block that records how long it took:

```python
yield dyui.Reasoning("Comparing departure times… ")
yield dyui.Reasoning("Friday evening keeps Saturday free.")
yield "TAP at 18:05 is the best fit."
```

`dyui.llm.stream` does this for you. Anthropic thinking deltas, and the `reasoning` fields that OpenAI-compatible providers send, arrive as `Reasoning`. The LangGraph adapter forwards thinking blocks the same way.

Reasoning and steps are **not** included in `chat.history`, so they don't cost tokens on later turns.

## Plans

For multi-step agents, the `plan` component shows a live checklist. Yield it with a stable `id` and update item statuses as work progresses:

```python
items = [ui.PlanItem("Find flights", "active"), ui.PlanItem("Shortlist hotels"), ui.PlanItem("Build itinerary")]
yield ui.Plan(*items, title="Planning your trip", id="plan")
```
