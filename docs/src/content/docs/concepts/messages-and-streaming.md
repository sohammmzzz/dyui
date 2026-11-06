---
title: Messages & streaming
description: Handler shapes, what you can yield, chat.history, chat.send, and how stop, regenerate and edit work.
sidebar:
  order: 2
---

## Handlers

`@app.on_message` is the only required handler. It receives the user's `Message` and the conversation's `Chat`.

```python
@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    yield "Hello!"
```

Any of these shapes works for `on_message`, `on_action` and `on_chat_start`:

| Shape | Example |
|---|---|
| async generator | `async def reply(msg, chat): yield "hi"` |
| sync generator | `def reply(msg, chat): yield "hi"` (runs in a worker thread) |
| coroutine | `async def reply(msg, chat): return ui.Stat("Users", 42)` |
| plain function | `def reply(msg, chat): return ["Done.", ui.Callout("Saved", level="success")]` |

## What you can yield

| Value | Becomes |
|---|---|
| `str` | Markdown text, appended to the reply. It is **parsed for ```` ```dyui ```` fences**, so raw model output works. |
| a component (`ui.Table(...)`, your `@app.component` classes) | A rendered component part |
| `dyui.Reasoning("...")` | A delta for the collapsible reasoning block |
| `{"ui": "stat", ...}` | Validated exactly like model output |
| a list or tuple | Each item in order |
| `None` | Ignored |

Anything else is shown as text, and a warning is logged.

## Updating a component in place

Give a component a stable `id`. Yielding another component with the same id replaces it where it stands, which suits progress bars and live numbers:

```python
for done in range(0, 101, 20):
    yield ui.Progress(done, label="Indexing", id="indexing")
    await asyncio.sleep(0.4)
```

## The message

`Message` has `id`, `text`, `files` (a list of `File` with `name`, `type`, `size`, `path` and `url`) and `action`. `action` is set when the turn came from an unhandled action; `text` then holds an LLM-friendly description of it.

```python
@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    for f in msg.files:
        yield f"Got **{f.name}** ({f.size} bytes) — saved at `{f.path}`."
```

## The chat

| Member | What it is |
|---|---|
| `chat.history` | `[{"role": "user" \| "assistant", "content": str}]`, ready for any chat API. Components the assistant showed are serialized as compact `dyui` blocks, so the model remembers what it rendered. Steps and reasoning are left out. |
| `chat.messages` | The stored messages with all their parts (protocol `Message` dicts). |
| `chat.session` | A dict persisted with the conversation. See [Sessions](../sessions-and-persistence/). |
| `chat.thread_id`, `chat.user_id` | The conversation and the anonymous browser identity. |
| `await chat.send(*items)` | Appends items to the current reply, the same as yielding them. |
| `chat.step(title, type=)` | A live step. See [Steps & reasoning](../steps-and-reasoning/). |
| `await chat.ask(component)` | Renders an interactive component and waits for the user's answer. |
| `await chat.set_title(title)` | Sets the conversation title and turns off auto-titling. |

### Greeting on a new conversation

`on_chat_start` runs when a thread is created. Use `chat.send` there to post a first assistant message:

```python
@app.on_chat_start
async def start(chat: dyui.Chat):
    await chat.send("Hi! I can plan trips and book flights.", ui.QuickReplies("Plan a weekend", "Find flights"))
```

## Stop, regenerate and edit

- **Stop:** the browser aborts the stream. The server cancels your handler task (`asyncio.CancelledError` is raised inside it) and stores the partial reply as `cancelled`.
- **Regenerate:** the last assistant reply is deleted and `on_message` runs again for the last user message.
- **Edit:** the user's last message is replaced, everything after it is deleted, and `on_message` runs again.
- **Errors:** if your handler raises, the user sees an inline error with **Retry**. The traceback is logged on the server and never sent to the browser.

During long silences the server sends an SSE comment every 15 seconds, so proxies don't time out the stream.
