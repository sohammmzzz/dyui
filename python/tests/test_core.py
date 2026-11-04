"""Core runtime tests: components, catalog/prompt, parser, server routes, actions, CLI."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

import dyui
from dyui import genui, ui
from dyui.cli import main as cli_main


# ------------------------------------------------------------------ helpers
def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        name, data = None, []
        for line in block.split("\n"):
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].strip())
        if name:
            events.append((name, json.loads("\n".join(data) or "{}")))
    return events


def client(app: dyui.App) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def make_app(**kw) -> dyui.App:
    return dyui.App(title="Test", persist=False, **kw)


# ------------------------------------------------------------------ components & prompt
def test_positional_constructors_and_nodes():
    node = ui.Stat("Revenue", "$48k", delta="+12%").to_node()
    assert node["ui"] == "stat" and node["props"]["label"] == "Revenue"
    card = ui.Card(title="T", children=[ui.Markdown("hi")]).to_node()
    assert card["ui"] == "card" and card["children"][0]["ui"] == "markdown"


def test_custom_component_joins_prompt_and_expands():
    app = make_app()

    @app.component
    class Flight(dyui.Component):
        """A bookable flight option."""
        airline: str
        price: float

        def render(self):
            return ui.Card(title=self.airline, children=[ui.Stat("Price", self.price)])

    prompt = app.catalog.prompt()
    assert "flight(" in prompt and "A bookable flight option" in prompt
    node = app.render_catalog.validate({"ui": "flight", "airline": "TAP", "price": 189})
    assert node["ui"] == "card"
    assert any(t["function"]["name"] == "render_flight" for t in app.catalog.tool_schemas("openai"))


def test_component_subset():
    app = make_app(components=["table", "stat"])
    assert set(app.catalog.names) == {"table", "stat"}


@pytest.mark.parametrize("step", [1, 2, 3, 7, 50])
def test_parser_chunk_boundaries(step):
    text = 'Hello **there**.\n```dyui\n{"ui":"stat","label":"Revenue","value":"$48k"}\n{"ui":"nope"}\n```\nBye.'
    p = genui.FenceParser(genui.catalog())
    events = []
    for i in range(0, len(text), step):
        events += p.feed(text[i:i + step])
    events += p.close()
    prose = "".join(e.text for e in events if isinstance(e, genui.TextDelta))
    assert prose.replace("\n", "") == "Hello **there**.Bye."
    ends = [e for e in events if isinstance(e, genui.ComponentEnd)]
    errors = [e for e in events if isinstance(e, genui.ComponentError)]
    assert len(ends) == 1 and ends[0].node["props"]["label"] == "Revenue"
    assert len(errors) == 1


def test_unsafe_urls_dropped():
    node = genui.catalog().validate({"ui": "image", "src": "javascript:alert(1)", "alt": "x"})
    assert node["ui"] == "invalid" or "javascript" not in json.dumps(node.get("props", {}))


# ------------------------------------------------------------------ server
async def test_config_and_chat_stream_persists():
    app = make_app(starters=["Hi"])

    @app.on_message
    async def reply(msg, chat):
        yield f"Echo: {msg.text}. "
        yield '```dyui\n{"ui":"stat","label":"Len","value":%d}\n```\n' % len(msg.text)
        yield ui.Callout("done", level="success")

    async with client(app) as c:
        cfg = (await c.get("/api/config")).json()
        assert cfg["title"] == "Test" and cfg["starters"][0]["message"] == "Hi"
        r = await c.post("/api/chat", json={"thread_id": None, "message": {"text": "hello"}})
        events = parse_sse(r.text)
        names = [e for e, _ in events]
        assert names[0] == "thread" and "user_message" in names and names[-1] == "done"
        uis = [d["node"]["ui"] for e, d in events if e == "ui"]
        assert "stat" in uis and "callout" in uis
        tid = events[0][1]["id"]
        thread = (await c.get(f"/api/threads/{tid}")).json()
        assert [m["role"] for m in thread["messages"]] == ["user", "assistant"]
        assert thread["title"] == "hello"
        assert (await c.get("/api/threads")).json()["threads"][0]["id"] == tid


async def test_threads_are_private_per_browser():
    app = make_app()

    @app.on_message
    def reply(msg, chat):
        return "ok"

    async with client(app) as a, client(app) as b:
        r = await a.post("/api/chat", json={"message": {"text": "x"}})
        tid = parse_sse(r.text)[0][1]["id"]
        assert (await b.get(f"/api/threads/{tid}")).status_code == 404


async def test_action_handler_and_forged_action():
    app = make_app()
    seen = {}

    @app.on_message
    async def reply(msg, chat):
        yield ui.Buttons(ui.Button("Go", action="go", data={"n": 1}))

    @app.on_action("go")
    async def go(action, chat):
        seen["data"] = action.data
        yield "went"

    async with client(app) as c:
        ev = parse_sse((await c.post("/api/chat", json={"message": {"text": "x"}})).text)
        tid = ev[0][1]["id"]
        node = next(d for e, d in ev if e == "ui")
        base = {"thread_id": tid, "message_id": node["message_id"], "component_id": node["node"]["id"]}
        bad = await c.post("/api/action", json={**base, "action": "steal"})
        assert bad.status_code == 400
        ok = parse_sse((await c.post("/api/action", json={**base, "action": "go", "label": "Go", "data": {"n": 1}})).text)
        assert any(e == "ui" and d["node"]["props"].get("__resolved__") for e, d in ok)
        assert "".join(d["delta"] for e, d in ok if e == "text") == "went"
        assert seen["data"] == {"n": 1}


async def test_unhandled_action_falls_back_to_on_message():
    app = make_app()
    texts = []

    @app.on_message
    async def reply(msg, chat):
        texts.append(msg.text)
        if msg.action is None:
            yield ui.Buttons(ui.Button("Pick", action="pick"))
        else:
            yield "picked"

    async with client(app) as c:
        ev = parse_sse((await c.post("/api/chat", json={"message": {"text": "x"}})).text)
        tid = ev[0][1]["id"]
        n = next(d for e, d in ev if e == "ui")
        await c.post("/api/action", json={"thread_id": tid, "message_id": n["message_id"],
                                          "component_id": n["node"]["id"], "action": "pick", "label": "Pick"})
    assert texts[-1].startswith("[action:pick]")


async def test_ask_round_trip():
    app = make_app()

    @app.on_message
    async def reply(msg, chat):
        answer = await chat.ask(ui.Confirm(title="Sure?"), timeout=5)
        yield f"confirmed={answer.values.get('confirmed')}"

    async with client(app) as c:
        await c.get("/api/config")  # establish the identity cookie (a browser gets it from the stream's headers)

        async def run_chat():
            return await c.post("/api/chat", json={"message": {"text": "x"}})

        task = asyncio.create_task(run_chat())
        for _ in range(100):
            await asyncio.sleep(0.02)
            if app._pending:
                break
        (tid, cid), (fut, turn) = next(iter(app._pending.items()))
        r = await c.post("/api/action", json={"thread_id": tid, "message_id": turn.message["id"], "component_id": cid,
                                              "action": "confirm", "label": "Confirm", "values": {"confirmed": True}})
        assert r.status_code == 200
        events = parse_sse((await task).text)
        assert "confirmed=True" in "".join(d["delta"] for e, d in events if e == "text")


async def test_regenerate_and_steps_and_errors():
    app = make_app()
    calls = []

    @app.on_message
    async def reply(msg, chat):
        calls.append(msg.text)
        async with chat.step("Thinking") as s:
            s.output = 42
        if len(calls) > 1:
            raise RuntimeError("boom")
        yield "first"

    async with client(app) as c:
        ev = parse_sse((await c.post("/api/chat", json={"message": {"text": "q"}})).text)
        tid = ev[0][1]["id"]
        steps = [d["step"]["status"] for e, d in ev if e == "step"]
        assert steps[-1] == "done"
        ev2 = parse_sse((await c.post("/api/chat", json={"thread_id": tid, "regenerate": True})).text)
        assert any(e == "error" for e, _ in ev2) and "boom" not in json.dumps(ev2)
        msgs = (await c.get(f"/api/threads/{tid}")).json()["messages"]
        assert calls == ["q", "q"] and len(msgs) == 2


async def test_password_gate_and_bad_body():
    app = make_app(password="s3cret")

    @app.on_message
    def reply(msg, chat):
        return "ok"

    async with client(app) as c:
        assert (await c.get("/api/config")).json()["authenticated"] is False
        assert (await c.get("/api/threads")).status_code == 401
        assert (await c.post("/api/login", json={"password": "nope"})).status_code == 401
        assert (await c.post("/api/login", json={"password": "s3cret"})).status_code == 200
        assert (await c.get("/api/threads")).status_code == 200
        assert (await c.post("/api/chat", content=b"{not json")).status_code == 400


async def test_upload_and_file_scoping(tmp_path):
    app = dyui.App(title="T", persist=False, data_dir=tmp_path)

    @app.on_message
    def reply(msg, chat):
        return f"files={[f.name for f in msg.files]}"

    async with client(app) as c, client(app) as other:
        up = (await c.post("/api/upload", files={"file": ("notes.txt", b"hello", "text/plain")})).json()
        assert up["size"] == 5
        assert (await c.get(f"/api/files/{up['id']}")).content == b"hello"
        assert (await other.get(f"/api/files/{up['id']}")).status_code == 404
        ev = parse_sse((await c.post("/api/chat", json={"message": {"text": "x", "files": [up["id"]]}})).text)
        assert "notes.txt" in "".join(d["delta"] for e, d in ev if e == "text")


def test_html_template_traversal(tmp_path):
    (tmp_path / "card.html").write_text("<b>{{ name }}</b>{{{ raw }}}")
    node = dyui.html_template("card.html", root=tmp_path, name="<x>", raw="<i>ok</i>").to_node()
    assert "&lt;x&gt;" in node["props"]["html"] and "<i>ok</i>" in node["props"]["html"]
    with pytest.raises(ValueError):
        dyui.html_template("../secret.html", root=tmp_path)


# ------------------------------------------------------------------ CLI
def test_cli_catalog_new_and_init(tmp_path, monkeypatch, capsys):
    app_file = tmp_path / "app.py"
    app_file.write_text("import dyui\napp = dyui.App(title='Cli', persist=False, components=['table'])\n")
    monkeypatch.chdir(tmp_path)
    assert cli_main(["catalog", "app.py"]) == 0
    assert "table(" in capsys.readouterr().out
    assert cli_main(["new", "my-bot", "--template", "basic"]) == 0
    assert (tmp_path / "my-bot" / "app.py").is_file()
    assert "{{title}}" not in (tmp_path / "my-bot" / "app.py").read_text()
    monkeypatch.setenv("DYUI_NO_LAUNCH", "1")
    assert cli_main(["claude", "init", "app.py"]) == 0
    assert (tmp_path / ".dyui" / "INIT_PROMPT.md").is_file()


async def test_demo_app_streams_components():
    from dyui.demo import app as demo

    async with client(demo) as c:
        ev = parse_sse((await c.post("/api/chat", json={"message": {"text": "Analyze Q3 sales"}})).text)
        uis = {d["node"]["ui"] for e, d in ev if e == "ui" and d["node"].get("status") == "done"}
        assert {"stats", "chart", "table", "callout"} <= uis
        assert not any(d["node"]["ui"] == "invalid" for e, d in ev if e == "ui")
