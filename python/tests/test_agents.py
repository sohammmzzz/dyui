"""`dyui agent` and the per-agent shortcuts: skill install and launch arguments."""
from __future__ import annotations

import pytest

import dyui
from dyui import agents, ui
from dyui.cli import main as cli_main


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DYUI_NO_LAUNCH", raising=False)
    return tmp_path


@pytest.fixture
def calls(monkeypatch):
    seen: list[list[str]] = []
    monkeypatch.setattr(agents.subprocess, "call", lambda argv: seen.append(argv) or 0)
    return seen


def fake_path(monkeypatch, *exes):
    monkeypatch.setattr(agents.shutil, "which", lambda n: f"/bin/{n}" if n in exes else None)


def test_skill_is_rendered_with_version_model_and_every_component():
    text = agents.render_skill()
    assert text.startswith("---\nname: dyui\n") and "{{" not in text
    assert dyui.__version__ in text and agents.DEFAULT_MODEL in text
    for name in dyui.genui.catalog().names:
        assert f"\n{name}(" in text, name


def test_skill_python_snippets_are_valid():
    """The constructor forms the skill teaches must actually work."""
    ui.Stats(ui.Stat("Today", "24°C", trend="up", delta="+2°"), ui.Stat("Rain", "10%"))
    ui.Table(["City", "Temp"], [["Lisbon", 24], ["Porto", 21]])
    ui.Chart("line", [ui.Series("EU", [41, 44, 48])])
    ui.KeyValue({"Departs": "Fri 18:05", "Price": "$189"})
    ui.Callout("Saved.", level="success")
    ui.Card("TAP", ui.Stat("Price", "$189"), actions=[ui.Button("Book", action="book", data={"a": 1}, style="primary")])
    ui.QuickReplies("Tomorrow?", "Compare with Porto")
    ui.Form(ui.Field("email", type="email", required=True),
            ui.Field("plan", type="select", options=["Starter", "Team"]), title="Sign up")
    ui.Confirm("Delete 14 conversations?", danger=True, confirm_label="Delete")
    ui.Sources(ui.Source("Title", "https://example.com"))
    ui.Plan(ui.PlanItem("Find flights", "active"), ui.PlanItem("Book hotel"), title="Trip", id="plan")
    ui.Html("<b>Boarding pass</b>", height=120)
    ui.Progress(60, label="Indexing", id="idx")
    dyui.Starter("Find flights", "Flights to Tokyo", icon="plane")
    assert callable(dyui.llm.complete)
    dyui.App(title="t", persist=False, embed_origins=["https://www.example.com"], max_upload_mb=5)


@pytest.mark.parametrize("name,skill,argv_head", [
    ("claude", ".claude/skills/dyui/SKILL.md", ["/bin/claude"]),
    ("gemini", ".gemini/skills/dyui/SKILL.md", ["/bin/gemini", "-i"]),
    ("codex", ".agents/skills/dyui/SKILL.md", ["/bin/codex"]),
    ("qwen", ".qwen/skills/dyui/SKILL.md", ["/bin/qwen", "-i"]),
    ("antigravity", ".agents/skills/dyui/SKILL.md", ["/bin/agy", "-i"]),
])
def test_shortcut_installs_skill_and_launches(project, calls, monkeypatch, name, skill, argv_head):
    fake_path(monkeypatch, "claude", "gemini", "codex", "qwen", "agy")
    assert cli_main([name, "convert", "this", "repo"]) == 0
    assert (project / skill).read_text(encoding="utf-8").startswith("---\nname: dyui")
    (argv,) = calls
    assert argv[:-1] == argv_head
    assert skill in argv[-1] and argv[-1].endswith("convert this repo")


def test_kimi_launches_without_a_prompt(project, calls, monkeypatch, capsys):
    fake_path(monkeypatch, "kimi")
    assert cli_main(["kimi"]) == 0
    assert calls == [["/bin/kimi"]]
    assert ".agents/skills/dyui/SKILL.md" in capsys.readouterr().out


def test_agent_autodetects_and_default_task(project, calls, monkeypatch):
    fake_path(monkeypatch, "codex")
    assert cli_main(["agent"]) == 0
    assert calls[0][0] == "/bin/codex" and "inspecting this project" in calls[0][1]


def test_agent_named_and_unknown_cli(project, calls, monkeypatch):
    fake_path(monkeypatch, "claude", "mytool")
    assert cli_main(["agent", "mytool", "build", "a", "bot"]) == 0
    assert calls[0][0] == "/bin/mytool" and calls[0][1].endswith("build a bot")
    assert (project / ".agents/skills/dyui/SKILL.md").is_file()


def test_no_agent_installed_writes_skill_and_fails(project, calls, monkeypatch, capsys):
    fake_path(monkeypatch)
    assert cli_main(["agent"]) == 2
    assert calls == [] and (project / ".agents/skills/dyui/SKILL.md").is_file()
    assert "no coding-agent CLI" in capsys.readouterr().err


def test_missing_named_agent(project, calls, monkeypatch):
    fake_path(monkeypatch)
    assert cli_main(["claude"]) == 2 and calls == []
    assert (project / ".claude/skills/dyui/SKILL.md").is_file()


def test_no_launch_flag_and_env(project, calls, monkeypatch):
    fake_path(monkeypatch, "claude")
    assert cli_main(["claude", "--no-launch"]) == 0
    monkeypatch.setenv("DYUI_NO_LAUNCH", "1")
    assert cli_main(["claude"]) == 0
    assert calls == []


def test_legacy_init_designs_components(project, calls, monkeypatch):
    fake_path(monkeypatch, "claude")
    (project / "app.py").write_text("import dyui\napp = dyui.App(persist=False)\n", encoding="utf-8")
    assert cli_main(["claude", "init"]) == 0
    assert "playbook D" in calls[0][-1] and "app.py" in calls[0][-1]


def test_list_and_print(project, monkeypatch, capsys):
    fake_path(monkeypatch, "qwen")
    assert cli_main(["agent", "--list"]) == 0
    out = capsys.readouterr().out
    assert "qwen" in out and "installed" in out and "not found" in out
    assert cli_main(["agent", "--print"]) == 0
    assert "# DyUI engineer" in capsys.readouterr().out


def test_windows_cmd_shim_prompt_is_sanitised(monkeypatch):
    monkeypatch.setattr(agents.os, "name", "nt")
    argv = agents.launch_argv(agents.AGENTS["claude"], r"C:\npm\claude.CMD", 'say "hi" & del x | y\nz 100%')
    assert not set(argv[-1]) & set(agents._CMD_UNSAFE)


def test_first_prompt_uses_relative_posix_path(tmp_path):
    p = tmp_path / ".claude" / "skills" / "dyui" / "SKILL.md"
    assert ".claude/skills/dyui/SKILL.md" in agents.first_prompt(p, "", tmp_path)
