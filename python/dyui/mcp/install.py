"""Register the DyUI MCP server with a coding agent (``dyui mcp install [client]``).

The entry always runs the interpreter that ran the installer (absolute ``sys.executable``), so
the agent starts the server from the right virtualenv::

    {"command": "<python>", "args": ["-m", "dyui.mcp"]}

Rules: existing config files are merged, never rewritten from scratch; other servers and keys
are kept as they are; the original is copied to ``<file>.bak`` before the first change;
re-running is a no-op; a file that is not plain JSON (comments, syntax errors) is left alone and
the snippet is printed instead. Codex's config is TOML in the user's home: the ``[mcp_servers.dyui]``
block is appended only when absent (no TOML dependency), and only after confirmation (or ``--yes``).
Nothing here needs the ``mcp`` package.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

__all__ = ["Client", "CLIENTS", "AGENT_CLIENTS", "Result", "server_entry", "snippet", "install", "resolve_client",
           "codex_config_path", "claude_desktop_config_path", "detect"]

SERVER_KEY = "dyui"


@dataclass(frozen=True)
class Client:
    name: str
    label: str
    kind: str                 # "json" (project file), "toml" (codex, user file), "print" (show the snippet)
    path: Optional[str] = None  # project-relative config path for "json"
    key: str = "mcpServers"   # top-level key holding the servers
    style: str = "std"        # "std" {command,args} | "vscode" {type,command,args} | "opencode"
    user_level: bool = False
    where: str = ""           # for "print": where the user should paste it


def codex_config_path() -> Path:
    home = os.environ.get("CODEX_HOME")
    return (Path(home) if home else Path.home() / ".codex") / "config.toml"


def claude_desktop_config_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "Claude" / "claude_desktop_config.json"


CLIENTS: dict[str, Client] = {c.name: c for c in [
    Client("claude", "Claude Code", "json", ".mcp.json"),
    Client("cursor", "Cursor", "json", ".cursor/mcp.json"),
    Client("vscode", "VS Code / GitHub Copilot", "json", ".vscode/mcp.json", key="servers", style="vscode"),
    Client("gemini", "Gemini CLI", "json", ".gemini/settings.json"),
    Client("qwen", "Qwen Code", "json", ".qwen/settings.json"),
    Client("opencode", "opencode", "json", "opencode.json", key="mcp", style="opencode"),
    Client("codex", "Codex CLI", "toml", user_level=True),
    Client("windsurf", "Windsurf", "print", where="~/.codeium/windsurf/mcp_config.json (Windsurf > Settings > MCP)"),
    Client("claude-desktop", "Claude Desktop", "print", where="claude_desktop_config.json (Settings > Developer > Edit Config)"),
    Client("zed", "Zed", "print", key="context_servers", where="Zed settings.json, under \"context_servers\""),
    Client("other", "another MCP client", "print", where="your client's MCP server settings (stdio transport)"),
]}

ALIASES = {"copilot": "vscode", "code": "vscode", "vs-code": "vscode", "claude-code": "claude",
           "cursor-agent": "cursor", "desktop": "claude-desktop", "claude_desktop": "claude-desktop",
           "gemini-cli": "gemini", "qwen-code": "qwen", "antigravity": "other", "agy": "other",
           "kimi": "other", "generic": "other"}

#: `dyui agent` names → the MCP client whose config that agent reads.
AGENT_CLIENTS = {"claude": "claude", "gemini": "gemini", "qwen": "qwen", "codex": "codex",
                 "cursor": "cursor", "opencode": "opencode"}


def resolve_client(name: str) -> Optional[Client]:
    key = name.strip().lower()
    return CLIENTS.get(ALIASES.get(key, key))


def server_entry(client: Client, python: Optional[str] = None) -> dict[str, Any]:
    exe = python or sys.executable
    if client.style == "vscode":
        return {"type": "stdio", "command": exe, "args": ["-m", "dyui.mcp"]}
    if client.style == "opencode":
        return {"type": "local", "command": [exe, "-m", "dyui.mcp"], "enabled": True}
    return {"command": exe, "args": ["-m", "dyui.mcp"]}


def _toml_block(python: Optional[str] = None) -> str:
    exe = python or sys.executable
    # A JSON string is a valid TOML basic string (same escapes), Windows backslashes included.
    return f'[mcp_servers.{SERVER_KEY}]\ncommand = {json.dumps(exe)}\nargs = ["-m", "dyui.mcp"]\n'


def snippet(client: Client, python: Optional[str] = None) -> str:
    """The config text to paste for ``client``."""
    if client.kind == "toml":
        return _toml_block(python)
    return json.dumps({client.key: {SERVER_KEY: server_entry(client, python)}}, indent=2)


@dataclass
class Result:
    client: Client
    status: str              # "created" | "updated" | "unchanged" | "printed" | "skipped" | "error"
    path: Optional[Path] = None
    message: str = ""
    snippet: str = ""

    @property
    def ok(self) -> bool:
        return self.status != "error"


# ------------------------------------------------------------------ JSON
def _indent_of(text: str) -> int:
    m = re.search(r"\n([ \t]+)\S", text)
    return len(m.group(1).expandtabs(4)) if m else 2


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".dyui-tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def _backup(path: Path) -> None:
    bak = path.with_name(path.name + ".bak")
    if path.is_file() and not bak.exists():
        shutil.copy2(path, bak)


def _install_json(client: Client, root: Path, python: Optional[str]) -> Result:
    assert client.path
    path = root / client.path
    entry = server_entry(client, python)
    text = ""
    data: Any = {}
    if path.is_file():
        text = path.read_text(encoding="utf-8-sig")
        if text.strip():
            try:
                data = json.loads(text)
            except ValueError as exc:
                return Result(client, "error", path,
                              f"{path} is not plain JSON ({exc.msg}, line {exc.lineno}); left it untouched. "
                              f"Add this under \"{client.key}\" yourself:", snippet(client, python))
            if not isinstance(data, dict):
                return Result(client, "error", path, f"{path} does not hold a JSON object; left it untouched.",
                              snippet(client, python))
    servers = data.get(client.key)
    if servers is None:
        servers = {}
    elif not isinstance(servers, dict):
        return Result(client, "error", path, f"\"{client.key}\" in {path} is not an object; left it untouched.",
                      snippet(client, python))
    if servers.get(SERVER_KEY) == entry:
        return Result(client, "unchanged", path, f"{client.label}: already configured in {path}")
    existed = SERVER_KEY in servers
    servers = {**servers, SERVER_KEY: entry}  # keeps the other servers and their order
    data = {**data, client.key: servers} if isinstance(data, dict) else {client.key: servers}
    _backup(path)
    _write(path, json.dumps(data, indent=_indent_of(text) if text else 2, ensure_ascii=False) + "\n")
    return Result(client, "updated" if existed else "created", path,
                  f"{client.label}: {'updated' if existed else 'added'} the dyui server in {path}")


# ------------------------------------------------------------------ TOML (codex)
_TOML_HEADER = re.compile(r"""(?m)^\s*\[\s*mcp_servers\s*\.\s*(?:dyui|"dyui"|'dyui')\s*\]\s*(?:#.*)?$""")


def _install_toml(client: Client, python: Optional[str], confirm: Callable[[str], bool], path: Optional[Path]) -> Result:
    path = path or codex_config_path()
    block = _toml_block(python)
    text = ""
    if path.is_file():
        text = path.read_text(encoding="utf-8-sig")
        if _TOML_HEADER.search(text):
            current = sys.executable if python is None else python
            note = "" if json.dumps(current) in text else (
                f" It points at a different Python; to use this one, edit the block to:\n\n{block}")
            return Result(client, "unchanged", path, f"{client.label}: [mcp_servers.dyui] is already in {path}.{note}")
    if not confirm(f"Add the dyui MCP server to {path} (your user-level Codex config)?"):
        return Result(client, "skipped", path, f"{client.label}: not changed. Add this to {path} yourself:", block)
    _backup(path)
    sep = "" if not text or text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    _write(path, text + sep + block)
    return Result(client, "created", path, f"{client.label}: added [mcp_servers.dyui] to {path}")


# ------------------------------------------------------------------ public
def _deny(_: str) -> bool:
    return False


def install(client: Client, root: Optional[Path] = None, *, python: Optional[str] = None,
            confirm: Callable[[str], bool] = _deny, user_path: Optional[Path] = None) -> Result:
    """Register the server for ``client`` (project files under ``root``, default the CWD)."""
    if client.kind == "json":
        try:
            return _install_json(client, Path(root or Path.cwd()), python)
        except OSError as exc:
            return Result(client, "error", None, f"{client.label}: could not write the config: {exc}",
                          snippet(client, python))
    if client.kind == "toml":
        try:
            return _install_toml(client, python, confirm, user_path)
        except OSError as exc:
            return Result(client, "error", None, f"{client.label}: could not write the config: {exc}",
                          snippet(client, python))
    where = str(claude_desktop_config_path()) if client.name == "claude-desktop" else client.where
    return Result(client, "printed", None, f"{client.label}: add this to {where}:", snippet(client, python))


def detect(root: Optional[Path] = None) -> list[Client]:
    """Project-level clients that look in use here (their folder exists or their CLI is on PATH)."""
    root = Path(root or Path.cwd())
    found = []
    probes = {"claude": (".claude", ("claude",)), "cursor": (".cursor", ("cursor-agent", "cursor")),
              "vscode": (".vscode", ()), "gemini": (".gemini", ("gemini",)), "qwen": (".qwen", ("qwen",)),
              "opencode": ("opencode.json", ("opencode",))}
    for name, (folder, exes) in probes.items():
        if (root / folder).exists() or (root / CLIENTS[name].path).is_file() or any(shutil.which(e) for e in exes):
            found.append(CLIENTS[name])
    return found
