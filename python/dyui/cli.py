"""The ``dyui`` command-line interface.

Commands: ``run``, ``new``, ``demo``, ``catalog``, ``claude|gemini|codex init``, ``version``.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Any, Optional

from .__version__ import __version__

TARGET_ENV = "DYUI_APP_TARGET"
DISCOVER = ("app.py", "main.py", "bot.py")


# ------------------------------------------------------------------ loading
def _discover(target: Optional[str]) -> str:
    if target:
        return target
    for name in DISCOVER:
        if Path(name).is_file():
            return name
    raise SystemExit("dyui: no app found — pass a file (dyui run app.py) or create app.py")


def split_target(target: str) -> tuple[str, Any]:
    r"""Split ``path_or_module[:attr]``, keeping Windows drive letters (``C:\proj\app.py:app``) intact."""
    has_drive = len(target) > 1 and target[1] == ":" and target[0].isalpha()
    if target.count(":") > (1 if has_drive else 0):
        spec, attr = target.rsplit(":", 1)
        return spec, attr or None
    return target, None


def load_target(target: str) -> Any:
    """Load ``file.py`` / ``file.py:attr`` / ``module:attr`` and return the app object."""
    spec_target, attr = split_target(target)
    if spec_target.endswith(".py") or Path(spec_target).is_file():
        path = Path(spec_target).resolve()
        if not path.is_file():
            raise SystemExit(f"dyui: {spec_target} not found")
        sys.path.insert(0, str(path.parent))
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        sys.modules[path.stem] = module
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    else:
        sys.path.insert(0, os.getcwd())
        module = importlib.import_module(spec_target)
    for name in ([attr] if attr else ["app", "application", "bot"]):
        if name and hasattr(module, name):
            return getattr(module, name)
    raise SystemExit(f"dyui: {target} has no `app` — create one with `app = dyui.App(...)`")


def _factory() -> Any:
    """uvicorn factory used by ``dyui run`` (reads the target from the environment)."""
    return load_target(os.environ[TARGET_ENV])


def _can_encode(text: str, stream: Any = None) -> bool:
    """Whether ``stream`` (default stdout) can print ``text`` without replacement."""
    enc = getattr(stream or sys.stdout, "encoding", None) or "ascii"
    try:
        text.encode(enc)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


def _safe_console() -> None:
    """Never crash on a console that can't encode a character (e.g. Windows cp1252).

    Unencodable characters print as ``?`` instead of raising ``UnicodeEncodeError``.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            if (getattr(stream, "errors", "strict") or "strict") == "strict":
                reconfigure(errors="replace")
        except (ValueError, OSError):  # pragma: no cover - detached / closed streams
            pass


_GLYPHS = "◉·"  # the banner's mark and separator


def _banner(title: str, url: str) -> None:
    dim, ind, bold, reset = "\033[2m", "\033[38;5;105m", "\033[1m", "\033[0m"
    if not sys.stdout.isatty():
        dim = ind = bold = reset = ""
    mark, sep = (_GLYPHS[0], _GLYPHS[1]) if _can_encode(_GLYPHS) else ("*", "-")
    print(f"\n  {ind}{mark}{reset}  {bold}{title}{reset} {dim}{sep} DyUI {__version__}{reset}\n")
    print(f"     {dim}Local{reset}   {ind}{url}{reset}")
    print(f"     {dim}Stop{reset}    Ctrl+C\n")


def _serve(target: str, host: str, port: int, reload: bool, open_browser: bool, title: str = "DyUI") -> None:
    import uvicorn

    url = f"http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{port}"
    _banner(title, url)
    if open_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    os.environ[TARGET_ENV] = target
    spec_target, _attr = split_target(target)
    if reload and spec_target.endswith(".py"):
        app_dir = str(Path(spec_target).resolve().parent)
        uvicorn.run("dyui.cli:_factory", factory=True, host=host, port=port, reload=True,
                    reload_dirs=[app_dir], log_level="warning", server_header=False)
    else:
        uvicorn.run(load_target(target), host=host, port=port, log_level="warning", server_header=False)


# ------------------------------------------------------------------ commands
def cmd_run(args: argparse.Namespace) -> int:
    target = _discover(args.target)
    title = "DyUI"
    try:
        obj = load_target(target)
        title = getattr(obj, "title", title)
    except SystemExit:
        raise
    _serve(target, args.host, args.port, not args.no_reload, args.open, title)
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    _serve("dyui.demo:app", args.host, args.port, False, args.open, "DyUI demo")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    src = Path(__file__).parent / "templates" / args.template
    if not src.is_dir():
        print(f"dyui: unknown template {args.template!r}", file=sys.stderr)
        return 2
    dest = Path(args.dir)
    if dest.exists() and any(dest.iterdir()):
        print(f"dyui: {dest} is not empty", file=sys.stderr)
        return 2
    title = dest.name.replace("-", " ").replace("_", " ").title() or "My Bot"
    for path in src.rglob("*"):
        if "__pycache__" in path.parts:
            continue
        out = dest / path.relative_to(src)
        if path.is_dir():
            out.mkdir(parents=True, exist_ok=True)
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            text = path.read_text(encoding="utf-8")
            out.write_text(text.replace("{{title}}", title).replace("{{name}}", dest.name), encoding="utf-8")
        except UnicodeDecodeError:
            shutil.copyfile(path, out)
    print(f"Created {dest}/ from the {args.template} template.\n\n  cd {dest}\n  dyui run\n")
    return 0


def cmd_catalog(args: argparse.Namespace) -> int:
    obj = load_target(_discover(args.target))
    cat = getattr(obj, "catalog", None)
    if cat is None:
        print("dyui: target is not a dyui.App", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"names": cat.names, "schemas": cat.json_schema()}, indent=2))
    else:
        print(cat.prompt(mode=args.mode))
        print(f"\n— {len(cat.names)} components · ≈{cat.token_estimate(mode=args.mode)} tokens ({args.mode} mode)")
    return 0


AGENT_BRIEF = """# DyUI — design custom components for this app

You are helping a developer give their DyUI chatbot a custom component library.
DyUI (https://pypi.org/project/dyui/) renders UI components that the LLM emits inline.

1. Read `{app}` and understand what the bot is for.
2. Propose 3–6 custom components that would make its answers better (name, fields, when the
   LLM should use it, which built-ins it renders to). **Ask the developer to confirm.**
3. Implement the confirmed ones in `{app}`:

```python
from dyui import ui
import dyui

@app.component
class Flight(dyui.Component):
    \"\"\"A bookable flight option. Use when listing specific flights.\"\"\"   # the LLM reads this
    airline: str
    depart: str
    price: float

    def render(self):                       # return built-in components
        return ui.Card(self.airline, ui.Stat("Price", f"${{self.price:.0f}}"),
                       actions=[ui.Button("Book", action="book_flight", data=self.model_dump())])

@app.on_action("book_flight")               # handle buttons/forms in Python
async def book(action, chat):
    yield ui.Callout("Booked!", level="success")
```

Built-ins you can compose: markdown, callout, code, quote, sources, badges, divider, table, stat,
stats, keyvalue, chart, progress, timeline, json, image, gallery, video, audio, file, link_preview,
buttons, quick_replies, choice, form, confirm, rating, card, grid, tabs, accordion, carousel, list,
step, reasoning, plan. Registered components are added to the system prompt automatically
(`dyui catalog {app}` prints it). Keep descriptions short and say *when* to use each component.
"""


def cmd_agent_init(args: argparse.Namespace) -> int:
    target = _discover(args.target)
    out = Path(".dyui") / "INIT_PROMPT.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(AGENT_BRIEF.format(app=target), encoding="utf-8")
    print(f"Wrote {out}")
    if os.environ.get("DYUI_NO_LAUNCH"):
        return 0
    exe = shutil.which(args.agent)
    if exe is None:
        print(f"dyui: `{args.agent}` CLI not found on PATH — open {out} in your coding agent instead.", file=sys.stderr)
        return 2
    instruction = f"Read {out.resolve()} and follow it exactly."
    argv = [exe, "-i", instruction] if args.agent == "gemini" else [exe, instruction]
    return subprocess.call(argv)


def cmd_version(_: argparse.Namespace) -> int:
    print(f"dyui {__version__}")
    return 0


# ------------------------------------------------------------------ parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dyui", description="DyUI — chatbots that answer in interfaces.")
    sub = p.add_subparsers(dest="command")

    def serve_opts(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--host", default="127.0.0.1")
        sp.add_argument("--port", type=int, default=8000)
        sp.add_argument("--open", action="store_true", help="open the browser")

    r = sub.add_parser("run", help="serve your app with hot reload")
    r.add_argument("target", nargs="?", help="app.py, app.py:attr or module:attr")
    r.add_argument("--no-reload", action="store_true")
    serve_opts(r)
    r.set_defaults(func=cmd_run)

    d = sub.add_parser("demo", help="a guided tour — no API key needed")
    serve_opts(d)
    d.set_defaults(func=cmd_demo)

    n = sub.add_parser("new", help="scaffold a project")
    n.add_argument("dir")
    n.add_argument("--template", default="basic", choices=["basic", "openai", "anthropic", "langgraph"])
    n.set_defaults(func=cmd_new)

    c = sub.add_parser("catalog", help="print the generated UI prompt")
    c.add_argument("target", nargs="?")
    c.add_argument("--json", action="store_true")
    c.add_argument("--mode", choices=["fence", "tools"], default="fence")
    c.set_defaults(func=cmd_catalog)

    for agent in ("claude", "gemini", "codex"):
        a = sub.add_parser(agent, help=f"design custom components with the {agent} CLI")
        a.add_argument("action", choices=["init"])
        a.add_argument("target", nargs="?")
        a.set_defaults(func=cmd_agent_init, agent=agent)

    v = sub.add_parser("version", help="print the version")
    v.set_defaults(func=cmd_version)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    _safe_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return int(args.func(args) or 0)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
