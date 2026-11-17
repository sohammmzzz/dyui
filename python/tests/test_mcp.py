"""The DyUI MCP server: docs reader, component introspection, validators and the MCP wiring.

Everything is offline. Tools are tested as plain functions and through the SDK's in-memory
client; one test drives ``python -m dyui.mcp`` over real stdio.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import queue
import subprocess
import sys
import threading
import types
from pathlib import Path

import pytest

import dyui
from dyui.cli import main as cli_main
from dyui.genui import catalog
from dyui.mcp import check, docs, introspect, server

REPO = Path(__file__).resolve().parents[2]
PKG_PARENT = Path(dyui.__file__).resolve().parents[1]
HAS_MCP = dyui.mcp.available()
needs_mcp = pytest.mark.skipif(not HAS_MCP, reason="the mcp SDK is not installed")
needs_repo = pytest.mark.skipif(not (REPO / "docs" / "src" / "content" / "docs").is_dir(),
                                reason="runs from a source checkout")

EXPECTED_TOOLS = {"dyui_overview", "list_docs", "read_doc", "search_docs", "list_components", "get_component",
                  "list_examples", "get_example", "get_template", "validate_ui", "check_app", "catalog_prompt"}


# ------------------------------------------------------------------ in-memory client (mcp 1.x and 2.x)
def _text(result) -> str:
    return "".join(getattr(c, "text", "") for c in result.content)


def _is_error(result) -> bool:
    return bool(getattr(result, "is_error", None) or getattr(result, "isError", None))


async def _session(fn):
    srv = server.build_server()
    try:
        from mcp import Client  # mcp 2.x

        async with Client(srv) as client:
            return await fn(client)
    except ImportError:  # mcp 1.x
        from mcp.shared.memory import create_connected_server_and_client_session

        async with create_connected_server_and_client_session(srv._mcp_server) as client:
            return await fn(client)


def run_client(fn):
    return asyncio.run(_session(fn))


# ------------------------------------------------------------------ the SDK wiring
@needs_mcp
def test_server_lists_every_tool_prompt_and_resource():
    async def go(c):
        tools = (await c.list_tools()).tools
        prompts = (await c.list_prompts()).prompts
        resources = (await c.list_resources()).resources
        return tools, prompts, resources

    tools, prompts, resources = run_client(go)
    assert {t.name for t in tools} == EXPECTED_TOOLS
    assert all(t.description for t in tools)
    assert {p.name for p in prompts} == {"build_app", "convert_project", "design_components", "production_checklist"}
    uris = {str(r.uri) for r in resources}
    assert "dyui://components/table" in uris and "dyui://examples/no_llm" in uris
    assert any(u.startswith("dyui://docs/concepts/") for u in uris)


@needs_mcp
def test_tools_answer_through_the_client():
    async def go(c):
        table = await c.call_tool("get_component", {"name": "table"})
        bad = await c.call_tool("get_component", {"name": "nope"})
        ok = await c.call_tool("validate_ui", {"payload": '{"ui":"stat","label":"Users","value":42}'})
        obj = await c.call_tool("validate_ui", {"payload": {"ui": "stat", "label": "Users"}})
        doc = await c.read_resource("dyui://components/confirm")
        prompt = await c.get_prompt("design_components", {"app_path": "bot.py"})
        return table, bad, ok, obj, doc, prompt

    table, bad, ok, obj, doc, prompt = run_client(go)
    assert not _is_error(table) and "ui.Table(columns, rows" in _text(table) and '"ui":"table"' in _text(table)
    assert _text(bad).startswith("Error: no built-in component 'nope'")
    assert _text(ok).startswith("OK")
    assert "value: Field required" in _text(obj)
    assert '"confirmed": true | false' in doc.contents[0].text
    msg = prompt.messages[0].content.text
    assert "bot.py" in msg and "### D. Design custom components" in msg and "dyui_overview" in msg


def _stdio_exchange(messages: list[dict], *, expect: int, timeout: float = 60.0) -> list[dict]:
    path = os.pathsep.join(p for p in (str(PKG_PARENT), os.environ.get("PYTHONPATH", "")) if p)
    env = dict(os.environ, PYTHONPATH=path, PYTHONIOENCODING="utf-8")
    proc = subprocess.Popen([sys.executable, "-m", "dyui.mcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env, cwd=str(REPO))
    lines: queue.Queue = queue.Queue()
    threading.Thread(target=lambda: [lines.put(ln) for ln in proc.stdout], daemon=True).start()
    out: list[dict] = []
    try:
        for msg in messages:
            proc.stdin.write((json.dumps(msg) + "\n").encode())
            proc.stdin.flush()
            if "id" in msg:
                while True:
                    try:
                        line = lines.get(timeout=timeout)
                    except queue.Empty:  # pragma: no cover - show why the server died
                        proc.kill()
                        pytest.fail(f"no reply to {msg['method']}: {proc.stderr.read().decode(errors='replace')[-2000:]}")
                    reply = json.loads(line)
                    if reply.get("id") == msg["id"]:
                        out.append(reply)
                        break
        assert len(out) == expect
        return out
    finally:
        proc.stdin.close()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:  # pragma: no cover
            proc.kill()


@needs_mcp
def test_stdio_end_to_end():
    init, listed, table = _stdio_exchange([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "pytest", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "get_component", "arguments": {"name": "table"}}},
    ], expect=3)
    assert init["result"]["serverInfo"]["name"] == "dyui"
    assert "dyui_overview" in init["result"]["instructions"]
    assert {t["name"] for t in listed["result"]["tools"]} == EXPECTED_TOOLS
    text = "".join(c.get("text", "") for c in table["result"]["content"])
    assert "# table" in text and '"columns"' in text


def test_dyui_mcp_without_the_sdk_exits_2(monkeypatch, capsys):
    monkeypatch.setattr(dyui.mcp, "available", lambda: False)
    assert cli_main(["mcp"]) == 2
    assert 'pip install "dyui[mcp]"' in capsys.readouterr().err


def test_server_main_reports_a_missing_sdk(monkeypatch, capsys):
    def boom():
        raise ImportError("No module named 'mcp'", name="mcp")

    monkeypatch.setattr(server, "build_server", boom)
    assert server.main() == 2
    assert 'pip install "dyui[mcp]"' in capsys.readouterr().err


def test_tools_never_raise():
    def broken() -> str:
        raise RuntimeError("nvapi-" + "x" * 30)

    safe = server._safe(broken)
    out = safe()
    assert out.startswith("Error: broken failed: RuntimeError") and "x" * 30 not in out


# ------------------------------------------------------------------ components
@pytest.mark.parametrize("cls", introspect.component_classes(), ids=lambda c: c.__dyui__.name)
def test_get_component_schema_validates_its_own_examples(cls):
    d = introspect.component_detail(cls)
    assert d["props_schema"]["type"] == "object" and d["fields"] is not None
    assert d["python_examples"], "every built-in has a working Python example"
    for code in d["python_examples"]:
        eval(code, {"ui": dyui.ui, "dyui": dyui}).to_node()  # noqa: S307
    if not cls.__dyui__.llm:
        assert d["llm_fence"] == ""
        return
    assert d["llm_examples"], "every model-facing component shows what the model writes"
    assert d["prompt_line"] in catalog().prompt()
    jsonschema = pytest.importorskip("jsonschema")
    for line in d["llm_examples"]:
        obj = json.loads(line)
        node = catalog().validate(obj)
        assert node["status"] != "error", (line, node)
        props = {k: v for k, v in obj.items() if k != "ui"}
        jsonschema.validate(props, d["props_schema"])


def test_get_component_lookup_is_forgiving_and_documents_actions():
    for name in ("keyvalue", "KeyValue", "ui.KeyValue", "key-value"):
        assert introspect.find_component(name) is dyui.ui.KeyValue, name
    form = server.get_component("form")
    assert "form_submit" in form and "## Actions" in form
    assert server.get_component("html").count("Developer-only") == 1
    listed = server.list_components()
    assert all(f"| `{n}` |" in listed for n in catalog().names)


def test_component_records_match_the_docs_data():
    """gen_components.py writes these records; the committed JSON must be what they produce."""
    data = REPO / "docs" / "src" / "data" / "components.json"
    if not data.is_file():
        pytest.skip("runs from a source checkout")
    committed = json.loads(data.read_text(encoding="utf-8"))["components"]
    live = [introspect.component_record(c) for c in introspect.component_classes()]
    assert live == committed


def test_skill_components_come_from_introspection():
    text = dyui.agents.render_skill()
    assert introspect.signature_lines() in text


# ------------------------------------------------------------------ validate_ui
REPLY = 'Here are the numbers.\n```dyui\n{"ui":"stat","label":"Users","value":1200}\n```\nUp 12% on last week.\n'


def test_validate_ui_good_bad_and_partial():
    good = check.validate_ui(REPLY)
    assert good["ok"] and good["mode"] == "reply" and good["prose_chars"] > 0 and not good["warnings"]

    bad = check.validate_ui('Look:\n```dyui\n{"ui":"chart","kind":"radar","series":[]}\n```\nDone.')
    assert not bad["ok"] and bad["components"][0]["path"] == "kind"

    partial = check.validate_ui('Look:\n```dyui\n{"ui":"stat","label":"Users",')
    assert not partial["ok"] and "incomplete" in partial["components"][0]["error"]
    assert any("not closed" in w for w in partial["warnings"])

    alone = check.validate_ui('```dyui\n{"ui":"stat","label":"A","value":1}\n```')
    assert alone["ok"] and any("no prose" in w for w in alone["warnings"])

    none = check.validate_ui("Just text, no components.")
    assert not none["ok"] and any("No components" in w for w in none["warnings"])


def test_validate_ui_objects_lists_and_json_lines():
    assert check.validate_ui({"ui": "stat", "label": "A", "value": 1})["ok"]
    lines = '{"ui":"stat","label":"A","value":1}\n{"ui":"callout","text":"Saved.","level":"success"}'
    assert check.validate_ui(lines)["mode"] == "objects" and check.validate_ui(lines)["ok"]
    mixed = check.validate_ui([{"ui": "stat", "label": "A", "value": 1}, {"ui": "flight", "airline": "TAP"}])
    assert [c["ok"] for c in mixed["components"]] == [True, False]
    assert "check_app" in mixed["components"][1]["hint"]
    limited = check.validate_ui({"ui": "table", "columns": ["a"], "rows": [["1"]]}, components=["stat"])
    assert not limited["ok"]
    text = server.validate_ui(REPLY)
    assert text.startswith("OK (1 component(s))") and json.loads(text.split("\n\n", 1)[1])["ok"]


# ------------------------------------------------------------------ check_app
def _app(tmp_path: Path, body: str, name: str = "app.py") -> Path:
    (tmp_path / ".gitignore").write_text(".dyui/\n", encoding="utf-8")
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


CUSTOM_APP = '''\
import os
import dyui
from dyui import ui

app = dyui.App(title="Flights", persist=False)


@app.component
class Flight(dyui.Component):
    """A bookable flight option."""

    airline: str
    price: float
    examples = [{"airline": "TAP", "price": 189}]

    def render(self):
        return ui.Card(self.airline, ui.Stat("Price", f"${self.price:.0f}"))


@app.on_message
async def reply(msg, chat):
    async for part in dyui.llm.stream(os.getenv("DYUI_MODEL", "nvidia/x"), chat.history, components=app.catalog):
        yield part


@app.on_action("book")
async def book(action, chat):
    yield "Booked."
'''


@needs_repo
def test_check_app_on_the_no_llm_example():
    report = check.check_app(REPO / "examples" / "no_llm.py")
    assert report["ok"], check.format_check(report)
    assert report["handlers"]["on_message"] == "reply" and "choice" in report["handlers"]["on_action"]
    assert "table" in report["catalog"] and report["tokens_fence"] > 100
    assert not report["errors"]


def test_check_app_reports_custom_components_and_handlers(tmp_path):
    report = check.check_app(_app(tmp_path, CUSTOM_APP))
    assert report["ok"], check.format_check(report)
    assert report["app_var"] == "app" and report["handlers"]["on_action"] == {"book": "book"}
    (flight,) = report["custom_components"]
    assert flight["name"] == "flight" and flight["example_results"] == [{"ok": True, "error": None}]
    assert "flight" in report["catalog"] and not report["warnings"]
    text = server.check_app(str(tmp_path / "app.py"))
    assert text.startswith("OK:") and "flight (Flight): 1/1 examples valid" in text


def test_check_app_syntax_error(tmp_path):
    report = check.check_app(_app(tmp_path, "import dyui\napp = dyui.App(\n    title='x'\nprint(1)\n"))
    assert not report["ok"] and report["errors"][0]["kind"] == "syntax_error"
    report = check.check_app(_app(tmp_path, "async def reply(msg, chat):\n    yield 1\n    return 2\n"))
    assert report["errors"][0]["kind"] == "syntax_error" and "return" in report["errors"][0]["message"]


def test_check_app_import_error_has_a_traceback(tmp_path):
    report = check.check_app(_app(tmp_path, "import dyui\nimport not_a_real_module_xyz\napp = dyui.App()\n"))
    (err,) = report["errors"]
    assert err["kind"] == "import_error" and "not_a_real_module_xyz" in err["message"]
    assert "Traceback" in err["traceback"]


def test_check_app_hard_coded_key_is_flagged_and_never_printed(tmp_path):
    key = "nvapi-" + "Ab3" * 12
    body = f'import dyui\nKEY = "{key}"\napp = dyui.App(persist=False)\n\n@app.on_message\ndef reply(m, c):\n    return "hi"\n'
    report = check.check_app(_app(tmp_path, body))
    assert [w["kind"] for w in report["warnings"]] == ["hardcoded_key"]
    text = check.format_check(report) + json.dumps(report)
    assert key not in text and "nvapi-…(masked)" in text


def test_check_app_missing_components_and_blocking_calls(tmp_path):
    body = (
        "import time, requests\nimport dyui\nfrom dyui.llm import stream\napp = dyui.App(persist=False)\n\n"
        "@app.on_message\nasync def reply(msg, chat):\n    time.sleep(1)\n    requests.get('http://x')\n"
        "    async for p in dyui.llm.stream('nvidia/x', chat.history):\n        yield p\n"
        "    async for p in stream('nvidia/x', chat.history, components=app.catalog):\n        yield p\n"
    )
    scan = check.scan_source(body)
    kinds = sorted(w["kind"] for w in scan["warnings"])
    assert kinds == ["blocking_call", "blocking_call", "no_components"]
    assert next(w for w in scan["warnings"] if w["kind"] == "no_components")["line"] == 10


def test_check_app_no_app_no_handler_gitignore_and_timeout(tmp_path):
    report = check.check_app(_app(tmp_path, "x = 1\n"))
    assert report["errors"][0]["kind"] == "no_app"
    report = check.check_app(_app(tmp_path, "import dyui\napp = dyui.App(persist=False)\n"))
    assert report["errors"][0]["kind"] == "no_on_message"
    (tmp_path / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    warnings = check.scan_source("")["warnings"] + [check._gitignore_warning(tmp_path / "app.py")]
    assert warnings[-1]["kind"] == "gitignore"
    slow = _app(tmp_path, "import time\ntime.sleep(30)\n", "slow.py")
    report = check.check_app(slow, timeout=2)
    assert "longer than 2s" in report["errors"][0]["message"]
    assert check.check_app(tmp_path / "missing.py")["errors"][0]["kind"] == "not_found"


def test_check_app_output_the_app_prints_does_not_break_the_report(tmp_path):
    body = 'import dyui\nprint("hello from import")\napp = dyui.App(persist=False)\n\n@app.on_message\ndef r(m, c):\n    return "x"\n'
    assert check.check_app(_app(tmp_path, body))["ok"]


def test_catalog_prompt_builtins_and_app(tmp_path):
    out = check.catalog_prompt(only=["stat", "table"])
    assert out["ok"] and out["names"] == ["table", "stat"] and "## UI components" in out["prompt"]
    assert not check.catalog_prompt(only=["nope"])["ok"]
    app = check.catalog_prompt(_app(tmp_path, CUSTOM_APP))
    assert app["ok"] and "flight(" in app["prompt"] and "flight" in app["names"]
    text = server.catalog_prompt(str(tmp_path / "app.py"), ["flight"])
    assert "flight(" in text and "-- 1 components" in text
    assert server.catalog_prompt(str(tmp_path / "nope.py")).startswith("Error:")


# ------------------------------------------------------------------ docs
@needs_repo
def test_read_doc_resolves_the_data_analyst_cookbook_to_the_full_source():
    text = server.read_doc("cookbook/data-analyst")
    source = (REPO / "examples" / "data_analyst.py").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert text.startswith("# Data analyst\n")
    assert source.strip() in text
    assert 'title="examples/data_analyst.py"' in text
    assert "import " not in text.split("```", 1)[0]  # the MDX import lines are gone
    assert "<Code" not in text


@needs_repo
def test_list_docs_and_lookup():
    slugs = {p.slug for p in docs.pages()}
    assert {"concepts/actions", "cookbook/data-analyst", "get-started/quickstart", "changelog"} <= slugs
    assert not any(s.startswith("reference/api") for s in slugs) and "index" not in slugs
    listed = server.list_docs()
    assert "`concepts/actions`" in listed and "## concepts" in listed
    for alias in ("/dyui/concepts/actions/", "https://sohammmzzz.github.io/dyui/concepts/actions/", "actions",
                  "dyui://docs/concepts/actions", "concepts/actions.md"):
        assert docs.page(alias).slug == "concepts/actions", alias
    assert server.read_doc("no/such/page").startswith("Error: no docs page")
    assert "## 1.2.0" in server.read_doc("changelog")  # `import { Content }` of CHANGELOG.md is inlined


@needs_repo
def test_search_docs_finds_the_right_places():
    hits = docs.search("on_action handler for a button")
    assert any(h["kind"] == "doc" and h["ref"] == "concepts/actions" for h in hits[:5])
    assert docs.search("confirm dialog")[0]["kind"] in ("component", "doc")
    assert docs.search("") == [] and docs.search("the a of") == []
    text = server.search_docs("langgraph emit")
    assert "read_doc('integrations/langgraph')" in text or "get_example('langgraph_agent')" in text
    assert server.search_docs("zzzzqqqq").startswith("No results")


def test_resolve_mdx_contract(tmp_path):
    root = tmp_path
    pages_dir = root / "docs" / "src" / "content" / "docs" / "guide"
    pages_dir.mkdir(parents=True)
    (root / "examples").mkdir()
    (root / "examples" / "demo.py").write_text("print('hi')\n", encoding="utf-8")
    (root / "NOTES.md").write_text("---\ntitle: x\n---\n# Notes\nHello notes.\n", encoding="utf-8")
    (tmp_path.parent / "secret.txt").write_text("TOP SECRET", encoding="utf-8")
    mdx = '''import { Code, Tabs, TabItem, Aside } from "@astrojs/starlight/components";
import Demo from "../../../../../examples/demo.py?raw";
import { Content as Notes } from "../../../../../NOTES.md";
import Secret from "../../../../../../secret.txt?raw";
import Widget from "../../../components/Widget.astro";

Intro text.

<Widget client:load />

<Tabs>
  <TabItem label="macOS">
```bash
export KEY=1
```
  </TabItem>
  <TabItem label="Windows">
Use `$env:KEY="1"`.
  </TabItem>
</Tabs>

<Aside type="tip" title="Heads up">Inner **text** stays.</Aside>

<Code code={Demo} lang="python" title="examples/demo.py" />
<Code code={Secret} lang="text" />

<Notes />

```jsx
<Tabs>kept inside code</Tabs>
import x from "y";
```
'''
    out = docs.resolve_mdx(mdx, pages_dir, docs.DocsRoot(root, "test"))
    assert "import " not in out.split("```jsx")[0]
    assert "**macOS**" in out and "**Windows**" in out and "<TabItem" not in out and "<Tabs>\n  " not in out
    assert "**Heads up**" in out and "Inner **text** stays." in out
    assert '```python title="examples/demo.py"\nprint(\'hi\')\n```' in out
    assert "TOP SECRET" not in out  # outside the docs root: never read
    assert "Hello notes." in out and "title: x" not in out
    assert "<Widget" not in out
    assert "```jsx\n<Tabs>kept inside code</Tabs>\nimport x from \"y\";\n```" in out


def test_frontmatter():
    meta, body = docs.split_frontmatter('---\ntitle: "A: B"\ndescription: d\nsidebar:\n  order: 3\n---\n\nBody\n')
    assert meta == {"title": "A: B", "description": "d", "sidebar.order": "3"} and body == "\nBody\n"
    assert docs.split_frontmatter("no header") == ({}, "no header")


@needs_repo
def test_examples_and_templates():
    listed = server.list_examples()
    assert "`no_llm`" in listed and "`nvidia`" in listed
    src = server.get_example("no-llm")
    assert src.startswith("# examples/no_llm.py") and "app = dyui.App(" in src
    assert server.get_example("nope").startswith("Error: no example")
    tpl = server.get_template("nvidia")
    assert "## app.py" in tpl and "## requirements.txt" in tpl and "{{title}}" in tpl
    assert server.get_template("nope").startswith("Error: no template")


@needs_repo
def test_overview_is_complete():
    text = server.dyui_overview()
    assert text.startswith(f"# DyUI {dyui.__version__}")
    for needle in ("## Tools on this server", "## The 30-second model", "NVIDIA_API_KEY", "## Custom components",
                   "## Actions and human-in-the-loop", "build_app", "## Mistakes to avoid", "get_component"):
        assert needle in text, needle
    assert "{{" not in text and "\n## Built-in components\n" in text
    assert "source" in text.splitlines()[-1]


def _load_hatch_build(monkeypatch):
    iface = types.ModuleType("hatchling.builders.hooks.plugin.interface")
    iface.BuildHookInterface = object
    for name in ("hatchling", "hatchling.builders", "hatchling.builders.hooks", "hatchling.builders.hooks.plugin"):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(sys.modules, "hatchling.builders.hooks.plugin.interface", iface)
    spec = importlib.util.spec_from_file_location("dyui_hatch_build", REPO / "python" / "hatch_build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@needs_repo
def test_bundled_docs_work_like_the_checkout(tmp_path, monkeypatch):
    """What the wheel ships (dyui/_docs, built by hatch_build.py) reads the same as the repo."""
    hb = _load_hatch_build(monkeypatch)
    dest = tmp_path / "_docs"
    count = hb.bundle_docs(REPO, dest)
    assert count > 20 and (dest / "examples" / "no_llm.py").is_file() and (dest / "CHANGELOG.md").is_file()
    assert not (dest / "docs" / "src" / "content" / "docs" / "reference" / "api").exists()
    monkeypatch.setenv("DYUI_DOCS_ROOT", str(dest))
    assert docs.root().kind == "env"
    text = server.read_doc("cookbook/data-analyst")
    assert "CATALOG" in text and "<Code" not in text
    assert "no_llm" in docs.examples()
    (dest / "stale.md").write_text("x", encoding="utf-8")
    hb.bundle_docs(REPO, dest)  # rebuilt from scratch
    assert not (dest / "stale.md").exists()
