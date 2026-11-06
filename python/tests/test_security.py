"""Security regression tests (1.0 hardening; maps the 0.1 security-branch fixes onto the rewrite)."""
from __future__ import annotations

import json

import httpx
import pytest

import dyui
from dyui import genui, ui
from dyui._jsonsafe import finite, has_nonfinite
from dyui.server import LOGIN_MAX_FAILURES, MAX_JSON_BYTES, _frame


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
            events.append((name, json.loads("\n".join(data) or "{}")))  # strict: NaN would still parse
    return events


def strict_loads(text: str):
    def bad(c):
        raise ValueError(f"non-standard JSON constant {c}")
    return json.loads(text, parse_constant=bad)


def client(app: dyui.App) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def make_app(**kw) -> dyui.App:
    return dyui.App(title="Test", persist=False, **kw)


async def chat_once(c, text="x"):
    ev = parse_sse((await c.post("/api/chat", json={"message": {"text": text}})).text)
    return ev, ev[0][1]["id"]


# ------------------------------------------------------------- model can't produce HTML
@pytest.mark.parametrize("block", [
    '{"ui":"html","html":"<form action=https://evil>Password<input></form>"}',
    '{"ui":"invalid","raw":"x","error":"y"}',
    '{"ui":"card","title":"t","children":[{"ui":"html","html":"<b>x</b>"}]}',
    '{"ui":"grid","children":[{"ui":"card","children":[{"ui":"html","html":"<b>deep</b>"}]}]}',
    '{"ui":"tabs","tabs":[{"label":"A","children":[{"ui":"html","html":"<b>x</b>"}]}]}',
    '{"ui":"accordion","items":[{"title":"A","children":[{"ui":"html","html":"<b>x</b>"}]}]}',
])
async def test_llm_text_cannot_render_developer_components(block):
    app = make_app()

    @app.on_message
    async def reply(msg, chat):
        yield f"Here:\n```dyui\n{block}\n```\n"

    async with client(app) as c:
        ev, _ = await chat_once(c)
    nodes = [d["node"] for e, d in ev if e == "ui"]
    final = nodes[-1]

    def walk(n):
        yield n
        for ch in n.get("children") or []:
            yield from walk(ch)
        for value in (n.get("props") or {}).values():  # tabs[].children / items[].children
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        for ch in item.get("children") or []:
                            if isinstance(ch, dict) and "ui" in ch:
                                yield from walk(ch)

    assert not any(n["ui"] == "html" for n in walk(final))
    assert any(n["ui"] == "invalid" for n in walk(final))


async def test_llm_dict_cannot_render_html_but_developer_instance_can():
    app = make_app()

    @app.on_message
    async def reply(msg, chat):
        yield {"ui": "html", "html": "<script>1</script>"}  # tools-mode LLM output shape
        yield ui.Html(html="<b>dev</b>")  # a developer-authored instance is trusted

    async with client(app) as c:
        ev, _ = await chat_once(c)
    kinds = [d["node"]["ui"] for e, d in ev if e == "ui"]
    assert kinds == ["invalid", "html"]


def test_untrusted_catalog_excludes_developer_only():
    app = make_app()
    assert "html" not in app.untrusted_catalog.names and "invalid" not in app.untrusted_catalog.names
    assert "html" in app.render_catalog.names
    assert "html" not in app.catalog.prompt()


# ------------------------------------------------------------- NaN / Infinity never reach JSON
@pytest.mark.parametrize("raw", [
    '{"ui":"progress","value":NaN}',
    '{"ui":"stat","label":"a","value":Infinity}',
    '{"ui":"json","data":{"x":-Infinity}}',
    '{"ui":"chart","kind":"bar","labels":["a"],"series":[{"name":"s","data":[NaN]}]}',
])
async def test_nonfinite_numbers_become_invalid_and_stream_is_strict_json(raw):
    app = make_app()

    @app.on_message
    async def reply(msg, chat):
        yield f"```dyui\n{raw}\n```\n"

    async with client(app) as c:
        r = await c.post("/api/chat", json={"message": {"text": "x"}})
        for line in r.text.splitlines():
            if line.startswith("data:"):
                strict_loads(line[5:])
        ev = parse_sse(r.text)
        tid = ev[0][1]["id"]
        assert [d["node"]["ui"] for e, d in ev if e == "ui"][-1] == "invalid"
        t = await c.get(f"/api/threads/{tid}")
        assert t.status_code == 200
        strict_loads(t.text)


async def test_python_component_with_nan_is_scrubbed():
    app = make_app()

    @app.on_message
    async def reply(msg, chat):
        yield ui.Json({"x": float("nan"), "ok": 1})
        async with chat.step("s") as s:
            s.output = {"v": float("inf")}

    async with client(app) as c:
        r = await c.post("/api/chat", json={"message": {"text": "x"}})
        for line in r.text.splitlines():
            if line.startswith("data:"):
                strict_loads(line[5:])
        tid = parse_sse(r.text)[0][1]["id"]
        t = await c.get(f"/api/threads/{tid}")
        assert t.status_code == 200 and not has_nonfinite(strict_loads(t.text))


def test_typed_float_fields_reject_nan():
    with pytest.raises(Exception):
        ui.Progress(float("nan"))
    assert finite({"a": [1.0, float("nan")], "b": (float("inf"),)}) == {"a": [1.0, None], "b": [None]}
    assert "NaN" not in _frame("ui", {"v": float("nan")})


# ------------------------------------------------------------- action integrity
async def _buttons_app(buttons, seen):
    app = make_app()

    @app.on_message
    async def reply(msg, chat):
        yield ui.Buttons(*buttons)

    @app.on_action("book")
    async def book(action, chat):
        seen.append(action.data)
        yield "booked"

    return app


async def test_action_data_comes_from_server_not_client():
    seen: list = []
    app = await _buttons_app([ui.Button("Book", action="book", data={"price": 189})], seen)
    async with client(app) as c:
        ev, tid = await chat_once(c)
        n = next(d for e, d in ev if e == "ui")
        r = await c.post("/api/action", json={"thread_id": tid, "message_id": n["message_id"],
                                              "component_id": n["node"]["id"], "action": "book",
                                              "data": {"price": 0}})
        assert r.status_code == 200
    assert seen == [{"price": 189}]


async def test_ambiguous_tampered_action_data_is_rejected():
    seen: list = []
    app = await _buttons_app([ui.Button("A", action="book", data={"id": 1}),
                              ui.Button("B", action="book", data={"id": 2})], seen)
    async with client(app) as c:
        ev, tid = await chat_once(c)
        n = next(d for e, d in ev if e == "ui")
        base = {"thread_id": tid, "message_id": n["message_id"], "component_id": n["node"]["id"], "action": "book"}
        assert (await c.post("/api/action", json={**base, "data": {"id": 3}})).status_code == 400
        assert (await c.post("/api/action", json={**base, "data": {"id": 2}})).status_code == 200
    assert seen == [{"id": 2}]


async def test_action_replay_is_rejected():
    seen: list = []
    app = await _buttons_app([ui.Button("Book", action="book")], seen)
    async with client(app) as c:
        ev, tid = await chat_once(c)
        n = next(d for e, d in ev if e == "ui")
        body = {"thread_id": tid, "message_id": n["message_id"], "component_id": n["node"]["id"], "action": "book"}
        assert (await c.post("/api/action", json=body)).status_code == 200
        assert (await c.post("/api/action", json=body)).status_code == 409
    assert len(seen) == 1


async def test_action_on_user_message_or_other_thread_rejected():
    seen: list = []
    app = await _buttons_app([ui.Button("Book", action="book")], seen)
    async with client(app) as a, client(app) as b:
        ev, tid = await chat_once(a)
        n = next(d for e, d in ev if e == "ui")
        body = {"thread_id": tid, "message_id": n["message_id"], "component_id": n["node"]["id"], "action": "book"}
        assert (await b.post("/api/action", json=body)).status_code == 404
        user_mid = next(d for e, d in ev if e == "user_message")["id"]
        assert (await a.post("/api/action", json={**body, "message_id": user_mid})).status_code == 400


# ------------------------------------------------------------- request limits & malformed bodies
async def test_oversized_json_body_rejected():
    app = make_app()

    @app.on_message
    async def reply(msg, chat):
        yield "ok"

    big = "x" * (MAX_JSON_BYTES + 10)
    async with client(app) as c:
        r = await c.post("/api/chat", json={"message": {"text": big}})
        assert r.status_code == 413

        async def chunks():  # no Content-Length: the streamed byte count is enforced too
            yield b'{"message":{"text":"'
            for _ in range(MAX_JSON_BYTES // 65536 + 2):
                yield b"x" * 65536
            yield b'"}}'

        r = await c.post("/api/chat", content=chunks(), headers={"content-type": "application/json"})
        assert r.status_code == 413
        assert (await c.post("/api/chat", json={"message": {"text": "small"}})).status_code == 200


async def test_oversized_upload_rejected_before_parsing(tmp_path):
    app = dyui.App(title="T", persist=False, data_dir=tmp_path, max_upload_mb=1)
    async with client(app) as c:
        r = await c.post("/api/upload", files={"file": ("a.bin", b"\0" * (2 * 1024 * 1024))})
        assert r.status_code == 413
        r = await c.post("/api/upload", files={"file": ("a.txt", b"hello")})
        assert r.status_code == 200


@pytest.mark.parametrize("path,body", [
    ("/api/chat", [1, 2]), ("/api/action", "str"), ("/api/feedback", [1]), ("/api/login", [1]),
])
async def test_non_object_json_bodies_are_400(path, body):
    app = make_app(password="pw")
    async with client(app) as c:
        await c.post("/api/login", json={"password": "pw"})
        r = await c.post(path, json=body)
        assert r.status_code in (400, 401) and "Traceback" not in r.text


async def test_feedback_bad_value_is_not_500():
    app = make_app()

    @app.on_message
    async def reply(msg, chat):
        yield "ok"

    async with client(app) as c:
        ev, tid = await chat_once(c)
        mid = next(d for e, d in ev if e == "message_start")["id"]
        r = await c.post("/api/feedback", json={"thread_id": tid, "message_id": mid, "value": "abc"})
        assert r.status_code == 200


# ------------------------------------------------------------- auth
async def test_login_throttled_after_repeated_failures():
    app = make_app(password="s3cret")
    async with client(app) as c:
        for _ in range(LOGIN_MAX_FAILURES):
            assert (await c.post("/api/login", json={"password": "nope"})).status_code == 401
        assert (await c.post("/api/login", json={"password": "s3cret"})).status_code == 429


async def test_login_non_ascii_password_is_not_500():
    app = make_app(password="pässwörd")
    async with client(app) as c:
        assert (await c.post("/api/login", json={"password": "日本語"})).status_code == 401
        assert (await c.post("/api/login", json={"password": "pässwörd"})).status_code == 200
        assert (await c.get("/api/threads")).status_code == 200
    async with client(app) as c:
        c.cookies.set("dyui_auth", "x" * 64)
        assert (await c.get("/api/threads")).status_code == 401


async def test_cookies_secure_over_https():
    app = make_app(password="pw")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test") as c:
        r = await c.get("/api/config")
        assert "Secure" in r.headers.get("set-cookie", "")
        r = await c.post("/api/login", json={"password": "pw"})
        assert "secure" in r.headers.get("set-cookie", "").lower()
    async with client(app) as c:
        r = await c.get("/api/config")
        assert "Secure" not in r.headers.get("set-cookie", "")


# ------------------------------------------------------------- uploaded files can't run as the app
@pytest.mark.parametrize("name,ctype,inline", [
    ("x.html", "text/html", False), ("x.svg", "image/svg+xml", False), ("x.js", "text/javascript", False),
    ("x.png", "image/png", True), ("x.txt", "text/plain", True),
])
async def test_active_uploads_are_downloaded_and_sandboxed(tmp_path, name, ctype, inline):
    app = dyui.App(title="T", persist=False, data_dir=tmp_path)
    async with client(app) as c:
        ref = (await c.post("/api/upload", files={"file": (name, b"<script>alert(1)</script>", ctype)})).json()
        r = await c.get(f"/api/files/{ref['id']}")
        assert r.status_code == 200
        assert "sandbox" in r.headers["content-security-policy"]
        assert r.headers["x-content-type-options"] == "nosniff"
        disp = r.headers["content-disposition"]
        if inline:
            assert disp.startswith("inline")
        else:
            assert disp.startswith("attachment") and r.headers["content-type"] == "application/octet-stream"


# ------------------------------------------------------------- URLs
@pytest.mark.parametrize("url,ok", [
    ("https://example.com/a", True), ("http://x.io", True), ("mailto:a@b.c", True),
    ("/api/files/f_1", True), ("api/files/f_1", True),
    ("javascript:alert(1)", False), ("JaVaScRiPt:alert(1)", False), (" javascript:x", False),
    ("data:text/html,x", False), ("vbscript:x", False), ("//evil.com/x", False), ("/etc/passwd", False),
    ("api/files/../secret", False), ("/api/files/..%2f", False), ("api/files/", False),
    ("api/files//evil.com", False), ("api/files/javascript:x", False), ("java\tscript:x", False),
    ("https://", False), ("mailto:", False),
])
def test_is_safe_url(url, ok):
    from dyui.ui.types import is_safe_url

    assert is_safe_url(url) is ok


def test_uploaded_file_urls_work_in_components():
    node = ui.File("a.txt", "api/files/f_1").to_node()
    assert node["props"]["url"] == "api/files/f_1"
    assert ui.Image("api/files/f_2").to_node()["props"]["src"] == "api/files/f_2"


# ------------------------------------------------------------- templates & static
def test_html_template_traversal_and_escaping(tmp_path):
    from dyui.html import html_template, render_template

    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "card.html").write_text("<p>{{ name }}</p>{{{ raw }}}", encoding="utf-8")
    (tmp_path / "secret.html").write_text("nope", encoding="utf-8")
    node = html_template("card.html", root=tmp_path / "t", name="<img onerror=1>", raw="<b>ok</b>")
    assert "&lt;img onerror=1&gt;" in node.html and "<b>ok</b>" in node.html
    for bad in ("../secret.html", str(tmp_path / "secret.html"), "..\\secret.html"):
        with pytest.raises((ValueError, FileNotFoundError, OSError)):
            html_template(bad, root=tmp_path / "t")
    assert render_template("{{ a.b }}", {"a": {"b": "\"q\""}}) == "&quot;q&quot;"


async def test_static_path_traversal_blocked(tmp_path, monkeypatch):
    import dyui.server as srv

    static = tmp_path / "_static"
    static.mkdir()
    (static / "index.html").write_text("<title>DyUI</title>app", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("SECRET", encoding="utf-8")
    monkeypatch.setattr(srv, "STATIC_DIR", static)
    app = dyui.App(title="<script>x</script>", persist=False)
    async with client(app) as c:
        for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/..%2fsecret.txt", "/%2e%2e%5csecret.txt"):
            r = await c.get(path)
            assert "SECRET" not in r.text
        r = await c.get("/")
        assert "<script>x</script>" not in r.text and "&lt;script&gt;" in r.text


def test_parser_rejects_html_in_markdown_component_is_text_only():
    # Markdown props are plain text for the client renderer (which renders no raw HTML);
    # the server must not try to interpret them, only pass them through.
    node = genui.catalog().validate({"ui": "markdown", "text": "<img src=x onerror=alert(1)>"})
    assert node["ui"] == "markdown" and node["props"]["text"].startswith("<img")
