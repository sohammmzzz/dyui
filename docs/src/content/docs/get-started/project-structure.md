---
title: Project structure
description: What a DyUI project contains and where DyUI keeps its data.
sidebar:
  order: 4
---

A DyUI project can be a single file. `dyui new my-bot` creates this:

```text
my-bot/
├── app.py              your App, handlers and components
├── README.md
└── requirements.txt    dyui (plus the SDK extra for the template)
```

The `nvidia`, `openai`, `anthropic` and `langgraph` templates also include an `.env.example`.

## Where the app object lives

`dyui run` loads the target file and looks for a variable named `app`, `application` or `bot`. To pick another one, name it explicitly:

```bash
dyui run app.py              # app.py → app
dyui run bots/support.py:bot # a file and an attribute
dyui run mypackage.main:app  # an importable module
```

`app` is a standard ASGI application, so `uvicorn app:app` serves it too.

## Data directory

DyUI keeps runtime data in `./.dyui/`, relative to the working directory. Change the location with `App(data_dir=...)`.

| Path | Contents |
|---|---|
| `.dyui/dyui.db` | SQLite database: conversations, messages, upload metadata |
| `.dyui/uploads/` | Uploaded files |
| `.dyui/secret` | Key that signs the password cookie when `password=` is set and `DYUI_SECRET` isn't |

`dyui agent` writes the DyUI skill for your coding agent outside `.dyui/`, in that agent's own skills folder (for example `.claude/skills/dyui/`); see [Build with a coding agent](../coding-agents/).

Add `.dyui/` to your `.gitignore`. In production, put it on a persistent volume; see [Production server](../../deploy/production/).

## Growing beyond one file

DyUI has no required layout. Larger apps usually split into modules, with the `App` created once and imported elsewhere:

```text
app.py             app = dyui.App(...); imports the modules below
components.py      @app.component classes
actions.py         @app.on_action handlers
cards/             HTML templates for dyui.html_template(...)
```

Decorators register on the `app` instance, so the modules only need to be imported once.
