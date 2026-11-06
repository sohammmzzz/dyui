---
title: How DyUI works
description: The path from your handler to a rendered component, and back again when the user clicks.
sidebar:
  order: 1
---

DyUI has three parts, and all of them ship in the `dyui` package:

1. **Your Python app**: an `App` with handlers (`@app.on_message`, `@app.on_action`…) and, optionally, your own components.
2. **The DyUI server**: a FastAPI app that runs your handlers, parses what they produce, stores conversations and streams events to the browser over Server-Sent Events.
3. **The chat app**: a React app, compiled into the package. It renders the stream with DyUI's component library.

```text
 your handler ──text──▶ fence parser ─┐
 (any LLM/SDK)                         ├─▶ validated UI nodes ──SSE──▶ chat app
 your handler ──ui.Table(...)─────────┘                                │
        ▲                                                              │
        └───────── @app.on_action / chat.ask / back to the model ◀── clicks, forms
```

## One turn, step by step

1. The user sends a message. The browser calls `POST /api/chat`, and the server stores the message and opens an SSE stream.
2. DyUI calls your `on_message(msg, chat)` handler. `chat.history` holds the conversation in OpenAI-style `{"role", "content"}` form.
3. Your handler yields values:
   - **Text** goes through the streaming **fence parser**. Prose streams straight through. A ```` ```dyui ```` block becomes components *while it's still being written*: a component appears as soon as its `"ui"` name is known, and fills in as its props arrive.
   - **Components** (`ui.Stat(...)`, or your own) are serialized to nodes. Custom components are expanded server-side through their `render()`, so the browser only ever renders built-ins.
   - **`dyui.Reasoning`** becomes a collapsible thinking block.
4. Every node is **validated** against its pydantic model. Invalid output turns into a quiet "Couldn't display this component" chip, and the surrounding prose is kept.
5. When the handler finishes, the message is stored with its parts. After the first exchange, the thread gets a title from the user's first words.

## When the user clicks

Interactive components send an **action** to `POST /api/action`. The server first checks that the component exists in that message and declared that action, and rejects forged actions. It then routes the action in this order:

1. to a `chat.ask(...)` that is waiting for this component;
2. otherwise to an `@app.on_action(name)` handler;
3. otherwise back to `on_message`, as an LLM-friendly message the model can respond to.

See [Actions & human-in-the-loop](../actions/).

## Why the model can render UI

`app.catalog` lists the components the model may use. `app.catalog.prompt()` renders it as a short system-prompt section with one signature line per component, generated from the pydantic models. Pass `components=app.catalog` to `dyui.llm.stream` and the section is added for you. Because the prompt is rebuilt from the live registry on every turn, registering a component or editing its docstring changes what the model knows on the next turn. See [Generative UI](../generative-ui/).

## Safety model

- The model only ever sends **data**. HTML from the model is never rendered, and Markdown is rendered without raw HTML.
- URLs must be `http(s):`, `mailto:` or app-relative `/api/files/...`; anything else is dropped. External links open in a new tab with `rel="noopener noreferrer"`.
- Actions are verified against the component that declared them.
- Developer HTML (`ui.Html`, `dyui.html_template`) renders in a sandboxed iframe without same-origin access, and the model can't produce it.
