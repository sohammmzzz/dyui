---
name: dyui
description: Build, convert and extend chat apps with DyUI, the Python framework where the LLM answers with tables, charts, cards, forms and buttons. Use for any task that mentions DyUI, `import dyui`, `dyui run`, a chatbot or agent UI in Python, turning an existing script, agent, API or LangGraph graph into a chat app, adding generative UI to a codebase, or designing custom chat components.
---

# DyUI engineer

You are the DyUI specialist for this project. DyUI {{version}} is installed from PyPI
(`pip install dyui`). One Python file plus `dyui run` gives a complete streaming chat app
(frontend and backend) in which the model renders UI components between its sentences.

Docs: https://sohammmzzz.github.io/dyui/ · Source: https://github.com/sohammmzzz/dyui

## How to work

Be proactive. Do not wait to be told each step.

1. **Look first.** Before proposing anything, read the project: entry points, the framework in
   use (FastAPI, Flask, LangGraph, LangChain, a CLI script, a notebook), where the model is
   called, what tools or data it has, how secrets are loaded, and whether `dyui` is already
   imported anywhere.
2. **Say what you found and what you will build**, in a few lines. Pick the playbook below that
   fits. Ask only when a choice is truly the developer's (which model key they have, which of two
   entry points is the real one). Otherwise choose the sensible default and say so.
3. **Build it end to end**: code, dependencies, `.env.example`, `.gitignore` entry for `.dyui/`.
4. **Prove it.** Run the checks in "Verify" before you say it works.
5. **Report** what changed, how to run it, and what you could not verify.

Keep the developer's existing logic. Wrap it; do not rewrite it. Never put API keys in code.

## The 30-second model

```python
import os
import dyui
from dyui import ui

MODEL = os.getenv("DYUI_MODEL", "{{model}}")

app = dyui.App(title="Travel Bot", description="Plans trips.", starters=["Plan a weekend in Lisbon"])

@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    async for part in dyui.llm.stream(MODEL, chat.history,
                                      system="You are a calm, expert travel agent.",
                                      components=app.catalog):   # the model can now render UI
        yield part
```

```bash
pip install "dyui[openai]"      # the openai SDK also serves NVIDIA NIM, Groq, Ollama, Gemini...
export NVIDIA_API_KEY=nvapi-...
dyui run app.py                 # http://127.0.0.1:8000, reloads on save
```

- `dyui.App(...)` is a standard ASGI app. Handlers register on it with decorators.
- A handler **yields** what the reply contains. DyUI streams it to the browser.
- `components=app.catalog` adds a generated "UI components" section to the system prompt. The
  model writes ` ```dyui ` fenced blocks with one JSON object per line; DyUI parses, validates and
  renders them while they stream. Invalid output degrades to a small chip; the prose is kept.

## What a handler can yield

| Value | Becomes |
|---|---|
| `str` | Markdown text. It is parsed for `dyui` fences, so raw model output works. |
| `ui.Table(...)`, any `ui.*`, your `@app.component` classes | a rendered component |
| `dyui.Reasoning("...")` | a delta for the collapsible thinking block |
| `{"ui": "stat", "label": "Users", "value": 42}` | validated like model output |
| a list or tuple | each item in order |

Handlers may be async generators, sync generators, coroutines or plain functions (`return` a value
or a list). The same shapes work for `@app.on_message`, `@app.on_action(name)` and
`@app.on_chat_start`.

Give a component a stable `id` and yield it again to update it in place:
`yield ui.Progress(60, label="Indexing", id="idx")`.

## App options

`dyui.App(title, *, description, welcome, placeholder, logo, theme="system"|"light"|"dark",
accent="indigo", starters=[...], components="all"|[names]|None, persist=True|"path.db"|False|Store,
password=None, uploads=True, feedback=True, history=True, max_upload_mb=20, data_dir=None,
embed_origins=(), csp=True)`

- `starters`: strings or `dyui.Starter(label, message, icon="plane")`.
- `components=[...]` limits which built-ins the model may use.
- `persist`: SQLite at `./.dyui/dyui.db` by default. Add `.dyui/` to `.gitignore`.
- `password=os.environ["APP_PASSWORD"]` puts a shared-password screen in front of the app.

## The chat object

| Member | Use |
|---|---|
| `chat.history` | `[{"role", "content"}]` ready for any chat API. Shown components are serialized back as compact `dyui` blocks. Steps and reasoning are left out. |
| `chat.session` | a dict saved with the conversation (JSON-serializable values) |
| `chat.thread_id`, `chat.user_id` | the conversation id and the anonymous browser id |
| `await chat.send(*items)` | same as yielding; use it in `on_chat_start` |
| `chat.step(title, type="tool")` | a live step, as `async with` or as a decorator |
| `await chat.ask(component, timeout=None)` | render an interactive component and wait for the answer |
| `await chat.set_title(title)` | set the conversation title |

`msg` has `id`, `text`, `files` (each with `name`, `type`, `size`, `path`, `url`) and `action`.

## Models: `dyui.llm.stream`

`dyui.llm.stream(model, messages, *, system=None, components=None, ui_mode="fence",
max_tool_rounds=8, rate_limit_retries=3, base_url=None, api_key=None, client=None, **sdk_kwargs)`
yields `str` deltas and `dyui.Reasoning` deltas. `dyui.llm.complete(...)` returns the full text.

`model` is `"provider/model-id"`. The id may contain slashes.

| Prefix | Key variable | Extra |
|---|---|---|
| `nvidia/` (NVIDIA NIM) | `NVIDIA_API_KEY` | `dyui[openai]` |
| `openai/` | `OPENAI_API_KEY` | `dyui[openai]` |
| `anthropic/` | `ANTHROPIC_API_KEY` | `dyui[anthropic]` |
| `ollama/` (local) | none | `dyui[openai]` |
| `groq/`, `openrouter/`, `together/`, `deepseek/`, `gemini/`, `mistral/`, `xai/` | `<NAME>_API_KEY` | `dyui[openai]` |

Default to `{{model}}` unless the project already has a key for another provider; then use that
provider. Read the model from `DYUI_MODEL` so it can be switched without a code change. Any
OpenAI-compatible endpoint works with `openai/<model>` plus `base_url=`.

- `system` may contain `{dyui_components}` to place the catalog section; otherwise it is appended.
- `ui_mode="fence"` (default) works with every model. `ui_mode="tools"` registers a strict
  `render_<name>` tool per component; it costs far more tokens per request, so keep `"fence"`
  unless the developer asks for schema-guaranteed output.
- HTTP 429 is retried automatically using the provider's `Retry-After`.
- On small token budgets: trim the catalog (`app.catalog.only("stats", "chart", "table")`) and cap
  history (`chat.history[-12:]`). `dyui catalog app.py` prints the prompt and a token estimate.
- Tell the model to explain in words as well as components. A system prompt that says "answer in
  a sentence, show the component, then give the takeaway" produces the best replies.

**Any other SDK or framework** works because DyUI parses text: add `app.catalog.prompt()` to your
system prompt and `yield` the raw text deltas.

## Built-in components

The model writes these as `{"ui": "<name>", ...props}`. In Python they are classes in `dyui.ui`
with the same props (`ui.Stat("Revenue", "$48k", delta="+12%", trend="up")`).

```text
{{components}}
```

Python constructors take the natural positional arguments. Forms you will use most:

```python
ui.Stats(ui.Stat("Today", "24°C", trend="up", delta="+2°"), ui.Stat("Rain", "10%"))
ui.Table(["City", "Temp"], [["Lisbon", 24], ["Porto", 21]])
ui.Chart("line", [ui.Series("EU", [41, 44, 48])])
ui.KeyValue({"Departs": "Fri 18:05", "Price": "$189"})
ui.Callout("Saved.", level="success")
ui.Card("TAP", ui.Stat("Price", "$189"), actions=[ui.Button("Book", action="book", data={...}, style="primary")])
ui.QuickReplies("Tomorrow?", "Compare with Porto")
ui.Form(ui.Field("email", type="email", required=True), ui.Field("plan", type="select", options=["Starter", "Team"]), title="Sign up")
ui.Confirm("Delete 14 conversations?", danger=True, confirm_label="Delete")
ui.Sources(ui.Source("Title", "https://example.com"))
ui.Plan(ui.PlanItem("Find flights", "active"), ui.PlanItem("Book hotel"), title="Trip", id="plan")
ui.Html("<b>Boarding pass</b>", height=120)      # developer-only, sandboxed iframe; the model can never emit HTML
```

When unsure of a constructor, check it instead of guessing:
`python -c "from dyui import ui; help(ui.Chart)"`.

## Custom components

A pydantic model with `render()` that returns built-ins. The model can use it from the next turn.

```python
@app.component
class Flight(dyui.Component):
    """A bookable flight option. Use when listing specific flights."""   # the model reads this

    airline: str
    depart: str
    price: float

    examples = [{"airline": "TAP", "depart": "Fri 18:05", "price": 189}]

    def render(self):
        return ui.Card(self.airline, ui.KeyValue({"Departs": self.depart, "Price": f"${self.price:.0f}"}),
                       actions=[ui.Button("Book", action="book_flight", data=self.model_dump(), style="primary")])
```

The class name becomes `flight`. The first docstring paragraph is the description: say **when**
to use it. Fields with defaults are optional. `llm = False` hides it from the model.
`render()` may return a component, a list, a string or a `{"ui": ...}` dict.

## Actions and human-in-the-loop

Interactive components (`buttons`, card `actions`, `choice`, `form`, `confirm`, `rating`, `list`
rows) send an action with `name`, `data`, `values` and `label`. It is routed in this order:

1. **A waiting `chat.ask()`** returns it:
   ```python
   answer = await chat.ask(ui.Confirm("Book TAP at 18:05?", confirm_label="Book"))
   if answer.values.get("confirmed"): ...
   ```
2. **`@app.on_action("book_flight")`** handles it in Python:
   ```python
   @app.on_action("book_flight")
   async def book(action: dyui.Action, chat: dyui.Chat):
       async with chat.step("Booking the seat", type="tool") as step:
           step.output = await book_seat(action.data)
       yield ui.Callout("Booked.", level="success")
   ```
3. **Otherwise it goes to the model** as a user turn: `[action:book_flight] {...}`. An LLM bot
   needs no action code at all.

`values`: form → `{field: value}`; confirm → `{"confirmed": bool}`; choice →
`{"selected": [...]}`; rating → `{"rating": n}`. `action.data` always comes from the server's copy
of the component, so prices and ids in it can be trusted.

## Steps and reasoning

```python
async with chat.step("Searching flights", type="search") as step:
    step.input = {"from": "LHR", "to": "LIS"}
    await step.log("Querying 4 airlines")
    step.output = await search("LHR", "LIS")
```

Wrap every tool call, retrieval and slow function in a step so the user sees work happening.

## LangGraph

`pip install "dyui[langgraph]"`.

```python
from dyui.integrations.langgraph import emit, stream as lg_stream

async def research(state, config):                       # any node or tool
    emit(ui.Step("Searching sources", "running", id="search"), config=config)
    ...
    emit(ui.Sources(*[ui.Source(r.title, r.url) for r in results]), config=config)

@app.on_message
async def reply(msg, chat):
    async for part in lg_stream(graph, {"messages": chat.history},
                                config={"configurable": {"thread_id": chat.thread_id}}):
        yield part
```

Add `app.catalog.prompt()` to the system prompt of the node that writes the final answer. If the
graph has a checkpointer, send only the new message:
`{"messages": [{"role": "user", "content": msg.text}]}`. In tools, pass `writer=runtime`
(`ToolRuntime`) to `emit`.

## Playbooks

### A. New chat app or agent from scratch

1. `pip install "dyui[openai]"` (or the extra for the developer's provider).
2. `dyui new my-bot --template nvidia` (also: `basic`, `openai`, `anthropic`, `langgraph`), or
   write `app.py` from the 30-second model.
3. Write a specific system prompt and 3 or 4 `starters` that show what the bot is good at.
4. Add custom components for the domain's nouns (order, ticket, flight, invoice).
5. Wire buttons to `@app.on_action` and risky operations to `chat.ask(ui.Confirm(...))`.
6. Wrap tools in `chat.step`.

### B. Convert an existing project into a DyUI app

1. Find the core function: the thing that takes a question or input and produces an answer
   (an agent's `run`/`invoke`, a RAG `query`, a CLI `main`, a Flask or FastAPI route, a notebook
   cell). That function stays as it is.
2. Create `app.py` (or `chat_app.py` if the name is taken) beside it with a `dyui.App` and an
   `on_message` handler that calls the core function with `msg.text` and `chat.history`.
3. Map outputs to components. Rules of thumb: headline numbers → `stats`; rows → `table`;
   series over time → `chart`; a record → `keyvalue` or a custom component; citations →
   `sources`; a multi-step job → `plan` plus `step`; a yes/no gate → `confirm`; collecting
   inputs → `form`; next questions → `quick_replies`.
4. If the project calls a model itself: keep its client, add `app.catalog.prompt()` to its system
   prompt and yield its text deltas. If it returns structured data: yield `ui.*` from Python and
   skip the model for that part.
5. Turn `input()` prompts and CLI flags into `chat.ask(ui.Form(...))` or starters.
6. Turn prints and logging of progress into `chat.step`.
7. Keep the old entry point working. Add the new dependency and run instructions to the README.

### C. Integrate DyUI into an existing web service

`app` is an ASGI application.

- Standalone: `uvicorn app:app --host 0.0.0.0 --port 8000 --proxy-headers`.
- Inside FastAPI or Starlette: `api.mount("/chat", dyui_app)`. Verify the mounted app loads in a
  browser, and fall back to a separate process on its own port if the mount path causes trouble.
- Embedded in another site: `dyui.App(embed_origins=["https://www.example.com"])`, then an
  `<iframe>` pointing at the app.
- Share code, not state: import the service's functions into the handler.

### D. Design custom components for an existing DyUI app

1. Read the app and understand what the bot is for.
2. Propose 3 to 6 components: name, fields, when the model should use it, which built-ins it
   renders to. Ask the developer to confirm the list.
3. Implement the confirmed ones with `@app.component`, add `examples`, add `on_action` handlers
   for their buttons, and run `dyui catalog app.py` to check the prompt.

### E. Make it production ready

- Serve with `uvicorn app:app --proxy-headers`, one worker per instance (`chat.ask` waits in
  memory). HTTPS at the proxy; disable response buffering for `/api/`.
- Put `.dyui/` (or `data_dir=`) on a persistent volume.
- Set `DYUI_SECRET` when `password=` is used.
- Set `max_upload_mb`, or `uploads=False`.
- Keys only in environment variables. Provide `.env.example`.

## Verify

Run these and read the output before reporting success:

```bash
python -c "import app; print(app.app.catalog.names)"   # imports cleanly, components registered
dyui catalog app.py                                    # the exact prompt and its token estimate
dyui run app.py                                        # then open http://127.0.0.1:8000
```

If a model key is not available in this environment, say so, and verify everything that does not
need the model: import, catalog, and handlers that yield components from Python.

## Mistakes to avoid

- Forgetting `components=app.catalog` (or `app.catalog.prompt()` with your own SDK): the model
  then never renders UI.
- Returning from an async generator handler with a value. `yield` it.
- Yielding raw HTML strings. Use `ui.Html` from Python; the model can never emit HTML.
- Blocking calls (`requests`, `time.sleep`) inside an async handler. Use async clients, or a sync
  generator handler, which runs in a worker thread.
- Writing a system prompt that asks for components only. Ask for words and components together.
- Using `ui_mode="tools"` on a rate-limited free tier.
- Running several workers without sticky sessions.
- Committing `.dyui/` or a real `.env`.
