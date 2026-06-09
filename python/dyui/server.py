"""FastAPI adapter: expose a LangGraph agent to the DyUI frontend over SSE.

The browser ``DyUIClient`` POSTs ``{"input": ..., "config": ...}`` and reads a
``text/event-stream`` response. Each frame from :func:`dyui.stream.astream_ui`
becomes one SSE event:

    event: ui
    data: {"id": "...", "component": "table", "props": {...}, "status": "done"}

    event: token
    data: {"text": "Hello", "node": "agent"}

    event: done
    data: {}

We use Starlette's plain ``StreamingResponse`` so the only hard dependency is
FastAPI itself. ``add_dyui_routes`` mounts onto an existing app;
``create_dyui_app`` spins up a ready-to-run app with permissive CORS for local
development.
"""

# NOTE: intentionally *not* using ``from __future__ import annotations`` here.
# FastAPI resolves route handler type hints against module globals; keeping the
# ``Request`` annotation a real object (evaluated at def time) avoids that.

import html as _html
import json
from pathlib import Path
from typing import Any, Callable, Optional

from .stream import astream_ui

_STATIC_DIR = Path(__file__).parent / "static"

# Request bodies above this size are rejected before we parse JSON, so a single
# oversized POST can't exhaust memory on the (dev) server.
_MAX_BODY_BYTES = 2 * 1024 * 1024  # 2 MiB

# Candidate state fields a bare user string is mapped onto, most-likely first.
_TEXT_FIELDS = (
    "messages", "input", "query", "question", "prompt", "text", "message", "task",
)


def _graph_input_keys(graph: Any) -> Optional[set[str]]:
    """Best-effort discovery of a compiled graph's top-level input field names.

    Returns ``None`` when nothing can be determined. Used only to make the
    default input handling plug-and-play; never raises.
    """
    # 1) The builder's state-schema annotations are the cleanest source.
    builder = getattr(graph, "builder", None)
    state_schema = getattr(builder, "state_schema", None)
    ann = getattr(state_schema, "__annotations__", None)
    if isinstance(ann, dict) and ann:
        return set(ann)
    # 2) Pydantic input schema (can raise on some Python/typing combos).
    getter = getattr(graph, "get_input_schema", None)
    if getter is not None:
        try:
            model_fields = getattr(getter(), "model_fields", None)
            if isinstance(model_fields, dict) and model_fields:
                return set(model_fields)
        except Exception:
            pass
    # 3) Channels, minus LangGraph's internal bookkeeping keys.
    channels = getattr(graph, "channels", None)
    if isinstance(channels, dict):
        keys = {
            k for k in channels
            if isinstance(k, str) and not k.startswith("__") and ":" not in k
        }
        if keys:
            return keys
    return None


def make_smart_input_adapter(graph: Any) -> Callable[[dict[str, Any]], Any]:
    """Build a forgiving ``(body) -> graph_input`` adapter for *any* graph.

    This is what makes DyUI plug-and-play: the browser only ever sends a plain
    string, and most LangGraph agents expect a state dict (``{"messages": ...}``,
    ``{"query": ...}``, etc.). The adapter inspects the graph's input schema once
    and maps a bare string onto the right field:

    * a structured ``input`` (dict/list) is passed through untouched;
    * a string is wrapped into the first matching well-known field
      (``messages`` becomes ``[("user", text)]``), or into the graph's sole input
      field when it has exactly one, or finally into the ubiquitous
      ``{"messages": [("user", text)]}`` chat shape.

    Pass your own ``input_adapter`` to ``create_dyui_app`` to override this.
    """
    keys = _graph_input_keys(graph)

    def adapter(body: dict[str, Any]) -> Any:
        raw = body.get("input")
        if isinstance(raw, (dict, list)) or raw is None:
            return raw  # already structured (or empty) -> trust the caller
        text = raw if isinstance(raw, str) else str(raw)
        if keys:
            for field in _TEXT_FIELDS:
                if field in keys:
                    return {"messages": [("user", text)]} if field == "messages" else {field: text}
            if len(keys) == 1:
                return {next(iter(keys)): text}
        return {"messages": [("user", text)]}

    return adapter


def _format_sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def render_ui_page(
    *,
    stream_path: str = "/dyui/stream",
    title: str = "DyUI",
    show_input: bool = True,
    auto_input: Optional[str] = None,
) -> str:
    """Return the built-in single-file UI page with placeholders filled in."""
    html = (_STATIC_DIR / "index.html").read_text(encoding="utf-8")
    # ``title`` lands in HTML text nodes (<title>, a <div>) -> HTML-escape it.
    # ``stream_path`` lands in a JS string literal -> JSON-encode it (the
    # template now reads ``const STREAM_PATH = __DYUI_STREAM_PATH__;`` with no
    # surrounding quotes). Both prevent injection if these are ever sourced from
    # user/tenant config rather than the developer.
    return (
        html.replace("__DYUI_STREAM_PATH__", json.dumps(stream_path))
        .replace("__DYUI_TITLE__", _html.escape(title))
        .replace("__DYUI_SHOW_INPUT__", "true" if show_input else "false")
        .replace("__DYUI_AUTO_INPUT__", json.dumps(auto_input))
    )


def mount_ui(
    app: Any,
    *,
    route: str = "/",
    stream_path: str = "/dyui/stream",
    title: str = "DyUI",
    show_input: bool = True,
    auto_input: Optional[str] = None,
) -> None:
    """Serve the built-in zero-config UI page at ``route`` (GET).

    This is what makes DyUI usable with *no frontend code*: the same server that
    runs your agent also hands the browser a ready-made screen that renders every
    built-in card plus your raw ``html`` cards.
    """
    from fastapi.responses import HTMLResponse

    page = render_ui_page(
        stream_path=stream_path, title=title, show_input=show_input, auto_input=auto_input
    )

    @app.get(route, response_class=HTMLResponse, include_in_schema=False)
    async def dyui_ui() -> "HTMLResponse":  # noqa: D401
        return HTMLResponse(page)


def _sanitize_client_config(cfg: Any) -> dict[str, Any]:
    """Strip security-sensitive keys from a client-supplied run config.

    A client must never be able to choose the checkpointer ``thread_id`` /
    checkpoint (that would let one caller read or resume another caller's
    persisted state) nor override server-controlled limits like
    ``recursion_limit``. We forward only a cleaned ``configurable`` mapping.
    """
    if not isinstance(cfg, dict):
        return {}
    safe: dict[str, Any] = {}
    configurable = cfg.get("configurable")
    if isinstance(configurable, dict):
        blocked = {"thread_id", "checkpoint_id", "checkpoint_ns", "checkpoint_map"}
        clean = {
            k: v
            for k, v in configurable.items()
            if k not in blocked and not str(k).startswith("__")
        }
        if clean:
            safe["configurable"] = clean
    return safe


def add_dyui_routes(
    app: Any,
    graph: Any,
    *,
    path: str = "/dyui/stream",
    stream_tokens: bool = True,
    input_adapter: Optional[Callable[[dict[str, Any]], Any]] = None,
    config_adapter: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None,
    smart_input: bool = True,
    allow_client_config: bool = False,
    api_token: Optional[str] = None,
    debug_errors: bool = False,
) -> None:
    """Mount a DyUI streaming endpoint on an existing FastAPI app.

    Args:
        app: A FastAPI/Starlette application.
        graph: A compiled LangGraph graph.
        path: Route to expose (POST).
        stream_tokens: Forward LLM tokens as ``token`` events too.
        input_adapter: Optional ``(body) -> graph_input`` hook. Overrides the
            default handling entirely when given.
        smart_input: When True (default) and no ``input_adapter`` is given, a
            schema-aware adapter (:func:`make_smart_input_adapter`) maps the
            browser's plain-string input onto the graph's expected state shape.
            Set False to fall back to passing ``body["input"]`` straight through.
        config_adapter: Optional ``(body) -> run_config`` hook. When given it is
            fully trusted and overrides the default config handling.
        allow_client_config: When False (the default) the request body's
            ``"config"`` is **ignored** -- a remote caller cannot influence the
            run config at all. When True the client config is forwarded after
            :func:`_sanitize_client_config` strips thread/checkpoint/limit keys.
        api_token: When set, require ``Authorization: Bearer <token>`` (or the
            ``X-DyUI-Token`` header) on the endpoint; otherwise 401.
        debug_errors: When True, send the raw exception text to the client on
            failure. Off by default so internal details don't leak.
    """
    import hmac

    from fastapi import HTTPException, Request
    from fastapi.responses import StreamingResponse

    _default_input = make_smart_input_adapter(graph) if smart_input else None

    def _to_input(body: dict[str, Any]) -> Any:
        if input_adapter is not None:
            return input_adapter(body)
        if _default_input is not None:
            return _default_input(body)
        return body.get("input")

    def _to_config(body: dict[str, Any]) -> dict[str, Any]:
        if config_adapter is not None:
            return config_adapter(body)
        if not allow_client_config:
            return {}
        return _sanitize_client_config(body.get("config"))

    def _check_auth(request: "Request") -> None:
        if api_token is None:
            return
        provided = request.headers.get("authorization", "")
        if provided.lower().startswith("bearer "):
            provided = provided[7:]
        if not provided:
            provided = request.headers.get("x-dyui-token", "")
        if not hmac.compare_digest(provided, api_token):
            raise HTTPException(status_code=401, detail="unauthorized")

    @app.post(path)
    async def dyui_stream(request: Request) -> StreamingResponse:  # noqa: D401
        _check_auth(request)

        # Reject oversized bodies before parsing so one POST can't exhaust memory.
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > _MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="request body too large")
        raw = await request.body()
        if len(raw) > _MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="request body too large")
        try:
            body = json.loads(raw or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise HTTPException(status_code=400, detail="invalid JSON body")
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="JSON body must be an object")

        graph_input = _to_input(body)
        run_config = _to_config(body)

        async def event_generator():
            try:
                async for kind, data in astream_ui(
                    graph,
                    graph_input,
                    config=run_config,
                    stream_tokens=stream_tokens,
                ):
                    if await request.is_disconnected():
                        break
                    yield _format_sse(kind, data)
            except Exception as exc:  # surface failures to the UI, don't 500 silently
                message = str(exc) if debug_errors else "The agent run failed."
                yield _format_sse("error", {"message": message})
                yield _format_sse("done", {})

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # disable proxy buffering (nginx)
            },
        )


def create_dyui_app(
    graph: Any,
    *,
    path: str = "/dyui/stream",
    stream_tokens: bool = True,
    cors_origins: Optional[list[str]] = None,
    api_token: Optional[str] = None,
    serve_ui: bool = True,
    ui_title: str = "DyUI",
    ui_show_input: bool = True,
    ui_auto_input: Optional[str] = None,
    **route_kwargs: Any,
) -> Any:
    """Create a ready-to-run FastAPI app serving a single LangGraph agent.

    Includes a ``GET /healthz`` probe. CORS defaults to **same-machine origins
    only** (``localhost``/``127.0.0.1`` on any port): a wildcard would let any
    website you happen to be visiting POST to your locally-running agent and
    trigger tool side-effects / token spend. Pass ``cors_origins=[...]`` to allow
    specific remote origins, and ``api_token=...`` to require a bearer token.

    This is a development convenience server. For anything exposed beyond
    localhost, set ``api_token`` (or put it behind your own auth) and scope
    ``cors_origins`` explicitly.

    With ``serve_ui=True`` (the default) the app also hosts the built-in
    zero-config UI at ``GET /`` -- so you get a working dynamic-UI screen with no
    frontend code at all: just ``uvicorn your_module:app`` and open the browser.
    """
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(title="DyUI Agent Server")
    cors_kwargs: dict[str, Any] = dict(
        allow_credentials=False, allow_methods=["*"], allow_headers=["*"]
    )
    if cors_origins is not None:
        cors_kwargs["allow_origins"] = cors_origins
    else:
        # Secure default: same-machine browser origins on any port.
        cors_kwargs["allow_origins"] = []
        cors_kwargs["allow_origin_regex"] = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
    app.add_middleware(CORSMiddleware, **cors_kwargs)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    add_dyui_routes(
        app, graph, path=path, stream_tokens=stream_tokens, api_token=api_token,
        **route_kwargs,
    )

    if serve_ui:
        mount_ui(
            app,
            route="/",
            stream_path=path,
            title=ui_title,
            show_input=ui_show_input,
            auto_input=ui_auto_input,
        )
    return app
