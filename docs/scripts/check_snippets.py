"""Check every complete example in the built docs, exactly as the copy button copies it.

A Python code block with a file title (``title="app.py"``, ``examples/travel_bot.py``…)
is a complete example: the reader saves it as that file and runs it. For each one in
``docs/dist/**/*.html`` this script takes the copy button's ``data-code`` and checks:

* it compiles (``compile(..., "exec")``: no module-level ``yield``, no glued lines);
* it ends with a newline, so a second paste can't join onto its last line;
* it has no CR characters;
* it creates a ``dyui.App`` (a complete program, not a fragment with a title).

Blocks without a title are fragments and are skipped. It also checks that every internal
link (and its #anchor) points at a page that exists. Run it after ``npm run build``:

    python docs/scripts/check_snippets.py            # checks docs/dist
    python docs/scripts/check_snippets.py path/to/dist
"""
from __future__ import annotations

import os
import sys
from html.parser import HTMLParser
from pathlib import Path

DIST = Path(__file__).resolve().parent.parent / "dist"


class _Blocks(HTMLParser):
    """Collects (title, language, copy text) for every Expressive Code block."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[dict[str, str]] = []
        self._figure_depth = 0
        self._cur: dict[str, str] | None = None
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        classes = a.get("class", "").split()
        if tag == "figure" and "frame" in classes:
            self._cur = {"title": "", "lang": "", "code": None}  # type: ignore[dict-item]
            self._figure_depth = 1
            return
        if self._cur is None:
            return
        if tag == "figure":
            self._figure_depth += 1
        if tag == "span" and "title" in classes:
            self._in_title = True
        if tag == "pre" and "data-language" in a:
            self._cur["lang"] = a["data-language"]
        if tag == "button" and "data-code" in a:
            self._cur["code"] = a["data-code"].replace("\x7f", "\n")

    def handle_endtag(self, tag: str) -> None:
        if self._cur is None:
            return
        if tag == "span" and self._in_title:
            self._in_title = False
        if tag == "figure":
            self._figure_depth -= 1
            if self._figure_depth == 0:
                if self._cur.get("code") is not None:
                    self.blocks.append(self._cur)  # type: ignore[arg-type]
                self._cur = None

    def handle_data(self, data: str) -> None:
        if self._cur is not None and self._in_title:
            self._cur["title"] += data


def check(dist: Path) -> tuple[int, list[str]]:
    problems: list[str] = []
    checked = 0
    for page in sorted(dist.rglob("*.html")):
        parser = _Blocks()
        parser.feed(page.read_text(encoding="utf-8"))
        rel = page.relative_to(dist).as_posix()
        for block in parser.blocks:
            title = block["title"].strip()
            if block["lang"] != "python" or not title.endswith(".py"):
                continue
            checked += 1
            code = block["code"]
            where = f"{rel} [{title}]"
            if "\r" in code:
                problems.append(f"{where}: copy text contains CR characters")
            if not code.endswith("\n"):
                problems.append(f"{where}: copy text does not end with a newline")
            if "dyui.App(" not in code:
                problems.append(f"{where}: titled as a file but creates no dyui.App (title fragments differently)")
            try:
                compile(code, title, "exec")
            except SyntaxError as exc:
                problems.append(f"{where}: SyntaxError line {exc.lineno}: {exc.msg}")
    return checked, problems


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "a" and "href" in a:
            self.hrefs.append(a["href"])


def check_links(dist: Path, base: str = "/dyui/") -> tuple[int, list[str]]:
    """Every internal link in the built site points at a page (and an anchor) that exists."""
    from urllib.parse import unquote, urljoin, urlsplit

    parsed: dict[Path, _Links] = {}

    def links(page: Path) -> _Links:
        if page not in parsed:
            p = _Links()
            p.feed(page.read_text(encoding="utf-8"))
            parsed[page] = p
        return parsed[page]

    def target(path: str) -> Path | None:
        rel = unquote(path[len(base):]) if path.startswith(base) else None
        if rel is None:
            return None
        cand = dist / rel
        if rel == "" or rel.endswith("/") or cand.is_dir():  # hosts serve dir/index.html (redirect pages too)
            cand = cand / "index.html"
        return cand if cand.is_file() else None

    problems: list[str] = []
    count = 0
    for page in sorted(dist.rglob("*.html")):
        rel = page.relative_to(dist).as_posix()
        page_url = base + (rel[: -len("index.html")] if rel.endswith("index.html") else rel)
        for href in links(page).hrefs:
            if href.startswith(("mailto:", "javascript:", "data:")) or not href:
                continue
            full = urljoin("https://docs.invalid" + page_url, href)
            parts = urlsplit(full)
            if parts.netloc != "docs.invalid":
                continue
            count += 1
            if not parts.path.startswith(base):
                problems.append(f"{rel}: link {href!r} leaves the site base {base}")
                continue
            dest = target(parts.path)
            if dest is None:
                problems.append(f"{rel}: broken link {href!r}")
            elif parts.fragment and dest.suffix == ".html" and unquote(parts.fragment) not in links(dest).ids:
                problems.append(f"{rel}: link {href!r} points at a missing anchor")
    return count, problems


def main(argv: list[str]) -> int:
    dist = Path(argv[1]) if len(argv) > 1 else DIST
    if not dist.is_dir():
        print(f"check_snippets: {dist} not found; run `npm run build` in docs/ first", file=sys.stderr)
        return 2
    base = ("/" + os.environ.get("DOCS_BASE", "/dyui").strip("/") + "/").replace("//", "/")
    n_links, link_problems = check_links(dist, base)
    print(f"check_snippets: {n_links} internal links checked, {len(link_problems)} broken")
    checked, problems = check(dist)
    problems = problems + link_problems
    for p in problems:
        print(f"check_snippets: {p}", file=sys.stderr)
    if checked == 0:
        print("check_snippets: found no complete examples; has the HTML structure changed?", file=sys.stderr)
        return 1
    if problems:
        print(f"check_snippets: {len(problems)} problem(s) in {checked} complete examples", file=sys.stderr)
        return 1
    print(f"check_snippets: {checked} complete examples compile and end with a newline; links OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
