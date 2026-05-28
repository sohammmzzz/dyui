# DyUI

**A dynamic UI layer for any LangGraph agent.**

Stream beautiful, live UI **cards** from inside any LangGraph node or tool — with
any LLM, or none. DyUI ships a polished, animated chat interface out of the box,
so you can go from *one Python agent file* to a working generative-UI app **without
writing any frontend code**. When you want full control, export it as a React project.

```python
from dyui import emit

emit("stat", {"label": "Revenue", "value": "$48.2k", "delta": "+12%"},
     title="This month", accent="emerald")
```

```bash
dyui serve agent.py        # open http://localhost:8000 — your cards, live
```

---

## Why

LLM agents do interesting work, but `print()`/plain text wastes it. DyUI lets the
agent **say what to render** — a table, a stat, a progress bar, a chart, your own
HTML — and streams those instructions to a frontend that animates them into a
chat. It rides LangGraph's native `custom` stream channel, so it works with **any
model and any graph**, no vendor lock-in.

## Install

```bash
pip install "dyui[server]"      # Python package + built-in served UI
```

For the optional React runtime:

```bash
npm install @dyui/react
```

## Quick start

**1. Emit cards from your agent** (any node or tool):

```python
from dyui import emit, ui_tool, Card

# imperative
emit("table", {"columns": ["city", "temp"], "rows": [["Berlin", 21]]}, title="Weather")

# decorator: auto "pending → done/error" around a tool
@ui_tool("stat", title="Sum", icon="calculator", accent="emerald")
def add(a, b): return {"label": f"{a}+{b}", "value": a + b}

# context manager: long work, one card updated in place
with Card("progress", title="Indexing") as card:
    for i in range(1, 4): card.progress({"value": i, "max": 3})
    card.done({"value": 3, "max": 3, "label": "Done"})
```

**2. Expose it** (one line):

```python
from dyui.server import create_dyui_app
app = create_dyui_app(graph)            # graph = your compiled LangGraph
```

**3. Run it:**

```bash
dyui serve agent.py                     # or: uvicorn agent:app
```

Open the browser — DyUI serves an animated chat UI that renders your cards live,
with a "thinking" indicator while the agent works. **No frontend code required.**

## Built-in cards

`text` · `markdown` · `table` · `stat` · `progress` · `list` · `keyvalue` ·
`json` · `alert` · `image` · `html` (sanitized custom markup).

```python
emit("alert", {"level": "success", "text": "Deploy finished"}, title="CI")
emit("markdown", {"text": "### Plan\n- step one\n- **step two**"})
```

## Custom cards with your own HTML — still no frontend code

Drop `.html` files in a folder and emit them by name (`{{ key }}` escaped,
`{{{ key }}}` raw):

```python
from dyui import HtmlTemplates
cards = HtmlTemplates("cards")          # ./cards/invoice.html, ...

cards.emit("invoice", {"number": 42, "total": "$1,200"}, title="Invoice", accent="emerald")
```

## CLI

DyUI installs a `dyui` command:

### `dyui <agent> init <file.py>` — let an AI build your cards

Every use case needs different cards. Pair DyUI with a coding agent to design and
build them for you. It reads your LangGraph file, gets a full brief on DyUI,
**proposes a card plan, asks you to confirm**, then implements and wires it up:

```bash
dyui claude init agent.py     # Claude Code
dyui gemini init agent.py     # Gemini CLI
dyui codex init agent.py      # Codex CLI
```

> Tip: set `DYUI_NO_LAUNCH=1` to just print the prepared command instead of launching.

### `dyui serve [target]` — run the served UI

```bash
dyui serve agent.py                 # file exposing `app` or `graph`
dyui serve module:app --port 8080   # explicit module:attr
dyui serve                          # auto-discovers app.py / agent.py / main.py
```

### `dyui export <name>` — eject to a real React project

When you outgrow the built-in UI, generate an editable Vite + React app wired to
your agent (uses `@dyui/react`):

```bash
dyui export my-ui
cd my-ui && npm install && npm run dev
```

## Using the React runtime directly

```tsx
import { useDyUIAgent, DyUISurface, createRegistry } from "@dyui/react";
import "@dyui/react/styles.css";

function App() {
  const registry = createRegistry({ my_card: MyCard });   // custom + built-ins
  const { cards, tokens, status, run, dismiss } = useDyUIAgent({ url: "/dyui/stream" });
  return (
    <>
      <button onClick={() => run("hello")}>Ask</button>
      <DyUISurface cards={cards} registry={registry} onDismiss={dismiss} />
    </>
  );
}
```

## How it works

```
your LangGraph agent ──emit()──► LangGraph custom stream ──► dyui.server (SSE)
                                                                  │
                                       built-in animated UI  ◄────┤
                                       or @dyui/react app    ◄────┘
```

Each card is one event: a `component` key (which card), `props` (the data), a
lifecycle `status` (`pending → active → done → error`), and an optional `id` to
update it in place. The Python `UIEvent` model and the TS `DyUIEvent` type are
identical, so the wire format never drifts.

## Repository layout

```
DyUI/
├─ python/        # the `dyui` pip package (emit, server, CLI, HTML templates)
│  ├─ dyui/       #   library + dyui/static/index.html (the served UI)
│  ├─ examples/   #   runnable agents (search demo, HTML-templates demo)
│  └─ tests/      #   pytest suite
└─ react/         # the `@dyui/react` npm package (hook, surface, card registry)
```

## Development

```bash
# Python
cd python && python -m venv .venv && . .venv/Scripts/activate    # Windows
pip install -e ".[dev]" && pytest

# React
cd react && npm install && npm run build && npm test
```

## License

MIT
