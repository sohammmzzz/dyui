---
title: Sessions & persistence
description: Per-conversation state, where conversations are stored, and how to plug in your own database.
sidebar:
  order: 7
---

## Per-conversation state

`chat.session` is a dict stored with the conversation. Read and write it freely. It's saved when the handler finishes, so values must be JSON-serializable.

```python
@app.on_message
async def reply(msg, chat):
    count = chat.session.get("turns", 0) + 1
    chat.session["turns"] = count
    yield f"This is message {count} in this conversation."
```

## Identity

DyUI has no user accounts. Each browser gets an anonymous `dyui_uid` cookie (random, `HttpOnly`, `SameSite=Lax`), and conversations, files and actions are scoped to it. `chat.user_id` exposes it. To restrict who can open the app, see [Authentication](../auth/).

## Storage

| `App(persist=...)` | Store |
|---|---|
| `True` (default) | SQLite at `<data_dir>/dyui.db` (`./.dyui/dyui.db`) |
| `"path/to/chats.db"` | SQLite at that path |
| `False` | In memory; everything is lost on restart |
| a `Store` instance | Yours |

Uploaded files are written to `<data_dir>/uploads/`, and their metadata goes in the store.

## Your own store

Implement the `dyui.store.Store` protocol and pass an instance as `persist=`. Every method is a coroutine, and records are plain dicts:

```python
from dyui.store import Store

class PostgresStore:  # implements dyui.store.Store
    async def create_thread(self, user_id, *, title="New chat"): ...
    async def get_thread(self, thread_id): ...
    async def list_threads(self, user_id, *, limit=200): ...
    async def update_thread(self, thread_id, **fields): ...   # title, title_locked, session, updated_at
    async def delete_thread(self, thread_id): ...
    async def get_messages(self, thread_id): ...
    async def get_message(self, thread_id, message_id): ...
    async def put_message(self, thread_id, message): ...      # insert or replace by id, keep position
    async def delete_messages_after(self, thread_id, message_id, *, inclusive=False): ...
    async def put_file(self, record): ...
    async def get_file(self, file_id): ...
    async def close(self): ...

app = dyui.App(persist=PostgresStore())
```

The record shapes are documented on [`dyui.store.Store`](../../reference/api/store/). `dyui.store.MemoryStore` is a short, complete reference implementation.
