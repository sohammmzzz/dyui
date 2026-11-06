---
title: Custom components
description: Define components in pure Python. The model learns them on the next turn.
sidebar:
  order: 4
---

A custom component is a pydantic model with a `render()` method that returns built-in components. Register it with `@app.component`. It joins `app.catalog`, its line is added to the system prompt, and the model can use it from the next turn on.

```python
import dyui
from dyui import ui

@app.component
class Flight(dyui.Component):
    """A bookable flight option. Use when listing specific flights."""

    airline: str
    depart: str
    arrive: str | None = None
    price: float

    examples = [{"airline": "TAP", "depart": "Fri 18:05", "price": 189}]

    def render(self):
        return ui.Card(
            self.airline,
            ui.Stat("Price", f"${self.price:.0f}"),
            actions=[ui.Button("Book", action="book_flight", data=self.model_dump())],
        )
```

The model sees:

```text
flight(airline: string, depart: string, arrive?: string, price: number) — A bookable flight option. Use when listing specific flights.
```

## How it maps

| Python | Prompt / behaviour |
|---|---|
| class name `Flight` | component name `flight` (snake_case). Override with `name = "flight_option"`. |
| first docstring paragraph | the description. Say **when** to use it. Override with `description = "..."`. |
| fields | props; fields with defaults are optional (`?`) |
| `examples = [...]` | validated when the class is defined, so a typo fails at import |
| `render()` | the built-in tree the browser receives |

`render()` may return a component, a list of components (wrapped in a card), a string (rendered as Markdown) or a `{"ui": ...}` dict.

Custom components are **expanded on the server**. The browser only renders built-ins, and the outer node keeps your name in `props.__component__` for debugging.

## Class options

Set these as plain class attributes:

| Option | Effect |
|---|---|
| `name` | The name the model writes (default: snake_case of the class name) |
| `description` | The prompt description (default: first docstring paragraph) |
| `examples` | Example prop dicts, validated at class creation |
| `llm = False` | Never offered to the model; your code can still yield it |
| `positional = ("airline", "depart")` | Props that can be passed positionally: `Flight("TAP", "Fri 18:05", price=189)` |

## Using it from Python

A registered component is an ordinary model, so you can construct and yield it yourself:

```python
yield Flight(airline="TAP", depart="Fri 18:05", price=189)
```

## Developer HTML

When the built-ins aren't enough, render your own HTML in a **sandboxed iframe**: `sandbox="allow-scripts"`, no same-origin access, height sized automatically. The model can never produce HTML; only your code can.

```python
yield ui.Html("<b>Boarding pass</b> · Gate B32", height=120)

# from a template file — {{ key }} is HTML-escaped, {{{ key }}} is inserted raw
yield dyui.html_template("cards/boarding_pass.html", passenger="Alex Morgan", gate="B32")
```

`dyui.html_template` only loads files from inside its `root` (the working directory by default) and raises `ValueError` for paths that escape it.

## Let a coding agent design them

```bash
dyui claude init app.py     # or: dyui gemini init / dyui codex init
```

This writes a brief to `.dyui/INIT_PROMPT.md` and launches the agent's CLI. The agent reads your app, proposes 3–6 components, asks you to confirm, and implements them.
