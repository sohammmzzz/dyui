"""The complete, runnable app shown at the end of every component page.

``component_app(c)`` takes one entry of ``src/data/components.json`` (``name``, ``class``,
``python``) and returns a whole ``app.py``: imports, the ``App``, an ``on_message`` handler
that yields the component, and one ``@app.on_action`` handler per action the component can
send (so buttons, forms, choices, confirms and ratings do something when clicked).

gen_components.py stores the result as ``app`` in components.json; the docs page shows it
with a title (so docs/scripts/check_snippets.py compiles it) and offers it as a download;
python/tests/test_docs_examples.py runs every one of them end to end.
"""
from __future__ import annotations

import keyword
import re
from typing import Any

import dyui
from dyui import ui
from dyui.chat import declared_action_entries


def _actions(examples: list[str]) -> list[str]:
    """Every action name the examples' components can send, in first-seen order."""
    seen: list[str] = []
    for code in examples:
        node = eval(code, {"ui": ui, "dyui": dyui}).to_node()  # noqa: S307 - our own verified examples
        stack = [node]
        while stack:
            n = stack.pop(0)
            for name, _data in declared_action_entries(n):
                if name not in seen:
                    seen.append(name)
            stack.extend(n.get("children") or [])
    return seen


def _ident(action: str) -> str:
    name = re.sub(r"\W+", "_", action).strip("_").lower() or "action"
    name = f"on_{name}"
    return name + "_" if keyword.iskeyword(name) else name


def component_app(c: dict[str, Any]) -> str:
    name, cls, examples = c["name"], c["class"], list(c["python"])
    lines = [
        f'"""A complete DyUI app that shows the `{name}` component.',
        "",
        "Save it as app.py, then run:  dyui run app.py",
        '"""',
        "import dyui",
        "from dyui import ui",
        "",
        f'app = dyui.App(title="{cls} demo", starters=["Show me"], persist=False)',
        "",
        "",
        "@app.on_message",
        "async def reply(msg: dyui.Message, chat: dyui.Chat):",
        f'    yield "Here is the `{name}` component."',
    ]
    lines += [f"    yield {code}" for code in examples]
    if name == "quick_replies":
        lines.append("    # tapping an option sends its text as a new message, which runs reply() again")
    for action in _actions(examples):
        lines += [
            "",
            "",
            f'@app.on_action("{action}")',
            f"async def {_ident(action)}(action: dyui.Action, chat: dyui.Chat):",
            "    # action.values holds what the user entered or chose; action.data is the static data",
            f'    yield f"Got `{{action.name}}` from **{{action.label}}** with values `{{action.values}}`."',
        ]
    return "\n".join(lines) + "\n"
