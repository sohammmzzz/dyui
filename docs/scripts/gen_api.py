"""Generate the Python API reference (griffe → Markdown) for the docs site.

Reads the source in ../python statically (no import side effects) and writes
one page per public area into docs/src/content/docs/reference/api/ (gitignored).

Usage:  python docs/scripts/gen_api.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import griffe

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "src" / "content" / "docs" / "reference" / "api"

# page slug → (title, description, [object paths])
PAGES: list[tuple[str, str, str, list[str]]] = [
    ("app", "App", "Declare a chatbot: config, decorators, catalog and the ASGI app.", ["App"]),
    ("chat", "Chat & messages", "The objects your handlers receive: Chat, Message, Action, Feedback, File, Step.",
     ["chat.Chat", "chat.Step", "chat.Message", "chat.Action", "chat.Feedback", "chat.File", "chat.Starter", "parts.Reasoning"]),
    ("components", "Components & catalog", "The Component base class, the Catalog and prompt generation.",
     ["ui.base.Component", "genui.catalog.Catalog", "genui.catalog.catalog", "html.html_template"]),
    ("llm", "dyui.llm", "Streaming helpers for OpenAI, Anthropic, Ollama and OpenAI-compatible providers.",
     ["llm._stream.stream", "llm._stream.complete", "llm._providers.Provider", "llm._errors.MissingDependencyError"]),
    ("langgraph", "dyui.integrations.langgraph", "Stream a LangGraph run into a DyUI reply and emit components from nodes.",
     ["integrations.langgraph.stream", "integrations.langgraph.emit"]),
    ("genui", "dyui.genui", "The streaming fence parser, partial JSON, validation and history serialization.",
     ["genui.parser.FenceParser", "genui.parser.parse_text", "genui.partial_json.parse_partial",
      "genui.history.serialize_history", "genui.history.action_text", "genui.validate.repair_message"]),
    ("store", "Stores", "Persistence: the Store protocol, SQLite and in-memory stores.",
     ["store.base.Store", "store.sqlite.SQLiteStore", "store.memory.MemoryStore"]),
]

PUBLIC_NAMES = {
    "chat.Chat": "dyui.Chat", "chat.Step": "dyui.Step", "chat.Message": "dyui.Message", "chat.Action": "dyui.Action",
    "chat.Feedback": "dyui.Feedback", "chat.File": "dyui.File", "chat.Starter": "dyui.Starter",
    "parts.Reasoning": "dyui.Reasoning", "ui.base.Component": "dyui.Component", "genui.catalog.Catalog": "dyui.Catalog",
    "genui.catalog.catalog": "dyui.catalog", "html.html_template": "dyui.html_template", "App": "dyui.App",
    "llm._stream.stream": "dyui.llm.stream", "llm._stream.complete": "dyui.llm.complete",
    "llm._providers.Provider": "dyui.llm.Provider", "llm._errors.MissingDependencyError": "dyui.llm.MissingDependencyError",
    "integrations.langgraph.stream": "dyui.integrations.langgraph.stream",
    "integrations.langgraph.emit": "dyui.integrations.langgraph.emit",
    "store.base.Store": "dyui.store.Store", "store.sqlite.SQLiteStore": "dyui.store.SQLiteStore",
    "store.memory.MemoryStore": "dyui.store.MemoryStore",
}

ROLE_RE = re.compile(r":(?:class|func|meth|data|attr|mod|obj):`~?([^`]+)`")
RST_CODE_RE = re.compile(r"``([^`]+)``")


def _inline(text: str) -> str:
    """Convert RST-ish inline markup to Markdown and escape stray angle brackets."""
    text = ROLE_RE.sub(r"`\1`", text)
    text = RST_CODE_RE.sub(r"`\1`", text)
    # escape < > { } outside code spans so Markdown/MDX never sees raw HTML
    out, in_code = [], False
    for ch in text:
        if ch == "`":
            in_code = not in_code
            out.append(ch)
        elif not in_code and ch in "<>":
            out.append("&lt;" if ch == "<" else "&gt;")
        else:
            out.append(ch)
    return "".join(out)


def _ann(value) -> str:
    return "" if value is None else str(value)


def _signature(obj) -> str:
    params = []
    star_seen = False
    for p in obj.parameters:
        if p.name in ("self", "cls"):
            continue
        kind = p.kind.value if p.kind else ""
        if kind == "keyword-only" and not star_seen:
            params.append("*")
            star_seen = True
        prefix = "*" if kind == "variadic positional" else "**" if kind == "variadic keyword" else ""
        if prefix == "*":
            star_seen = True
        piece = prefix + p.name
        if p.annotation is not None:
            piece += f": {_ann(p.annotation)}"
        if p.default is not None and not prefix:
            piece += f" = {p.default}"
        params.append(piece)
    ret = f" -> {_ann(obj.returns)}" if getattr(obj, "returns", None) else ""
    asyn = "async " if "async" in getattr(obj, "labels", set()) else ""
    one = f"{asyn}def {obj.name}({', '.join(params)}){ret}"
    if len(one) <= 88:
        return one
    inner = ",\n".join(f"    {x}" for x in params)
    return f"{asyn}def {obj.name}(\n{inner},\n){ret}"


def _sections(doc) -> list[str]:
    if doc is None:
        return []
    out: list[str] = []
    for sec in doc.parsed:
        kind = sec.kind.value
        if kind == "text":
            out.append(_inline(sec.value))
        elif kind in ("parameters", "other parameters", "attributes"):
            label = {"parameters": "Parameters", "other parameters": "Other parameters", "attributes": "Attributes"}[kind]
            rows = [f"| `{p.name}` | {('`' + _ann(p.annotation) + '`') if p.annotation else ''} | "
                    f"{_inline(p.description).replace(chr(10), ' ').replace('|', chr(92) + '|')} |" for p in sec.value]
            out.append(f"**{label}**\n\n| Name | Type | Description |\n|---|---|---|\n" + "\n".join(rows))
        elif kind in ("returns", "yields"):
            label = "Returns" if kind == "returns" else "Yields"
            items = [f"- {('`' + _ann(r.annotation) + '` — ') if r.annotation else ''}{_inline(r.description)}" for r in sec.value]
            out.append(f"**{label}**\n\n" + "\n".join(items))
        elif kind in ("raises", "warns"):
            items = [f"- `{_ann(r.annotation)}` — {_inline(r.description)}" for r in sec.value]
            out.append(f"**{'Raises' if kind == 'raises' else 'Warns'}**\n\n" + "\n".join(items))
        elif kind == "examples":
            for sub_kind, value in sec.value:
                if sub_kind.value == "examples":
                    out.append("```python\n" + value + "\n```")
                else:
                    out.append(_inline(value))
        elif kind == "admonition":
            out.append(f"> **{sec.title or ''}** {_inline(sec.value.description)}")
    return out


# public-by-name but server plumbing, not part of the user-facing API
INTERNAL = {"App.handle_chat", "App.handle_action", "App.handle_feedback", "App.start_thread", "App.config"}


def _is_public(member) -> bool:
    return not member.name.startswith("_") and f"{member.parent.name}.{member.name}" not in INTERNAL


def _render_function(obj, heading: str, level: int = 2) -> list[str]:
    hashes = "#" * level
    lines = [f"{hashes} `{heading}`", "", "```python", _signature(obj), "```", ""]
    lines += [s + "\n" for s in _sections(obj.docstring)]
    return lines


def _render_class(obj, public: str) -> list[str]:
    lines = [f"## `{public}`", ""]
    init = obj.members.get("__init__")
    if init is not None and getattr(init, "is_function", False) and init.parameters and len(list(init.parameters)) > 1:
        sig = _signature(init).replace("def __init__", f"class {obj.name}", 1).replace(" -> None", "")
        lines += ["```python", sig, "```", ""]
    else:
        bases = ", ".join(str(b) for b in obj.bases)
        lines += ["```python", f"class {obj.name}{f'({bases})' if bases else ''}", "```", ""]
    lines += [s + "\n" for s in _sections(obj.docstring)]
    if init is not None and init.docstring and init.docstring is not obj.docstring:
        lines += [s + "\n" for s in _sections(init.docstring)]
    for name, member in obj.members.items():
        if not _is_public(member) or member.is_alias:
            continue
        if member.is_function:
            label = "property" if "property" in member.labels else ("async method" if "async" in member.labels else "method")
            if label == "property":
                ann = f": {_ann(member.returns)}" if member.returns else ""
                lines += [f"### `{obj.name}.{name}`", "", f"*property*{(' — `' + ann[2:] + '`') if ann else ''}", ""]
                lines += [s + "\n" for s in _sections(member.docstring)]
            else:
                lines += _render_function(member, f"{obj.name}.{name}()", level=3)
        elif member.is_attribute and member.docstring:
            ann = f" `{_ann(member.annotation)}`" if member.annotation else ""
            lines += [f"### `{obj.name}.{name}`{ann}", ""] + [s + "\n" for s in _sections(member.docstring)]
    return lines


def _frontmatter(title: str, description: str, order: int) -> str:
    esc = lambda s: s.replace('"', '\\"')  # noqa: E731
    return f'---\ntitle: "{esc(title)}"\ndescription: "{esc(description)}"\nsidebar:\n  order: {order}\n---\n\n'


def main() -> int:
    pkg = griffe.load("dyui", search_paths=[str(ROOT / "python")], docstring_parser="google",
                      resolve_aliases=True, resolve_external=False)
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.md"):
        stale.unlink()
    index_rows = []
    for order, (slug, title, description, paths) in enumerate(PAGES, start=1):
        body: list[str] = [
            ":::note\nGenerated from the docstrings in `python/dyui` at build time.\n:::\n",
        ]
        for path in paths:
            try:
                obj = pkg[path]
            except KeyError:
                print(f"gen_api: {path} not found", file=sys.stderr)
                return 1
            if obj.is_alias:
                obj = obj.final_target
            public = PUBLIC_NAMES.get(path, f"dyui.{path}")
            if obj.is_class:
                body += _render_class(obj, public)
            elif obj.is_function:
                body += _render_function(obj, f"{public}()")
            body.append("")
        (OUT / f"{slug}.md").write_text(_frontmatter(title, description, order) + "\n".join(body), encoding="utf-8")
        index_rows.append(f"- [{title}](./{slug}/) — {description}")
    index = _frontmatter("Python API reference", "Every public class and function in the dyui package.", 0)
    index += ("The reference is generated from the package's docstrings with "
              "[griffe](https://mkdocstrings.github.io/griffe/) on every docs build, so it always matches the code.\n\n"
              + "\n".join(index_rows) + "\n\nThe built-in components (`dyui.ui.*`) are documented on the "
              "[component pages](../../components/).\n")
    (OUT / "index.md").write_text(index, encoding="utf-8")
    print(f"gen_api: wrote {len(PAGES) + 1} pages -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
