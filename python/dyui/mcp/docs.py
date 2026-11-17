"""The DyUI docs and examples, read offline from the installed package.

Where the files come from (first match wins):

1. ``$DYUI_DOCS_ROOT`` — a folder laid out like the repository (tests, custom builds).
2. A source checkout: the repository the package was imported from (``<repo>/python/dyui``),
   so docs edits show up without a rebuild.
3. ``dyui/_docs/`` — the copy the wheel ships (written by ``python/hatch_build.py``), laid out
   like the repository too: ``docs/src/content/docs/**``, ``examples/*.py``,
   ``docs/examples/**/*.py`` and ``CHANGELOG.md``.

MDX contract (shared with the docs site): pages contain inline fenced code, and
``import x from "<rel>/<file>?raw"`` + ``<Code code={x} ... />``. :func:`resolve_mdx` turns the
second form into a fenced block holding the file, inlines ``import { Content as X } from "x.md"``
+ ``<X />``, renders ``<TabItem label="X">`` as a ``**X**`` sub-heading, keeps the inner text of
other components (``<Aside>``, ``<Tabs>``...) and drops the rest of the JSX.

Nothing here needs the ``mcp`` package.
"""
from __future__ import annotations

import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

__all__ = [
    "DocsRoot",
    "Page",
    "root",
    "pages",
    "page",
    "read_doc",
    "resolve_mdx",
    "examples",
    "read_example",
    "templates",
    "read_template",
    "search",
    "split_frontmatter",
]

_PKG = Path(__file__).resolve().parent.parent  # .../dyui
_CONTENT = Path("docs") / "src" / "content" / "docs"
_SKIP_DIRS = ("reference/api",)  # generated at docs build time from docstrings


# ------------------------------------------------------------------ roots
@dataclass(frozen=True)
class DocsRoot:
    path: Path
    kind: str  # "env" | "source" | "bundled" | "missing"

    @property
    def content(self) -> Path:
        return self.path / _CONTENT

    def contains(self, p: Path) -> bool:
        try:
            p.resolve().relative_to(self.path.resolve())
            return True
        except ValueError:
            return False


def _has_content(p: Path) -> bool:
    return (p / _CONTENT).is_dir()


def root() -> DocsRoot:
    """Where the docs are read from (see the module docstring)."""
    env = os.environ.get("DYUI_DOCS_ROOT")
    if env:
        return DocsRoot(Path(env), "env")
    source = _PKG.parent.parent
    if _has_content(source) and (source / "python" / "dyui").is_dir():
        return DocsRoot(source, "source")
    bundled = _PKG / "_docs"
    if _has_content(bundled) or (bundled / "examples").is_dir():
        return DocsRoot(bundled, "bundled")
    return DocsRoot(bundled, "missing")


# ------------------------------------------------------------------ frontmatter
def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """``(meta, body)`` for a page with a ``---`` YAML header (flat keys + ``sidebar.order``)."""
    text = text.lstrip("﻿").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    head, body = text[4:end], text[end + 4:]
    body = body[1:] if body.startswith("\n") else body
    meta: dict[str, Any] = {}
    parent: Optional[str] = None
    for line in head.split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^(\s*)([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not m:
            continue
        indent, key, value = m.groups()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if indent and parent:
            meta[f"{parent}.{key}"] = value
        else:
            parent = key if not value else None
            if value:
                meta[key] = value
    return meta, body


# ------------------------------------------------------------------ MDX
_FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})")
_IMPORT = re.compile(r"""^import\s+(.+?)\s+from\s+["']([^"']+)["'];?\s*$""")
_DEFAULT_NAME = re.compile(r"^([A-Za-z_$][\w$]*)$")
_CONTENT_NAME = re.compile(r"^\{\s*Content\s+as\s+([A-Za-z_$][\w$]*)\s*\}$")
_CODE_TAG = re.compile(r"<Code\b((?:[^>{}]|\{[^}]*\})*?)/>", re.S)
_ATTR = re.compile(r"""([A-Za-z_][\w-]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|\{([^}]*)\})""")
_TABITEM = re.compile(r"<TabItem\b((?:[^>{}]|\{[^}]*\})*)>", re.S)
_SELF_CLOSING = re.compile(r"<([A-Z][\w.]*)\b(?:[^>{}]|\{[^}]*\})*/>", re.S)
_OPEN_TAG = re.compile(r"<([A-Z][\w.]*)\b((?:[^>{}]|\{[^}]*\})*)>", re.S)
_CLOSE_TAG = re.compile(r"</([A-Z][\w.]*)\s*>")


def _attrs(text: str) -> dict[str, str]:
    out = {}
    for m in _ATTR.finditer(text):
        out[m.group(1)] = next(g for g in m.groups()[1:] if g is not None).strip()
    return out


def _segments(text: str) -> list[tuple[bool, str]]:
    """Split Markdown into ``(is_code, text)`` runs so JSX handling never touches code blocks."""
    out: list[tuple[bool, str]] = []
    buf: list[str] = []
    fence: Optional[str] = None
    for line in text.splitlines(keepends=True):
        m = _FENCE.match(line)
        if fence is None and m:
            if buf:
                out.append((False, "".join(buf)))
            buf, fence = [line], m.group(2)
        elif fence is not None:
            buf.append(line)
            if m and m.group(2)[0] == fence[0] and len(m.group(2)) >= len(fence) and not line.strip()[len(m.group(2)):].strip():
                out.append((True, "".join(buf)))
                buf, fence = [], None
        else:
            buf.append(line)
    if buf:
        out.append((fence is not None, "".join(buf)))
    return out


def _fenced(code: str, lang: str = "", title: str = "") -> str:
    ticks = "```"
    while ticks in code:
        ticks += "`"
    info = lang + (f' title="{title}"' if title else "")
    return f"{ticks}{info}\n{code if code.endswith(chr(10)) else code + chr(10)}{ticks}\n"


def resolve_mdx(text: str, base: Optional[Path] = None, docs_root: Optional[DocsRoot] = None) -> str:
    """Turn an MDX page body into plain Markdown (see the module docstring).

    ``base`` is the directory the page lives in (``import`` paths resolve against it); files
    outside ``docs_root`` are never read.
    """
    docs_root = docs_root or root()
    raw: dict[str, str] = {}
    content: dict[str, str] = {}
    kept: list[str] = []
    for is_code, seg in _segments(text):
        if is_code:
            kept.append(seg)
            continue
        lines = []
        for line in seg.splitlines(keepends=True):
            m = _IMPORT.match(line.strip())
            if not m:
                lines.append(line)
                continue
            what, src = m.groups()
            if base is None or not src.startswith("."):
                continue  # package import (components, Starlight helpers): drop
            path = (base / src.split("?", 1)[0]).resolve()
            if not docs_root.contains(path) or not path.is_file():
                continue
            try:
                body = path.read_text(encoding="utf-8").replace("\r\n", "\n")
            except (OSError, UnicodeDecodeError):
                continue
            dm, cm = _DEFAULT_NAME.match(what), _CONTENT_NAME.match(what)
            if dm and src.endswith("?raw"):
                raw[dm.group(1)] = body
            elif cm and path.suffix in (".md", ".mdx"):
                content[cm.group(1)] = resolve_mdx(split_frontmatter(body)[1], path.parent, docs_root)
        kept.append("".join(lines))
    text = "".join(kept)

    # Inserted blocks (example files, inlined pages) go in as placeholders so the blank-line
    # cleanup below only ever touches prose, never code.
    blocks: list[str] = []

    def hold(text: str) -> str:
        blocks.append(text)
        return f"\x00{len(blocks) - 1}\x00"

    def code_tag(m: re.Match) -> str:
        a = _attrs(m.group(1))
        name = a.get("code", "")
        if name in raw:
            return hold(_fenced(raw[name], a.get("lang", ""), a.get("title", "")))
        if name.startswith(("`", '"', "'")):  # code={`literal`}
            return hold(_fenced(name.strip("`\"'"), a.get("lang", ""), a.get("title", "")))
        return ""

    def open_tag(m: re.Match) -> str:
        title = _attrs(m.group(2)).get("title")
        return f"**{title}**\n" if m.group(1) == "Aside" and title else ""

    out = []
    for is_code, seg in _segments(text.replace("\x00", "")):
        if is_code:
            out.append(hold(seg))
            continue
        seg = _CODE_TAG.sub(code_tag, seg)
        seg = _TABITEM.sub(lambda m: f"**{_attrs(m.group(1)).get('label', '')}**\n", seg)
        seg = _SELF_CLOSING.sub(lambda m: hold(content[m.group(1)]) if m.group(1) in content else "", seg)
        seg = _OPEN_TAG.sub(open_tag, seg)
        seg = _CLOSE_TAG.sub("", seg)
        out.append(re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", seg))
    result = re.sub(r"\x00(\d+)\x00", lambda m: blocks[int(m.group(1))], "".join(out))
    return result.strip() + "\n"


# ------------------------------------------------------------------ pages
@dataclass
class Page:
    slug: str
    title: str
    description: str
    section: str
    path: Path
    order: float = 1000.0
    meta: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, str]:
        return {"slug": self.slug, "title": self.title, "description": self.description, "section": self.section}


def _slug(rel: Path) -> str:
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "index" and len(parts) > 1:
        parts.pop()
    return "/".join(parts)


@lru_cache(maxsize=8)
def _pages(path: str) -> tuple[Page, ...]:
    docs_root = DocsRoot(Path(path), "")
    content = docs_root.content
    if not content.is_dir():
        return ()
    found = []
    for p in sorted(content.rglob("*")):
        if p.suffix not in (".md", ".mdx") or not p.is_file():
            continue
        rel = p.relative_to(content)
        if any(rel.as_posix().startswith(d + "/") for d in _SKIP_DIRS):
            continue
        try:
            meta, _ = split_frontmatter(p.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        if meta.get("template") == "splash":
            continue  # the landing page is an interactive component, not prose
        try:
            order = float(meta.get("sidebar.order", 1000))
        except ValueError:
            order = 1000.0
        slug = _slug(rel)
        found.append(Page(slug=slug, title=meta.get("title", slug), description=meta.get("description", ""),
                          section=rel.parts[0] if len(rel.parts) > 1 else "", path=p, order=order, meta=meta))
    found.sort(key=lambda pg: (pg.section, pg.order, pg.slug))
    return tuple(found)


def pages() -> list[Page]:
    """Every docs page (generated API reference and the landing page excluded)."""
    return list(_pages(str(root().path)))


def _norm_slug(slug: str) -> str:
    s = slug.strip().replace("\\", "/")
    s = re.sub(r"^(?:https?://[^/]+)?/?(?:dyui/)?", "", s)
    s = s.removeprefix("dyui://docs/").strip("/")
    for ext in (".mdx", ".md"):
        s = s.removesuffix(ext)
    return s.lower()


def page(slug: str) -> Optional[Page]:
    """A page by slug (``concepts/actions``); URLs and ``.md`` suffixes are tolerated."""
    want = _norm_slug(slug)
    every = pages()
    for pg in every:
        if pg.slug.lower() == want:
            return pg
    tails = [pg for pg in every if pg.slug.lower().rsplit("/", 1)[-1] == want.rsplit("/", 1)[-1]]
    return tails[0] if len(tails) == 1 else None


@lru_cache(maxsize=256)
def _read_resolved(path: str, mtime: float, docs_root: str) -> str:
    p = Path(path)
    _meta, body = split_frontmatter(p.read_text(encoding="utf-8"))
    if p.suffix == ".mdx":
        return resolve_mdx(body, p.parent, DocsRoot(Path(docs_root), ""))
    return body.strip() + "\n"


def page_body(pg: Page) -> str:
    return _read_resolved(str(pg.path), pg.path.stat().st_mtime, str(root().path))


def read_doc(slug: str) -> Optional[str]:
    """One page as Markdown with a title header, or ``None`` if there is no such page."""
    pg = page(slug)
    if pg is None:
        return None
    head = f"# {pg.title}\n\n"
    if pg.description:
        head += f"> {pg.description}\n\n"
    return head + page_body(pg)


# ------------------------------------------------------------------ examples & templates
def examples() -> dict[str, Path]:
    """Runnable example apps: ``examples/<name>.py`` and ``docs/examples/<section>/<page>.py``."""
    r = root().path
    out: dict[str, Path] = {}
    ex = r / "examples"
    if ex.is_dir():
        for p in sorted(ex.glob("*.py")):
            out[p.stem] = p
    dex = r / "docs" / "examples"
    if dex.is_dir():
        for p in sorted(dex.rglob("*.py")):
            if "__pycache__" not in p.parts:
                out["docs/" + p.relative_to(dex).with_suffix("").as_posix()] = p
    return out


def example_summary(path: Path) -> str:
    """First docstring line of an example file."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    m = re.match(r'\s*(?:#[^\n]*\n\s*)*[rRuU]?("""|\'\'\')(.*?)(\1|$)', text, re.S)
    return " ".join(m.group(2).strip().split("\n\n")[0].split()) if m else ""


def read_example(name: str) -> Optional[tuple[str, str]]:
    """``(name, source)`` for an example (``data_analyst``, ``data-analyst`` or ``data_analyst.py``)."""
    every = examples()
    key = name.strip().replace("\\", "/").removesuffix(".py").removeprefix("examples/")
    for cand in (key, key.replace("-", "_")):
        if cand in every:
            return cand, every[cand].read_text(encoding="utf-8").replace("\r\n", "\n")
    return None


def templates() -> dict[str, Path]:
    """The ``dyui new`` templates shipped in the package."""
    base = _PKG / "templates"
    return {p.name: p for p in sorted(base.iterdir()) if p.is_dir() and not p.name.startswith(("_", "."))}


def read_template(name: str) -> Optional[dict[str, str]]:
    """``{relative path: text}`` for every file of a template, or ``None``."""
    t = templates().get(name.strip().lower())
    if t is None:
        return None
    out = {}
    for p in sorted(t.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            try:
                out[p.relative_to(t).as_posix()] = p.read_text(encoding="utf-8").replace("\r\n", "\n")
            except UnicodeDecodeError:
                continue
    return out


# ------------------------------------------------------------------ search
_WORD = re.compile(r"[a-z0-9_]+")
_STOP = frozenset("a an and are as at be by can do for from how i in is it of on or the to this that with you your".split())


def _tokens(text: str) -> list[str]:
    out = []
    for w in _WORD.findall(text.lower()):
        if w in _STOP or len(w) < 2:
            continue
        out.append(w)
        if "_" in w:  # on_action → on, action as well
            out.extend(p for p in w.split("_") if len(p) > 1 and p not in _STOP)
    return out


@dataclass
class _Chunk:
    kind: str  # "doc" | "example" | "component"
    ref: str   # slug / example name / component name
    title: str
    heading: str
    text: str
    tf: Counter = field(default_factory=Counter)
    head_tokens: frozenset = frozenset()
    length: int = 0


def _doc_chunks(pg: Page) -> list[_Chunk]:
    body = page_body(pg)
    out = []
    heading, buf = "", []
    in_code = False
    for line in body.split("\n"):
        if _FENCE.match(line):
            in_code = not in_code
        m = None if in_code else re.match(r"^(#{2,3})\s+(.*)$", line)
        if m:
            if "".join(buf).strip():
                out.append((heading, "\n".join(buf)))
            heading, buf = m.group(2).strip(), []
        else:
            buf.append(line)
    if "".join(buf).strip():
        out.append((heading, "\n".join(buf)))
    return [_Chunk("doc", pg.slug, pg.title, h, t) for h, t in out]


@lru_cache(maxsize=4)
def _index(path: str) -> tuple[list[_Chunk], dict[str, int], float]:
    chunks: list[_Chunk] = []
    for pg in pages():
        try:
            chunks.extend(_doc_chunks(pg))
        except (OSError, UnicodeDecodeError):
            continue
    for name, p in examples().items():
        try:
            chunks.append(_Chunk("example", name, f"Example: {name}", example_summary(p), p.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
    try:
        from .introspect import component_classes, details, md

        for cls in component_classes():
            info = cls.__dyui__
            chunks.append(_Chunk("component", info.name, f"Component: {info.name}", f"ui.{cls.__name__}",
                                 f"{info.name} {cls.__name__} {md(info.description)} {details(cls)} {cls.signature()}"))
    except Exception:  # pragma: no cover - search still works on docs alone
        pass
    df: Counter = Counter()
    total = 0
    for c in chunks:
        toks = _tokens(c.text)
        c.tf = Counter(toks)
        c.length = len(toks) or 1
        c.head_tokens = frozenset(_tokens(f"{c.title} {c.heading} {c.ref}"))
        total += c.length
        df.update(set(toks) | set(c.head_tokens))
    avg = total / len(chunks) if chunks else 1.0
    return chunks, dict(df), avg


def _snippet(text: str, terms: list[str], width: int = 280) -> str:
    flat = " ".join(text.split())
    low = flat.lower()
    pos = min((i for i in (low.find(t) for t in terms) if i >= 0), default=0)
    start = max(0, pos - width // 3)
    snip = flat[start:start + width]
    return ("…" if start else "") + snip + ("…" if start + width < len(flat) else "")


def search(query: str, limit: int = 8) -> list[dict[str, Any]]:
    """BM25 keyword search over docs sections, example files and component descriptions."""
    terms = list(dict.fromkeys(_tokens(query)))
    if not terms:
        return []
    chunks, df, avg = _index(str(root().path))
    n = len(chunks)
    k1, b = 1.4, 0.75
    phrase = " ".join(query.lower().split())
    scored = []
    for c in chunks:
        score = 0.0
        for t in terms:
            f = c.tf.get(t, 0)
            in_head = t in c.head_tokens
            if not f and not in_head:
                continue
            idf = math.log(1 + (n - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5))
            score += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * c.length / avg)) if f else 0.0
            if in_head:
                score += idf * 1.2
        if score and len(phrase) > 3 and phrase in " ".join(c.text.lower().split()):
            score *= 1.5
        if score:
            scored.append((score, c))
    scored.sort(key=lambda sc: -sc[0])
    out = []
    for score, c in scored[: max(1, min(int(limit), 50))]:
        out.append({
            "kind": c.kind,
            "ref": c.ref,
            "title": c.title,
            "heading": c.heading,
            "snippet": _snippet(c.text, terms),
            "score": round(score, 2),
        })
    return out
