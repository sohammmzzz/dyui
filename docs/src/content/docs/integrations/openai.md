---
title: OpenAI
description: Stream OpenAI models with dyui.llm.stream, in fence or structured mode.
sidebar:
  order: 1
---

```bash
pip install "dyui[openai]"
export OPENAI_API_KEY=sk-...
```

```python
@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    async for part in dyui.llm.stream(
        "openai/gpt-5",
        chat.history,
        system="You are a helpful analyst.",
        components=app.catalog,
    ):
        yield part
```

`dyui.llm.stream(model, messages, *, system=None, components=None, ui_mode="fence", max_tool_rounds=8, base_url=None, api_key=None, client=None, **kwargs)` yields `str` text deltas and `dyui.Reasoning` deltas. With `ui_mode="tools"` it also yields `{"ui": ...}` component dicts.

| Argument | Meaning |
|---|---|
| `model` | `"openai/<model id>"` |
| `messages` | Usually `chat.history`; any OpenAI-style `{"role", "content"}` list. `system=` (plus the catalog) is sent as the first message. |
| `components` | A catalog. Its prompt is appended to the system prompt, or placed at `{dyui_components}`. |
| `ui_mode` | `"fence"` (default) or `"tools"`; see below |
| `base_url`, `api_key` | Override `OPENAI_BASE_URL` / `OPENAI_API_KEY` |
| `client` | A pre-built `openai.AsyncOpenAI` client (for Azure, proxies, custom HTTP settings) |
| `**kwargs` | Passed to `client.chat.completions.create`, e.g. `temperature`, `reasoning_effort`, `tools` |

Reasoning fields in the stream (`reasoning_content` / `reasoning`) arrive as `dyui.Reasoning`.

## Structured mode

```python
async for part in dyui.llm.stream("openai/gpt-5", chat.history, components=app.catalog, ui_mode="tools"):
    yield part
```

DyUI sends one strict function tool per component, `render_<name>`. The JSON schemas have `additionalProperties: false`, and every field is required, with optional ones nullable. DyUI runs the tool loop for you. If the model calls a tool you passed in `tools=`, the loop stops, because custom tools need their own loop. See [Generative UI](../../concepts/generative-ui/#structured-mode-ui_modetools).

## Azure OpenAI and proxies

Pass a configured client:

```python
from openai import AsyncAzureOpenAI

client = AsyncAzureOpenAI(azure_endpoint="https://….openai.azure.com", api_version="2024-10-21")
async for part in dyui.llm.stream("openai/my-deployment", chat.history, components=app.catalog, client=client):
    yield part
```

## Non-streaming

`await dyui.llm.complete(model, messages, **kwargs)` returns the full text, with reasoning dropped. It's useful for titles, summaries and classification.
