"""Generate python/README.md (the PyPI project page) from the root README.md.

PyPI renders the package README out of context, so relative links and images are
rewritten to absolute GitHub URLs. Run from anywhere: ``python scripts/sync_pypi_readme.py``.
The release workflow runs it before building, so the published page is always current.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "https://github.com/sohammmzzz/dyui"
RAW = "https://raw.githubusercontent.com/sohammmzzz/dyui/main/"
BLOB = REPO + "/blob/main/"
TREE = REPO + "/tree/main/"
ASSET = re.compile(r"\.(svg|png|jpe?g|gif|webp)$", re.I)


def _absolute(path: str) -> str:
    path = path.removeprefix("./")
    if ASSET.search(path):
        return RAW + path
    if (ROOT / path.split("#")[0]).is_dir():
        return TREE + path.rstrip("/")
    return BLOB + path


def convert(text: str) -> str:
    rel = r"(?!https?:|mailto:|#|/)([^)\s\"]+)"
    text = re.sub(r"\]\(" + rel + r"\)", lambda m: f"]({_absolute(m.group(1))})", text)
    text = re.sub(r'\b(src|srcset|href)="' + rel + '"', lambda m: f'{m.group(1)}="{_absolute(m.group(2))}"', text)
    # in-page anchors don't resolve on PyPI the same way; point them at GitHub
    text = re.sub(r"\]\((#[^)]+)\)", lambda m: f"]({REPO}{m.group(1)})", text)
    return text


def main() -> None:
    src = (ROOT / "README.md").read_text(encoding="utf-8")
    header = "<!-- Generated from ../README.md by scripts/sync_pypi_readme.py — edit the root README instead. -->\n"
    (ROOT / "python" / "README.md").write_text(header + convert(src), encoding="utf-8", newline="\n")
    print("wrote python/README.md")


if __name__ == "__main__":
    main()
