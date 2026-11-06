# Changelog

All notable changes to DyUI are documented here. DyUI follows [Semantic Versioning](https://semver.org/).

## 1.0.0 — 2026-11-05

The first stable release. DyUI 1.0 is a ground-up rewrite. 0.1 streamed UI cards out of LangGraph agents; 1.0 is a framework for professional chat apps whose model renders the interface.

### Highlights

- **One file to a full chat app.** `dyui.App` plus `@app.on_message` gives you a streaming chat app with conversation history, stop, regenerate and edit, file uploads, feedback, light and dark themes, a mobile layout and an optional password gate. `dyui run` serves it with hot reload.
- **The model renders UI.** 36 built-in components the model can use (content, data, media, interactive, layout, agent), plus developer-only `html`. DyUI generates the component section of the system prompt from pydantic models (`app.catalog.prompt()`), parses the model's `dyui` fences while they stream, validates every component and renders it inline. Invalid output degrades to a quiet chip, and the prose is never lost.
- **Structured mode.** `dyui.llm.stream(..., ui_mode="tools")` registers a strict `render_<name>` tool per component on OpenAI and Anthropic and runs the tool loop for you.
- **Custom components in pure Python.** `@app.component` on a `dyui.Component` subclass. The docstring becomes the prompt description, the fields become props, and `render()` returns built-ins. The prompt updates on the next turn.
- **Interfaces that talk back.** Buttons, forms, choices, approvals and ratings route to `await chat.ask(...)`, to `@app.on_action(name)`, or back to the model as a message. Actions are verified against the component that declared them.
- **Steps and reasoning.** `chat.step(...)` renders live, timed steps. `dyui.Reasoning` deltas (and provider thinking) render as a collapsible block.
- **Any model.** `dyui.llm.stream("provider/model", ...)` for OpenAI, Anthropic, Ollama, Groq, OpenRouter, Together, DeepSeek, Gemini, Mistral and xAI. LangGraph integration through `dyui.integrations.langgraph` (`stream`, `emit`). Or yield raw text from any SDK.
- **Persistence.** SQLite by default (`./.dyui/dyui.db`), in-memory, or your own `Store`. `chat.session` holds per-conversation state.
- **CLI.** `dyui run`, `dyui demo` (no API key), `dyui new` (templates: basic, openai, anthropic, langgraph), `dyui catalog`, `dyui claude|gemini|codex init`, `dyui version`.
- **Safe by design.** The model only sends data. There is no model HTML, links are filtered, uploads and threads are scoped to the browser identity, and developer HTML renders in a sandboxed iframe.
- **Documentation site** with live component demos: https://sohammmzzz.github.io/dyui/

### Upgrading from 0.1

1.0 has a different API. There are no deprecation shims, so port an app like this:

| 0.1 | 1.0 |
|---|---|
| `pip install "dyui[server]"` | `pip install dyui`. The server is part of the core package. Extras are now `openai`, `anthropic`, `langgraph` and `all`. |
| `create_dyui_app(graph)` + `dyui serve agent.py` | `app = dyui.App(...)`, an `@app.on_message` handler that streams the graph with `dyui.integrations.langgraph.stream(graph, ...)`, and `dyui run app.py` |
| `emit("stat", {"label": ..., "value": ...})` | Inside LangGraph nodes and tools: `from dyui.integrations.langgraph import emit`, then `emit(ui.Stat("Revenue", "$48.2k"))`. In a handler, just `yield ui.Stat(...)`. |
| `@ui_tool(...)` decorator | `chat.step("Title", type="tool")`, as an `async with` block or a decorator |
| `with Card("progress") as card: card.progress(...)` | Yield a component again with the same `id=` to update it in place: `ui.Progress(60, label="Indexing", id="idx")` |
| `HtmlTemplates("cards").emit("invoice", {...})` | `yield dyui.html_template("cards/invoice.html", **props)`. Same `{{ }}` / `{{{ }}}` syntax, still sandboxed. |
| `text` and `alert` cards | `markdown` and `callout` |
| `dyui export` | Removed. The web app ships compiled inside the wheel. |
| npm package `dyui-react` | Not published from 1.0. A React package of the new component library is planned. Existing `dyui-react` releases remain on npm but target the 0.1 event format. |

`dyui claude|gemini|codex init` still exists, and now designs custom components for a 1.0 app.

## 0.1.0 — 2026-05-28

Initial release: stream UI cards from LangGraph agents (`emit`, `ui_tool`, `Card`), a served chat UI (`dyui serve`), HTML templates, `dyui export`, and the `dyui-react` npm runtime.
