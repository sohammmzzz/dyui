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

from .._jsonsafe import finite
from ..chat import Turn

if TYPE_CHECKING:  # pragma: no cover
    from ..app import App

log = logging.getLogger("dyui")

__all__ = ["create_server"]

STATIC_DIR = Path(__file__).resolve().parent.parent / "_static"
UID_COOKIE = "dyui_uid"
AUTH_COOKIE = "dyui_auth"
HEARTBEAT_S = 15.0
MAX_JSON_BYTES = 1024 * 1024          # JSON API bodies (a chat message is far smaller)
LOGIN_WINDOW_S = 300.0                # failed-login throttle window...
LOGIN_MAX_FAILURES = 10               # ...and how many failures it allows per client

# Uploaded files are served same-origin; anything a browser could execute is
# forced to download and sandboxed, so an uploaded .html/.svg can't run as the app.
_INLINE_SAFE = ("image/png", "image/jpeg", "image/gif", "image/webp", "image/avif", "image/bmp",
                "audio/", "video/", "application/pdf", "text/plain", "text/csv", "application/json")

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
        secure = "; Secure" if scope.get("scheme") == "https" else ""
        cookies = _parse_cookies(scope)
        uid = cookies.get(UID_COOKIE)
        new = not (uid and len(uid) <= 64 and uid.replace("_", "").isalnum())
        if new:
            uid = "u_" + secrets.token_hex(12)
        scope.setdefault("state", {})["dyui_uid"] = uid

        async def send_wrapper(message: Any) -> None:
            if new and message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"set-cookie", f"{UID_COOKIE}={uid}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Lax{secure}".encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)


class _BodyLimitMiddleware:
    """Pure-ASGI middleware: reject request bodies over a size limit with 413.

    Checks ``Content-Length`` up front and also counts streamed (chunked) bytes,
    so an oversized body is never buffered in memory or spooled to disk.
    """

    def __init__(self, app: Any, limit_for: Callable[[str], int]) -> None:
        self.app = app
        self.limit_for = limit_for

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope.get("method") in ("GET", "HEAD", "OPTIONS"):
            await self.app(scope, receive, send)
            return
        limit = self.limit_for(scope.get("path", ""))
        for k, v in scope.get("headers", []):
            if k == b"content-length":
                try:
                    declared = int(v)
                except ValueError:
                    await _send_json(send, 400, {"error": "Bad Content-Length."})
                    return
                if declared > limit:
                    await _send_json(send, 413, {"error": "Request is too large."})
                    return
        seen = 0
        exceeded = False
        started = False

        async def limited_receive() -> Any:
            nonlocal seen, exceeded
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    exceeded = True
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Any) -> None:
            nonlocal started
            if exceeded:
                return  # the 413 below replaces whatever the app tries to say
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if not exceeded:
                raise
        if exceeded and not started:
            await _send_json(send, 413, {"error": "Request is too large."})


async def _send_json(send: Any, status: int, body: Any) -> None:
    raw = json.dumps(body).encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(raw)).encode())]})
    await send({"type": "http.response.body", "body": raw})


class _LoginThrottle:
    """Failed-login counter per client address (in memory, sliding window)."""

    def __init__(self) -> None:
        self._fails: dict[str, list[float]] = {}

    def _recent(self, key: str, now: float) -> list[float]:
        hits = [t for t in self._fails.get(key, []) if now - t < LOGIN_WINDOW_S]
        if hits:
            self._fails[key] = hits
        else:
            self._fails.pop(key, None)
        return hits

    def blocked(self, key: str, now: float) -> bool:
        return len(self._recent(key, now)) >= LOGIN_MAX_FAILURES

    def fail(self, key: str, now: float) -> None:
        self._recent(key, now)
        self._fails.setdefault(key, []).append(now)
        if len(self._fails) > 10_000:  # bound memory under a spray of addresses
            self._fails.pop(next(iter(self._fails)))

    def clear(self, key: str) -> None:
        self._fails.pop(key, None)


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
    return hmac.compare_digest(token.encode("utf-8", "replace"), _auth_token(app).encode())


def _err(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


# ------------------------------------------------------------------ SSE
def _frame(event: str, data: Any) -> str:
    payload = json.dumps(finite(data), separators=(",", ":"), default=str, allow_nan=False)
    return f"event: {event}\ndata: {payload}\n\n"


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
    throttle = _LoginThrottle()

    async def guard(request: Request) -> JSONResponse | None:
        if not _authed(app, request):
            return _err(401, "Password required.")
        return None

    @api.get("/api/config")
    async def get_config(request: Request) -> Any:
        return app.config(authenticated=_authed(app, request))

    @api.post("/api/login")
    async def login(request: Request) -> Any:
        import time

        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        if throttle.blocked(client, now):
            return _err(429, "Too many attempts. Try again in a few minutes.")
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError
        except Exception:
            return _err(400, "Invalid JSON.")
        given = str(body.get("password", "")).encode("utf-8", "replace")
        if not app.password or not hmac.compare_digest(given, app.password.encode("utf-8")):
            throttle.fail(client, now)
            return _err(401, "Wrong password.")
        throttle.clear(client)
        resp = JSONResponse({"ok": True})
        resp.set_cookie(AUTH_COOKIE, _auth_token(app), max_age=60 * 60 * 24 * 30, httponly=True,
                        samesite="lax", secure=request.url.scheme == "https")
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
        return finite({**_summary(t), "messages": [_public(m) for m in msgs]})

    @api.patch("/api/threads/{thread_id}")
    async def rename_thread(thread_id: str, request: Request) -> Any:
        if (denied := await guard(request)) is not None:
            return denied
        t = await app.store.get_thread(thread_id)
        if t is None or t.get("user_id") != _uid(request):
            return _err(404, "Conversation not found.")
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError
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
        # verify before opening the stream so forged/replayed actions get a real 4xx
        status, problem, _ = await app.check_action(uid, body)
        if status:
            return _err(status, problem)
        return _sse(app, lambda turn: app.handle_action(turn, uid, body))

    @api.post("/api/feedback")
    async def feedback(request: Request) -> Any:
        if (denied := await guard(request)) is not None:
            return denied
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError
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
        ctype = (rec.get("type") or "application/octet-stream").split(";")[0].strip().lower()
        inline = ctype.startswith(_INLINE_SAFE)
        return FileResponse(rec["path"], media_type=ctype if inline else "application/octet-stream",
                            filename=rec.get("name"), content_disposition_type="inline" if inline else "attachment",
                            headers={"X-Content-Type-Options": "nosniff",
                                     "Content-Security-Policy": "sandbox; default-src 'none'; img-src 'self'; media-src 'self'"})

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

    upload_limit = app.max_upload_mb * 1024 * 1024 + 64 * 1024  # multipart overhead

    def limit_for(path: str) -> int:
        return upload_limit if path.rstrip("/").endswith("/api/upload") else MAX_JSON_BYTES

    return _IdentityMiddleware(_BodyLimitMiddleware(api, limit_for))


def _html_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))
