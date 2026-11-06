---
title: Bring your own SDK
description: Use any client or framework — add the catalog prompt and yield the raw text.
sidebar:
  order: 6
---

DyUI doesn't need to own your model calls. It parses **text**, so anything that streams text can render components. Two steps:

1. Add `app.catalog.prompt()` to your system prompt.
2. Yield the raw text deltas. DyUI finds the `dyui` fences while they stream.

```python
from openai import AsyncOpenAI

client = AsyncOpenAI()

@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    system = "You are a data analyst.\n\n" + app.catalog.prompt()
    stream = await client.chat.completions.create(
        model="gpt-5",
        messages=[{"role": "system", "content": system}, *chat.history],
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta
```

The same applies to any framework (LlamaIndex, Haystack, DSPy, your own HTTP client): put the prompt in, and stream the text out.

## Rendering components from code

When your code already has structured data, skip the model and yield components directly:

```python
rows = await db.fetch("select city, temp from weather")
yield ui.Table(["City", "Temp"], [[r.city, r.temp] for r in rows])
```

## Validating JSON yourself

If your framework produces component objects (for example, from your own tool calls), yield the dict. DyUI validates it like model output:

```python
yield {"ui": "stat", "label": "Revenue", "value": "$48.2k", "delta": "+12%"}
```

`app.catalog.json_schema()` returns `{name: JSON schema}`, and `app.catalog.tool_schemas("openai" | "anthropic")` returns ready-to-send `render_<name>` tool definitions if you want to run your own structured loop.
