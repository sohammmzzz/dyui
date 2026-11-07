"""Regression tests for the 1.0 backend VAPT (see security/vapt-backend.md).

Each section names the finding it locks down.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time

import httpx
import pytest

import dyui
from dyui import genui, ui
from dyui._jsonsafe import MAX_DEPTH, too_deep
from dyui.genui import FenceParser
from dyui.genui.parser import MAX_COMPONENT_CHARS, MAX_PARTIAL_CHARS
from dyui.ui.registry import BUILTINS


def client(app: dyui.App, **headers) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=headers)


def make_app(**kw) -> dyui.App:
    kw.setdefault("persist", False)
    return dyui.App(title="Test", **kw)


def stream(parser: FenceParser, text: str, chunk: int = 7) -> list:
    out = []
    for i in range(0, len(text), chunk):
        out += parser.feed(text[i:i + chunk])
    return out + parser.close()


def table_line(chars: int) -> str:
    rows = ",".join(['["aaaa",1]'] * (chars // 10))
    return '{"ui":"table","columns":["a","b"],"rows":[' + rows + "]}"


def deep_card(levels: int) -> str:
    return '{"ui":"card","children":[' * levels + '{"ui":"markdown","text":"x"}' + "]}" * levels


CATALOG = genui.Catalog(list(BUILTINS))


# ===================================================================== V-01 quadratic parser DoS
def test_long_component_line_parses_in_linear_time():
    # 8 kB used to take ~8 s (every 7-char chunk re-parsed and re-validated the whole line);
    # 400 kB must now finish well under a few seconds.
    text = "```dyui\n" + table_line(400_000) + "\n```\nafter\n"
    t0 = time.perf_counter()
    events = stream(FenceParser(CATALOG), text)
    elapsed = time.perf_counter() - t0
    kinds = [type(e).__name__ for e in events]
    assert elapsed < 6, f"parser took {elapsed:.1f}s"
    assert kinds.count("ComponentEnd") == 1
    assert kinds.count("ComponentUpdate") < 64  # previews grow geometrically, not per chunk
    assert "after" in "".join(e.text for e in events if isinstance(e, genui.TextDelta))


def test_partial_previews_stop_above_limit_but_component_completes():
    text = "```dyui\n" + table_line(MAX_PARTIAL_CHARS * 3) + "\n```\n"
    events = stream(FenceParser(CATALOG), text)
    sizes = [len(json.dumps(e.node)) for e in events if isinstance(e, genui.ComponentUpdate)]
    assert sizes and max(sizes) < MAX_PARTIAL_CHARS * 2
    assert isinstance([e for e in events if not isinstance(e, genui.TextDelta)][-1], genui.ComponentEnd)


def test_component_over_size_cap_fails_cleanly_and_prose_continues():
    text = "before\n```dyui\n" + table_line(MAX_COMPONENT_CHARS + 50_000) + "\n```\nafter\n"
    t0 = time.perf_counter()
    events = stream(FenceParser(CATALOG), text)
    assert time.perf_counter() - t0 < 6
    errors = [e for e in events if isinstance(e, genui.ComponentError)]
    assert len(errors) == 1 and "too large" in errors[0].error
    assert len(errors[0].node()["props"]["raw"]) <= 4000
    prose = "".join(e.text for e in events if isinstance(e, genui.TextDelta))
    assert "before" in prose and "after" in prose


def test_ui_key_last_does_not_reparse_every_chunk():
    rows = ",".join(['["aaaa",1]'] * 8000)
    text = '```dyui\n{"columns":["a","b"],"rows":[' + rows + '],"ui":"table"}\n```\n'
    t0 = time.perf_counter()
    events = stream(FenceParser(CATALOG), text)
    assert time.perf_counter() - t0 < 4
    assert any(isinstance(e, genui.ComponentEnd) for e in events)


def test_multiline_component_is_linear():
    lines = ["{", '"ui": "table",', '"columns": ["a","b"],', '"rows": ['] + ['["aaaa", 1],'] * 8000 + ['["z", 2]', "]", "}"]
    t0 = time.perf_counter()
    events = stream(FenceParser(CATALOG), "```dyui\n" + "\n".join(lines) + "\n```\n")
    assert time.perf_counter() - t0 < 4
    end = [e for e in events if isinstance(e, genui.ComponentEnd)]
    assert end and len(end[0].node["props"]["rows"]) == 8001


def test_huge_bare_line_is_not_held_back_forever():
    t0 = time.perf_counter()
    events = stream(FenceParser(CATALOG), table_line(200_000) + "\nprose\n")
    assert time.perf_counter() - t0 < 4
    assert "prose" in "".join(e.text for e in events if isinstance(e, genui.TextDelta))


async def test_server_stays_responsive_while_a_huge_component_streams():
    app = make_app()

    @app.on_message
    async def reply(msg, chat):
        text = "```dyui\n" + table_line(300_000) + "\n```\n"
        for i in range(0, len(text), 7):
            yield text[i:i + 7]
            if i % 7000 == 0:
                await asyncio.sleep(0)

    async with client(app) as c:
        await c.get("/api/config")
        task = asyncio.create_task(c.post("/api/chat", json={"message": {"text": "go"}}))
        await asyncio.sleep(0.05)
        t0 = time.perf_counter()
        assert (await c.get("/api/config")).status_code == 200
        latency = time.perf_counter() - t0
        r = await task
    assert r.status_code == 200 and "event: done" in r.text
    assert latency < 2.0


# ===================================================================== V-02 deep nesting crash
@pytest.mark.parametrize("levels", [30, 200, 5000])
def test_deep_nesting_in_fence_becomes_invalid_not_exception(levels):
    events = stream(FenceParser(CATALOG), "```dyui\n" + deep_card(levels) + "\n```\nok\n")
    errors = [e for e in events if isinstance(e, genui.ComponentError)]
    assert errors and "nested too deeply" in errors[0].error
    assert "ok" in "".join(e.text for e in events if isinstance(e, genui.TextDelta))


@pytest.mark.parametrize("levels", [30, 400, 2000])
def test_deep_nesting_unterminated_and_bare(levels):
    stream(FenceParser(CATALOG), "```dyui\n" + deep_card(levels)[:-5])  # must not raise
    stream(FenceParser(CATALOG), deep_card(levels) + "\nok\n")


def test_catalog_validate_rejects_deep_dicts_without_recursing():
    node = CATALOG.validate(json.loads(deep_card(300)))
    assert node["ui"] == "invalid" and "nested too deeply" in node["props"]["error"]
    assert len(node["props"]["raw"]) < 400


def test_reasonable_nesting_still_works():
    obj = {"ui": "tabs", "tabs": [{"label": "A", "children": [
        {"ui": "grid", "children": [{"ui": "card", "title": "x", "children": [
            {"ui": "table", "columns": ["a"], "rows": [[1], [2]]}]}]}]}]}
    assert not too_deep(obj) and CATALOG.validate(obj)["ui"] == "tabs"


def test_too_deep_is_iterative():
    value: list = []
    for _ in range(sys.getrecursionlimit() * 3):
        value = [value]
    assert too_deep(value) and not too_deep([[1]], MAX_DEPTH)


async def test_dict_yield_and_tools_mode_deep_component_render_invalid():
    app = make_app()

    @app.on_message
    async def reply(msg, chat):
        yield json.loads(deep_card(400))
        yield "still here"

    async with client(app) as c:
        r = await c.post("/api/chat", json={"message": {"text": "x"}})
    assert '"ui":"invalid"' in r.text and "still here" in r.text and "event: error" not in r.text


# ===================================================================== V-03 CSRF
@pytest.mark.parametrize("site", ["cross-site", "same-site"])
@pytest.mark.parametrize("method,path,kw", [
    ("POST", "/api/chat", {"content": '{"message":{"text":"x"}}', "headers": {"Content-Type": "text/plain"}}),
    ("POST", "/api/chat", {"json": {"message": {"text": "x"}}}),
    ("POST", "/api/threads", {}),
    ("POST", "/api/action", {"json": {}}),
    ("POST", "/api/feedback", {"json": {}}),
    ("POST", "/api/login", {"json": {"password": "x"}}),
    ("PATCH", "/api/threads/t_x", {"json": {"title": "x"}}),
    ("DELETE", "/api/threads/t_x", {}),
    ("POST", "/api/upload", {"files": {"file": ("a.txt", b"x", "text/plain")}}),
])
async def test_cross_origin_writes_are_refused(site, method, path, kw):
    app = make_app()
    async with client(app) as c:
        headers = {**kw.pop("headers", {}), "Sec-Fetch-Site": site}
        r = await c.request(method, path, headers=headers, **kw)
    assert r.status_code == 403


@pytest.mark.parametrize("origin", ["http://evil.example", "http://test.evil", "null", "http://localhost:3000"])
async def test_mismatching_origin_refused_without_fetch_metadata(origin):
    app = make_app()
    async with client(app) as c:
        r = await c.post("/api/chat", json={"message": {"text": "x"}}, headers={"Origin": origin})
    assert r.status_code == 403


async def test_same_origin_writes_allowed():
    app = make_app()

    @app.on_message
    async def reply(msg, chat):
        yield "ok"

    async with client(app) as c:
        for headers in ({"Sec-Fetch-Site": "same-origin"}, {"Origin": "http://test"}, {"Sec-Fetch-Site": "none"},
                        {"Origin": "https://chat.example.com", "X-Forwarded-Host": "chat.example.com"}, {}):
            r = await c.post("/api/chat", json={"message": {"text": "x"}}, headers=headers)
            assert r.status_code == 200, headers
        r = await c.post("/api/upload", files={"file": ("a.txt", b"x", "text/plain")}, headers={"Sec-Fetch-Site": "same-origin"})
        assert r.status_code == 200
        assert (await c.get("/api/threads", headers={"Sec-Fetch-Site": "cross-site"})).status_code == 200  # reads unaffected


@pytest.mark.parametrize("ctype", ["text/plain", "application/x-www-form-urlencoded", "multipart/form-data; boundary=x"])
async def test_json_routes_require_json_content_type(ctype):
    app = make_app()
    async with client(app) as c:
        r = await c.post("/api/chat", content=b'{"message":{"text":"x"}}', headers={"Content-Type": ctype})
        assert r.status_code == 415
        r = await c.post("/api/chat", content=b'{"message":{"text":"x"}}',
                         headers={"Content-Type": "application/json; charset=utf-8"})
        assert r.status_code == 200


# ===================================================================== V-04 security headers / CSP
async def test_html_gets_nonce_csp_and_hardening_headers(tmp_path, monkeypatch):
    from dyui import server

    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text(
        "<!doctype html><html><head><title>DyUI</title><script>var a=1</script>"
        '<script type="module" src="./assets/m.js"></script></head><body></body></html>', encoding="utf-8")
    monkeypatch.setattr(server, "STATIC_DIR", static)
    app = make_app()
    async with client(app) as c:
        r1, r2 = await c.get("/"), await c.get("/some/spa/route")
    csp = r1.headers["content-security-policy"]
    nonce = re.search(r"'nonce-([^']+)'", csp).group(1)
    assert f'<meta name="dyui-csp-nonce" content="{nonce}">' in r1.text
    assert f'<script nonce="{nonce}">var a=1</script>' in r1.text
    assert '<script type="module" src="./assets/m.js">' in r1.text  # external scripts untouched
    assert nonce not in r2.headers["content-security-policy"]  # fresh per response
    for directive in ("default-src 'self'", "object-src 'none'", "base-uri 'self'", "frame-ancestors 'self'",
                      "connect-src 'self'", "form-action 'self'"):
        assert directive in csp
    assert "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]
    h = r1.headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "SAMEORIGIN"
    assert h["referrer-policy"] == "same-origin" and h["cross-origin-opener-policy"] == "same-origin"
    assert "camera=()" in h["permissions-policy"]


async def test_api_headers():
    app = make_app()
    async with client(app) as c:
        r = await c.get("/api/config")
    assert r.headers["cache-control"] == "no-store" and r.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" not in r.headers


async def test_csp_options(tmp_path, monkeypatch):
    from dyui import server

    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<html><head><title>DyUI</title></head></html>", encoding="utf-8")
    monkeypatch.setattr(server, "STATIC_DIR", static)
    async with client(make_app(embed_origins=["https://example.com", "https://*.corp.example:8443"])) as c:
        r = await c.get("/")
    assert "frame-ancestors 'self' https://example.com https://*.corp.example:8443" in r.headers["content-security-policy"]
    assert "x-frame-options" not in r.headers
    async with client(make_app(csp=False)) as c:
        r = await c.get("/")
    assert "content-security-policy" not in r.headers and "dyui-csp-nonce" not in r.text
    async with client(make_app(csp="default-src 'none'")) as c:
        assert (await c.get("/")).headers["content-security-policy"] == "default-src 'none'"


@pytest.mark.parametrize("bad", ["https://e.com; script-src *", "javascript:alert(1)", "e.com", "https://e.com/path", "*"])
def test_embed_origins_validated(bad):
    with pytest.raises(ValueError):
        make_app(embed_origins=[bad])


def test_csp_option_rejects_header_injection():
    with pytest.raises(ValueError):
        make_app(csp="default-src 'self'\r\nSet-Cookie: x=1")


def test_inline_script_hashes():
    from dyui.server import build_csp, inline_script_hashes

    hashes = inline_script_hashes("<script>a()</script><script src=x.js></script><SCRIPT type='x'>b</SCRIPT>")
    assert len(hashes) == 2
    assert f"'sha256-{hashes[0]}'" in build_csp(hashes)


# ===================================================================== V-05 secret file
def test_secret_created_once_owner_only_and_shared(tmp_path, monkeypatch):
    from dyui.server import _secret

    monkeypatch.delenv("DYUI_SECRET", raising=False)
    app = make_app(data_dir=tmp_path / "d")
    first = _secret(app)
    assert len(first) >= 32 and _secret(app) == first
    if os.name == "posix":
        assert (tmp_path / "d" / "secret").stat().st_mode & 0o077 == 0
    (tmp_path / "d" / "secret").write_bytes(b"short")  # corrupt -> replaced, not trusted
    assert _secret(app) != b"short" and len(_secret(app)) >= 32


# ===================================================================== V-06 password compare
async def test_login_compares_fixed_length_digests():
    app = make_app(password="correct horse")
    async with client(app) as c:
        for guess in ("", "c", "correct hors", "correct horse battery", "ü" * 500):
            assert (await c.post("/api/login", json={"password": guess})).status_code == 401
        assert (await c.post("/api/login", json={"password": "correct horse"})).status_code == 200


# ===================================================================== F-01 Html(template=...)
def test_html_template_loads_file_from_app_dir(tmp_path, monkeypatch):
    from dyui.html import register_template_root

    (tmp_path / "templates" / "cards").mkdir(parents=True)
    (tmp_path / "templates" / "cards" / "flight.html").write_text("<b>{{ airline }}</b>{{{ raw }}}", encoding="utf-8")
    (tmp_path / "top.html").write_text("<i>top</i>", encoding="utf-8")
    monkeypatch.chdir(tmp_path.parent)
    register_template_root(tmp_path)
    node = ui.Html(template="cards/flight.html", props={"airline": "<TAP>", "raw": "<em>ok</em>"}).to_node()
    assert node["props"]["html"] == "<b>&lt;TAP&gt;</b><em>ok</em>"
    assert set(node["props"]) <= {"html", "height"}  # template/props/template_root never reach the client
    assert ui.Html(template="top.html").to_node()["props"]["html"] == "<i>top</i>"
    assert ui.Html("<p>inline</p>").to_node()["props"]["html"] == "<p>inline</p>"


def test_html_template_root_param_and_pathlike(tmp_path):
    (tmp_path / "x.html").write_text("X", encoding="utf-8")
    assert ui.Html(template="x.html", template_root=tmp_path).to_node()["props"]["html"] == "X"


@pytest.mark.parametrize("bad", ["../secret.html", "a/../../secret.html", "..\\secret.html", "/etc/passwd.html",
                                 "C:/Windows/win.ini", "C:secret.html", "secret.txt", "app.py", "x\x00.html", "",
                                 "missing.html", "sub/../../../secret.html"])
def test_html_template_traversal_refused(tmp_path, bad):
    root = tmp_path / "app"
    root.mkdir()
    (tmp_path / "secret.html").write_text("SECRET", encoding="utf-8")
    (root / "secret.txt").write_text("SECRET", encoding="utf-8")
    (root / "app.py").write_text("SECRET", encoding="utf-8")
    with pytest.raises(ValueError):
        ui.Html(template=bad, template_root=root).to_node()


def test_html_template_symlink_escape_refused(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    (tmp_path / "outside.html").write_text("SECRET", encoding="utf-8")
    try:
        (root / "link.html").symlink_to(tmp_path / "outside.html")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not available")
    with pytest.raises(ValueError):
        ui.Html(template="link.html", template_root=root).to_node()


def test_html_component_never_in_llm_catalog():
    assert "html" not in dyui.App(persist=False).catalog.names


# ===================================================================== AppConfig / demo
async def test_config_reports_upload_limit():
    async with client(make_app(max_upload_mb=7)) as c:
        assert (await c.get("/api/config")).json()["max_upload_mb"] == 7
    async with client(make_app(uploads=False)) as c:
        assert (await c.get("/api/config")).json()["max_upload_mb"] is None


async def test_demo_rating_gets_a_thank_you(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import importlib

    demo = importlib.import_module("dyui.demo")
    app = demo.app
    app._store = None
    app._persist = False
    async with client(app) as c:
        await c.get("/api/config")
        ev = (await c.post("/api/chat", json={"message": {"text": "File a support ticket"}})).text
        tid = re.search(r'"thread_id":"(t_[^"]+)"|"id":"(t_[^"]+)"', ev)
        thread_id = tid.group(1) or tid.group(2)
        form = re.search(r'"ui":"form"', ev)
        assert form
        thread = (await c.get(f"/api/threads/{thread_id}")).json()
        msg = thread["messages"][-1]
        form_node = next(p["node"] for p in msg["parts"] if p["type"] == "ui" and p["node"]["ui"] == "form")
        r = await c.post("/api/action", json={"thread_id": thread_id, "message_id": msg["id"],
                                              "component_id": form_node["id"], "action": "submit_ticket",
                                              "values": {"subject": "Export broken"}})
        thread = (await c.get(f"/api/threads/{thread_id}")).json()
        msg = thread["messages"][-1]
        rating = next(p["node"] for p in msg["parts"] if p["type"] == "ui" and p["node"]["ui"] == "rating")
        r = await c.post("/api/action", json={"thread_id": thread_id, "message_id": msg["id"],
                                              "component_id": rating["id"], "action": "rating",
                                              "label": "5 stars", "values": {"rating": 5}})
    text = "".join(json.loads(line[6:])["delta"] for line in r.text.splitlines()
                   if line.startswith("data: ") and '"delta"' in line)
    assert "5/5" in text and "few tricks" not in text


# ===================================================================== ask() bookkeeping
async def test_abandoned_ask_is_cleaned_up():
    app = make_app()

    @app.on_message
    async def reply(msg, chat):
        await chat.ask(ui.Confirm("Proceed?"))
        yield "never"

    from dyui.chat import Turn

    queue: asyncio.Queue = asyncio.Queue()
    turn = Turn(app, {"id": ""}, queue)
    task = asyncio.create_task(app.handle_chat(turn, "u_1", {"message": {"text": "x"}}))
    for _ in range(100):
        await asyncio.sleep(0.01)
        if app._pending:
            break
    assert app._pending
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not app._pending
