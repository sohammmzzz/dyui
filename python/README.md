# dyui

A **dynamic-UI layer for any LangGraph agent.** Emit rich, live UI "cards" from
inside any LangGraph node or tool — with any LLM, or none — and render them on
the frontend with the companion [`dyui-react`](../react) package.

DyUI rides LangGraph's first-class `custom` stream channel, so it is
transport-, model-, and framework-agnostic. No voice, no vendor lock-in.

## Install

```bash
pip install dyui            # core (langgraph + pydantic)
pip install "dyui[server]"  # + FastAPI SSE server
```

## Try it in one command

```bash
dyui demo          # animated showcase of every card type — no API key, opens the browser
dyui new agent.py  # scaffold a runnable starter agent
dyui serve         # run your agent's dynamic UI (auto-discovers app.py/agent.py)
dyui init          # write a DyUI guide into AGENTS.md/CLAUDE.md/GEMINI.md for coding agents
```

## Emit cards from your agent

```python
from dyui import emit, ui_tool, Card

# 1. Imperative — call anywhere inside a node:
emit("table", {"columns": ["city", "temp"], "rows": [["Berlin", 21]]},
     title="Weather", icon="cloud", accent="cyan")

# 2. Decorator — auto pending -> done/error around a tool:
@ui_tool("stat", title="Sum", icon="plus", accent="emerald")
def add(a: float, b: float) -> dict:
    return {"label": f"{a} + {b}", "value": a + b}

# 3. Context manager — long-running work, one card updated in place:
with Card("progress", title="Indexing") as card:
    for i in range(1, 4):
        card.progress({"value": i, "max": 3})
    card.done({"value": 3, "max": 3, "label": "Done"})
```

Each event carries an `id` (auto or yours), a `component` key (which card to
render), `props` (the data), a `status` (`pending`/`active`/`done`/`error`), and
an optional `surface` (which screen region hosts it).

## Zero frontend: serve a UI from Python

You don't need React or npm to get a working screen. `create_dyui_app` hosts a
built-in single-file UI at `GET /` that renders every built-in card **and your
raw HTML cards**:

```python
from dyui.server import create_dyui_app

app = create_dyui_app(my_compiled_graph)   # uvicorn my_module:app --port 8008
# open http://localhost:8008  -> a live dynamic-UI screen, no frontend code
```

`create_dyui_app` is **plug-and-play**: it inspects your graph's state schema and
maps the browser's plain-text input onto the right field automatically
(`{"messages": [...]}`, `{"query": ...}`, a single custom field, …). Pass
`input_adapter=...` only if you need a custom shape.

### Use your own HTML files as cards

Drop `.html` templates in a folder and emit them by name — placeholders are
filled from props (`{{ key }}` escaped, `{{{ key }}}` raw):

```python
from dyui import HtmlTemplates

cards = HtmlTemplates("cards")             # ./cards/invoice.html, weather.html, ...

def my_node(state):
    cards.emit("invoice",
               {"number": 42, "total": "$1,200", "customer": "Acme"},
               title="Invoice", accent="emerald")
```

That's the whole "one Python file + HTML templates → dynamic UI" path. See
[`examples/html_agent.py`](examples/html_agent.py) and [`examples/cards/`](examples/cards).

> The served UI renders the built-in card types and `html` cards. Bespoke
> *React* card components live in `dyui-react`; for the no-frontend path, model
> custom cards as HTML templates instead.

## Connect a React frontend (optional)

`POST /dyui/stream` is a plain SSE endpoint the `dyui-react` `useDyUIAgent` hook
consumes directly. Or mount onto an existing app:

```python
from dyui.server import add_dyui_routes
add_dyui_routes(existing_fastapi_app, my_graph, path="/agent/stream")
```

## Test / consume without HTTP

```python
from dyui import collect_events
for ev in collect_events(my_graph, {"query": "berlin"}):
    print(ev["status"], ev["component"], ev["props"])
```

## Built-in card components (frontend)

`text`, `markdown`, `table`, `stat`, `progress`, `list`, `keyvalue`, `json`,
`alert`, `image`, and `html` (custom markup, run through a parser-based allowlist
sanitizer — a sane default, not a hardened boundary; override the `html` card
with DOMPurify for hostile input, and never feed untrusted data to the raw
`{{{ }}}` template placeholders). Register your own React components for any
`component` key to fully customise — see the React package.

> The `create_dyui_app` / `dyui serve` server is a development convenience:
> CORS defaults to localhost-only; pass `api_token="…"` to require a bearer
> token, and `allow_client_config=True` only if you trust callers with the run
> config. Put it behind real auth before exposing it beyond your machine.

## Development

```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows
pip install -e ".[dev]"
pytest
```
