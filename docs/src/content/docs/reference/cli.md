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
dyui new <dir> [--template basic|nvidia|openai|anthropic|langgraph]
```

Scaffolds a project: `app.py`, `README.md`, `requirements.txt`, plus `.env.example` for the model templates. The target directory must be empty or missing.

## `dyui catalog`

```bash
dyui catalog [target] [--mode fence|tools] [--json]
```

Prints the exact UI section DyUI adds to the system prompt for your app, followed by the component count and a token estimate. `--mode tools` prints the structured-mode variant. `--json` prints the component names and their strict JSON schemas.

## `dyui agent`

```bash
dyui agent [name] [task ...] [--no-launch] [--list] [--print]
```

Installs the DyUI skill into the current project and starts a coding-agent CLI with it. The agent can build a new app, convert an existing project, integrate DyUI into a service or design custom components. See [Build with a coding agent](../../get-started/coding-agents/).

| | |
|---|---|
| `name` | `claude`, `gemini`, `codex`, `qwen`, `antigravity`, `kimi`, `opencode`, `cursor`, or any other CLI on your `PATH` that takes a prompt argument. If omitted, DyUI uses the agent CLI it finds, and asks when there are several. |
| `task` | What the agent should do. If omitted, it inspects the project and proposes a plan. |
| `--no-launch` | Only write the skill file. `DYUI_NO_LAUNCH=1` does the same. |
| `--list` | List the supported agents and whether each is installed |
| `--print` | Print the skill to stdout |

## `dyui claude` · `dyui gemini` · `dyui codex` · `dyui qwen` · `dyui antigravity` · `dyui kimi` · `dyui opencode` · `dyui cursor`

```bash
dyui claude [task ...] [--no-launch]
dyui claude init [target]
```

Shortcuts for `dyui agent <name>`. With `init`, the agent designs custom components for `target` (default: the app DyUI discovers): it proposes components, asks you to confirm, and implements them.

## `dyui version`

Prints the installed version.
