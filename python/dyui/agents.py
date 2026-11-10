"""Launch a coding-agent CLI preloaded with the DyUI skill (``dyui agent``, ``dyui claude`` ...).

The skill is one Markdown file (``dyui/skill/SKILL.md``). ``install()`` renders it with the
installed version and the live component catalog, and writes it where the chosen agent discovers
project skills. ``launch()`` then starts the agent's CLI with a first prompt that points at it.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from .__version__ import __version__

DEFAULT_MODEL = "nvidia/moonshotai/kimi-k2.6"
SKILL_NAME = "dyui"
DEFAULT_TASK = (
    "Start by inspecting this project, then tell me what you found and how you would "
    "build or integrate DyUI here."
)
INIT_TASK = "Follow playbook D of the skill and design custom components for {target}."


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
def _component_lines() -> str:
    from .genui import catalog

    return "\n".join(cls.signature() for cls in catalog())


def render_skill() -> str:
    """The skill text for the installed DyUI: version, default model and built-in components."""
    text = (Path(__file__).parent / "skill" / "SKILL.md").read_text(encoding="utf-8")
    return (text.replace("{{version}}", __version__)
                .replace("{{model}}", DEFAULT_MODEL)
                .replace("{{components}}", _component_lines()))


def skill_path(agent: Agent, root: Path) -> Path:
    return root / agent.skills_dir / SKILL_NAME / "SKILL.md"


def install(agent: Agent, root: Optional[Path] = None) -> Path:
    """Write the skill into ``root`` (default: the current directory) for ``agent``."""
    path = skill_path(agent, root or Path.cwd())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_skill(), encoding="utf-8")
    return path


# ------------------------------------------------------------------ launching
_CMD_UNSAFE = '"&|<>^%!\r\n'


def first_prompt(skill: Path, task: str, root: Optional[Path] = None) -> str:
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


def run(name: Optional[str], task: str = "", *, launch: bool = True) -> int:
    """Install the skill for an agent and start its CLI. Returns a process exit code."""
    if name:
        agent = resolve(name)
    else:
        found = installed()
        if not found:
            path = install(Agent("any", "your coding agent", (), ".agents/skills"))
            print(f"Wrote {path}")
            print("dyui: no coding-agent CLI found on PATH (looked for: "
                  + ", ".join(e for a in AGENTS.values() for e in a.exes)
                  + ").\nOpen that file in your coding agent, or install one and run `dyui agent` again.",
                  file=sys.stderr)
            return 2
        agent = choose(found)
    path = install(agent)
    print(f"Wrote {path}")
    if not launch or os.environ.get("DYUI_NO_LAUNCH"):
        return 0
    exe = find_exe(agent)
    if exe is None:
        print(f"dyui: `{agent.exes[0]}` not found on PATH. Open {path} in your coding agent instead.",
              file=sys.stderr)
        return 2
    prompt = first_prompt(path, task)
    if agent.prompt_args is None:
        print(f"Starting {agent.label}. Paste this as your first message:\n\n  {prompt}\n")
    else:
        print(f"Starting {agent.label} with the DyUI skill...")
    return subprocess.call(launch_argv(agent, exe, prompt))
