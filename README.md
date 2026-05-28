<div align="center">

<img src="assets/banner.svg" alt="DyUI — Dynamic UI for any LangGraph agent" width="100%" />

<br/>

[![PyPI](https://img.shields.io/pypi/v/dyui?style=flat-square&color=f5b544&logo=pypi&logoColor=white&label=PyPI)](https://pypi.org/project/dyui/)
[![Python](https://img.shields.io/pypi/pyversions/dyui?style=flat-square&color=5eead4&logo=python&logoColor=white)](https://pypi.org/project/dyui/)
[![Downloads](https://img.shields.io/pypi/dm/dyui?style=flat-square&color=ff8a6b&label=installs)](https://pypi.org/project/dyui/)
[![License](https://img.shields.io/badge/license-MIT-eef1f5?style=flat-square)](LICENSE)
[![Built for LangGraph](https://img.shields.io/badge/built%20for-LangGraph-a78bfa?style=flat-square)](https://langchain-ai.github.io/langgraph/)

### Stream beautiful, live UI **cards** from any LangGraph agent — with any LLM, or none.

From *one Python file* to an animated generative-UI chat app, **without writing any frontend code.**

<br/>

```bash
pip install "dyui[server]"
```

**[Install](#-install) · [Quickstart](#-quickstart) · [Zero-frontend UI](#-zero-frontend-bring-your-own-html) · [CLI](#%EF%B8%8F-cli) · [React](#-prefer-react) · [PyPI ↗](https://pypi.org/project/dyui/)**

</div>

<br/>

<div align="center">
<img src="assets/gallery.svg" alt="DyUI rendered cards: markdown, stat, progress, and a custom HTML invoice card" width="100%" />
<sub><i>The same agent event stream, rendered as animated cards — built-in components and your own HTML.</i></sub>
</div>

---

## ✨ Why DyUI

LLM agents do interesting work — but `print()` and plain text throw most of it away. **DyUI lets the agent say *what to render*** — a table, a stat, a progress bar, your own HTML — and streams those instructions to a frontend that animates them into a chat.

It rides LangGraph's native `custom` stream channel, so it works with **any model and any graph**. No voice, no vendor lock-in, no glue code.

```python
from dyui import emit

emit("stat", {"label": "Revenue", "value": "$48.2k", "delta": "+12%"},
     title="This month", accent="emerald")
```

<table>
<tr>
<td width="33%" valign="top">

### 🧩 Plug into any agent
One line in any node or tool. Works with OpenAI, Anthropic, Groq, local models — or no LLM at all.

</td>
<td width="33%" valign="top">

### 🎨 Zero frontend code
Ships a polished, animated chat UI. Run one command, open the browser. Bring your own HTML cards.

</td>
<td width="33%" valign="top">

### 🤖 AI-assisted setup
`dyui claude init agent.py` hands your code to a coding agent that designs custom cards for you.

</td>
</tr>
</table>

---

## 📦 Install

```bash
pip install "dyui[server]"     # Python package + built-in served UI
npm install @dyui/react        # optional: the React runtime
```

---

## 🚀 Quickstart

**1 — Emit cards** from any node or tool:

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

**2 — Expose it** (one line):

```python
from dyui.server import create_dyui_app
app = create_dyui_app(graph)        # graph = your compiled LangGraph
```

**3 — Run it:**

```bash
dyui serve agent.py                 # or: uvicorn agent:app
```

Open the browser → an animated chat that renders your cards live, with a “thinking” indicator while the agent works.

---

## 🖥️ Zero-frontend: bring your own HTML

No React, no npm. Drop `.html` files in a folder and emit them by name — `{{ key }}` is escaped, `{{{ key }}}` is raw:

```python
from dyui import HtmlTemplates
cards = HtmlTemplates("cards")      # ./cards/invoice.html, ...

cards.emit("invoice", {"number": 42, "total": "$1,200"}, title="Invoice", accent="emerald")
```

The bundled UI renders it instantly. That's the whole *“one Python file + HTML templates → dynamic UI”* path.

---

## 🃏 Built-in cards

| component | props | | component | props |
|---|---|---|---|---|
| `text` | `{text}` | | `list` | `{items}` |
| `markdown` | `{text}` | | `keyvalue` | `{data}` |
| `table` | `{columns, rows}` | | `json` | any |
| `stat` | `{label, value, unit?, delta?}` | | `alert` | `{text, level?, title?}` |
| `progress` | `{value, max?, label?}` | | `image` | `{src, alt?, caption?}` |
| `html` | `{html}` *(sanitized, fully custom)* | | | |

---

## 🛠️ CLI

`pip install dyui` installs the `dyui` command:

| Command | What it does |
|---|---|
| `dyui claude init agent.py` | Hand your agent file to **Claude Code** — it reads your graph, proposes a card plan, **asks you to confirm**, then builds + wires the cards. |
| `dyui gemini init agent.py` | Same, via the **Gemini CLI**. |
| `dyui codex init agent.py` | Same, via the **Codex CLI**. |
| `dyui serve [target]` | Run the served dynamic UI (auto-discovers `app`/`graph`). |
| `dyui export <name>` | Eject the whole UI as an editable **Vite + React** project. |

---

## 🔭 How it works

```mermaid
flowchart LR
    A["🧠 LangGraph agent<br/>(any LLM / any node)"] -- "emit() · ui_tool · Card" --> B(["📡 LangGraph<br/>custom stream"])
    B --> C["⚡ dyui.server<br/>(SSE endpoint)"]
    C --> D["✨ Built-in animated UI<br/>(zero frontend code)"]
    C --> E["⚛️ @dyui/react app<br/>(dyui export)"]
    style A fill:#1d2128,stroke:#f5b544,color:#eef1f5
    style B fill:#1d2128,stroke:#a78bfa,color:#eef1f5
    style C fill:#1d2128,stroke:#5eead4,color:#eef1f5
    style D fill:#1d2128,stroke:#ff8a6b,color:#eef1f5
    style E fill:#1d2128,stroke:#ff8a6b,color:#eef1f5
```

Each card is **one event**: a `component` key (which card), `props` (the data), a lifecycle `status`, and an optional `id` to update it in place. The Python `UIEvent` model and the TypeScript `DyUIEvent` type are identical, so the wire format never drifts.

```mermaid
stateDiagram-v2
    direction LR
    [*] --> pending: emit(status="pending")
    pending --> active: card.progress()
    active --> done: card.done()
    pending --> done
    active --> error: exception
    done --> [*]
    error --> [*]
```

---

## ⚛️ Prefer React?

```tsx
import { useDyUIAgent, DyUISurface, createRegistry } from "@dyui/react";
import "@dyui/react/styles.css";

function App() {
  const registry = createRegistry({ my_card: MyCard });  // custom + built-ins
  const { cards, tokens, status, run, dismiss } = useDyUIAgent({ url: "/dyui/stream" });
  return (
    <>
      <button onClick={() => run("hello")}>Ask</button>
      <DyUISurface cards={cards} registry={registry} onDismiss={dismiss} />
    </>
  );
}
```

---

## 🗂️ Repository layout

```
dyui/
├─ python/        # the `dyui` pip package
│  ├─ dyui/       #   emit · server · cli · scaffold · html templates + the served UI
│  ├─ examples/   #   runnable agents (search demo, HTML-templates demo)
│  └─ tests/      #   pytest suite
└─ react/         # the `@dyui/react` npm package (hook · surface · card registry)
```

---

## 🧪 Development

```bash
# Python
cd python && python -m venv .venv && . .venv/Scripts/activate    # Windows
pip install -e ".[dev]" && pytest

# React
cd react && npm install && npm run build && npm test
```

---

<div align="center">

**MIT Licensed** · Built with ❤️ for the LangGraph community

<sub>If DyUI makes your agents prettier, consider giving it a ⭐</sub>

</div>
