"""Launch a coding-agent CLI briefed on DyUI (``dyui agent``, ``dyui claude`` ...).

With the ``mcp`` extra installed (``pip install "dyui[mcp]"``) and an agent whose MCP config DyUI
can write (Claude Code, Gemini CLI, Qwen Code, Cursor Agent, opencode, Codex), :func:`run`:

1. registers the DyUI MCP server for that agent (``dyui.mcp.install``); the server serves the
   docs, component schemas and validators of the installed version;
2. writes a short pointer skill (:data:`POINTER_SKILL`) where the agent discovers project skills;
3. starts the agent's CLI with a first prompt that tells it to use the MCP server.

Otherwise (no ``mcp`` package, or an agent DyUI cannot configure) it falls back to the full
skill (``dyui/skill/SKILL.md``), rendered with the installed version and the live component
catalog, and a first prompt that points at it.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from .__version__ import __version__

DEFAULT_MODEL = "nvidia/moonshotai/kimi-k2.6"
SKILL_NAME = "dyui"
DEFAULT_TASK = (
    "Start by inspecting this project, then tell me what you found and how you would "
    "build or integrate DyUI here."
)
INIT_TASK = "Follow DyUI playbook D (design custom components) for {target}."
MCP_PROMPT = "Use the dyui MCP server (call dyui_overview first). "
MCP_HINT = ('tip: pip install "dyui[mcp]" gives the agent the DyUI MCP server '
            "(live docs, component schemas, validators).")


@dataclass(frozen=True)
class Agent:
    name: str
    label: str
    exes: tuple[str, ...]  # executable names, tried in order
    skills_dir: str  # project-relative folder the agent reads skills from
    prompt_args: Optional[tuple[str, ...]] = ()  # flags before the first prompt; None = can't pass one


AGENTS: dict[str, Agent] = {
    a.name: a
    for a in [
        Agent("claude", "Claude Code", ("claude",), ".claude/skills"),
        Agent("gemini", "Gemini CLI", ("gemini",), ".gemini/skills", ("-i",)),
        Agent("codex", "Codex CLI", ("codex",), ".agents/skills"),
        Agent("qwen", "Qwen Code", ("qwen",), ".qwen/skills", ("-i",)),
        Agent("antigravity", "Antigravity CLI", ("agy", "antigravity"), ".agents/skills", ("-i",)),
        Agent("kimi", "Kimi Code", ("kimi",), ".agents/skills", None),
        Agent("opencode", "opencode", ("opencode",), ".agents/skills", ("--prompt",)),
        Agent("cursor", "Cursor Agent", ("cursor-agent",), ".agents/skills"),
    ]
}


def resolve(name: str) -> Agent:
    """A known agent, or any other command treated as a CLI that takes a prompt argument."""
    return AGENTS.get(name) or Agent(name, name, (name,), ".agents/skills")


def find_exe(agent: Agent) -> Optional[str]:
    for exe in agent.exes:
        found = shutil.which(exe)
        if found:
            return found
    return None


def installed() -> list[Agent]:
    return [a for a in AGENTS.values() if find_exe(a)]


# ------------------------------------------------------------------ the skill
POINTER_SKILL = """\
---
name: dyui
description: Build, convert and extend chat apps with DyUI, the Python framework where the LLM answers with tables, charts, cards, forms and buttons. Use for any task that mentions DyUI, `import dyui`, `dyui run`, a chatbot or agent UI in Python, turning a script, agent, API or LangGraph graph into a chat app, or designing custom chat components.
---

# DyUI

DyUI {{version}} is installed for this project. Everything you need is served, for exactly this
version, by the **`dyui` MCP server** (registered in {{config}}).

1. Call the `dyui_overview` tool first. It explains the API, the handler model, providers and
   API keys, and the playbooks (also available as the prompts `build_app`, `convert_project`,
   `design_components` and `production_checklist`).
2. Never guess a component's props or constructor: call `get_component(name)`. Find docs with
   `search_docs(query)` and `read_doc(slug)`, and complete apps with `get_example(name)`.
3. Look at the project before proposing changes. Keep the developer's existing logic and wrap
   it. Never put API keys in code.
4. Before you report success, run `check_app(path)` on the app file and `validate_ui(...)` on
   any component JSON you wrote. Fix what they report.
5. Report what changed, how to run it (`dyui run app.py`) and what you could not verify.

If the `dyui` tools are missing, the agent may need you to approve the server or restart.
The server runs with `python -m dyui.mcp`. As a last resort, `dyui agent --print` prints the
full offline guide.
"""


def _component_lines() -> str:
    from .mcp.introspect import signature_lines

    return signature_lines()


def render_skill() -> str:
    """The full skill text for the installed DyUI: version, default model and built-in components."""
    text = (Path(__file__).parent / "skill" / "SKILL.md").read_text(encoding="utf-8")
    return (text.replace("{{version}}", __version__)
                .replace("{{model}}", DEFAULT_MODEL)
                .replace("{{components}}", _component_lines()))


def render_pointer(config: str = "this project's MCP config") -> str:
    """The short skill written when the MCP server is registered: it points the agent at the tools."""
    return POINTER_SKILL.replace("{{version}}", __version__).replace("{{config}}", f"`{config}`")


def skill_path(agent: Agent, root: Path) -> Path:
    return root / agent.skills_dir / SKILL_NAME / "SKILL.md"


def install(agent: Agent, root: Optional[Path] = None, *, text: Optional[str] = None) -> Path:
    """Write the skill (default: the full one) into ``root`` (default: the CWD) for ``agent``."""
    path = skill_path(agent, root or Path.cwd())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_skill() if text is None else text, encoding="utf-8")
    return path


# ------------------------------------------------------------------ the MCP server
def _confirm(yes: bool) -> Callable[[str], bool]:
    def ask(question: str) -> bool:
        if yes:
            return True
        if not sys.stdin.isatty():
            return False
        try:
            return input(f"{question} [Y/n] ").strip().lower() in ("", "y", "yes")
        except EOFError:
            return False

    return ask


def _mcp_install() -> Any:
    from .mcp import install as mcp_install

    return mcp_install


def mcp_available() -> bool:
    from . import mcp as dyui_mcp

    return dyui_mcp.available()


def register_mcp(agent: Agent, root: Optional[Path] = None, *, yes: bool = False) -> Optional[str]:
    """Register the DyUI MCP server for ``agent``; return the config file it is in, or ``None``.

    ``None`` when the ``mcp`` package is missing, DyUI cannot configure this agent, or the user
    declined (Codex); the caller then falls back to the full skill. Never raises.
    """
    inst = _mcp_install()
    if agent.name not in inst.AGENT_CLIENTS or not mcp_available():
        return None
    base = root or Path.cwd()
    client = inst.CLIENTS[inst.AGENT_CLIENTS[agent.name]]
    try:
        result = inst.install(client, base, confirm=_confirm(yes))
    except Exception as exc:  # noqa: BLE001 - never block launching the agent
        print(f"dyui: could not register the MCP server for {agent.label}: {exc}", file=sys.stderr)
        return None
    print(result.message)
    if result.snippet:
        print(result.snippet)
    if result.status not in ("created", "updated", "unchanged") or result.path is None:
        return None
    try:
        return result.path.relative_to(base).as_posix()
    except ValueError:
        return result.path.as_posix()


# ------------------------------------------------------------------ launching
_CMD_UNSAFE = '"&|<>^%!\r\n'


def first_prompt(skill: Path, task: str, root: Optional[Path] = None, *, mcp: bool = False) -> str:
    if mcp:
        return f"{MCP_PROMPT}{task.strip() or DEFAULT_TASK}"
    try:
        shown = skill.relative_to(root or Path.cwd()).as_posix()
    except ValueError:
        shown = skill.as_posix()
    return f"Read the DyUI skill at {shown} and follow it for this whole session. {task.strip() or DEFAULT_TASK}"


def launch_argv(agent: Agent, exe: str, prompt: str) -> list[str]:
    if agent.prompt_args is None:
        return [exe]
    if os.name == "nt" and exe.lower().endswith((".cmd", ".bat")):
        # npm shims run through cmd.exe, which would interpret these characters
        prompt = "".join(" " if c in _CMD_UNSAFE else c for c in prompt)
    return [exe, *agent.prompt_args, prompt]


def choose(candidates: Sequence[Agent]) -> Agent:
    """Pick one of several installed agents: ask on a terminal, else take the first."""
    if len(candidates) == 1 or not sys.stdin.isatty():
        return candidates[0]
    print("Which coding agent?")
    for i, a in enumerate(candidates, 1):
        print(f"  {i}. {a.label} ({a.name})")
    while True:
        try:
            answer = input(f"Choose 1-{len(candidates)} [1]: ").strip()
        except EOFError:
            return candidates[0]
        if not answer:
            return candidates[0]
        if answer.isdigit() and 1 <= int(answer) <= len(candidates):
            return candidates[int(answer) - 1]
        for a in candidates:
            if answer.lower() == a.name:
                return a


def run(name: Optional[str], task: str = "", *, launch: bool = True, yes: bool = False) -> int:
    """Brief an agent on DyUI (MCP server + pointer skill, or the full skill) and start its CLI.

    ``yes`` allows writing user-level config (Codex) without asking. Returns a process exit code.
    """
    if name:
        agent = resolve(name)
    else:
        found = installed()
        if not found:
            path = install(Agent("any", "your coding agent", (), ".agents/skills"))
            print(f"Wrote {path}")
            print("dyui: no coding-agent CLI found on PATH (looked for: "
                  + ", ".join(e for a in AGENTS.values() for e in a.exes)
                  + ").\nOpen that file in your coding agent, or install one and run `dyui agent` again."
                  + "\nFor IDE agents (Cursor, VS Code, Windsurf...) run `dyui mcp install <client>`.",
                  file=sys.stderr)
            return 2
        agent = choose(found)
    config = register_mcp(agent, yes=yes)
    if config is not None:
        path = install(agent, text=render_pointer(config))
    else:
        path = install(agent)
        if not mcp_available():
            print(f"dyui: {MCP_HINT}", file=sys.stderr)
    print(f"Wrote {path}")
    if not launch or os.environ.get("DYUI_NO_LAUNCH"):
        return 0
    exe = find_exe(agent)
    if exe is None:
        print(f"dyui: `{agent.exes[0]}` not found on PATH. Open {path} in your coding agent instead.",
              file=sys.stderr)
        return 2
    prompt = first_prompt(path, task, mcp=config is not None)
    if agent.prompt_args is None:
        print(f"Starting {agent.label}. Paste this as your first message:\n\n  {prompt}\n")
    else:
        print(f"Starting {agent.label} with the DyUI {'MCP server' if config else 'skill'}...")
    return subprocess.call(launch_argv(agent, exe, prompt))
