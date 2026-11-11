"""CLI commands, `dyui new` templates and the examples: all usable without an API key."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

import dyui
from dyui.cli import main as cli_main

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = sorted((ROOT / "examples").glob("*.py"))
TEMPLATES = ["basic", "nvidia", "openai", "anthropic", "langgraph"]


@pytest.fixture(autouse=True)
def no_keys(monkeypatch):
    for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_BASE_URL"):
        monkeypatch.delenv(k, raising=False)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(name, None)
    return mod


def test_version(capsys):
    assert cli_main(["version"]) == 0
    assert capsys.readouterr().out.strip() == f"dyui {dyui.__version__}"
    assert dyui.__version__ == "1.2.0"


def test_catalog_json_and_modes(tmp_path, capsys):
    app_py = tmp_path / "app.py"
    app_py.write_text("import dyui\napp = dyui.App(persist=False, components=['stat', 'table'])\n", encoding="utf-8")
    assert cli_main(["catalog", str(app_py), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data["names"]) == {"stat", "table"} and set(data["schemas"]) == {"stat", "table"}
    assert cli_main(["catalog", str(app_py), "--mode", "tools"]) == 0
    out = capsys.readouterr().out
    assert "render_" in out and "```dyui" not in out.split("\n— ")[0]


def test_catalog_rejects_non_app(tmp_path, capsys):
    bad = tmp_path / "bad.py"
    bad.write_text("app = 42\n", encoding="utf-8")
    assert cli_main(["catalog", str(bad)]) != 0


@pytest.mark.parametrize("template", TEMPLATES)
def test_new_template_scaffolds_an_importable_app(tmp_path, template, capsys):
    dest = tmp_path / f"proj_{template}"
    assert cli_main(["new", str(dest), "--template", template]) == 0
    files = {p.name for p in dest.iterdir()}
    assert {"app.py", "README.md", "requirements.txt"} <= files
    text = (dest / "app.py").read_text(encoding="utf-8")
    assert "{{title}}" not in text and "{{" not in (dest / "README.md").read_text(encoding="utf-8")
    if template == "langgraph":
        pytest.importorskip("langgraph")
    mod = load(dest / "app.py", f"tpl_{template}")
    assert isinstance(mod.app, dyui.App) and mod.app.catalog.names


def test_new_refuses_non_empty_dir(tmp_path, capsys):
    (tmp_path / "x.txt").write_text("keep", encoding="utf-8")
    assert cli_main(["new", str(tmp_path)]) != 0
    assert (tmp_path / "x.txt").read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("path", EXAMPLES, ids=[p.stem for p in EXAMPLES])
def test_example_imports_without_api_key(path):
    if "langgraph" in path.stem:
        pytest.importorskip("langgraph")
    mod = load(path, f"ex_{path.stem}")
    app = mod.app
    assert isinstance(app, dyui.App)
    assert app.catalog.prompt().startswith("## UI components")
    assert app._on_message is not None


async def test_no_llm_example_runs_end_to_end():
    import httpx

    mod = load(ROOT / "examples" / "no_llm.py", "ex_no_llm_run")
    app = mod.app
    app._persist = False
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/chat", json={"message": {"text": "hello"}})
        assert r.status_code == 200 and "event: done" in r.text
        assert "event: error" not in r.text
