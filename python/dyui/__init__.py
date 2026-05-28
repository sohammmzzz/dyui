"""DyUI -- a dynamic-UI layer for any LangGraph agent.

Emit rich, live UI "cards" from inside any LangGraph node or tool, with any LLM
(or none). The companion ``dyui-react`` package renders those cards on the
frontend via a pluggable registry that also supports raw custom HTML.

Quick start (agent side)::

    from dyui import emit, ui_tool

    @ui_tool("stat", title="Weather", icon="cloud", accent="cyan")
    def get_weather(city: str) -> dict:
        return {"label": city, "value": 21, "unit": "C"}

    # or imperatively, anywhere inside a node:
    emit("table", {"columns": ["a", "b"], "rows": [[1, 2]]}, title="Results")

Quick start (server side)::

    from dyui.server import create_dyui_app
    app = create_dyui_app(my_compiled_graph)   # uvicorn dyui_app:app
"""

from .__version__ import __version__
from .emit import Card, emit, ui_tool, update
from .events import DYUI_KEY, Status, UIEvent, is_dyui_payload, parse_envelope
from .stream import astream_ui, collect, collect_events
from .templates import HtmlTemplates, render_template

__all__ = [
    "__version__",
    "emit",
    "update",
    "ui_tool",
    "Card",
    "UIEvent",
    "Status",
    "DYUI_KEY",
    "is_dyui_payload",
    "parse_envelope",
    "astream_ui",
    "collect",
    "collect_events",
    "HtmlTemplates",
    "render_template",
    # lazily provided (need FastAPI):
    "create_dyui_app",
    "add_dyui_routes",
    "mount_ui",
    "render_ui_page",
]


def __getattr__(name: str):
    # Lazily expose the FastAPI helpers so importing ``dyui`` never hard-requires
    # FastAPI (it's an optional ``[server]`` extra).
    if name in {"create_dyui_app", "add_dyui_routes", "mount_ui", "render_ui_page"}:
        from . import server

        return getattr(server, name)
    raise AttributeError(f"module 'dyui' has no attribute {name!r}")
