"""Tests for the dyui CLI: export scaffolding, init brief, serve resolution."""

import os
from pathlib import Path

import pytest

from dyui.cli import (
    _resolve_app,
    build_parser,
    cmd_agent_init,
    cmd_export,
    cmd_init,
    cmd_new,
)
from dyui.scaffold import write_react_project


def test_parser_accepts_all_commands():
    p = build_parser()
    assert p.parse_args(["claude", "init", "a.py"]).cmd == "claude"
    assert p.parse_args(["gemini", "init", "a.py"]).action == "init"
    assert p.parse_args(["serve"]).cmd == "serve"
    assert p.parse_args(["export", "myui"]).name == "myui"
    assert p.parse_args(["demo"]).cmd == "demo"
    assert p.parse_args(["new"]).file == "agent.py"
    assert p.parse_args(["init"]).cmd == "init"
    assert p.parse_args(["serve", "--open", "--reload"]).open is True


def test_export_scaffold_writes_project(tmp_path):
    dest = tmp_path / "myui"
    files = write_react_project(
        dest, project_name="myui", stream_url="http://x/dyui/stream", local_react="../../react"
    )
    assert "package.json" in files
    assert "src/App.tsx" in files
    assert "src/vite-env.d.ts" in files

    pkg = (dest / "package.json").read_text()
    assert '"name": "myui"' in pkg
    assert "file:../../react" in pkg  # local override applied

    app = (dest / "src/App.tsx").read_text()
    assert "useDyUIAgent" in app and "http://x/dyui/stream" in app


def test_export_default_uses_npm_version(tmp_path):
    write_react_project(tmp_path / "p", project_name="p", stream_url="u")
    assert '"dyui-react": "^0.1.0"' in (tmp_path / "p" / "package.json").read_text()


def test_cmd_export_refuses_nonempty(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "taken").mkdir()
    (tmp_path / "taken" / "x.txt").write_text("hi")
    assert cmd_export("taken", "u", force=False, local=None) == 1


def test_cmd_agent_init_writes_brief_without_launching(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DYUI_NO_LAUNCH", "1")
    agent = tmp_path / "agent.py"
    agent.write_text("from dyui import emit\n\ngraph = None\n")

    rc = cmd_agent_init("claude", str(agent))
    assert rc == 0
    brief = (tmp_path / ".dyui" / "INIT_PROMPT.md").read_text()
    assert "DyUI integration brief" in brief
    assert "graph = None" in brief        # the user's code is embedded
    assert "YOUR TASK" in brief           # the workflow instructions are present


def test_cmd_agent_init_missing_file(tmp_path, capsys):
    assert cmd_agent_init("claude", str(tmp_path / "nope.py")) == 1


# --------------------------------------------------------------------------- #
# `dyui new` -- starter agent scaffold
# --------------------------------------------------------------------------- #
def test_cmd_new_writes_runnable_starter(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cmd_new("agent.py", force=False) == 0
    code = (tmp_path / "agent.py").read_text()
    assert "create_dyui_app" in code and "build_graph" in code
    # The scaffold must be valid, importable Python that builds a graph + app.
    ns: dict = {}
    exec(compile(code, "agent.py", "exec"), ns)
    assert ns["graph"] is not None and ns["app"] is not None


def test_cmd_new_refuses_existing_without_force(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "agent.py").write_text("x = 1\n")
    assert cmd_new("agent.py", force=False) == 1
    assert cmd_new("agent.py", force=True) == 0  # --force overwrites


# --------------------------------------------------------------------------- #
# `dyui init` -- coding-agent memory files
# --------------------------------------------------------------------------- #
def test_cmd_init_writes_agent_memory_files(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cmd_init(None) == 0
    for name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
        text = (tmp_path / name).read_text()
        assert "Using DyUI in this project" in text
        assert "<!-- dyui:start -->" in text


def test_cmd_init_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cmd_init(None)
    cmd_init(None)  # second run updates in place, no duplicate section
    text = (tmp_path / "AGENTS.md").read_text()
    assert text.count("<!-- dyui:start -->") == 1


def test_cmd_init_preserves_existing_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CLAUDE.md").write_text("# My rules\n\nKeep functions small.\n")
    cmd_init(None)
    text = (tmp_path / "CLAUDE.md").read_text()
    assert "Keep functions small." in text          # existing content kept
    assert "Using DyUI in this project" in text      # guide appended


def test_cmd_init_embeds_agent_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "myagent.py").write_text("graph = 'SENTINEL_GRAPH'\n")
    cmd_init("myagent.py")
    assert "SENTINEL_GRAPH" in (tmp_path / "AGENTS.md").read_text()


def test_serve_resolves_graph_into_app(tmp_path):
    mod = tmp_path / "myagent.py"
    mod.write_text(
        "from langgraph.graph import StateGraph, START, END\n"
        "from dyui import emit\n"
        "def n(s):\n    emit('text', {'text': 'hi'})\n    return {}\n"
        "g = StateGraph(dict)\n"
        "g.add_node('n', n)\n"
        "g.add_edge(START, 'n')\n"
        "g.add_edge('n', END)\n"
        "graph = g.compile()\n"
    )
    app = _resolve_app(str(mod), serve_ui=True, title="T")
    # It wrapped `graph` into a FastAPI app with the stream route + served UI.
    routes = {getattr(r, "path", None) for r in app.routes}
    assert "/dyui/stream" in routes
    assert "/" in routes
