"""The ``dyui`` command-line interface.

Commands
--------
* ``dyui claude init <file.py>`` / ``dyui gemini init <file.py>`` /
  ``dyui codex init <file.py>`` -- hand your LangGraph agent file to a coding
  agent (Claude Code / Gemini CLI / Codex CLI) together with a full brief on how
  to use DyUI, so it designs + builds custom cards for your specific agent,
  confirms the plan with you, and wires them into the served UI.
* ``dyui serve [target]`` -- run the agent's served dynamic-UI in one command
  (uvicorn under the hood). ``target`` is a ``file.py`` or ``module:attr``;
  auto-discovered when omitted.
* ``dyui export <name>`` -- scaffold the whole dynamic UI as an editable React
  project (``dyui-react``) in ``./<name>``.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Any, Optional

from .__version__ import __version__

# --------------------------------------------------------------------------- #
# The brief handed to coding agents on `dyui <agent> init`.
# --------------------------------------------------------------------------- #
AGENT_BRIEF = r'''# DyUI integration brief (for a coding agent)

You are helping a developer add a **dynamic UI** to their existing LangGraph
agent using the **DyUI** Python package (already `pip install`ed). Your job:
read their agent code, design a set of UI **cards** tailored to what the agent
does, get the developer's confirmation, then implement and wire it up.

## How DyUI works (the essentials)

DyUI streams "cards" from inside a LangGraph graph to a frontend over LangGraph's
native `custom` stream channel. You emit cards from any node or tool:

```python
from dyui import emit, ui_tool, Card, HtmlTemplates

# 1) Imperative emit (call anywhere inside a node/tool):
emit("table", {"columns": ["city","temp"], "rows": [["Berlin",21]]},
     title="Weather", icon="cloud", accent="cyan")

# 2) Decorator: auto pending -> done/error around a tool:
@ui_tool("stat", title="Sum", icon="calculator", accent="emerald")
def add(a: float, b: float) -> dict:
    return {"label": f"{a}+{b}", "value": a + b}   # dict becomes the card props

# 3) Context manager: long work, one card updated in place:
with Card("progress", title="Indexing") as card:
    for i in range(1, 4):
        card.progress({"value": i, "max": 3})
    card.done({"value": 3, "max": 3, "label": "Done"})
```

`emit(component, props, *, id=None, status="done", surface="default", title=None,
icon=None, accent=None, ttl_ms=None)`. Re-emit with the same `id` to update a card
(lifecycle: `pending` -> `active` -> `done`/`error`).

## Built-in card components (no frontend code needed)

| component  | props |
|------------|-------|
| `text`     | `{text}` |
| `markdown` | `{text}` (supports #/##/### , **bold**, `code`, - lists) |
| `table`    | `{columns: string[], rows: any[][]}` |
| `stat`     | `{label, value, unit?, delta?}` |
| `progress` | `{value, max?, label?}` |
| `list`     | `{items: (string | {title, subtitle?, badge?})[]}` |
| `keyvalue` | `{data: {k: v}}` |
| `json`     | any |
| `alert`    | `{text, level?: info|success|warning|error, title?}` |
| `image`    | `{src, alt?, caption?}` |
| `html`     | `{html}` (raw, sanitized) -- for fully custom markup |

`icon` hints (served UI): `search, calculator, cloud, check, list, sparkles, plus`.
`accent` is any CSS color or one of `cyan, violet, emerald, amber, rose`.

## Custom cards via HTML templates (preferred for bespoke visuals)

Put `.html` files in a `./cards/` folder; `{{ key }}` is HTML-escaped, `{{{ key }}}`
is raw. Then:

```python
cards = HtmlTemplates("cards")
cards.emit("invoice", {"number": 42, "total": "$1,200"}, title="Invoice", accent="emerald")
```

Reserved kwargs (`id,status,surface,title,icon,accent,ttl_ms`) are card config —
put template values with those names inside the dict.

## Serving (already handled by the package)

```python
from dyui.server import create_dyui_app
app = create_dyui_app(graph, input_adapter=lambda b: {"messages": [("user", b["input"])]})
```
The developer runs `dyui serve` (or `uvicorn module:app`) and opens the browser —
the package ships an animated chat UI that renders all the cards above.

## YOUR TASK (do these in order)

1. Read the developer's agent file (shown below / at the given path). Identify the
   nodes, tools, and the data each produces.
2. **Propose** a concrete set of cards: for each meaningful tool/node output, pick
   a built-in component or design an HTML template, with titles/icons/accents.
   Present this plan as a short table.
3. **ASK the developer to confirm** (or adjust) the plan before writing code. Do
   not skip this confirmation step.
4. On approval, implement:
   - Add `emit(...)` / `@ui_tool(...)` calls (or `HtmlTemplates`) at the right
     points so cards stream as the agent runs.
   - Create any `./cards/*.html` templates you designed.
   - Ensure the file exposes `app = create_dyui_app(graph, ...)` with an
     `input_adapter` matching the agent's expected input.
5. Tell the developer to run `dyui serve <file>` and open the browser.

Keep changes minimal and faithful to the existing agent logic — you are adding a
UI layer, not rewriting the agent.
'''


# --------------------------------------------------------------------------- #
# A runnable starter agent written by `dyui new`.
# --------------------------------------------------------------------------- #
STARTER_AGENT = '''"""A starter LangGraph agent wired to DyUI.

Run it with no frontend code:

    dyui serve agent.py            # or: uvicorn agent:app --reload

Then open the browser. Swap the node bodies for your real LLM calls / tools and
`emit(...)` cards wherever you want them to show up. See every built-in card with
`dyui demo`, or read AGENTS.md (run `dyui init`) for the full catalogue.
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from dyui import Card, emit


class State(TypedDict, total=False):
    query: str


def respond(state: State) -> State:
    q = state.get("query", "there")

    emit(
        "markdown",
        {"text": f"### Hello, **{q}**\\nThis card was streamed straight from Python."},
        title="Greeting", icon="sparkles", accent="violet",
    )
    emit(
        "stat",
        {"label": "Frontend code you had to write", "value": 0, "unit": "lines"},
        title="Result", icon="check", accent="emerald",
    )
    return {}


def build_graph():
    g = StateGraph(State)
    g.add_node("respond", respond)
    g.add_edge(START, "respond")
    g.add_edge("respond", END)
    return g.compile()


graph = build_graph()

# create_dyui_app auto-detects how to feed the browser's text into your graph, so
# this works with no input_adapter. Pass input_adapter=... for a custom shape.
from dyui.server import create_dyui_app  # noqa: E402

app = create_dyui_app(graph, ui_title="My DyUI Agent")
'''


# --------------------------------------------------------------------------- #
# Persistent project memory written by `dyui init` so *any* coding agent
# (Claude Code, Codex, Gemini CLI, Cursor, ...) understands DyUI.
# --------------------------------------------------------------------------- #
_GUIDE_START = "<!-- dyui:start -->"
_GUIDE_END = "<!-- dyui:end -->"

DYUI_GUIDE = _GUIDE_START + r"""
## Using DyUI in this project

This project uses **DyUI** to stream live UI **cards** from a LangGraph agent to a
frontend, over LangGraph's native `custom` stream channel. Emit a card from any
node or tool with one call — no frontend code required.

```python
from dyui import emit, ui_tool, Card, HtmlTemplates

# 1) Imperative — call anywhere inside a node/tool:
emit("table", {"columns": ["city", "temp"], "rows": [["Berlin", 21]]},
     title="Weather", icon="cloud", accent="cyan")

# 2) Decorator — auto pending -> done/error around a tool:
@ui_tool("stat", title="Sum", icon="calculator", accent="emerald")
def add(a: float, b: float) -> dict:
    return {"label": f"{a}+{b}", "value": a + b}   # dict becomes the card props

# 3) Context manager — long work, one card updated in place:
with Card("progress", title="Indexing") as card:
    for i in range(1, 4):
        card.progress({"value": i, "max": 3})
    card.done({"value": 3, "max": 3, "label": "Done"})
```

`emit(component, props, *, id=None, status="done", surface="default", title=None,
icon=None, accent=None, ttl_ms=None)`. Re-emit with the same `id` to update a card
(lifecycle: `pending` -> `active` -> `done`/`error`).

### Built-in card components (no frontend code needed)

| component  | props |
|------------|-------|
| `text`     | `{text}` |
| `markdown` | `{text}` (#/##/### , **bold**, `code`, - lists, links) |
| `table`    | `{columns: string[], rows: any[][]}` |
| `stat`     | `{label, value, unit?, delta?}` |
| `progress` | `{value, max?, label?}` |
| `list`     | `{items: (string | {title, subtitle?, badge?})[]}` |
| `keyvalue` | `{data: {k: v}}` |
| `json`     | any |
| `alert`    | `{text, level?: info|success|warning|error, title?}` |
| `image`    | `{src, alt?, caption?}` |
| `html`     | `{html}` (custom markup, sanitized) |

`icon` hints (served UI): `search, calculator, cloud, check, list, sparkles, plus`.
`accent` is any CSS color or one of `cyan, violet, emerald, amber, rose`.

### Custom cards via HTML templates

Put `.html` files in `./cards/`; `{{ key }}` is HTML-escaped, `{{{ key }}}` is raw
(only pass pre-trusted HTML to raw placeholders). Then:

```python
cards = HtmlTemplates("cards")
cards.emit("invoice", {"number": 42, "total": "$1,200"}, title="Invoice")
```

### Serving (zero frontend)

```python
from dyui.server import create_dyui_app
app = create_dyui_app(graph)        # auto-detects the graph's input shape
```

Run `dyui serve` (auto-discovers `app`/`graph`) or `uvicorn module:app`, then open
the browser — the package ships an animated chat UI that renders every card above.
`dyui demo` runs a no-API-key showcase of all card types.

### When adding a UI to an agent here

1. Identify each meaningful node/tool output.
2. Pick a built-in component or design an HTML template (title/icon/accent).
3. Add `emit(...)` / `@ui_tool(...)` / `Card(...)` at the right points.
4. Expose `app = create_dyui_app(graph)` and tell the user to run `dyui serve`.

Keep changes minimal and faithful to the existing agent logic — you are adding a
UI layer, not rewriting the agent.
""" + _GUIDE_END


def _c(text: str, code: str = "1") -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


# --------------------------------------------------------------------------- #
# `dyui <agent> init <file>`
# --------------------------------------------------------------------------- #
AGENT_LAUNCHERS = {
    # agent -> function(prompt_path) -> argv list
    "claude": lambda p: ["claude", f"Read {p} and follow it exactly."],
    "gemini": lambda p: ["gemini", "-i", f"Read {p} and follow it exactly."],
    "codex": lambda p: ["codex", f"Read {p} and follow it exactly."],
}
AGENT_INSTALL_HINT = {
    "claude": "npm install -g @anthropic-ai/claude-code   (or see claude.com/claude-code)",
    "gemini": "npm install -g @google/gemini-cli",
    "codex": "npm install -g @openai/codex",
}


def cmd_agent_init(agent: str, file: str) -> int:
    src = Path(file)
    if not src.exists():
        print(_c(f"error: file not found: {file}", "31"))
        return 1

    code = src.read_text(encoding="utf-8")
    prompt = (
        AGENT_BRIEF
        + f"\n\n## The developer's LangGraph agent: `{src.name}`\n\n"
        + f"```python\n{code}\n```\n"
    )
    out_dir = Path(".dyui")
    out_dir.mkdir(exist_ok=True)
    prompt_path = (out_dir / "INIT_PROMPT.md").resolve()
    prompt_path.write_text(prompt, encoding="utf-8")

    print(_c(f"\n  DyUI :: {agent} init", "1"))
    print(f"  Brief + your agent written to {_c(str(prompt_path), '36')}")

    launcher = AGENT_LAUNCHERS[agent]
    argv = launcher(str(prompt_path))
    exe = shutil.which(argv[0])

    manual = f'{argv[0]} "Read {prompt_path} and follow it."'
    if exe is None:
        print(_c(f"\n  '{argv[0]}' CLI not found.", "33"))
        print(f"  Install it:  {AGENT_INSTALL_HINT[agent]}")
        print(f"  Then run:    {manual}\n")
        return 2

    # Let users (or tests) skip auto-launch and just get the command to run.
    if os.environ.get("DYUI_NO_LAUNCH"):
        print(f"  Run this to start the session:\n    {manual}\n")
        return 0

    argv[0] = exe
    print(f"  Launching {_c(argv[0], '36')} - it will design cards and confirm with you.\n")
    try:
        # On Windows the resolved CLI is a .CMD shim and must go through the shell.
        if os.name == "nt":
            return subprocess.run(subprocess.list2cmdline(argv), shell=True).returncode
        return subprocess.run(argv).returncode
    except (FileNotFoundError, OSError) as exc:
        print(_c(f"\n  could not launch {agent}: {exc}", "33"))
        print(f"  Run it manually:  {manual}\n")
        return 2
    except KeyboardInterrupt:
        return 130


# --------------------------------------------------------------------------- #
# `dyui serve`
# --------------------------------------------------------------------------- #
def _load_module_from_path(path: Path) -> Any:
    # SECURITY: this imports and executes ``path`` (and, via the sys.path insert
    # below, lets it import sibling modules from its own directory). ``dyui
    # serve`` is a developer tool meant to run *your own* trusted agent file from
    # your project; only point it at code you trust, just as with ``python
    # file.py``. Auto-discovery (``_discover_target``) only looks in the current
    # working directory for the same reason.
    # Make sibling imports (e.g. `from calculator import ...`) resolve.
    sys.path.insert(0, str(path.resolve().parent))
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    # Register before exec so typing.get_type_hints (used by LangGraph on
    # TypedDict state schemas) can resolve the module's own annotations.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _discover_target() -> Optional[str]:
    for name in ("app.py", "agent.py", "main.py", "graph.py"):
        if Path(name).exists():
            return name
    return None


def _resolve_app(target: Optional[str], *, serve_ui: bool, title: str) -> Any:
    """Return a FastAPI app from a target ``file.py`` or ``module:attr``."""
    from .server import create_dyui_app

    if target is None:
        target = _discover_target()
        if target is None:
            raise SystemExit(
                "error: no target given and none of app.py/agent.py/main.py found.\n"
                "       usage: dyui serve <file.py | module:attr>"
            )
        print(_c(f"  discovered {target}", "36"))

    attr = None
    if ":" in target and not target.endswith(".py"):
        mod_name, attr = target.split(":", 1)
        module = __import__(mod_name, fromlist=["*"])
    else:
        path = Path(target)
        if not path.exists():
            raise SystemExit(f"error: file not found: {target}")
        module = _load_module_from_path(path)

    # Prefer an explicit attr, else `app`, else wrap a `graph`.
    obj = getattr(module, attr) if attr else getattr(module, "app", None)
    if obj is not None:
        return obj
    graph = getattr(module, "graph", None)
    if graph is not None:
        print(_c("  no `app` found — wrapping `graph` with create_dyui_app()", "36"))
        return create_dyui_app(graph, serve_ui=serve_ui, ui_title=title)
    raise SystemExit(
        f"error: {target} exposes neither `app` nor `graph`.\n"
        "       Define `app = create_dyui_app(graph)` or expose a compiled `graph`."
    )


def _open_browser_later(url: str, delay: float = 1.2) -> None:
    """Open ``url`` in the default browser shortly after the server starts."""

    def _open() -> None:
        try:
            webbrowser.open(url)
        except Exception:  # pragma: no cover - headless / no browser
            pass

    threading.Timer(delay, _open).start()


def cmd_serve(
    target: Optional[str],
    host: str,
    port: int,
    no_ui: bool,
    title: str,
    open_browser: bool = False,
    reload: bool = False,
) -> int:
    try:
        import uvicorn
    except ImportError:
        print(_c("error: uvicorn not installed. Run: pip install 'dyui[server]'", "31"))
        return 1

    url = f"http://{host}:{port}"
    print(_c(f"\n  DyUI serving on {url}", "1")
          + (f"   (UI at /)" if not no_ui else "  (UI disabled)"))
    print(f"  stream endpoint: POST {url}/dyui/stream\n")
    if open_browser and not no_ui:
        _open_browser_later(url)

    # uvicorn's reload needs an import string, which we only have for
    # ``module:attr`` targets. Fall back gracefully for file/auto targets.
    if reload and target and ":" in target and not target.endswith(".py"):
        uvicorn.run(target, host=host, port=port, reload=True)
        return 0
    if reload:
        print(_c("  note: --reload needs a 'module:attr' target; serving without reload.", "33"))

    app = _resolve_app(target, serve_ui=not no_ui, title=title)
    uvicorn.run(app, host=host, port=port)
    return 0


# --------------------------------------------------------------------------- #
# `dyui demo` -- instant, no-API-key showcase of every card type
# --------------------------------------------------------------------------- #
def cmd_demo(host: str, port: int, open_browser: bool = True) -> int:
    try:
        import uvicorn
    except ImportError:
        print(_c("error: uvicorn not installed. Run: pip install 'dyui[server]'", "31"))
        return 1

    from .demo import build_app

    url = f"http://{host}:{port}"
    print(_c(f"\n  DyUI demo on {url}", "1") + "   (no API key needed)")
    print("  Showcasing every built-in card type, streamed from one Python file.\n")
    if open_browser:
        _open_browser_later(url)
    uvicorn.run(build_app(), host=host, port=port)
    return 0


# --------------------------------------------------------------------------- #
# `dyui new` -- scaffold a runnable starter agent
# --------------------------------------------------------------------------- #
def cmd_new(file: str, force: bool) -> int:
    dest = Path(file)
    if dest.exists() and not force:
        print(_c(f"error: {file} already exists (use --force to overwrite)", "31"))
        return 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(STARTER_AGENT, encoding="utf-8")
    print(_c(f"\n  Created starter agent: {dest}", "1"))
    print(
        "\n  Next:\n"
        f"    dyui serve {file}      # then open the browser\n"
        "    dyui demo              # see every built-in card type\n"
        "    dyui init              # teach your coding agent about DyUI\n"
    )
    return 0


# --------------------------------------------------------------------------- #
# `dyui init` -- write a DyUI guide into AGENTS.md / CLAUDE.md / GEMINI.md so any
# coding agent (Claude Code, Codex, Gemini CLI, Cursor, ...) understands DyUI.
# --------------------------------------------------------------------------- #
_AGENT_MEMORY_FILES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md")


def _upsert_guide(path: Path, guide: str) -> str:
    """Insert or replace the DyUI section in ``path``; return 'created'/'updated'."""
    header = "# Project guide\n"
    if not path.exists():
        path.write_text(header + "\n" + guide + "\n", encoding="utf-8")
        return "created"
    text = path.read_text(encoding="utf-8")
    if _GUIDE_START in text and _GUIDE_END in text:
        before = text[: text.index(_GUIDE_START)]
        after = text[text.index(_GUIDE_END) + len(_GUIDE_END):]
        path.write_text(before + guide + after, encoding="utf-8")
        return "updated"
    sep = "" if text.endswith("\n") else "\n"
    path.write_text(text + sep + "\n" + guide + "\n", encoding="utf-8")
    return "updated"


def cmd_init(file: Optional[str]) -> int:
    guide = DYUI_GUIDE
    if file:
        src = Path(file)
        if not src.exists():
            print(_c(f"error: file not found: {file}", "31"))
            return 1
        code = src.read_text(encoding="utf-8")
        guide = guide.replace(
            _GUIDE_END,
            f"\n### This project's agent (`{src.name}`)\n\n"
            f"```python\n{code}\n```\n" + _GUIDE_END,
        )

    print(_c("\n  DyUI :: init", "1"))
    for name in _AGENT_MEMORY_FILES:
        action = _upsert_guide(Path(name), guide)
        print(f"    {action:>7}  {name}")
    print(
        "\n  Any coding agent that reads these files now knows how to add DyUI\n"
        "  cards to your agent. Try: \"add a dynamic UI to my agent with DyUI\".\n"
    )
    return 0


# --------------------------------------------------------------------------- #
# `dyui export <name>`
# --------------------------------------------------------------------------- #
def cmd_export(name: str, stream_url: str, force: bool, local: Optional[str]) -> int:
    from .scaffold import write_react_project

    dest = Path(name)
    if dest.exists() and any(dest.iterdir()) and not force:
        print(_c(f"error: ./{name} exists and is not empty (use --force to overwrite)", "31"))
        return 1
    files = write_react_project(
        dest, project_name=name, stream_url=stream_url, local_react=local
    )
    print(_c(f"\n  Exported React project to ./{name}/", "1"))
    for f in files:
        print(f"    {f}")
    print(
        "\n  Next:\n"
        f"    cd {name}\n"
        "    npm install\n"
        "    npm run dev\n\n"
        "  Edit src/cards/ to add custom card components; they render the same\n"
        "  events your `dyui serve` UI shows.\n"
    )
    return 0


# --------------------------------------------------------------------------- #
# arg parsing
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dyui", description="Dynamic UI for LangGraph agents.")
    p.add_argument("--version", action="version", version=f"dyui {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    dp = sub.add_parser("demo", help="run an instant, no-API-key showcase of every card")
    dp.add_argument("--host", default="127.0.0.1")
    dp.add_argument("--port", type=int, default=8000)
    dp.add_argument("--no-open", action="store_true", help="don't auto-open the browser")

    np = sub.add_parser("new", help="scaffold a runnable starter agent .py")
    np.add_argument("file", nargs="?", default="agent.py", help="output file (default: agent.py)")
    np.add_argument("--force", action="store_true", help="overwrite if it exists")

    ip = sub.add_parser(
        "init", help="write a DyUI guide into AGENTS.md/CLAUDE.md/GEMINI.md for any coding agent"
    )
    ip.add_argument("file", nargs="?", help="optionally embed your agent .py in the guide")

    for agent in ("claude", "gemini", "codex"):
        ap = sub.add_parser(agent, help=f"launch {agent} to design + build cards for your agent")
        ap.add_argument("action", choices=["init"], help="init: analyse a file and build cards")
        ap.add_argument("file", help="your LangGraph agent .py file")

    sp = sub.add_parser("serve", help="run the agent's served dynamic UI")
    sp.add_argument("target", nargs="?", help="file.py or module:attr (auto-discovered if omitted)")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8000)
    sp.add_argument("--no-ui", action="store_true", help="serve only the stream endpoint")
    sp.add_argument("--title", default="DyUI")
    sp.add_argument("--open", action="store_true", help="auto-open the browser")
    sp.add_argument("--reload", action="store_true", help="auto-reload (needs a module:attr target)")

    ep = sub.add_parser("export", help="export the dynamic UI as a React project")
    ep.add_argument("name", help="project directory name")
    ep.add_argument("--stream-url", default="http://localhost:8000/dyui/stream")
    ep.add_argument("--local", help="use a local dyui-react build path instead of the npm package")
    ep.add_argument("--force", action="store_true")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd in ("claude", "gemini", "codex"):
        return cmd_agent_init(args.cmd, args.file)
    if args.cmd == "demo":
        return cmd_demo(args.host, args.port, open_browser=not args.no_open)
    if args.cmd == "new":
        return cmd_new(args.file, args.force)
    if args.cmd == "init":
        return cmd_init(args.file)
    if args.cmd == "serve":
        return cmd_serve(
            args.target, args.host, args.port, args.no_ui, args.title,
            open_browser=args.open, reload=args.reload,
        )
    if args.cmd == "export":
        return cmd_export(args.name, args.stream_url, args.force, args.local)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
