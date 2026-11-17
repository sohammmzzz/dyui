"""Every complete program the docs show actually runs.

Covers the cookbook apps (``examples/*.py``), the per-page complete examples
(``docs/examples/**/*.py``) and the generated app on every component page. Each runs
in its own subprocess through ``docs_driver.py``: imported with the model SDKs faked
(no network, no API key), then a conversation is driven through the real ASGI app,
``chat.ask()`` prompts are answered and interactive components are clicked. Any error
event, HTTP failure or exception fails the test.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DRIVER = Path(__file__).with_name("docs_driver.py")
EXAMPLES = sorted((ROOT / "examples").glob("*.py"))
DOC_EXAMPLES = sorted((ROOT / "docs" / "examples").rglob("*.py"))
COMPONENTS_JSON = ROOT / "docs" / "src" / "data" / "components.json"
NEEDS = {"langgraph": "langgraph", "openai": "openai", "anthropic": "anthropic"}


def _component_apps() -> list[tuple[str, str]]:
    sys.path.insert(0, str(ROOT / "docs" / "scripts"))
    try:
        from component_apps import component_app
    finally:
        sys.path.pop(0)
    data = json.loads(COMPONENTS_JSON.read_text(encoding="utf-8"))
    return [(c["name"], component_app(c)) for c in data["components"]]


COMPONENT_APPS = _component_apps()


@pytest.fixture(scope="session")
def reports(tmp_path_factory) -> dict[str, dict]:
    """Run every example once, in one subprocess, and index the reports by id."""
    items = [{"id": p.relative_to(ROOT).as_posix(), "path": str(p)} for p in EXAMPLES + DOC_EXAMPLES
             if _missing_sdk(p) is None]
    items += [{"id": f"component:{name}", "source": src} for name, src in COMPONENT_APPS]
    env = {k: v for k, v in os.environ.items() if not k.endswith(("_API_KEY", "_BASE_URL"))}
    env.update({
        "PYTHONPATH": os.pathsep.join([str(ROOT / "python"), env.get("PYTHONPATH", "")]),
        "PYTHONIOENCODING": "utf-8",
        "DYUI_MODEL": "nvidia/moonshotai/kimi-k2.6",
        # read by examples that build their own SDK client; the fake client never sends it
        "NVIDIA_API_KEY": "test-key-not-real",
        "APP_PASSWORD": "docs-test-password",
    })
    proc = subprocess.run(
        [sys.executable, str(DRIVER)], input=json.dumps(items), capture_output=True, text=True,
        encoding="utf-8", cwd=tmp_path_factory.mktemp("docs-examples"), env=env, timeout=600,
    )
    out = {}
    for line in proc.stdout.splitlines():
        if line.startswith("{"):
            r = json.loads(line)
            out[r["id"]] = r
    out["__stderr__"] = {"text": proc.stderr[-6000:]}
    return out


def _check(reports: dict[str, dict], item_id: str) -> dict:
    report = reports.get(item_id)
    assert report is not None, f"the driver produced no report for {item_id}\n{reports['__stderr__']['text']}"
    assert not report["errors"], f"{item_id} failed: {report['errors']}"
    assert report["texts"] > 0, f"{item_id} produced no reply"
    return report


def _missing_sdk(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    for needle, module in NEEDS.items():
        if f"import {needle}" in text or f"from {needle}" in text:
            if importlib.util.find_spec(module) is None:
                return module
    return None


@pytest.mark.parametrize("path", EXAMPLES + DOC_EXAMPLES,
                         ids=[p.relative_to(ROOT).as_posix() for p in EXAMPLES + DOC_EXAMPLES])
def test_complete_example_runs(path, reports):
    text = path.read_bytes()
    assert b"\r\n" not in text, "complete examples must use LF line endings"
    assert text.endswith(b"\n"), "complete examples must end with a newline"
    missing = _missing_sdk(path)
    if missing:
        pytest.skip(f"{missing} not installed")
    _check(reports, path.relative_to(ROOT).as_posix())


@pytest.mark.parametrize("name,source", COMPONENT_APPS, ids=[n for n, _ in COMPONENT_APPS])
def test_component_page_app_runs(name, source, reports):
    compile(source, f"{name}.py", "exec")
    report = _check(reports, f"component:{name}")
    if name in ("buttons", "choice", "form", "confirm", "rating", "card", "list"):
        assert report["actions"], f"{name}: no action was clicked"


def test_component_json_apps_are_current():
    """components.json (what the site renders) holds the same app the generator makes."""
    data = json.loads(COMPONENTS_JSON.read_text(encoding="utf-8"))
    current = dict(COMPONENT_APPS)
    for c in data["components"]:
        assert c.get("app") == current[c["name"]], (
            f"components.json is stale for {c['name']}: run python docs/scripts/gen_components.py")


def test_there_are_doc_examples():
    assert len(EXAMPLES) >= 7
    assert DOC_EXAMPLES, "docs/examples/ holds the complete example of every concept and integration page"
