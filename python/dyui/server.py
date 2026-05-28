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

import json
from pathlib import Path
from typing import Any, Callable, Optional

from .stream import astream_ui

_STATIC_DIR = Path(__file__).parent / "static"


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
    return (
        html.replace("__DYUI_STREAM_PATH__", stream_path)
        .replace("__DYUI_TITLE__", title)
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


def add_dyui_routes(
    app: Any,
    graph: Any,
    *,
    path: str = "/dyui/stream",
    stream_tokens: bool = True,
    input_adapter: Optional[Callable[[dict[str, Any]], Any]] = None,
    config_adapter: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None,
) -> None:
    """Mount a DyUI streaming endpoint on an existing FastAPI app.

    Args:
        app: A FastAPI/Starlette application.
        graph: A compiled LangGraph graph.
        path: Route to expose (POST).
        stream_tokens: Forward LLM tokens as ``token`` events too.
        input_adapter: Optional ``(body) -> graph_input`` hook. By default the
            request body's ``"input"`` field is passed straight to the graph.
        config_adapter: Optional ``(body) -> run_config`` hook. By default the
            request body's ``"config"`` field is used.
    """
    from fastapi import Request
    from fastapi.responses import StreamingResponse

    def _to_input(body: dict[str, Any]) -> Any:
        if input_adapter is not None:
            return input_adapter(body)
        return body.get("input")

    def _to_config(body: dict[str, Any]) -> dict[str, Any]:
        if config_adapter is not None:
            return config_adapter(body)
        return body.get("config") or {}

    @app.post(path)
    async def dyui_stream(request: Request) -> StreamingResponse:  # noqa: D401
        body = await request.json()
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
                yield _format_sse("error", {"message": str(exc)})
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
    serve_ui: bool = True,
    ui_title: str = "DyUI",
    ui_show_input: bool = True,
    ui_auto_input: Optional[str] = None,
    **route_kwargs: Any,
) -> Any:
    """Create a ready-to-run FastAPI app serving a single LangGraph agent.

    Includes a ``GET /healthz`` probe and permissive CORS (``*`` by default) so
    a local frontend on another port can connect immediately.

    With ``serve_ui=True`` (the default) the app also hosts the built-in
    zero-config UI at ``GET /`` -- so you get a working dynamic-UI screen with no
    frontend code at all: just ``uvicorn your_module:app`` and open the browser.
    """
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(title="DyUI Agent Server")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    add_dyui_routes(
        app, graph, path=path, stream_tokens=stream_tokens, **route_kwargs
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
