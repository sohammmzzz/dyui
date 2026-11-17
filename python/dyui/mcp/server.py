"""The DyUI MCP server (stdio): tools, resources and prompts for coding agents.

Every tool is a plain Python function in this module (``TOOLS``), so it can be tested and
reused without the ``mcp`` package; :func:`build_server` registers them on the SDK's server
class (``mcp.server.mcpserver.MCPServer`` in mcp 2.x, ``mcp.server.fastmcp.FastMCP`` in 1.x).
Tools never raise to the client: problems come back as text starting with ``Error:``.
"""
from __future__ import annotations

import functools
import inspect
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Optional, Union

from ..__version__ import __version__
from . import INSTALL_HINT

__all__ = [
    "TOOLS",
    "PROMPTS",
    "SERVER_NAME",
    "INSTRUCTIONS",
    "build_server",
    "main",
    "dyui_overview",
    "list_docs",
    "read_doc",
    "search_docs",
    "list_components",
    "get_component",
    "list_examples",
    "get_example",
    "get_template",
    "validate_ui",
    "check_app",
    "catalog_prompt",
]

SERVER_NAME = "dyui"
INSTRUCTIONS = (
    f"DyUI {__version__}: the Python framework for chat apps whose LLM answers with tables, charts, cards, "
    "forms and buttons. Call `dyui_overview` first. Look up components with `get_component` instead of "
    "guessing constructors, search the docs with `search_docs`/`read_doc`, and verify your work with "
    "`validate_ui` and `check_app` before reporting success."
)


# ------------------------------------------------------------------ skill text reuse
def _skill_body() -> str:
    """The fallback skill (``dyui/skill/SKILL.md``) rendered, without its frontmatter."""
    from ..agents import render_skill

    text = render_skill()
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        text = text[end + 4:].lstrip("\n") if end != -1 else text
    return text


def _sections(text: str, level: str = "## ") -> list[tuple[str, str]]:
    """``[(heading, body)]`` split on headings of one level (code blocks respected)."""
    out: list[tuple[str, str]] = []
    heading, buf = "", []
    in_code = False
    for line in text.split("\n"):
        if line.startswith("```"):
            in_code = not in_code
        if not in_code and line.startswith(level):
            out.append((heading, "\n".join(buf)))
            heading, buf = line[len(level):].strip(), []
        else:
            buf.append(line)
    out.append((heading, "\n".join(buf)))
    return out


def _playbooks() -> dict[str, str]:
    """Playbooks A–E of the skill, keyed by letter."""
    body = dict(_sections(_skill_body())).get("Playbooks", "")
    out = {}
    for heading, text in _sections(body, "### "):
        m = re.match(r"([A-E])\.\s*(.*)", heading)
        if m:
            out[m.group(1)] = f"### {heading}\n{text.strip()}\n"
    return out


_TOOL_GUIDE = """\
## Tools on this server

| Tool | Use it to |
|---|---|
| `dyui_overview()` | read this page (start here) |
| `list_docs()` / `read_doc(slug)` / `search_docs(query)` | read the docs of the installed version, offline |
| `list_components()` / `get_component(name)` | exact props, types, defaults, JSON schema, Python and model examples, actions |
| `list_examples()` / `get_example(name)` / `get_template(name)` | complete runnable apps and the `dyui new` templates |
| `validate_ui(payload)` | check a `{"ui": ...}` object, JSON lines or a whole reply with ```dyui fences |
| `check_app(path)` | import an app in a subprocess: errors, handlers, components, catalog, common mistakes |
| `catalog_prompt(path, only)` | the exact "UI components" section the model receives |

Prompts (playbooks): `build_app`, `convert_project`, `design_components`, `production_checklist`.
Resources: `dyui://docs/<slug>`, `dyui://components/<name>`, `dyui://examples/<name>`.

Never guess a constructor or a prop: call `get_component`. Before you report success, run
`check_app` on the app file and `validate_ui` on any component JSON you wrote by hand.
"""


# ------------------------------------------------------------------ tool helpers
def _safe(fn: Callable[..., str]) -> Callable[..., str]:
    """Turn any exception into ``Error: ...`` text (tools never raise to the client)."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> str:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - reported to the agent, not swallowed
            from .check import mask_secrets

            return mask_secrets(f"Error: {fn.__name__} failed: {type(exc).__name__}: {exc}")

    return wrapper


def _names(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        return [v.strip() for v in values.split(",") if v.strip()]
    return [str(v).strip() for v in values if str(v).strip()]


# ------------------------------------------------------------------ tools
@_safe
def dyui_overview() -> str:
    """Start here. DyUI's mental model, the 30-second app, what handlers yield, models and API keys,
    custom components, actions, the playbooks and the mistakes to avoid, for the installed version."""
    from . import docs

    keep_skip = {"Built-in components", "Playbooks", "How to work", "Verify"}
    parts = [f"# DyUI {__version__}: overview for coding agents\n",
             "Python package `dyui` (`pip install dyui`). One Python file plus `dyui run` gives a complete "
             "streaming chat app (frontend and backend) in which the model renders UI components between its "
             "sentences.\n",
             "How to work: look at the project first, say what you found and what you will build, build it end "
             "to end (code, dependencies, `.env.example`, `.gitignore` entry for `.dyui/`), verify with "
             "`check_app` and `validate_ui`, then report what changed and what you could not verify. Keep the "
             "developer's existing logic: wrap it, do not rewrite it. Never put API keys in code.\n",
             _TOOL_GUIDE]
    for heading, body in _sections(_skill_body())[1:]:
        if heading in keep_skip:
            if heading == "Built-in components":
                from .introspect import component_classes

                names = ", ".join(c.__dyui__.name for c in component_classes(include_developer=False))
                parts.append("## Built-in components\n\nThe model writes `{\"ui\": \"<name>\", ...props}`; in Python "
                             "they are classes in `dyui.ui` with the same props. Names: " + names + ". Developer-only: "
                             "`html` (`ui.Html`). Call `get_component(name)` for the exact props and examples.\n")
            elif heading == "Playbooks":
                parts.append("## Playbooks\n\nA. new app from scratch (prompt `build_app`) · B. convert an existing "
                             "project (`convert_project`) · C. integrate into a web service (`convert_project`) · "
                             "D. design custom components (`design_components`) · E. production readiness "
                             "(`production_checklist`).\n")
            continue
        parts.append(f"## {heading}\n{body.rstrip()}\n")
    r = docs.root()
    parts.append(f"\n_Docs source: {r.kind}. {len(docs.pages())} pages, {len(docs.examples())} examples._\n")
    return "\n".join(parts)


@_safe
def list_docs() -> str:
    """Every DyUI docs page of the installed version: slug, title, description and section. Read one with read_doc(slug)."""
    from . import docs

    every = docs.pages()
    if not every:
        return "Error: no docs are bundled with this install. See https://sohammmzzz.github.io/dyui/"
    lines = [f"{len(every)} pages. Read one with read_doc(slug).", ""]
    section = None
    for pg in every:
        if pg.section != section:
            section = pg.section
            lines.append(f"## {section or 'root'}")
        lines.append(f"- `{pg.slug}`: {pg.title}" + (f". {pg.description}" if pg.description else ""))
    return "\n".join(lines)


@_safe
def read_doc(slug: str) -> str:
    """One docs page as Markdown (MDX resolved, full example sources inlined). slug is like 'concepts/actions' or 'cookbook/data-analyst'."""
    from . import docs

    text = docs.read_doc(slug)
    if text is None:
        hits = docs.search(slug.replace("/", " ").replace("-", " "), 5)
        near = ", ".join(f"`{h['ref']}`" for h in hits if h["kind"] == "doc") or "none"
        return f"Error: no docs page {slug!r}. Closest: {near}. Call list_docs() for every slug."
    return text


@_safe
def search_docs(query: str, limit: int = 8) -> str:
    """Keyword search over the docs, the example apps and component descriptions. Returns where to look (slug/name), the heading and a snippet."""
    from . import docs

    hits = docs.search(query, limit)
    if not hits:
        return f"No results for {query!r}. Try fewer or different words, or call list_docs()."
    lines = []
    for i, h in enumerate(hits, 1):
        how = {"doc": f"read_doc({h['ref']!r})", "example": f"get_example({h['ref']!r})",
               "component": f"get_component({h['ref']!r})"}[h["kind"]]
        where = f"{h['title']}" + (f" > {h['heading']}" if h["heading"] else "")
        lines.append(f"{i}. {where}  [{how}]\n   {h['snippet']}")
    return "\n".join(lines)


@_safe
def list_components() -> str:
    """Every built-in component: name, group, one-line description and Python class. Details: get_component(name)."""
    from .introspect import component_classes, component_summary

    rows = [component_summary(c) for c in component_classes()]
    lines = ["| name | group | python | description |", "|---|---|---|---|"]
    for r in rows:
        desc = r["description"] + ("" if r["offered_to_model"] else " (developer-only, never offered to the model)")
        lines.append(f"| `{r['name']}` | {r['group']} | `{r['python']}` | {desc} |")
    return "\n".join(lines)


@_safe
def get_component(name: str) -> str:
    """Everything about one component: props (types, defaults, required, positional), its JSON schema, the
    Python constructor and working examples, what the model writes, the prompt line, and for interactive
    components the action name and `values` shape. name: 'table', 'quick_replies', 'ui.KeyValue'..."""
    from .introspect import component_classes, component_markdown, find_component

    cls = find_component(name)
    if cls is None:
        names = ", ".join(c.__dyui__.name for c in component_classes())
        return (f"Error: no built-in component {name!r}. Built-ins: {names}. For an app's custom components "
                "use check_app(path) or catalog_prompt(path).")
    return component_markdown(cls)


@_safe
def list_examples() -> str:
    """The complete example apps (cookbook) and the `dyui new` templates. Source: get_example(name) / get_template(name)."""
    from . import docs

    lines = ["## Examples (get_example(name))"]
    for name, path in docs.examples().items():
        lines.append(f"- `{name}`: {docs.example_summary(path)}")
    lines += ["", "## Templates for `dyui new <dir> --template <name>` (get_template(name))"]
    for name in docs.templates():
        lines.append(f"- `{name}`")
    return "\n".join(lines)


@_safe
def get_example(name: str) -> str:
    """The full source of one example app, e.g. 'no_llm', 'travel_bot', 'data_analyst'. Run it with `dyui run <file>`."""
    from . import docs

    found = docs.read_example(name)
    if found is None:
        return f"Error: no example {name!r}. Examples: {', '.join(docs.examples()) or 'none bundled'}."
    key, source = found
    path = docs.examples()[key]
    rel = f"examples/{path.name}" if not key.startswith("docs/") else f"docs/examples/{key[5:]}.py"
    return f"# {rel}\n\n{docs.example_summary(path)}\n\n```python\n{source.rstrip()}\n```\n"


@_safe
def get_template(name: str) -> str:
    """Every file of a `dyui new` template ('basic', 'nvidia', 'openai', 'anthropic', 'langgraph'). {{title}}/{{name}} are filled in by `dyui new`."""
    from . import docs

    files = docs.read_template(name)
    if files is None:
        return f"Error: no template {name!r}. Templates: {', '.join(docs.templates())}."
    out = [f"# Template `{name}` (`dyui new my-bot --template {name}`)", ""]
    for rel, text in files.items():
        lang = {"py": "python", "md": "markdown", "txt": "text"}.get(rel.rsplit(".", 1)[-1], "")
        out += [f"## {rel}", "", f"````{lang}", text.rstrip(), "````", ""]
    return "\n".join(out)


@_safe
def validate_ui(payload: Union[str, dict[str, Any], list[Any]], components: Optional[list[str]] = None) -> str:
    """Run DyUI's real parser and validator on model output: one {"ui": ...} object, a JSON list, JSON lines,
    or a whole reply with ```dyui fences. Reports OK or the failing prop per component. components optionally
    limits the allowed built-ins."""
    from .check import format_validation, validate_ui as run

    if isinstance(payload, (dict, list)):
        result = run(payload, _names(components))
    else:
        result = run(str(payload), _names(components))
    return format_validation(result) + "\n\n" + json.dumps(result, ensure_ascii=False)


@_safe
def check_app(path: str) -> str:
    """Check a DyUI app file: syntax, import errors with traceback (imported in a subprocess, 20 s timeout),
    the App and its handlers, custom components and whether their examples validate, the catalog and its
    token cost, and common mistakes (no components= in dyui.llm.stream, hard-coded API keys, blocking calls in
    async handlers, .dyui/ not in .gitignore). Relative paths resolve against the server's working directory."""
    from .check import check_app as run, format_check

    return format_check(run(Path(path)))


@_safe
def catalog_prompt(path: Optional[str] = None, only: Optional[list[str]] = None) -> str:
    """The exact "UI components" system-prompt section the model gets (like `dyui catalog app.py`). With path:
    that app's catalog (built-ins it enables + its custom components). only limits it to some component names."""
    from .check import catalog_prompt as run

    result = run(path or None, _names(only))
    if not result.get("ok"):
        tb = result.get("traceback", "")
        return f"Error: {result.get('error')}" + (f"\n{tb}" if tb else "")
    return f"{result['prompt']}\n\n-- {len(result['names'])} components, ~{result['tokens']} tokens (fence mode)"


TOOLS: tuple[Callable[..., str], ...] = (
    dyui_overview, list_docs, read_doc, search_docs, list_components, get_component,
    list_examples, get_example, get_template, validate_ui, check_app, catalog_prompt,
)


# ------------------------------------------------------------------ prompts
def _prompt_text(letters: str, task: str) -> str:
    books = _playbooks()
    body = "\n".join(books[c] for c in letters if c in books)
    return (f"You are building with DyUI {__version__} using the `dyui` MCP server. First call `dyui_overview`. "
            "Use `get_component` for every component you use (never guess props), `search_docs`/`read_doc` "
            "for details, and finish by running `check_app` on the app file and `validate_ui` on any component "
            "JSON you wrote by hand. Report what changed, how to run it and what you could not verify.\n\n"
            f"Task: {task}\n\nFollow this playbook:\n\n{body}")


def build_app(description: str = "") -> str:
    """Playbook A: build a new DyUI chat app or agent from scratch."""
    return _prompt_text("A", description.strip() or "Build a new DyUI chat app in this project. Ask what it is for if it is unclear.")


def convert_project(path: str = ".") -> str:
    """Playbooks B and C: turn an existing script, agent, API or web service into a DyUI app."""
    return _prompt_text("BC", f"Convert the project at {path!r} into a DyUI app, keeping its existing logic and entry points working.")


def design_components(app_path: str = "app.py") -> str:
    """Playbook D: design custom components for an existing DyUI app."""
    return _prompt_text("D", f"Design custom components for {app_path}. Run check_app({app_path!r}) first to see what it has.")


def production_checklist(app_path: str = "app.py") -> str:
    """Playbook E: make a DyUI app production ready."""
    return _prompt_text("E", f"Review {app_path} for production and fix what is missing. Run check_app({app_path!r}) first.")


PROMPTS: tuple[Callable[..., str], ...] = (build_app, convert_project, design_components, production_checklist)


# ------------------------------------------------------------------ the SDK server
def _server_class() -> type:
    try:  # mcp 2.x
        from mcp.server.mcpserver import MCPServer

        return MCPServer
    except ImportError:  # mcp 1.x
        from mcp.server.fastmcp import FastMCP

        return FastMCP


def _read_only() -> Any:
    for mod in ("mcp_types", "mcp.types"):
        try:
            module = __import__(mod, fromlist=["ToolAnnotations"])
            return module.ToolAnnotations(readOnlyHint=True, openWorldHint=False)
        except Exception:  # noqa: BLE001 - optional nicety, older SDKs lack it
            continue
    return None


def _supports(fn: Callable[..., Any], param: str) -> bool:
    try:
        return param in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def _first_line(fn: Callable[..., Any]) -> str:
    return " ".join((inspect.getdoc(fn) or "").split())


def _static(fn: Callable[..., str], *args: Any) -> Callable[[], str]:
    def read() -> str:
        return fn(*args)

    read.__name__ = f"{fn.__name__}_resource"
    return read


def build_server() -> Any:
    """The configured MCP server object (needs the ``mcp`` package)."""
    cls = _server_class()
    kwargs: dict[str, Any] = {"instructions": INSTRUCTIONS}
    if _supports(cls.__init__, "version"):
        kwargs["version"] = __version__
    server = cls(SERVER_NAME, **kwargs)

    tool_kw: dict[str, Any] = {}
    if _supports(server.add_tool, "structured_output"):
        tool_kw["structured_output"] = False  # plain text results; the text is the contract
    ann = _read_only() if _supports(server.add_tool, "annotations") else None
    for fn in TOOLS:
        kw = dict(tool_kw)
        if ann is not None and fn is not check_app:  # check_app runs the user's code
            kw["annotations"] = ann
        server.add_tool(fn, name=fn.__name__, description=_first_line(fn), **kw)

    for fn in PROMPTS:
        server.prompt(name=fn.__name__, description=_first_line(fn))(fn)

    from . import docs
    from .introspect import component_classes, component_markdown

    for pg in docs.pages():
        server.resource(f"dyui://docs/{pg.slug}", name=f"docs/{pg.slug}", description=pg.description or pg.title,
                        mime_type="text/markdown")(_static(read_doc, pg.slug))
    for comp in component_classes():
        name = comp.__dyui__.name
        server.resource(f"dyui://components/{name}", name=f"components/{name}",
                        description=comp.__dyui__.description, mime_type="text/markdown")(_static(component_markdown, comp))
    for ex in docs.examples():
        server.resource(f"dyui://examples/{ex}", name=f"examples/{ex}", description=f"Example app {ex}",
                        mime_type="text/markdown")(_static(get_example, ex))
    return server


def main(argv: Optional[list[str]] = None) -> int:
    """Run the server over stdio. Exit code 2 when the ``mcp`` package is missing."""
    try:
        server = build_server()
    except ImportError as exc:
        print(f"dyui mcp: the MCP server needs the 'mcp' package ({exc.name or exc}). "
              f"Install it with:  {INSTALL_HINT}", file=sys.stderr)
        return 2
    try:
        server.run("stdio")
    except KeyboardInterrupt:  # pragma: no cover - interactive stop
        pass
    return 0
