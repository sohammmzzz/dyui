---
title: Build with a coding agent
description: Open Claude Code, Gemini CLI, Codex, Qwen Code, Antigravity or another coding agent with the DyUI skill loaded, and let it build or convert your app.
sidebar:
  order: 5
---

`dyui agent` opens your coding agent already briefed on DyUI. It installs a **DyUI skill** into the project and starts the agent's CLI with it, so the agent knows the API, every component, and how to approach the job.

```bash
pip install dyui
cd my-project
dyui agent
```

The agent starts by reading your project, then tells you what it found and what it proposes. Give it a task up front if you already know what you want:

```bash
dyui agent "turn this RAG script into a chat app with sources and a feedback form"
dyui claude "add a booking flow with a confirmation step"
```

## What the agent can do

| You have | Ask for | What it does |
|---|---|---|
| Nothing yet | "Build a support bot for a bike shop" | Scaffolds `app.py`, writes the system prompt and starters, designs custom components, wires buttons and approvals |
| A script, notebook, CLI tool or API | "Convert this into a DyUI app" | Keeps your logic, wraps it in an `on_message` handler, and maps outputs to tables, charts, cards, forms and steps |
| An agent (LangGraph, your own loop) | "Give this agent a chat UI" | Streams it through DyUI, emits components from nodes and tools, shows tool calls as live steps |
| A web service | "Add a chat to this FastAPI app" | Adds DyUI beside it and shares your service's functions with the handler |
| A DyUI app | "Design components for this app" | Proposes components, asks you to confirm, implements them with their actions |

The skill tells the agent to look before it proposes, to keep your existing code working, and to run the app's import, `dyui catalog` and `dyui run` checks before it reports success.

## Pick an agent

With no name, `dyui agent` uses the agent CLI it finds on your `PATH` and asks when there are several. To pick one, name it:

| Command | Agent | Skill is written to |
|---|---|---|
| `dyui claude` | Claude Code | `.claude/skills/dyui/SKILL.md` |
| `dyui gemini` | Gemini CLI | `.gemini/skills/dyui/SKILL.md` |
| `dyui codex` | Codex CLI | `.agents/skills/dyui/SKILL.md` |
| `dyui qwen` | Qwen Code | `.qwen/skills/dyui/SKILL.md` |
| `dyui antigravity` | Antigravity CLI (`agy`) | `.agents/skills/dyui/SKILL.md` |
| `dyui kimi` | Kimi Code | `.agents/skills/dyui/SKILL.md` |
| `dyui opencode` | opencode | `.agents/skills/dyui/SKILL.md` |
| `dyui cursor` | Cursor Agent (`cursor-agent`) | `.agents/skills/dyui/SKILL.md` |

Each of these is the same as `dyui agent <name>`. `dyui agent --list` shows which ones are installed.

Any other CLI that accepts a prompt as its argument works too:

```bash
dyui agent aider "convert this repo"
```

## How the skill is loaded

1. DyUI renders the skill for the version you have installed. It includes the live list of built-in components, so it never goes stale.
2. The skill is written into the project folder that agent reads skills from (the table above). It is a plain Markdown file: read it, edit it, commit it or ignore it.
3. The agent is started with a first message that points at the skill and carries your task.

Because the file stays in the project, later sessions of an agent that discovers project skills pick it up without `dyui agent`. Run the command again after upgrading DyUI to refresh it.

Kimi Code is started without a first message; DyUI prints the line to paste.

## Options

```bash
dyui agent --list          # supported agents and whether each is installed
dyui agent --print         # print the skill, e.g. to paste into another tool
dyui claude --no-launch    # only write the skill file
```

Setting `DYUI_NO_LAUNCH=1` has the same effect as `--no-launch`.

## Design components for an existing app

```bash
dyui claude init app.py
```

`init` starts the agent on one specific job: read the app, propose three to six custom components, ask you to confirm, and implement them. See [Custom components](../../concepts/custom-components/).
