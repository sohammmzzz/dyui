"""A small, dependency-free ``.env`` loader used by ``dyui run``.

Supported syntax, one assignment per line::

    # comments and blank lines are ignored
    NVIDIA_API_KEY=nvapi-...
    export OPENAI_API_KEY=sk-...        # an ``export`` prefix is allowed
    DYUI_MODEL="openai/gpt-5"           # double quotes: \\n, \\t, \\" and \\\\ escapes
    GREETING='Hello # not a comment'    # single quotes: taken literally
    EMPTY=

There is no variable interpolation (``$OTHER`` stays as written) and no multi-line
values. Variables that are already set in the environment are never overridden
unless ``override=True``, so a value from your shell or your platform's secrets wins.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable, MutableMapping, Optional, Union

__all__ = ["parse_dotenv", "load_dotenv", "find_dotenv"]

_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}


def _unquote_double(body: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body) and body[i + 1] in _ESCAPES:
            out.append(_ESCAPES[body[i + 1]])
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _value(raw: str) -> Optional[str]:
    """The value part of ``KEY=<raw>``; ``None`` if a quote is never closed."""
    raw = raw.strip()
    if raw[:1] in ("'", '"'):
        quote = raw[0]
        i = 1
        while i < len(raw):
            if raw[i] == "\\" and quote == '"':
                i += 2
                continue
            if raw[i] == quote:
                break
            i += 1
        else:
            return None
        rest = raw[i + 1:].strip()
        if rest and not rest.startswith("#"):
            return None
        body = raw[1:i]
        return _unquote_double(body) if quote == '"' else body
    # unquoted: an inline comment starts at " #" (a "#" inside a value such as a URL fragment is kept)
    m = re.search(r"\s#", raw)
    if m:
        raw = raw[:m.start()]
    return raw.strip()


def parse_dotenv(text: str) -> dict[str, str]:
    """Parse ``.env`` text into a dict. Malformed lines are skipped."""
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export ") or line.startswith("export\t"):
            line = line[len("export"):].lstrip()
        key, sep, raw = line.partition("=")
        key = key.strip()
        if not sep or not _KEY.fullmatch(key):
            continue
        value = _value(raw)
        if value is None:
            continue
        values[key] = value
    return values


def load_dotenv(
    path: Union[str, os.PathLike],
    *,
    override: bool = False,
    environ: Optional[MutableMapping[str, str]] = None,
) -> list[str]:
    """Load ``path`` into ``environ`` (default ``os.environ``).

    Returns the names that were set (never the values). Names that already exist in
    the environment are left alone unless ``override=True``. A missing file loads nothing.
    """
    env = os.environ if environ is None else environ
    p = Path(path)
    if not p.is_file():
        return []
    text = p.read_text(encoding="utf-8-sig")
    loaded: list[str] = []
    for key, value in parse_dotenv(text).items():
        if not override and key in env:
            continue
        env[key] = value
        loaded.append(key)
    return loaded


def find_dotenv(dirs: Iterable[Union[str, os.PathLike]]) -> Optional[Path]:
    """The first ``.env`` file found in ``dirs`` (in order), or ``None``."""
    seen: set[Path] = set()
    for d in dirs:
        candidate = (Path(d) / ".env").resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.is_file():
            return candidate
    return None
