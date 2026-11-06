---
title: CLI
description: Every dyui command and option.
sidebar:
  order: 1
---

`pip install dyui` installs the `dyui` command.

## `dyui run`

```bash
dyui run [target] [--host 127.0.0.1] [--port 8000] [--open] [--no-reload]
```

Serves your app and reloads it when files in the app's directory change.

| | |
|---|---|
| `target` | `app.py`, `app.py:attr` or `module:attr`. If omitted, DyUI looks for `app.py`, `main.py` or `bot.py` in the current directory. Without `:attr`, it uses the variable `app`, `application` or `bot`. |
| `--host`, `--port` | Bind address (default `127.0.0.1:8000`). Use `--host 0.0.0.0` to reach the app from other devices. |
| `--open` | Open the browser once the server is up |
| `--no-reload` | Disable auto-reload |

## `dyui demo`

```bash
dyui demo [--host 127.0.0.1] [--port 8000] [--open]
```

A guided tour bot that shows components, custom components, actions, steps and approvals with a simulated model. No API key needed.

## `dyui new`

```bash
dyui new <dir> [--template basic|openai|anthropic|langgraph]
```

Scaffolds a project: `app.py`, `README.md`, `requirements.txt`, plus `.env.example` for the model templates. The target directory must be empty or missing.

## `dyui catalog`

```bash
dyui catalog [target] [--mode fence|tools] [--json]
```

Prints the exact UI section DyUI adds to the system prompt for your app, followed by the component count and a token estimate. `--mode tools` prints the structured-mode variant. `--json` prints the component names and their strict JSON schemas.

## `dyui claude init` · `dyui gemini init` · `dyui codex init`

```bash
dyui claude init [target]
```

Writes `.dyui/INIT_PROMPT.md`, a brief for designing custom components for your app, then launches that agent's CLI with it. The agent proposes components, asks you to confirm, and implements them. Set `DYUI_NO_LAUNCH=1` to only write the brief.

## `dyui version`

Prints the installed version.
