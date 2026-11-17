"""The ``dyui`` command-line interface.

Commands: ``run``, ``new``, ``demo``, ``catalog``, ``agent`` (and ``claude``, ``gemini``,
``codex``, ``qwen``, ``antigravity``, ``kimi``, ``opencode``, ``cursor``), ``version``.
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
def _run_env(target: str, env_file: Optional[str], enabled: bool) -> int:
    """Load ``.env`` for ``dyui run``: ``--env-file``, else the app's directory, else the CWD.

    Never overrides a variable that is already set, and prints names only, never values.
    Returns a non-zero exit code when an explicit ``--env-file`` is missing.
    """
    from ._env import find_dotenv, load_dotenv, parse_dotenv, read_dotenv

    if not enabled:
        return 0
    if env_file:
        path: Optional[Path] = Path(env_file)
        if not path.is_file():
            print(f"dyui: --env-file {env_file} not found", file=sys.stderr)
            return 2
    else:
        spec_target, _attr = split_target(target)
        dirs = [Path(spec_target).resolve().parent] if spec_target.endswith(".py") else []
        path = find_dotenv([*dirs, Path.cwd()])
        if path is None:
            return 0
    try:
        loaded = load_dotenv(path)
        kept = sorted(set(parse_dotenv(read_dotenv(path))) - set(loaded))
    except (OSError, UnicodeDecodeError) as exc:
        print(f"dyui: could not read {path}: {exc.__class__.__name__}", file=sys.stderr)
        return 2
    try:
        shown = path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        shown = path
    noun = "key" if len(loaded) == 1 else "keys"
    line = f"dyui: loaded {shown} ({len(loaded)} {noun}{': ' + ', '.join(loaded) if loaded else ''})"
    if kept:
        line += f"; already set, kept: {', '.join(kept)}"
    print(line)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    target = _discover(args.target)
    code = _run_env(target, getattr(args, "env_file", None), not getattr(args, "no_env_file", False))
    if code:
        return code
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


def cmd_agent(args: argparse.Namespace) -> int:
    from . import agents

    if getattr(args, "list", False):
        for a in agents.AGENTS.values():
            exe = agents.find_exe(a)
            print(f"  {a.name:<12} {a.label:<16} {'installed' if exe else 'not found'}")
        return 0
    if getattr(args, "print", False):
        print(agents.render_skill())
        return 0
    words = list(args.task or [])
    name = getattr(args, "agent", None)
    if name is None and words and (words[0] in agents.AGENTS or shutil.which(words[0])):
        name = words.pop(0)
    if words and words[0] == "init":  # `dyui claude init [app.py]`: design custom components
        task = agents.INIT_TASK.format(target=_discover(words[1] if len(words) > 1 else None))
    else:
        task = " ".join(words)
    return agents.run(name, task, launch=not getattr(args, "no_launch", False), yes=getattr(args, "yes", False))


def cmd_mcp(args: argparse.Namespace) -> int:
    from . import mcp as dyui_mcp

    if getattr(args, "mcp_command", None) != "install":
        if not dyui_mcp.available():
            print(f"dyui mcp: the MCP server needs the 'mcp' package. Install it with:  {dyui_mcp.INSTALL_HINT}",
                  file=sys.stderr)
            return 2
        from .mcp.server import main as serve

        return serve()

    from .mcp import install as inst

    if args.client:
        client = inst.resolve_client(args.client)
        if client is None:
            print(f"dyui mcp: unknown client {args.client!r}. Known: {', '.join(inst.CLIENTS)}", file=sys.stderr)
            return 2
        clients = [client]
    else:
        clients = inst.detect()
        if not clients:
            print("dyui mcp: no coding agent detected here. Name one: dyui mcp install <client>\n"
                  f"Clients: {', '.join(inst.CLIENTS)}\n\nGeneric stdio entry:\n"
                  + inst.snippet(inst.CLIENTS["other"]))
            return 0
    if args.print:
        for client in clients:
            print(f"# {client.label}" + (f" ({client.path})" if client.path else ""))
            print(inst.snippet(client))
        return 0
    if not dyui_mcp.available():
        print(f"dyui mcp: warning: the 'mcp' package is not installed in this Python ({sys.executable}), so the "
              f"server will not start until you run:  {dyui_mcp.INSTALL_HINT}", file=sys.stderr)
    from .agents import _confirm

    code = 0
    for client in clients:
        result = inst.install(client, confirm=_confirm(args.yes))
        print(result.message)
        if result.snippet:
            print(result.snippet)
        if not result.ok:
            code = 1
    return code


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
    r.add_argument("--env-file", metavar="PATH",
                   help="load environment variables from PATH (default: .env next to the app, then in the CWD)")
    r.add_argument("--no-env-file", action="store_true", help="don't load any .env file")
    serve_opts(r)
    r.set_defaults(func=cmd_run)

    d = sub.add_parser("demo", help="a guided tour — no API key needed")
    serve_opts(d)
    d.set_defaults(func=cmd_demo)

    n = sub.add_parser("new", help="scaffold a project")
    n.add_argument("dir")
    n.add_argument("--template", default="basic", choices=["basic", "nvidia", "openai", "anthropic", "langgraph"])
    n.set_defaults(func=cmd_new)

    c = sub.add_parser("catalog", help="print the generated UI prompt")
    c.add_argument("target", nargs="?")
    c.add_argument("--json", action="store_true")
    c.add_argument("--mode", choices=["fence", "tools"], default="fence")
    c.set_defaults(func=cmd_catalog)

    from .agents import AGENTS

    def agent_opts(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("task", nargs="*", help="what the agent should do (optional)")
        sp.add_argument("--no-launch", action="store_true", help="only write the config and skill files")
        sp.add_argument("-y", "--yes", action="store_true", help="allow user-level config changes (Codex) without asking")

    g = sub.add_parser("agent", help="open a coding agent briefed on DyUI (MCP server + skill)",
                       description="Register the DyUI MCP server for a coding agent, write a DyUI skill into this "
                                   "project and start the agent's CLI. Without a name, DyUI uses the agent CLI it "
                                   "finds on PATH. Without the 'mcp' extra, the full offline skill is used.")
    agent_opts(g)
    g.add_argument("--list", action="store_true", help="list supported agents and whether they are installed")
    g.add_argument("--print", action="store_true", help="print the full offline skill to stdout")
    g.set_defaults(func=cmd_agent, agent=None)
    for a in AGENTS.values():
        sp = sub.add_parser(a.name, help=f"open {a.label} briefed on DyUI")
        agent_opts(sp)
        sp.set_defaults(func=cmd_agent, agent=a.name)

    m = sub.add_parser("mcp", help="run the DyUI MCP server (stdio) for coding agents",
                       description="Without a subcommand: serve DyUI's docs, component schemas and validators "
                                   "to a coding agent over stdio (same as `python -m dyui.mcp`). Needs "
                                   "`pip install \"dyui[mcp]\"`.")
    m.set_defaults(func=cmd_mcp, mcp_command=None)
    msub = m.add_subparsers(dest="mcp_command")
    mi = msub.add_parser("install", help="register the server in a coding agent's MCP config",
                         description="Add the dyui server to an agent's MCP config, keeping every other server. "
                                     "Clients: claude, cursor, vscode, gemini, qwen, opencode, codex (user-level), "
                                     "windsurf, claude-desktop, zed, other (print the snippet). Without a client: "
                                     "every project-level client detected here.")
    mi.add_argument("client", nargs="?", help="which client (default: detect)")
    mi.add_argument("--print", action="store_true", help="print the config snippet instead of writing it")
    mi.add_argument("-y", "--yes", action="store_true", help="allow user-level config changes (Codex) without asking")
    mi.set_defaults(func=cmd_mcp)

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
