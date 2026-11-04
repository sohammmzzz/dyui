"""DyUI — chatbots that answer in interfaces.

Write one Python file, run ``dyui run app.py``, and get a professional chat app
whose LLM can render tables, charts, cards, forms and buttons inline.

Example:
    >>> import dyui
    >>> app = dyui.App(title="Travel Bot")
    >>> @app.on_message
    ... async def reply(msg, chat):
    ...     async for part in dyui.llm.stream("openai/gpt-5", chat.history, components=app.catalog):
    ...         yield part
"""
from __future__ import annotations

from typing import Any

from . import ui
from .__version__ import __version__
from .app import App
from .chat import Action, Chat, Feedback, File, Message, Starter, Step
from .genui import Catalog, catalog
from .html import html_template
from .parts import Reasoning
from .ui import Component

__all__ = [
    "App", "Chat", "Message", "Action", "Feedback", "File", "Starter", "Step",
    "Component", "Reasoning", "Catalog", "catalog", "ui", "html_template", "llm", "__version__",
]


def __getattr__(name: str) -> Any:  # lazy: keeps `import dyui` cheap and SDK-free
    if name in ("llm", "integrations"):
        import importlib

        module = importlib.import_module(f"dyui.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module 'dyui' has no attribute {name!r}")
