---
title: Build with AI
description: Give Claude Code, Cursor, VS Code Copilot, Gemini CLI, Codex and other coding agents the DyUI MCP server, so they read the docs, look up components and validate their own work for the exact version you have installed.
sidebar:
  order: 5
---

DyUI ships an **MCP server** for coding agents. It runs locally against the DyUI you have installed, so everything the agent sees matches your version exactly, and it works offline:

- the full docs and every example app, searchable;
- every component's props, types, defaults, JSON schema, working Python and model examples, and the action each interactive component sends;
- validators the agent runs on its own work: `validate_ui` for component JSON and model replies, `check_app` to import your app and catch common mistakes.

## Set it up

```bash
pip install "dyui[mcp]"
cd my-project
dyui mcp install claude      # or: cursor, vscode, gemini, qwen, opencode, codex, windsurf, claude-desktop, zed
```

`dyui mcp install` adds one entry to the agent's MCP config. It keeps every other server you have, backs the file up to `<file>.bak` before the first change, and does nothing when the entry is already there. The entry runs the Python you installed DyUI into, so the agent always gets the right virtualenv:

```json
{
  "mcpServers": {
    "dyui": { "command": "/path/to/.venv/bin/python", "args": ["-m", "dyui.mcp"] }
  }
}
```

| Client | Command | Config written |
|---|---|---|
| Claude Code | `dyui mcp install claude` | `.mcp.json` |
| Cursor (IDE and `cursor-agent`) | `dyui mcp install cursor` | `.cursor/mcp.json` |
| VS Code / GitHub Copilot | `dyui mcp install vscode` | `.vscode/mcp.json` (`servers`, `type: stdio`) |
| Gemini CLI | `dyui mcp install gemini` | `.gemini/settings.json` |
| Qwen Code | `dyui mcp install qwen` | `.qwen/settings.json` |
| opencode | `dyui mcp install opencode` | `opencode.json` (`mcp`) |
| Codex CLI | `dyui mcp install codex` | `~/.codex/config.toml` (user-level: asks first, or pass `--yes`) |
| Windsurf, Claude Desktop, Zed, others | `dyui mcp install windsurf` ... | prints the snippet and where to paste it |

- With no client name, DyUI configures every project-level client it detects (a `.claude/`, `.cursor/`, `.vscode/`... folder, or the CLI on your `PATH`).
- `--print` shows the snippet without writing anything.
- A config file with comments or other non-JSON content is left untouched; DyUI prints the snippet for you to add.
- Claude Code asks you to approve project MCP servers the first time; VS Code shows a **Start** button in `mcp.json`.

To run the server by hand (for any other MCP client, stdio transport): `dyui mcp` or `python -m dyui.mcp`.

## What the agent gets

| Tool | What it does |
|---|---|
| `dyui_overview` | The mental model, the 30-second app, what handlers yield, providers and API keys, actions, custom components, mistakes to avoid. Agents call it first. |
| `list_docs`, `read_doc(slug)` | Every docs page of your version as Markdown, with example sources inlined |
| `search_docs(query)` | Keyword search over the docs, the example apps and the components |
| `list_components`, `get_component(name)` | Props, JSON schema, Python constructor and examples, what the model writes, the prompt line, actions |
| `list_examples`, `get_example(name)`, `get_template(name)` | The complete cookbook apps and the `dyui new` templates |
| `validate_ui(payload)` | Runs DyUI's real parser and validator on a `{"ui": ...}` object, JSON lines or a whole reply with `dyui` fences |
| `check_app(path)` | Imports the app in a subprocess and reports import errors, handlers, custom components (and whether their examples validate), the catalog and its token cost, plus common mistakes: no `components=` in `dyui.llm.stream`, hard-coded API keys, blocking calls in async handlers, `.dyui/` missing from `.gitignore` |
| `catalog_prompt(path, only)` | The exact "UI components" section the model receives, like `dyui catalog` |

It also exposes the docs, components and examples as resources (`dyui://docs/<slug>`, `dyui://components/<name>`, `dyui://examples/<name>`), and four prompts for clients with a prompt picker: `build_app`, `convert_project`, `design_components` and `production_checklist` (in Claude Code: `/mcp__dyui__build_app`).

API keys never leave your machine through the server: anything shaped like a key is masked in every report.

## Then ask for what you want

| You have | Ask for | What it does |
|---|---|---|
| Nothing yet | "Build a support bot for a bike shop" | Scaffolds `app.py`, writes the system prompt and starters, designs custom components, wires buttons and approvals |
| A script, notebook, CLI tool or API | "Convert this into a DyUI app" | Keeps your logic, wraps it in an `on_message` handler, and maps outputs to tables, charts, cards, forms and steps |
| An agent (LangGraph, your own loop) | "Give this agent a chat UI" | Streams it through DyUI, emits components from nodes and tools, shows tool calls as live steps |
| A web service | "Add a chat to this FastAPI app" | Adds DyUI beside it and shares your service's functions with the handler |
| A DyUI app | "Design components for this app" | Proposes components, asks you to confirm, implements them with their actions |

The agent is told to look at your project before it proposes anything, to keep your existing code working, and to run `check_app` and `validate_ui` before it reports success.

## Start an agent CLI in one command

`dyui agent` does the setup and opens your coding agent with a first message:

```bash
dyui agent                                       # the agent CLI found on your PATH
dyui claude "add a booking flow with a confirmation step"
dyui gemini "turn this RAG script into a chat app with sources"
```

For Claude Code, Gemini CLI, Qwen Code, Cursor Agent, opencode and Codex it registers the MCP server (as above), writes a short skill that points the agent at the tools, and starts the agent with `Use the dyui MCP server (call dyui_overview first).` followed by your task.

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

Each is the same as `dyui agent <name>`; `dyui agent --list` shows which are installed. Any other CLI that takes a prompt as its argument works too: `dyui agent aider "convert this repo"`.

```bash
dyui agent --list          # supported agents and whether each is installed
dyui agent --print         # print the full offline guide, e.g. to paste into another tool
dyui claude --no-launch    # only write the config and skill files
dyui codex --yes           # allow the user-level Codex config change without asking
dyui claude init app.py    # design custom components for an existing app
```

Setting `DYUI_NO_LAUNCH=1` has the same effect as `--no-launch`. Kimi Code is started without a first message; DyUI prints the line to paste.

## Without the MCP extra

If `dyui[mcp]` is not installed, or for agents DyUI cannot configure (Antigravity, Kimi, other CLIs), `dyui agent` falls back to the **full offline skill**: one Markdown file with the API, every component's prompt line and the playbooks, rendered for your installed version. It is written to the same skills folder. Run the command again after upgrading DyUI to refresh it.

## Agents without MCP

The docs site also publishes `llms.txt` (an index of every page) and `llms-full.txt` (every page in one file) for tools that read documentation from a URL instead of an MCP server.
