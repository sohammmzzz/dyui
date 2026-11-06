"""Regression tests for bugs confirmed by the 1.0 code review."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path

import httpx
import pytest

import dyui
from dyui import ui


def client(app: dyui.App) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def events(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        name, data = None, None
        for line in block.split("\n"):
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
        if name:
            out.append((name, data))
    return out


# ------------------------------------------------------------- (2) on_chat_start session kept
@pytest.mark.parametrize("persist", [False, "sqlite"])
async def test_session_from_on_chat_start_reaches_on_message_and_persists(tmp_path, persist):
    app = dyui.App(persist=False if persist is False else str(tmp_path / "db.sqlite"), data_dir=tmp_path)
    seen = []

    @app.on_chat_start
    async def start(chat):
        chat.session["plan"] = "pro"
        chat.session["count"] = 0

    @app.on_message
    async def reply(msg, chat):
        seen.append(dict(chat.session))
        chat.session["count"] = chat.session.get("count", 0) + 1
        yield "ok"

    async with client(app) as c:
        ev = events((await c.post("/api/chat", json={"thread_id": None, "message": {"text": "hi"}})).text)
        tid = next(d["id"] for e, d in ev if e == "thread")
        await c.post("/api/chat", json={"thread_id": tid, "message": {"text": "again"}})
    assert seen == [{"plan": "pro", "count": 0}, {"plan": "pro", "count": 1}]
    assert (await app.store.get_thread(tid))["session"] == {"plan": "pro", "count": 2}


# ------------------------------------------------------------- (3) concurrent duplicate actions
@pytest.mark.parametrize("persist", [False, "sqlite"])
async def test_concurrent_clicks_run_the_action_once(tmp_path, persist):
    app = dyui.App(persist=False if persist is False else str(tmp_path / "db.sqlite"), data_dir=tmp_path)
    runs = []

    @app.on_message
    async def reply(msg, chat):
        yield ui.Buttons(ui.Button("Book", action="book", data={"id": 1}))

    @app.on_action("book")
    async def book(action, chat):
        runs.append(action.data)
        await asyncio.sleep(0.05)
        yield "booked"

    async with client(app) as c:
        await c.get("/api/config")
        ev = events((await c.post("/api/chat", json={"thread_id": None, "message": {"text": "x"}})).text)
        tid = next(d["id"] for e, d in ev if e == "thread")
        node = next(d for e, d in ev if e == "ui")
        body = {"thread_id": tid, "message_id": node["message_id"], "component_id": node["node"]["id"],
                "action": "book", "label": "Book"}
        rs = await asyncio.gather(*[c.post("/api/action", json=body) for _ in range(6)])
    codes = sorted(r.status_code for r in rs)
    assert len(runs) == 1, codes
    assert codes.count(200) >= 1 and all(code in (200, 409) for code in codes)
    ok_streams = [r for r in rs if r.status_code == 200]
    assert sum("booked" in r.text for r in ok_streams) == 1


async def test_concurrent_answers_to_ask_resolve_once():
    app = dyui.App(persist=False)
    answers = []

    @app.on_message
    async def reply(msg, chat):
        a = await chat.ask(ui.Confirm("Go?"))
        answers.append(a.values)
        yield "done"

    async with client(app) as c:
        await c.get("/api/config")
        chat_task = asyncio.create_task(c.post("/api/chat", json={"thread_id": None, "message": {"text": "x"}}))
        for _ in range(200):
            await asyncio.sleep(0.01)
            if app._pending:
                break
        (tid, cid), (fut, turn) = next(iter(app._pending.items()))
        body = {"thread_id": tid, "message_id": turn.message["id"], "component_id": cid, "action": "confirm"}
        rs = await asyncio.gather(*[c.post("/api/action", json={**body, "values": {"confirmed": i % 2 == 0}})
                                    for i in range(5)])
        await chat_task
    assert len(answers) == 1
    assert sorted(r.status_code for r in rs).count(409) >= 4 or sum("error" in r.text for r in rs) >= 4


def test_stale_claims_expire(monkeypatch):
    import dyui.app as app_mod

    app = dyui.App(persist=False)
    req = {"thread_id": "t", "component_id": "c"}
    assert app.claim_action(req) == ("t", "c")
    assert app.claim_action(req) is None
    monkeypatch.setattr(app_mod, "_CLAIM_TTL_S", 0.0)
    assert app.claim_action(req) == ("t", "c")


# ------------------------------------------------------------- (6) feedback handler
async def test_feedback_handler_session_saved_and_send_warned(caplog):
    app = dyui.App(persist=False)

    @app.on_message
    async def reply(msg, chat):
        yield "answer"

    @app.on_feedback
    async def fb(feedback, chat):
        chat.session["votes"] = chat.session.get("votes", 0) + feedback.value
        await chat.send("thanks!")  # can't be delivered: must be ignored with a warning

    async with client(app) as c:
        ev = events((await c.post("/api/chat", json={"thread_id": None, "message": {"text": "x"}})).text)
        tid = next(d["id"] for e, d in ev if e == "thread")
        mid = next(d["id"] for e, d in ev if e == "message_start")
        with caplog.at_level(logging.WARNING, logger="dyui"):
            r = await c.post("/api/feedback", json={"thread_id": tid, "message_id": mid, "value": 1})
    assert r.status_code == 200
    assert (await app.store.get_thread(tid))["session"] == {"votes": 1}
    assert any("on_feedback can't send" in rec.message for rec in caplog.records)
    assert not app._live_messages


async def test_failing_feedback_handler_is_not_a_500():
    app = dyui.App(persist=False)

    @app.on_message
    async def reply(msg, chat):
        yield "answer"

    @app.on_feedback
    def fb(feedback, chat):
        raise RuntimeError("boom")

    async with client(app) as c:
        ev = events((await c.post("/api/chat", json={"thread_id": None, "message": {"text": "x"}})).text)
        tid = next(d["id"] for e, d in ev if e == "thread")
        mid = next(d["id"] for e, d in ev if e == "message_start")
        r = await c.post("/api/feedback", json={"thread_id": tid, "message_id": mid, "value": -1})
    assert r.status_code == 200


# ------------------------------------------------------------- (7) streaming forever after restart
async def test_orphaned_streaming_message_shows_cancelled(tmp_path):
    db = str(tmp_path / "db.sqlite")
    app = dyui.App(persist=db, data_dir=tmp_path)

    @app.on_message
    async def reply(msg, chat):
        await chat.ask(ui.Confirm("Go?"))
        yield "never"

    async with client(app) as c:
        await c.get("/api/config")
        task = asyncio.create_task(c.post("/api/chat", json={"thread_id": None, "message": {"text": "x"}}))
        for _ in range(200):
            await asyncio.sleep(0.01)
            if app._pending:
                break
        (tid, _), _ = next(iter(app._pending.items()))
        live = (await c.get(f"/api/threads/{tid}")).json()
        assert live["messages"][-1]["status"] == "streaming"  # still genuinely live
        cookies = dict(c.cookies)
        task.cancel()
        with pytest.raises(BaseException):
            await task

    restarted = dyui.App(persist=db, data_dir=tmp_path)  # same database, nothing live
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=restarted), base_url="http://test",
                                 cookies=cookies) as c2:
        stored = await restarted.store.get_messages(tid)
        if stored[-1]["status"] == "streaming":  # persisted mid-ask, process "died"
            thread = (await c2.get(f"/api/threads/{tid}")).json()
            assert thread["messages"][-1]["status"] == "cancelled"


async def test_streaming_status_rewrite_only_for_orphans():
    app = dyui.App(persist=False)
    thread = await app.store.create_thread("u_x")
    await app.store.put_message(thread["id"], {"id": "m_orphan", "role": "assistant", "created_at": 1,
                                               "parts": [], "status": "streaming"})
    await app.store.put_message(thread["id"], {"id": "m_live", "role": "assistant", "created_at": 2,
                                               "parts": [], "status": "streaming"})
    app._live_messages.add("m_live")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                                 cookies={"dyui_uid": "u_x"}) as c:
        msgs = (await c.get(f"/api/threads/{thread['id']}")).json()["messages"]
    assert [m["status"] for m in msgs] == ["cancelled", "streaming"]


# ------------------------------------------------------------- (8) Windows app paths
@pytest.mark.parametrize("target,expected", [
    ("app.py", ("app.py", None)),
    ("app.py:bot", ("app.py", "bot")),
    (r"C:\proj\app.py", (r"C:\proj\app.py", None)),
    (r"C:\proj\app.py:bot", (r"C:\proj\app.py", "bot")),
    ("D:/x/y/main.py:app", ("D:/x/y/main.py", "app")),
    ("pkg.mod:app", ("pkg.mod", "app")),
    ("pkg.mod", ("pkg.mod", None)),
])
def test_split_target(target, expected):
    from dyui.cli import split_target

    assert split_target(target) == expected


def test_serve_uses_drive_aware_split_for_reload(monkeypatch, tmp_path):
    import dyui.cli as cli

    calls = {}

    class FakeUvicorn:
        @staticmethod
        def run(*args, **kwargs):
            calls.update(kwargs, target=args[0])

    monkeypatch.setitem(__import__("sys").modules, "uvicorn", FakeUvicorn)
    app_file = tmp_path / "proj" / "app.py"
    app_file.parent.mkdir()
    app_file.write_text("import dyui\napp = dyui.App(persist=False)\n", encoding="utf-8")
    cli._serve(f"{app_file}:app", "127.0.0.1", 8999, reload=True, open_browser=False)
    assert calls["reload"] is True and calls["reload_dirs"] == [str(app_file.parent.resolve())]
    assert calls["server_header"] is False


# ------------------------------------------------------------- hatch build hook
def test_hatch_rebuilds_stale_static(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("hatch_build", Path(__file__).parents[1] / "hatch_build.py")
    try:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    except ImportError:
        pytest.skip("hatchling not installed")
    web, static = tmp_path / "web", tmp_path / "static"
    (web / "src").mkdir(parents=True)
    (web / "src" / "main.tsx").write_text("x", encoding="utf-8")
    assert mod.needs_web_build(web, static)                      # nothing built yet
    static.mkdir()
    (static / "index.html").write_text("<html>", encoding="utf-8")
    old = time.time() - 100
    os.utime(static / "index.html", (old, old))
    assert mod.needs_web_build(web, static)                      # sources newer -> rebuild
    new = time.time() + 100
    os.utime(static / "index.html", (new, new))
    assert not mod.needs_web_build(web, static)                  # fresh build -> skip
    assert mod.needs_web_build(web, static, force=True)
