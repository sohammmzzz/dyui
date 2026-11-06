---
title: Anthropic
description: Stream Claude models through the Anthropic SDK, with extended thinking and strict tool use.
sidebar:
  order: 2
---

```bash
pip install "dyui[anthropic]"
export ANTHROPIC_API_KEY=sk-ant-...
```

```python
@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    async for part in dyui.llm.stream(
        "anthropic/claude-sonnet-5-5",
        chat.history,
        system="You are a careful research assistant.",
        components=app.catalog,
    ):
        yield part
```

DyUI uses the Messages streaming API. The system prompt (yours plus the catalog section) is sent as `system`. `max_tokens` defaults to `4096`; pass `max_tokens=` to change it. Other keyword arguments go to `client.messages.stream(...)`.

## Extended thinking

Thinking deltas become a collapsible reasoning block automatically. Turn thinking on with the SDK's own parameter:

```python
async for part in dyui.llm.stream(
    "anthropic/claude-opus-5-5",
    chat.history,
    components=app.catalog,
    max_tokens=16000,
    thinking={"type": "enabled", "budget_tokens": 8000},
):
    yield part
```

## Structured mode

`ui_mode="tools"` registers a strict `render_<name>` tool per component and runs the tool loop, keeping text and tool calls in order:

```python
async for part in dyui.llm.stream("anthropic/claude-sonnet-5-5", chat.history,
                                  components=app.catalog, ui_mode="tools"):
    yield part
```

## Custom endpoints

`ANTHROPIC_BASE_URL` or `base_url=` points DyUI at a proxy or gateway. Pass `client=` with a pre-built `anthropic.AsyncAnthropic` for full control.
