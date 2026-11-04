"""HTTP + SSE server for a DyUI app (SPEC §4). Built lazily by :meth:`dyui.App.asgi`."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import mimetypes
import secrets
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator, Awaitable, Callable

from fastapi import FastAPI, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse

from ..chat import Turn

if TYPE_CHECKING:  # pragma: no cover
    from ..app import App

log = logging.getLogger("dyui")

__all__ = ["create_server"]

STATIC_DIR = Path(__file__).resolve().parent.parent / "_static"
UID_COOKIE = "dyui_uid"
AUTH_COOKIE = "dyui_auth"
HEARTBEAT_S = 15.0

FALLBACK_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>
<style>body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#F7F6F3;color:#1A1A1F;
font:15px/1.6 ui-sans-serif,system-ui,sans-serif}}main{{max-width:520px;padding:32px}}
h1{{font:400 34px/1.15 Georgia,serif;letter-spacing:-.01em;margin:0 0 8px}}code{{background:#ECEAFD;
padding:2px 6px;border-radius:6px}}</style></head><body><main><h1>{title} is running.</h1>
<p>The DyUI web app isn't bundled in this install. If you're working from a source checkout, build it once:</p>
<p><code>cd web &amp;&amp; npm install &amp;&amp; npm run build:py</code></p>
<p>The API is live at <code>/api/config</code>.</p></main></body></html>"""


# ------------------------------------------------------------------ identity
class _IdentityMiddleware:
    """Pure-ASGI middleware: assigns an anonymous ``dyui_uid`` cookie."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        cookies = _parse_cookies(scope)
        uid = cookies.get(UID_COOKIE)
        new = not (uid and len(uid) <= 64 and uid.replace("_", "").isalnum())
        if new:
            uid = "u_" + secrets.token_hex(12)
        scope.setdefault("state", {})["dyui_uid"] = uid

        async def send_wrapper(message: Any) -> None:
            if new and message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"set-cookie", f"{UID_COOKIE}={uid}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Lax".encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)


def _parse_cookies(scope: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in scope.get("headers", []):
        if k == b"cookie":
            for piece in v.decode("latin-1").split(";"):
                if "=" in piece:
                    name, _, val = piece.strip().partition("=")
                    out[name] = val
    return out


def _uid(request: Request) -> str:
    return request.scope.get("state", {}).get("dyui_uid", "anonymous")


# ------------------------------------------------------------------ auth
def _secret(app: "App") -> bytes:
    import os

    env = os.environ.get("DYUI_SECRET")
    if env:
        return env.encode()
    path = app.data_dir / "secret"
    try:
        return path.read_bytes()
    except FileNotFoundError:
        path.parent.mkdir(parents=True, exist_ok=True)
        value = secrets.token_hex(32).encode()
        path.write_bytes(value)
        return value


def _auth_token(app: "App") -> str:
    pw = (app.password or "").encode()
    return hmac.new(_secret(app), b"dyui-auth:" + hashlib.sha256(pw).digest(), hashlib.sha256).hexdigest()


def _authed(app: "App", request: Request) -> bool:
    if not app.password:
        return True
    token = request.cookies.get(AUTH_COOKIE, "")
    return hmac.compare_digest(token, _auth_token(app))


def _err(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


# ------------------------------------------------------------------ SSE
def _frame(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'), default=str)}\n\n"


def _sse(app: "App", run: Callable[[Turn], Awaitable[Any]]) -> StreamingResponse:
    """Stream a turn's events; cancel the handler if the client disconnects."""
    queue: asyncio.Queue[Any] = asyncio.Queue()
    turn = Turn(app, {"id": ""}, queue)

    async def runner() -> None:
        try:
            await run(turn)
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover - defensive
            log.exception("dyui: turn failed")
            turn.emit("error", {"message": "Something went wrong."})
        finally:
            queue.put_nowait(None)

    async def body() -> AsyncIterator[str]:
        task = asyncio.create_task(runner())
        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), HEARTBEAT_S)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                if item is None:
                    break
                yield _frame(*item)
            yield _frame("done", {})
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

    return StreamingResponse(body(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})


def _public(msg: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in msg.items() if k != "meta"}


def _summary(t: dict[str, Any]) -> dict[str, Any]:
    return {k: t[k] for k in ("id", "title", "created_at", "updated_at")}


# ------------------------------------------------------------------ factory
def create_server(app: "App") -> Any:
    """Build the FastAPI app for ``app`` (wrapped in the identity middleware)."""
    api = FastAPI(title=app.title, docs_url=None, redoc_url=None, openapi_url=None)

    async def guard(request: Request) -> JSONResponse | None:
        if not _authed(app, request):
            return _err(401, "Password required.")
        return None

    @api.get("/api/config")
    async def get_config(request: Request) -> Any:
        return app.config(authenticated=_authed(app, request))

    @api.post("/api/login")
    async def login(request: Request) -> Any:
        try:
            body = await request.json()
        except Exception:
            return _err(400, "Invalid JSON.")
        if not app.password or not hmac.compare_digest(str(body.get("password", "")), app.password):
            return _err(401, "Wrong password.")
        resp = JSONResponse({"ok": True})
        resp.set_cookie(AUTH_COOKIE, _auth_token(app), max_age=60 * 60 * 24 * 30, httponly=True, samesite="lax")
        return resp

    @api.get("/api/threads")
    async def list_threads(request: Request) -> Any:
        if (denied := await guard(request)) is not None:
            return denied
        rows = await app.store.list_threads(_uid(request))
        return {"threads": [_summary(t) for t in rows]}

    @api.post("/api/threads")
    async def create_thread(request: Request) -> Any:
        if (denied := await guard(request)) is not None:
            return denied
        uid = _uid(request)
        return _sse(app, lambda turn: app.start_thread(turn, uid))

    @api.get("/api/threads/{thread_id}")
    async def get_thread(thread_id: str, request: Request) -> Any:
        if (denied := await guard(request)) is not None:
            return denied
        t = await app.store.get_thread(thread_id)
        if t is None or t.get("user_id") != _uid(request):
            return _err(404, "Conversation not found.")
        msgs = await app.store.get_messages(thread_id)
        return {**_summary(t), "messages": [_public(m) for m in msgs]}

    @api.patch("/api/threads/{thread_id}")
    async def rename_thread(thread_id: str, request: Request) -> Any:
        if (denied := await guard(request)) is not None:
            return denied
        t = await app.store.get_thread(thread_id)
        if t is None or t.get("user_id") != _uid(request):
            return _err(404, "Conversation not found.")
        try:
            body = await request.json()
        except Exception:
            return _err(400, "Invalid JSON.")
        title = str(body.get("title", "")).strip()[:120] or t["title"]
        t = await app.store.update_thread(thread_id, title=title, title_locked=True)
        return _summary(t)

    @api.delete("/api/threads/{thread_id}")
    async def delete_thread(thread_id: str, request: Request) -> Any:
        if (denied := await guard(request)) is not None:
            return denied
        t = await app.store.get_thread(thread_id)
        if t is None or t.get("user_id") != _uid(request):
            return _err(404, "Conversation not found.")
        await app.store.delete_thread(thread_id)
        return {"ok": True}

    @api.post("/api/chat")
    async def chat(request: Request) -> Any:
        if (denied := await guard(request)) is not None:
            return denied
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError
        except Exception:
            return _err(400, "Invalid request body.")
        uid = _uid(request)
        return _sse(app, lambda turn: app.handle_chat(turn, uid, body))

    @api.post("/api/action")
    async def action(request: Request) -> Any:
        if (denied := await guard(request)) is not None:
            return denied
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError
        except Exception:
            return _err(400, "Invalid request body.")
        uid = _uid(request)
        # verify before opening the stream so forged actions get a real 400
        from ..chat import declared_actions, find_node

        thread = await app.store.get_thread(body.get("thread_id", ""))
        if thread is None or thread.get("user_id") != uid:
            return _err(404, "Conversation not found.")
        pending = app._pending.get((thread["id"], body.get("component_id", "")))
        if pending is None:
            stored = await app.store.get_message(thread["id"], body.get("message_id", ""))
            node = find_node(stored["parts"], body.get("component_id", "")) if stored else None
            if node is None or str(body.get("action", "")) not in declared_actions(node):
                return _err(400, "Unknown action.")
        else:
            live = pending[1].message
            node = find_node(live["parts"], body.get("component_id", "")) if live else None
            if node is None or str(body.get("action", "")) not in declared_actions(node):
                return _err(400, "Unknown action.")
        return _sse(app, lambda turn: app.handle_action(turn, uid, body))

    @api.post("/api/feedback")
    async def feedback(request: Request) -> Any:
        if (denied := await guard(request)) is not None:
            return denied
        try:
            body = await request.json()
        except Exception:
            return _err(400, "Invalid JSON.")
        problem = await app.handle_feedback(_uid(request), body)
        return _err(404, problem) if problem else {"ok": True}

    @api.post("/api/upload")
    async def upload(file: UploadFile, request: Request) -> Any:
        if (denied := await guard(request)) is not None:
            return denied
        if not app.uploads:
            return _err(403, "Uploads are disabled.")
        limit = app.max_upload_mb * 1024 * 1024
        fid = "f_" + secrets.token_hex(10)
        folder = app.data_dir / "uploads"
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / fid
        size = 0
        with dest.open("wb") as fh:
            while chunk := await file.read(1024 * 256):
                size += len(chunk)
                if size > limit:
                    fh.close()
                    dest.unlink(missing_ok=True)
                    return _err(413, f"File is larger than {app.max_upload_mb} MB.")
                fh.write(chunk)
        name = Path(file.filename or "file").name[:200]
        ctype = file.content_type or mimetypes.guess_type(name)[0] or "application/octet-stream"
        rec = {"id": fid, "user_id": _uid(request), "name": name, "type": ctype, "size": size, "path": str(dest)}
        await app.store.put_file(rec)
        return {"id": fid, "name": name, "type": ctype, "size": size, "url": f"api/files/{fid}"}

    @api.get("/api/files/{file_id}")
    async def get_file(file_id: str, request: Request) -> Any:
        if (denied := await guard(request)) is not None:
            return denied
        rec = await app.store.get_file(file_id)
        if rec is None or rec.get("user_id") != _uid(request) or not Path(rec["path"]).is_file():
            return _err(404, "File not found.")
        return FileResponse(rec["path"], media_type=rec.get("type") or "application/octet-stream",
                            filename=rec.get("name"), content_disposition_type="inline",
                            headers={"X-Content-Type-Options": "nosniff"})

    @api.get("/api/logo")
    async def logo() -> Any:
        if app.logo and Path(app.logo).is_file():
            return FileResponse(app.logo, headers={"X-Content-Type-Options": "nosniff"})
        return _err(404, "No logo.")

    @api.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def api_404(rest: str) -> Any:
        return _err(404, "Not found.")

    @api.get("/{path:path}")
    async def static(path: str) -> Any:
        index = STATIC_DIR / "index.html"
        if not index.is_file():
            return HTMLResponse(FALLBACK_PAGE.format(title=_html_escape(app.title)))
        if path:
            target = (STATIC_DIR / path).resolve()
            if STATIC_DIR.resolve() in target.parents and target.is_file():
                cache = "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
                return FileResponse(target, headers={"Cache-Control": cache})
        html = index.read_text(encoding="utf-8").replace("<title>DyUI</title>", f"<title>{_html_escape(app.title)}</title>")
        return HTMLResponse(html, headers={"Cache-Control": "no-cache"})

    return _IdentityMiddleware(api)


def _html_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))
