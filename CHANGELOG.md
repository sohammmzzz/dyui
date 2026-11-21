# Changelog

All notable changes to DyUI are documented here. DyUI follows [Semantic Versioning](https://semver.org/).

## Unreleased

### Docs site

- The docs open with the same loading splash as every DyUI app (the mark assembles: dot, dot, card), once per browser session.
- The landing page's second section is now the real `dyui demo` app running in the page with its scripted, deterministic model — no API key, no server. It is a separate demo build of the web shell; the app bundled in the package is unchanged.
- The landing page reads like a presentation: Lenis smooth scrolling with spring-settled scroll stops, one per section, and every section fits the viewport. Phones and reduced motion keep native scrolling.

## 1.3.0 — 2026-11-18

### Added

- **DyUI MCP server** (`pip install "dyui[mcp]"`, `dyui mcp` / `python -m dyui.mcp`). Coding agents get version-exact tools instead of a static skill file: `dyui_overview`, `list_docs`, `read_doc`, `search_docs`, `list_components`, `get_component` (full prop schema, examples, action contract, catalog line), `list_examples`, `get_example`, `get_template`, `validate_ui` (runs the real parser and validator on a `dyui` block), `check_app` (imports your app in a subprocess and flags common mistakes) and `catalog_prompt`, plus docs/component/example resources and the build/convert/design/production playbooks as prompts. The docs ship inside the wheel, so it works offline.
- **`dyui mcp install [agent]`** registers the server for Claude Code (`.mcp.json`), Cursor, VS Code, Gemini CLI, Qwen Code, Codex, opencode, Zed and Claude Desktop, merging into existing config without touching other servers. `--print` shows the snippet.
- **`.env` loading.** `dyui run` loads `.env` from the app's folder (then the current directory) without overriding variables already set; `--env-file PATH`, `--no-env-file`. UTF-16 files written by Windows PowerShell load too.
- A missing API key now fails fast with a clear message naming the variable (`MissingAPIKeyError`), instead of an SDK error.
- Docs: **API keys & environment** page, **Models & providers** overview, `llms.txt` and `llms-full.txt`.

### Changed

- `dyui agent` / `dyui claude` / ... now register the MCP server and write a short pointer skill. Without the `mcp` extra, or for agents DyUI can't configure, they fall back to the full skill as before. `--print` still prints the full skill.
- **Docs rewritten around complete programs.** Every concept, integration, cookbook and component page ends with a complete `app.py` you can save and run, with save/run steps and a download link. Copied code ends with a newline. CI runs every complete example and compiles every copyable one on the built site, and checks all internal links.
- Template READMEs: `cp .env.example .env` replaces the `export $(grep …)` line, which failed on Windows.

### Fixed

- Pasting a copied example could glue its last line to the next one (`yield part"""Data analyst…` SyntaxError), because the copy text had no trailing newline and the page didn't say to save it as a new file.
- Component pages showed `yield ui.X(...)` at module level, which is a SyntaxError when pasted.
- Examples are checked out with LF line endings on every platform.

## 1.2.0 — 2026-11-11

### Added

- **`dyui agent`** opens a coding agent with the DyUI skill loaded: Claude Code, Gemini CLI, Codex, Qwen Code, Antigravity, Kimi Code, opencode and Cursor Agent (`dyui claude`, `dyui gemini`, ...), or any CLI that takes a prompt. The skill is rendered for the installed version with the live component catalog and written to the agent's project skills folder. The agent can build a new app, convert an existing project, integrate DyUI into a service, or design components. `--list`, `--print`, `--no-launch`.
- **Loading splash.** The page opens on the DyUI mark assembling (dot, dot, card) from the first paint, then the chat fades in. It follows the theme, respects reduced motion and runs under the strict CSP.
- `dyui new --template nvidia`.

### Changed

- **Design refresh.** Chat app: every text tier now meets WCAG AA in both themes, a three-step elevation system, calmer focus rings, centred starters, neutral disabled buttons and real depth in dark mode. Docs site: rebuilt landing page and restyled docs chrome. Brand: new README banners, lockups, app icons, social cards and a brand sheet (`brand/BRAND.md`). The mark itself is unchanged.
- Examples, templates and docs snippets use `nvidia/moonshotai/kimi-k2.6` (NVIDIA NIM, `NVIDIA_API_KEY`) as the model. Every other provider works as before.
- `dyui claude|gemini|codex init` now runs through the DyUI skill instead of writing `.dyui/INIT_PROMPT.md`.

## 1.1.0 — 2026-11-11

### Fixed

- **Rate limits no longer kill the reply.** `dyui.llm.stream` retries HTTP 429 using the provider's `Retry-After` (new `rate_limit_retries=3`; waits over a minute fail fast). A 429 or 413 that does get through shows a clear message in the chat instead of `RateLimitError: something went wrong`.
- **Replies always include text.** The catalog prompt (both modes) now tells the model to introduce and explain its components and never to answer with components alone, and the example shows prose around the block. In `ui_mode="tools"` the tool result asks the model to continue in text instead of the bare `"rendered"`.

### Added

- `nvidia/` provider prefix for NVIDIA NIM (`NVIDIA_API_KEY`).
- Docs: "Rate limits and free tiers" in the providers guide. `examples/data_analyst.py` uses a trimmed catalog.

## 1.0.0 — 2026-11-07

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
- **Safe by design.** The model only sends data: no model HTML (developer-only components are rejected from model output), and links are filtered. Threads, uploads and actions are scoped to the browser identity, and developer HTML renders in a sandboxed iframe. Action `data` is taken from the server's copy of the component, and an interactive component can only be answered once (`409`). JSON bodies are limited to 1 MB and uploads to `max_upload_mb` (`413`), and failed logins are throttled (`429`). Cookies are `Secure` over HTTPS, and uploaded files that aren't safe to display inline are served as downloads under a sandboxing CSP. Pages ship a strict per-request nonce CSP plus framing, nosniff, referrer and permissions headers (`App(csp=..., embed_origins=...)`); cross-site writes are refused (`403`) and JSON routes require `application/json` (`415`); concurrent answers to one component are serialised. Model components are bounded (512 KiB per line, 48 nesting levels) and parsed in linear time. 1.0 was penetration-tested end to end before release — see [`SECURITY.md`](SECURITY.md) and `security/`.
- **Python 3.10–3.13.** On 3.10, pass `config=` or `writer=` to `dyui.integrations.langgraph.emit(...)`; see the LangGraph docs. The `langgraph` extra requires `langgraph>=1.0`.
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
