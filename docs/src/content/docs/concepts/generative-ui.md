---
title: Generative UI
description: The dyui fence format, the generated catalog prompt, streaming validation and structured (tools) mode.
sidebar:
  order: 3
---

The model renders UI by writing **data**, never markup. DyUI tells the model which components exist, parses what it writes as it streams, and validates every component against the same pydantic model that produced its description.

## The fence format

The model writes ordinary Markdown. A component goes in a fenced block tagged `dyui`, with **one JSON object per line**:

````md
Here are two options for this weekend.
```dyui
{"ui":"flight","airline":"TAP","depart":"Fri 18:05","price":189}
{"ui":"quick_replies","options":["Check hotels too","Book the cheaper one"]}
```
Want me to hold a seat?
````

- `"ui"` names the component; the other keys are its props.
- Layout components take `"children": [ ...component objects... ]`.
- A whole JSON array on one line also works. A block tagged `json` is accepted when its objects have a `"ui"` key.
- The fence lines are never shown to the user.

## The catalog prompt

`app.catalog` is the set of components this app's model may use: the enabled built-ins plus your registered components. `app.catalog.prompt()` renders it. For an app with `components=["table", "stat", "quick_replies"]` and a custom `Flight`, the prompt is exactly:

````text
## UI components
You can show UI components inside your reply. To do so, write a fenced code block
tagged `dyui` containing one JSON object per line: {"ui": "<name>", ...props}.
Put prose outside the block. Use plain text when a component isn't clearly better.

Components:
table(columns: string[], rows: (string|number)[][], caption?: string) — Tabular data; use for 3+ rows.
stat(label: string, value: string|number, unit?: string, delta?: string, trend?: "up"|"down"|"flat", help?: string) — One headline number.
quick_replies(options: string[]) — Suggested follow-up replies the user can tap.
flight(airline: string, depart: string, price: number) — A bookable flight option. Use when listing specific flights.

Example:
```dyui
{"ui":"stat","label":"Revenue","value":"$48.2k","delta":"+12%","trend":"up"}
```
````

The prompt is rebuilt from the live registry on every access. Its order is deterministic (built-ins in catalog order, then your components in registration order), so provider prompt caching keeps hitting. The full built-in catalog is about 1,250 tokens. DyUI logs a warning when a catalog's estimate passes 1,800.

### Using the prompt

`dyui.llm.stream(..., components=catalog)` appends the section to your system prompt. If your prompt contains a `{dyui_components}` placeholder, the section is placed there instead. With any other SDK, add `app.catalog.prompt()` to the system prompt yourself; see [Bring your own SDK](../../integrations/bring-your-own-sdk/).

```bash
dyui catalog app.py                # print the exact prompt and a token estimate
dyui catalog app.py --mode tools   # the structured-mode variant
dyui catalog app.py --json         # names + JSON schemas
```

### Choosing components

```python
app = dyui.App(components="all")                         # default: every built-in
app = dyui.App(components=["table", "chart", ui.Stat])   # names or classes
app = dyui.App(components=None)                          # only your own components

app.catalog.only("flight", "confirm", "quick_replies")    # a subset, e.g. at checkout
app.catalog.without("chart")
dyui.catalog("data", "interactive")                        # built-ins by group
app.catalog.names, app.catalog.token_estimate()
```

The catalog only controls what the model is **told** about. Model output (fences, and `{"ui": ...}` dicts) is validated against every model-usable built-in plus your components, so a `table` still renders even if it isn't in the catalog. The developer-only `html` and `invalid` are never accepted from model output. Component instances your code yields (`ui.Html(...)` included) always render.

## Streaming and validation

The server-side `FenceParser` is an incremental state machine that handles chunk boundaries anywhere, even in the middle of a JSON string. For the line being written:

1. Once `"ui"` is known, an empty component appears as a soft skeleton.
2. As props arrive, a tolerant partial-JSON parser closes open strings, arrays and objects. The component updates in place, at most every ~60 ms of input.
3. At the end of the line, the JSON is parsed and validated.

Validation is **lax**: values are coerced where it's safe (`"189"` → `189`), unknown props are dropped, and common aliases are accepted (`"type": "dropdown"` → `select`). An unknown component, invalid props or an unterminated block become an `invalid` component, a quiet, collapsible "Couldn't display this component" chip. The text around it is never lost.

The `invalid` chip only covers what the model wrote. If your own code builds an invalid component, pydantic raises in your handler as usual.

## Structured mode (`ui_mode="tools"`)

For OpenAI and Anthropic you can opt into **schema-guaranteed** components:

```python
async for part in dyui.llm.stream("openai/gpt-5", chat.history, components=app.catalog, ui_mode="tools"):
    yield part
```

DyUI registers one strict tool per component, `render_<name>`, whose parameters are the component's JSON schema. The provider's constrained decoding then guarantees valid props. DyUI runs the tool loop itself, up to `max_tool_rounds=8` requests: each completed call is rendered where it happened, the tool result `"rendered"` is sent back, and generation continues. Prose and components still interleave. The catalog prompt in this mode tells the model to call `render_*` tools instead of writing fences.

Use fence mode (the default) for every other provider and for local models.

## What the model sees afterwards

`chat.history` gives the model back what it rendered. Each component in an assistant message is re-serialized as a one-line `dyui` block containing its props, so a follow-up like "book the cheaper one" has the data it refers to. Action messages appear as `[action:name] {...}`.
