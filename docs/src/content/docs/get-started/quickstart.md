---
title: Quickstart
description: A working chatbot in one file — first without a model, then with one.
sidebar:
  order: 2
---

This page builds a bot in a single `app.py`. The first version needs no API key. It shows how a handler streams text and components into a reply.

## 1. Write a handler

```python title="app.py"
import dyui
from dyui import ui

app = dyui.App(
    title="Weather Desk",
    description="Ask about the weather in any city.",
    starters=["Weather in Lisbon", dyui.Starter("Compare two cities", "Compare Lisbon and Porto", icon="map")],
)

@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    yield f"Here's the outlook for **{msg.text}**."
    yield ui.Stats(ui.Stat("Today", "24°C", trend="up", delta="+2°"), ui.Stat("Rain", "10%"))
    yield ui.QuickReplies("Tomorrow?", "Compare with Porto")
```

A handler can yield three kinds of value:

- **Strings**: streamed into the reply as Markdown.
- **Components** (`ui.*`): rendered inline where they're yielded.
- **`dyui.Reasoning(...)`**: shown as a collapsible "thinking" block.

Handlers can be async generators, sync generators or plain functions. A plain function may `return` a value or a list of values.

## 2. Run it

```bash
dyui run app.py
```

Open [http://localhost:8000](http://localhost:8000). `dyui run` finds `app.py`, `main.py` or `bot.py` when you leave the file out, and reloads the app whenever you save.

You now have:
- a welcome screen with your starters;
- a streaming reply with stats and quick replies;
- a sidebar of past conversations, stored in SQLite at `./.dyui/dyui.db`;
- stop, regenerate, edit, copy, feedback, file uploads, and light and dark themes.

## 3. Let a model answer

Install an SDK extra and stream a model instead of yielding fixed text:

```bash
pip install "dyui[openai]"
export NVIDIA_API_KEY=nvapi-...     # free key at build.nvidia.com
```

```python title="app.py"
@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    async for part in dyui.llm.stream(
        "nvidia/moonshotai/kimi-k2.6",
        chat.history,
        system="You are a concise weather assistant.",
        components=app.catalog,      # teaches the model DyUI's components
    ):
        yield part
```

The `openai` extra is the SDK that talks to every OpenAI-compatible endpoint, which is why it is the one to install here. Any `provider/model` string works; see [Integrations](../../integrations/other-providers/).

`components=app.catalog` appends a generated "UI components" section to the system prompt. The model then writes components into its reply, and DyUI parses, validates and renders them while they stream. [Generative UI](../../concepts/generative-ui/) explains how.

## Start from a template

`dyui new` scaffolds a project with an `app.py`, a README and a `requirements.txt`:

```bash
dyui new my-bot --template nvidia    # basic · nvidia · openai · anthropic · langgraph
cd my-bot
dyui run
```

## Let a coding agent build it

```bash
dyui agent "build a weather bot with a forecast chart"
```

`dyui agent` opens Claude Code, Gemini CLI, Codex or another coding agent with the DyUI skill loaded. See [Build with a coding agent](../coding-agents/).

## Next

- [Your first LLM bot](../first-llm-bot/): custom components, actions and steps.
- [Components](../../components/): everything the model can render.
