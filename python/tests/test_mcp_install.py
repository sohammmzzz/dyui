"""`dyui mcp install`: config merges keep other servers, are idempotent, and never clobber."""
from __future__ import annotations

import json
import sys

import pytest

from dyui.cli import main as cli_main
from dyui.mcp import install as inst

PY = r"C:\Users\me\proj\.venv\Scripts\python.exe" if sys.platform == "win32" else "/home/me/proj/.venv/bin/python"


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.setattr(inst.shutil, "which", lambda _n: None)
    return tmp_path


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_entry_uses_the_running_python():
    entry = inst.server_entry(inst.CLIENTS["claude"])
    assert entry == {"command": sys.executable, "args": ["-m", "dyui.mcp"]}
    assert inst.server_entry(inst.CLIENTS["vscode"])["type"] == "stdio"
    assert inst.server_entry(inst.CLIENTS["opencode"])["command"] == [sys.executable, "-m", "dyui.mcp"]


def test_merge_into_existing_mcp_json_keeps_other_servers_and_is_idempotent(project):
    cfg = project / ".mcp.json"
    original = {"mcpServers": {"github": {"command": "gh-mcp", "env": {"TOKEN": "${GITHUB_TOKEN}"}}}, "other": [1, 2]}
    cfg.write_text(json.dumps(original, indent=4) + "\n", encoding="utf-8")
    r = inst.install(inst.CLIENTS["claude"], project, python=PY)
    assert r.status == "created" and r.path == cfg
    data = read(cfg)
    assert data["other"] == [1, 2] and data["mcpServers"]["github"] == original["mcpServers"]["github"]
    assert data["mcpServers"]["dyui"] == {"command": PY, "args": ["-m", "dyui.mcp"]}
    assert list(data["mcpServers"]) == ["github", "dyui"]
    assert cfg.read_text(encoding="utf-8").startswith('{\n    "mcpServers"')  # kept the 4-space indent
    assert read(project / ".mcp.json.bak") == original

    before = cfg.read_bytes()
    again = inst.install(inst.CLIENTS["claude"], project, python=PY)
    assert again.status == "unchanged" and cfg.read_bytes() == before

    moved = inst.install(inst.CLIENTS["claude"], project, python=PY + "3")
    assert moved.status == "updated" and read(cfg)["mcpServers"]["dyui"]["command"] == PY + "3"
    assert read(project / ".mcp.json.bak") == original  # the first backup is kept


@pytest.mark.parametrize("name,path,key", [
    ("cursor", ".cursor/mcp.json", "mcpServers"),
    ("vscode", ".vscode/mcp.json", "servers"),
    ("gemini", ".gemini/settings.json", "mcpServers"),
    ("qwen", ".qwen/settings.json", "mcpServers"),
    ("opencode", "opencode.json", "mcp"),
])
def test_each_project_client_creates_its_file(project, name, path, key):
    r = inst.install(inst.CLIENTS[name], project, python=PY)
    assert r.status == "created" and not (project / (path + ".bak")).exists()
    assert "dyui" in read(project / path)[key]


def test_gemini_settings_keep_unrelated_settings(project):
    cfg = project / ".gemini" / "settings.json"
    cfg.parent.mkdir()
    cfg.write_text('{"theme": "GitHub", "mcpServers": {}}', encoding="utf-8")
    inst.install(inst.CLIENTS["gemini"], project, python=PY)
    assert read(cfg)["theme"] == "GitHub" and "dyui" in read(cfg)["mcpServers"]


@pytest.mark.parametrize("text", ['{\n  // comment\n  "servers": {}\n}', "[1, 2]", '{"servers": []}', "{oops"])
def test_unparseable_or_odd_files_are_left_alone(project, text):
    cfg = project / ".vscode" / "mcp.json"
    cfg.parent.mkdir()
    cfg.write_text(text, encoding="utf-8")
    r = inst.install(inst.CLIENTS["vscode"], project, python=PY)
    assert r.status == "error" and not r.ok and '"dyui"' in r.snippet
    assert cfg.read_text(encoding="utf-8") == text and not (project / ".vscode" / "mcp.json.bak").exists()


def test_codex_toml_is_appended_once_and_only_when_confirmed(project):
    toml = project / "codex-home" / "config.toml"
    toml.parent.mkdir()
    toml.write_text('model = "gpt-5"\n\n[mcp_servers.other]\ncommand = "x"\n', encoding="utf-8")
    declined = inst.install(inst.CLIENTS["codex"], project, python=PY)
    assert declined.status == "skipped" and "[mcp_servers.dyui]" in declined.snippet
    assert "dyui" not in toml.read_text(encoding="utf-8")

    yes = inst.install(inst.CLIENTS["codex"], project, python=PY, confirm=lambda _q: True)
    assert yes.status == "created"
    text = toml.read_text(encoding="utf-8")
    assert text.startswith('model = "gpt-5"\n\n[mcp_servers.other]\ncommand = "x"\n\n[mcp_servers.dyui]\n')
    assert f"command = {json.dumps(PY)}" in text and 'args = ["-m", "dyui.mcp"]' in text
    assert (toml.parent / "config.toml.bak").read_text(encoding="utf-8").count("[mcp_servers") == 1

    again = inst.install(inst.CLIENTS["codex"], project, python=PY, confirm=lambda _q: True)
    assert again.status == "unchanged" and toml.read_text(encoding="utf-8") == text
    other = inst.install(inst.CLIENTS["codex"], project, python="/elsewhere/python", confirm=lambda _q: True)
    assert other.status == "unchanged" and "different Python" in other.message
    assert toml.read_text(encoding="utf-8").count("[mcp_servers.dyui]") == 1


def test_codex_toml_in_a_fresh_home(project):
    r = inst.install(inst.CLIENTS["codex"], project, python=PY, confirm=lambda _q: True)
    assert r.status == "created" and (project / "codex-home" / "config.toml").read_text(encoding="utf-8").startswith(
        "[mcp_servers.dyui]\n")


def test_toml_header_detection_variants():
    for text in ('[mcp_servers.dyui]\n', '  [ mcp_servers . "dyui" ]  # mine\n', "[mcp_servers.'dyui']\n"):
        assert inst._TOML_HEADER.search(text), text
    assert not inst._TOML_HEADER.search("[mcp_servers.dyui_old]\n")
    assert not inst._TOML_HEADER.search("# [mcp_servers.dyui]\n")


def test_print_only_clients(project):
    for name in ("windsurf", "claude-desktop", "zed", "other"):
        r = inst.install(inst.CLIENTS[name], project, python=PY)
        assert r.status == "printed" and "dyui.mcp" in r.snippet and r.path is None
    assert '"context_servers"' in inst.snippet(inst.CLIENTS["zed"], PY)
    assert "claude_desktop_config.json" in inst.install(inst.CLIENTS["claude-desktop"], project).message
    assert not any(project.iterdir())  # nothing written


def test_aliases():
    assert inst.resolve_client("Copilot").name == "vscode"
    assert inst.resolve_client("claude-code").name == "claude"
    assert inst.resolve_client("kimi").name == "other"
    assert inst.resolve_client("nope") is None


# ------------------------------------------------------------------ the CLI
def test_cli_install_named_client(project, capsys):
    assert cli_main(["mcp", "install", "cursor"]) == 0
    assert "dyui" in read(project / ".cursor" / "mcp.json")["mcpServers"]
    assert "added the dyui server" in capsys.readouterr().out
    assert cli_main(["mcp", "install", "cursor"]) == 0
    assert "already configured" in capsys.readouterr().out


def test_cli_print_writes_nothing(project, capsys):
    assert cli_main(["mcp", "install", "claude", "--print"]) == 0
    out = capsys.readouterr().out
    assert json.loads(out.split("\n", 1)[1])["mcpServers"]["dyui"]["args"] == ["-m", "dyui.mcp"]
    assert not (project / ".mcp.json").exists()
    assert cli_main(["mcp", "install", "codex", "--print"]) == 0
    assert "[mcp_servers.dyui]" in capsys.readouterr().out
    assert not (project / "codex-home").exists()


def test_cli_codex_needs_yes_off_a_terminal(project, capsys):
    assert cli_main(["mcp", "install", "codex"]) == 0
    assert not (project / "codex-home" / "config.toml").exists()
    assert cli_main(["mcp", "install", "codex", "--yes"]) == 0
    assert (project / "codex-home" / "config.toml").is_file()


def test_cli_detects_clients(project, capsys):
    assert cli_main(["mcp", "install"]) == 0
    assert "no coding agent detected" in capsys.readouterr().out and not any(p.suffix == ".json" for p in project.rglob("*"))
    (project / ".vscode").mkdir()
    (project / ".claude").mkdir()
    assert cli_main(["mcp", "install"]) == 0
    assert (project / ".mcp.json").is_file() and (project / ".vscode" / "mcp.json").is_file()
    assert not (project / ".cursor").exists()


def test_cli_unknown_client_and_bad_file_exit_codes(project, capsys):
    assert cli_main(["mcp", "install", "nope"]) == 2
    assert "unknown client" in capsys.readouterr().err
    (project / ".mcp.json").write_text("{bad", encoding="utf-8")
    assert cli_main(["mcp", "install", "claude"]) == 1
    assert (project / ".mcp.json").read_text(encoding="utf-8") == "{bad"


def test_cli_warns_when_the_sdk_is_missing(project, monkeypatch, capsys):
    import dyui.mcp

    monkeypatch.setattr(dyui.mcp, "available", lambda: False)
    assert cli_main(["mcp", "install", "claude"]) == 0
    assert 'pip install "dyui[mcp]"' in capsys.readouterr().err
    assert (project / ".mcp.json").is_file()
