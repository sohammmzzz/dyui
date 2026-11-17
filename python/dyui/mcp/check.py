"""Checks a coding agent runs on its own work: ``validate_ui``, ``check_app``, ``catalog_prompt``.

- :func:`validate_ui` runs the real streaming parser and validator on model-style output.
- :func:`check_app` statically scans an app file for common mistakes, then imports it in a
  **subprocess** (so a broken or slow app can never take the MCP server down) and reports its
  handlers, components and catalog.
- :func:`catalog_prompt` returns the exact system-prompt section the model gets.

Secrets never leave this module: anything that looks like an API key is masked in every
report, tracebacks included. Nothing here needs the ``mcp`` package.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence, Union

__all__ = ["validate_ui", "check_app", "catalog_prompt", "mask_secrets", "scan_source", "probe_app"]

CHECK_TIMEOUT = 20.0
_MARK = "@@DYUI_MCP_PROBE@@"

# Provider key shapes. Only used to *mask* and to flag hard-coded keys; never printed in full.
_SECRET = re.compile(
    r"\b(?:sk-ant-[A-Za-z0-9_\-]{8,}|sk-(?:proj-|or-v1-)?[A-Za-z0-9_\-]{16,}|nvapi-[A-Za-z0-9_\-]{16,}"
    r"|gsk_[A-Za-z0-9]{16,}|xai-[A-Za-z0-9]{16,}|AIza[0-9A-Za-z_\-]{30,}|hf_[A-Za-z0-9]{20,}"
    r"|ghp_[A-Za-z0-9]{20,}|r8_[A-Za-z0-9]{20,})"
)


def mask_secrets(text: str) -> str:
    """Replace anything shaped like an API key with ``<prefix>…(masked)``."""
    def mask(m: re.Match) -> str:
        s = m.group(0)
        cut = s.find("-") + 1 if "-" in s[:8] else (s.find("_") + 1 if "_" in s[:5] else 4)
        return s[:cut] + "…(masked)"

    return _SECRET.sub(mask, text)


# ------------------------------------------------------------------ validate_ui
def _catalog(components: Optional[Sequence[str]] = None) -> Any:
    from ..genui import catalog

    cat = catalog()
    if components:
        cat = cat.only(*components)
    return cat


def _objects(payload: str) -> Optional[list[Any]]:
    """The component objects if ``payload`` is JSON / JSON lines; ``None`` if it is a reply text."""
    s = payload.strip()
    if not s or s[0] not in "{[":
        return None
    try:
        value = json.loads(s)
        return value if isinstance(value, list) else [value]
    except ValueError:
        pass
    out = []
    for line in s.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except ValueError:
            return None
        out.extend(value if isinstance(value, list) else [value])
    return out


def validate_ui(payload: Union[str, dict, list], components: Optional[Sequence[str]] = None) -> dict[str, Any]:
    """Validate model output with DyUI's own parser and validator.

    ``payload`` may be one ``{"ui": ...}`` object (or a list of them), JSON lines, or a whole
    model reply containing ```` ```dyui ```` fences. ``components`` restricts the allowed
    built-ins (default: every built-in the model may use).

    Returns ``{"ok", "components": [{"index", "ui", "ok", "error"?, "path"?}], "prose_chars",
    "warnings"}``.
    """
    from ..genui import ComponentEnd, ComponentError, TextDelta, parse_text
    from ..genui.validate import ValidationFailure, render_instance, validate_instance

    cat = _catalog(components)
    results: list[dict[str, Any]] = []
    warnings: list[str] = []
    prose = 0
    objs = payload if isinstance(payload, list) else [payload] if isinstance(payload, dict) else _objects(str(payload))
    mode = "objects" if objs is not None else "reply"
    if objs is not None:
        for i, obj in enumerate(objs, 1):
            name = obj.get("ui") if isinstance(obj, dict) else None
            try:
                render_instance(validate_instance(obj, cat), f"c_check{i}", obj)
                results.append({"index": i, "ui": name, "ok": True})
            except ValidationFailure as f:
                results.append({"index": i, "ui": f.component or name, "ok": False, "error": f.message, "path": f.path})
    else:
        text = str(payload)
        i = 0
        for ev in parse_text(text, cat):
            if isinstance(ev, TextDelta):
                prose += len(ev.text.strip())
            elif isinstance(ev, ComponentEnd):
                i += 1
                results.append({"index": i, "ui": ev.node.get("props", {}).get("__component__") or ev.node.get("ui"), "ok": True})
            elif isinstance(ev, ComponentError):
                i += 1
                results.append({"index": i, "ui": ev.component, "ok": False, "error": ev.error, "path": ev.path})
        opens = len(re.findall(r"(?m)^\s*(?:`{3,}|~{3,})\s*dyui\s*$", text))
        fences = len(re.findall(r"(?m)^\s*(?:`{3,}|~{3,})", text))
        if opens and fences % 2:
            warnings.append("A ```dyui fence is not closed; close every block with ``` on its own line.")
        if not results:
            warnings.append("No components found. Components go in a ```dyui fenced block, one JSON object per line.")
        elif prose == 0:
            warnings.append("The reply has components but no prose. DyUI's prompt asks the model to explain in words too.")
    for r in results:
        if not r["ok"] and str(r.get("error", "")).startswith("unknown component"):
            r["hint"] = ("Not a built-in. For an app's custom components run check_app(path) "
                         "or catalog_prompt(path) to see its catalog.")
    return {"ok": bool(results) and all(r["ok"] for r in results),
            "mode": mode, "components": results, "prose_chars": prose, "warnings": warnings}


def format_validation(result: dict[str, Any]) -> str:
    lines = [("OK" if result["ok"] else "PROBLEMS FOUND") + f" ({len(result['components'])} component(s))"]
    for r in result["components"]:
        if r["ok"]:
            lines.append(f"  {r['index']}. OK     {r['ui']}")
        else:
            where = f" at `{r['path']}`" if r.get("path") else ""
            lines.append(f"  {r['index']}. ERROR  {r['ui'] or '?'}{where}: {r['error']}")
            if r.get("hint"):
                lines.append(f"            {r['hint']}")
    for w in result["warnings"]:
        lines.append(f"  warning: {w}")
    return "\n".join(lines)


# ------------------------------------------------------------------ static scan
_BLOCKING = {("time", "sleep"), ("requests", "get"), ("requests", "post"), ("requests", "put"),
             ("requests", "delete"), ("requests", "patch"), ("requests", "request"), ("requests", "head"),
             ("urllib.request", "urlopen"), ("subprocess", "run"), ("subprocess", "call"), ("subprocess", "check_output")}


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        head = _dotted(node.value)
        return f"{head}.{node.attr}" if head else node.attr
    return ""


def _is_llm_stream(call: ast.Call, stream_names: set[str]) -> Optional[str]:
    name = _dotted(call.func)
    if name in ("dyui.llm.stream", "llm.stream", "dyui.llm.complete", "llm.complete") or name in stream_names:
        return name
    return None


def scan_source(source: str, filename: str = "app.py") -> dict[str, list[dict[str, Any]]]:
    """Static checks that need no import. Returns ``{"errors": [...], "warnings": [...]}``."""
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        line = (exc.text or "").rstrip("\n")
        errors.append({"kind": "syntax_error", "line": exc.lineno, "column": exc.offset,
                       "message": f"{exc.msg}", "source": mask_secrets(line)})
        tree = None
    if tree is not None:
        try:
            compile(source, filename, "exec")  # errors ast.parse lets through ('return' in async generator...)
        except SyntaxError as exc:
            errors.append({"kind": "syntax_error", "line": exc.lineno, "column": exc.offset,
                           "message": f"{exc.msg}", "source": mask_secrets((exc.text or "").rstrip())})
        except (ValueError, RecursionError) as exc:  # pragma: no cover - null bytes, absurd nesting
            errors.append({"kind": "syntax_error", "line": None, "message": str(exc)})
    for lineno, text in enumerate(source.splitlines(), 1):
        if _SECRET.search(text) and not text.lstrip().startswith("#"):
            warnings.append({"kind": "hardcoded_key", "line": lineno,
                             "message": "Looks like a hard-coded API key: " + mask_secrets(text.strip())[:120]
                                        + ". Read it from an environment variable (os.environ / .env) instead."})
    if tree is None:
        return {"errors": errors, "warnings": warnings}

    stream_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in ("dyui.llm", "dyui"):
            for a in node.names:
                if a.name in ("stream", "complete"):
                    stream_names.add(a.asname or a.name)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_llm_stream(node, stream_names):
            kws = {k.arg for k in node.keywords}
            if "components" not in kws and None not in kws:
                warnings.append({"kind": "no_components", "line": node.lineno,
                                 "message": f"`{_dotted(node.func)}(...)` has no `components=`: the model is never "
                                            "told about UI components. Pass `components=app.catalog`."})
        if isinstance(node, ast.AsyncFunctionDef):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    name = _dotted(sub.func)
                    mod, _, attr = name.rpartition(".")
                    if (mod, attr) in _BLOCKING:
                        warnings.append({"kind": "blocking_call", "line": sub.lineno,
                                         "message": f"`{name}()` blocks the event loop inside `async def {node.name}`. "
                                                    "Use an async client / `await asyncio.sleep`, or make the handler a "
                                                    "plain (sync) generator, which runs in a worker thread."})
    return {"errors": errors, "warnings": warnings}


def _gitignore_warning(app: Path) -> Optional[dict[str, Any]]:
    """Warn when no .gitignore between the app and the repo root ignores ``.dyui/``."""
    d = app.parent.resolve()
    found_any = False
    for cur in [d, *d.parents]:
        gi = cur / ".gitignore"
        if gi.is_file():
            found_any = True
            try:
                lines = [ln.strip() for ln in gi.read_text(encoding="utf-8", errors="replace").splitlines()]
            except OSError:
                lines = []
            if any(ln.rstrip("/").lstrip("/") in (".dyui", ".dyui/*", "**/.dyui") for ln in lines):
                return None
        if (cur / ".git").exists():
            break
    where = "the project's .gitignore" if found_any else "a .gitignore next to the app"
    return {"kind": "gitignore", "line": None,
            "message": f"`.dyui/` (the chat database and uploads) is not ignored. Add `.dyui/` to {where}."}


# ------------------------------------------------------------------ the import probe
_PROBE = r'''
import importlib.util, json, os, sys, traceback
from pathlib import Path

MARK = sys.argv[1]
path = Path(sys.argv[2]).resolve()
mode = sys.argv[3]
only = [n for n in sys.argv[4].split(",") if n] if len(sys.argv) > 4 else []
out = {"ok": False}
real_stdout = sys.stdout
sys.stdout = sys.stderr  # whatever the app prints must not corrupt the report
try:
    import dyui
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    apps = [(k, v) for k, v in vars(module).items() if isinstance(v, dyui.App)]
    out["ok"] = True
    out["apps"] = [k for k, _ in apps]
    if apps:
        pick = next((p for p in apps if p[0] == "app"), apps[0])
        name, app = pick
        cat = app.catalog
        if only:
            cat = cat.only(*only)
        out["app_var"] = name
        out["title"] = app.title
        def fname(f):
            return getattr(f, "__name__", repr(f)) if f is not None else None
        out["handlers"] = {
            "on_message": fname(app._on_message),
            "on_chat_start": fname(app._on_chat_start),
            "on_feedback": fname(app._on_feedback),
            "on_action": {k: fname(v) for k, v in app._actions.items()},
        }
        customs = []
        for cls in app._custom:
            info = cls.__dyui__
            ex = []
            for e in info.examples:
                node = cat.validate({"ui": info.name, **dict(e)}, id="c_probe")
                ex.append({"ok": node.get("status") != "error",
                           "error": (node.get("props") or {}).get("error") if node.get("status") == "error" else None})
            customs.append({"name": info.name, "class": cls.__name__, "description": info.description,
                            "llm": info.llm, "examples": len(info.examples), "example_results": ex,
                            "prompt_line": cls.signature()})
        out["custom_components"] = customs
        out["catalog"] = cat.names
        out["tokens_fence"] = cat.token_estimate(mode="fence")
        if mode == "prompt":
            out["prompt"] = cat.prompt(mode="fence")
except SystemExit as exc:
    out["error"] = f"SystemExit({exc.code!r}) during import"
except BaseException as exc:
    out["error"] = f"{type(exc).__name__}: {exc}"
    out["traceback"] = traceback.format_exc(limit=12)
real_stdout.write(MARK + json.dumps(out, default=str) + "\n")
real_stdout.flush()
'''


def probe_app(path: Union[str, Path], *, mode: str = "check", only: Iterable[str] = (),
              timeout: float = CHECK_TIMEOUT, python: Optional[str] = None) -> dict[str, Any]:
    """Import ``path`` in a fresh interpreter (cwd = its folder) and describe its ``dyui.App``."""
    p = Path(path).resolve()
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("DYUI_NO_LAUNCH", "1")
    # Make the probe import *this* dyui when it is not installed in site-packages (a source
    # checkout run via PYTHONPATH, tests). Never put site-packages itself ahead of the stdlib.
    pkg_parent = Path(__file__).resolve().parent.parent.parent
    if pkg_parent.name not in ("site-packages", "dist-packages"):
        env["PYTHONPATH"] = str(pkg_parent) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    try:
        proc = subprocess.run(
            [python or sys.executable, "-c", _PROBE, _MARK, str(p), mode, ",".join(only)],
            cwd=str(p.parent), env=env, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as exc:
        tail = (exc.stderr or "") if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", "replace")
        return {"ok": False, "error": f"importing the app took longer than {timeout:.0f}s (does it do work or "
                                      "network calls at import time? move them into a handler)",
                "stderr": mask_secrets(tail[-2000:])}
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith(_MARK):
            try:
                out = json.loads(line[len(_MARK):])
            except ValueError:
                break
            out["stderr"] = mask_secrets(proc.stderr[-2000:])
            if "traceback" in out:
                out["traceback"] = mask_secrets(out["traceback"])
            if "error" in out:
                out["error"] = mask_secrets(out["error"])
            return out
    return {"ok": False, "error": f"the import probe exited with code {proc.returncode} without a report",
            "stderr": mask_secrets(proc.stderr[-2000:])}


# ------------------------------------------------------------------ check_app
def check_app(path: Union[str, Path], *, timeout: float = CHECK_TIMEOUT) -> dict[str, Any]:
    """Statically scan and import-check a DyUI app file. See the module docstring."""
    p = Path(path).expanduser()
    if not p.is_file():
        return {"ok": False, "path": str(p), "errors": [{"kind": "not_found", "message": f"{p} is not a file"}],
                "warnings": []}
    try:
        source = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {"ok": False, "path": str(p), "errors": [{"kind": "unreadable", "message": str(exc)}], "warnings": []}
    report: dict[str, Any] = {"path": str(p.resolve())}
    scan = scan_source(source, p.name)
    errors, warnings = list(scan["errors"]), list(scan["warnings"])
    gi = _gitignore_warning(p)
    if gi:
        warnings.append(gi)
    if not errors:
        probe = probe_app(p, timeout=timeout)
        if not probe.get("ok"):
            errors.append({"kind": "import_error", "message": probe.get("error", "import failed"),
                           "traceback": probe.get("traceback", ""), "stderr": probe.get("stderr", "")})
        elif not probe.get("apps"):
            errors.append({"kind": "no_app", "message": "Imported, but no `dyui.App` found at module level. "
                                                        "Create one with `app = dyui.App(...)`."})
        else:
            for k in ("app_var", "title", "handlers", "custom_components", "catalog", "tokens_fence"):
                report[k] = probe.get(k)
            if not probe["handlers"]["on_message"]:
                errors.append({"kind": "no_on_message", "message": "No `@app.on_message` handler: the app cannot reply."})
            for c in probe.get("custom_components", []):
                for i, r in enumerate(c["example_results"], 1):
                    if not r["ok"]:
                        errors.append({"kind": "bad_example", "message":
                                       f"custom component `{c['name']}` example {i} does not validate: {r['error']}"})
                if c["llm"] and not c["examples"]:
                    warnings.append({"kind": "no_examples", "message": f"custom component `{c['name']}` has no "
                                     "`examples = [...]`; one example helps the model use it correctly."})
            from ..genui import TOKEN_WARN_LIMIT

            if (probe.get("tokens_fence") or 0) > TOKEN_WARN_LIMIT:
                warnings.append({"kind": "big_prompt", "message": f"The catalog prompt is ~{probe['tokens_fence']} "
                                 "tokens. Trim it with `app.catalog.only(...)` on small token budgets."})
    report["errors"], report["warnings"] = errors, warnings
    report["ok"] = not errors
    return report


def format_check(report: dict[str, Any]) -> str:
    out = [f"{'OK' if report['ok'] else 'FAILED'}: {report['path']}"]
    if report.get("app_var"):
        h = report["handlers"]
        out.append(f"App: `{report['app_var']}` (title {report['title']!r})")
        out.append(f"Handlers: on_message={h['on_message']}, on_chat_start={h['on_chat_start']}, "
                   f"on_action={json.dumps(h['on_action']) if h['on_action'] else '{}'}")
        customs = report.get("custom_components") or []
        if customs:
            out.append("Custom components:")
            for c in customs:
                ok = sum(1 for r in c["example_results"] if r["ok"])
                out.append(f"  - {c['name']} ({c['class']}): {ok}/{c['examples']} examples valid"
                           + ("" if c["llm"] else ", hidden from the model"))
        out.append(f"Catalog ({len(report['catalog'])}): {', '.join(report['catalog'])}")
        out.append(f"Catalog prompt: ~{report['tokens_fence']} tokens (fence mode)")
    for e in report["errors"]:
        where = f" (line {e['line']})" if e.get("line") else ""
        out.append(f"ERROR [{e['kind']}]{where}: {e['message']}")
        if e.get("source"):
            out.append(f"    {e['source']}")
        if e.get("traceback"):
            out.append("    " + e["traceback"].strip().replace("\n", "\n    "))
        elif e.get("stderr"):
            out.append("    " + e["stderr"].strip()[-1200:].replace("\n", "\n    "))
    for w in report["warnings"]:
        where = f" (line {w['line']})" if w.get("line") else ""
        out.append(f"warning [{w['kind']}]{where}: {w['message']}")
    return "\n".join(out)


# ------------------------------------------------------------------ catalog_prompt
def catalog_prompt(path: Optional[Union[str, Path]] = None, only: Optional[Sequence[str]] = None) -> dict[str, Any]:
    """The "UI components" system-prompt section: for an app file (its catalog) or the built-ins."""
    names = [n.strip() for n in (only or []) if n and n.strip()]
    if path:
        p = Path(path).expanduser()
        if not p.is_file():
            return {"ok": False, "error": f"{p} is not a file"}
        probe = probe_app(p, mode="prompt", only=names)
        if not probe.get("ok") or not probe.get("apps"):
            return {"ok": False, "error": probe.get("error") or "no `dyui.App` found in the file",
                    "traceback": probe.get("traceback", "")}
        return {"ok": True, "prompt": probe["prompt"], "names": probe["catalog"], "tokens": probe["tokens_fence"]}
    try:
        cat = _catalog(names)
    except (KeyError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "prompt": cat.prompt(), "names": cat.names, "tokens": cat.token_estimate()}
