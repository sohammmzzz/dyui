"""Generator kit: context object, number/table/entity generators, reply assembly, user-turn styling."""
from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from bank import (CITIES, COMPANIES, DOMAINS, FIRST, LANGS, LAST, MONTHS, PERSONA_SUFFIX, WEEKDAYS, Domain)


def compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


# ----------------------------------------------------------------------------------------------
# number formatting
# ----------------------------------------------------------------------------------------------

# kind -> (prefix, suffix, chart unit)
FMT = {
    "usd_k": ("$", "k", "$k"), "usd": ("$", "", "$"), "pct": ("", "%", "%"), "count": ("", "", ""), "ms": ("", " ms", "ms"),
    "min": ("", " min", "min"), "days": ("", " days", "days"), "score": ("", "", "pts"), "hrs": ("", " h", "h"),
    "km": ("", " km", "km"), "bpm": ("", " bpm", "bpm"), "kwh": ("", " kWh", "kWh"), "kw": ("", " kW", "kW"),
    "ratio": ("", "x", "x"), "gb": ("", " GB", "GB"), "mbps": ("", " Mbps", "Mbps"), "t": ("", " t", "t"),
    "mm": ("", " mm", "mm"), "kl": ("", " kl", "kl"), "l": ("", " L", "L"), "sec": ("", " s", "s"), "mpg": ("", " mpg", "mpg"), "kg": ("", " kg", "kg"),
}


def fnum(v: float, dec: int, sep: bool = True) -> str:
    if dec <= 0:
        v = int(round(v))
        return f"{v:,}" if sep else str(v)
    s = f"{v:,.{dec}f}" if sep else f"{v:.{dec}f}"
    return s


def num(v: float, dec: int) -> Any:
    """JSON number for a value (int when integral and dec == 0)."""
    if dec <= 0:
        return int(round(v))
    return round(v, dec)


@dataclass
class Metric:
    label: str
    fmt: str
    lo: float
    hi: float
    dec: int
    good: str   # "up" / "down"

    @property
    def unit(self) -> str:
        return FMT[self.fmt][2]

    def gen(self, rng: random.Random) -> float:
        v = rng.uniform(self.lo, self.hi)
        return round(v, self.dec) if self.dec else float(int(round(v)))

    def show(self, v: float, sep: bool = True) -> str:
        p, s, _ = FMT[self.fmt]
        return f"{p}{fnum(v, self.dec, sep)}{s}"

    def bare(self, v: float, sep: bool = True) -> str:
        return fnum(v, self.dec, sep)


def parse_metric(s: str) -> Metric:
    label, fmt, lo, hi, dec, good = s.split(":")
    return Metric(label, fmt, float(lo), float(hi), int(dec), good)


# ----------------------------------------------------------------------------------------------
# context
# ----------------------------------------------------------------------------------------------

STYLES = ["terse", "casual", "formal", "detailed"]


class Ctx:
    """Everything a single item shares: rng, domain, persona, language, number style, derived numbers."""

    def __init__(self, rng: random.Random, dom: Domain, lang: str = "en", style: str = "casual") -> None:
        self.rng = rng
        self.dom = dom
        self.lang = lang
        self.style = style
        self.sep = rng.random() < 0.7          # thousands separators in user text
        self.derived: set[str] = set()
        self.persona = rng.choice(dom.personas) + rng.choice(PERSONA_SUFFIX)
        self.metrics = [parse_metric(m) for m in dom.metrics]

    # helpers ----------------------------------------------------------------------------
    def d(self, x: Any) -> str:
        """Register a derived number (computed by code, not in the context) and return its text."""
        s = str(x)
        self.derived.add(s)
        return s

    def pick(self, seq):
        return self.rng.choice(list(seq))

    def sample(self, seq, k):
        return self.rng.sample(list(seq), k)

    def person(self) -> str:
        return f"{self.rng.choice(FIRST)} {self.rng.choice(LAST)}"

    def metric(self) -> Metric:
        return self.rng.choice(self.metrics)

    def metrics_k(self, k: int) -> list[Metric]:
        return self.rng.sample(self.metrics, min(k, len(self.metrics)))

    def set_items(self, k: Optional[int] = None, key: Optional[str] = None) -> tuple[str, list[str]]:
        name = key or self.rng.choice(list(self.dom.sets))
        items = self.dom.sets[name].split(",")
        if k is not None:
            k = min(k, len(items))
            items = self.rng.sample(items, k)
        return name, items

    def months(self, n: int) -> list[str]:
        start = self.rng.randrange(0, 12 - n + 1)
        return MONTHS[self.lang][start:start + n]

    def days(self, n: int = 7) -> list[str]:
        return WEEKDAYS[self.lang][:n]


# ----------------------------------------------------------------------------------------------
# series / shares generators
# ----------------------------------------------------------------------------------------------

def gen_series(rng: random.Random, m: Metric, n: int, direction: Optional[str] = None) -> list[float]:
    """A plausible time series for a metric (monotone-ish with noise)."""
    direction = direction or rng.choice(["up", "up", "down", "wobble"])
    span = (m.hi - m.lo)
    base = m.lo + span * rng.uniform(0.25, 0.55)
    step = span * rng.uniform(0.02, 0.06)
    vals = []
    v = base
    for i in range(n):
        if direction == "up":
            v += step * rng.uniform(0.4, 1.6)
        elif direction == "down":
            v -= step * rng.uniform(0.4, 1.6)
        else:
            v += step * rng.uniform(-1.3, 1.3)
        v = max(m.lo * 0.9, min(m.hi * 1.05, v))
        if m.fmt == "pct":
            v = min(v, 100)
        vals.append(round(v, m.dec) if m.dec else float(int(round(v))))
    return vals


def gen_distinct_values(rng: random.Random, n: int, lo: float, hi: float, dec: int) -> list[float]:
    vals: set[float] = set()
    guard = 0
    while len(vals) < n and guard < 500:
        guard += 1
        vals.add(round(rng.uniform(lo, hi), dec) if dec else float(int(round(rng.uniform(lo, hi)))))
    return list(vals)


# ----------------------------------------------------------------------------------------------
# tables / entities from the mini-language
# ----------------------------------------------------------------------------------------------

def _cell(c: Ctx, kind: str, arg: str, used: set, idx: int) -> Any:
    rng = c.rng
    if kind == "pick":
        return rng.choice(arg.split(","))
    if kind == "num":
        lo, hi, dec = arg.split(",")
        dec = int(dec)
        v = rng.uniform(float(lo), float(hi))
        return round(v, dec) if dec else int(round(v))
    if kind == "money":
        lo, hi = arg.split(",")
        return "$" + f"{int(round(rng.uniform(float(lo), float(hi)))):,}"
    if kind == "id":
        for _ in range(50):
            if arg.endswith("."):
                s = f"{arg}{rng.randint(1, 9)}.{rng.randint(0, 20)}"
            elif arg.endswith("-"):
                s = f"{arg}{rng.randint(1000, 9999)}"
            else:
                s = f"{arg}-{rng.randint(100, 999)}"
            if s not in used:
                used.add(s)
                return s
        return f"{arg}-{idx}"
    if kind == "person":
        return c.person()
    if kind == "item":
        return rng.choice(COMPANIES)
    if kind == "city":
        return rng.choice(CITIES)
    if kind == "date":
        return f"{rng.choice(MONTHS['en'])} {rng.randint(1, 28)}"
    return "?"


def parse_cols(spec: str) -> tuple[str, list[tuple[str, str, str]]]:
    title, cols = spec.split("|", 1)
    out = []
    for part in cols.split(";"):
        key, rest = part.split("=", 1)
        kind, _, arg = rest.partition(":")
        out.append((key, kind, arg))
    return title, out


def gen_table(c: Ctx, spec: Optional[str] = None, nrows: int = 4, ncols: Optional[int] = None) -> tuple[str, list[str], list[list[Any]]]:
    spec = spec or c.rng.choice(c.dom.tables)
    title, cols = parse_cols(spec)
    if ncols is not None and ncols < len(cols):
        cols = cols[:max(2, ncols)]
    used: set = set()
    rows: list[list[Any]] = []
    seen_first: set = set()
    for i in range(nrows):
        for _ in range(30):
            row = [_cell(c, kind, arg, used, i) for _, kind, arg in cols]
            if row[0] not in seen_first:
                seen_first.add(row[0])
                break
        rows.append(row)
    return title, [k for k, _, _ in cols], rows


def gen_entity(c: Ctx) -> tuple[str, list[tuple[str, Any]]]:
    title, cols = parse_cols(c.dom.entity)
    used: set = set()
    items = [(k, _cell(c, kind, arg, used, 0)) for k, kind, arg in cols]
    return title, items


# ----------------------------------------------------------------------------------------------
# text rendering of data for user turns
# ----------------------------------------------------------------------------------------------

def cell_text(v: Any, sep: bool = True) -> str:
    if isinstance(v, float) and v == int(v) and abs(v) < 1e15:
        v = int(v)
    if isinstance(v, int) and not isinstance(v, bool) and sep and abs(v) >= 1000:
        return f"{v:,}"
    return str(v)


def rows_text(c: Ctx, cols: list[str], rows: list[list[Any]], style: Optional[str] = None) -> str:
    style = style or c.rng.choice(["pipes", "bullets", "inline", "colon"])
    if style == "pipes":
        lines = [" | ".join(cols)] + [" | ".join(cell_text(x, c.sep) for x in r) for r in rows]
        return "\n".join(lines)
    if style == "bullets":
        return "\n".join("- " + ", ".join(f"{k}: {cell_text(x, c.sep)}" for k, x in zip(cols, r)) for r in rows)
    if style == "colon":
        return "\n".join(f"{cell_text(r[0], c.sep)}: " + ", ".join(cell_text(x, c.sep) for x in r[1:]) for r in rows) + \
            f"\n(columns: {', '.join(cols)})"
    return "; ".join(f"{cell_text(r[0], c.sep)} (" + ", ".join(f"{k} {cell_text(x, c.sep)}" for k, x in zip(cols[1:], r[1:])) + ")"
                     for r in rows) + f". First column is {cols[0]}."


def pairs_text(c: Ctx, labels: list[str], values: list[float], m: Optional[Metric] = None, style: Optional[str] = None,
               dec: int = 0) -> str:
    style = style or c.rng.choice(["comma", "semi", "lines", "eq"])
    parts = []
    for l, v in zip(labels, values):
        vs = m.show(v, c.sep) if m else fnum(v, dec, c.sep)
        parts.append((l, vs))
    if style == "comma":
        return ", ".join(f"{l} {v}" for l, v in parts)
    if style == "semi":
        return "; ".join(f"{l}: {v}" for l, v in parts)
    if style == "lines":
        return "\n".join(f"- {l}: {v}" for l, v in parts)
    return " | ".join(f"{l}={v}" for l, v in parts)


def series_text(c: Ctx, labels: list[str], values: list[float], m: Optional[Metric] = None, dec: int = 0) -> str:
    """'Jun–Nov: 31.2, 33.8, ...' or 'Jun 31.2, Jul 33.8'."""
    style = c.rng.choice(["range", "pairs", "arrow"])
    vs = [m.bare(v, c.sep) if m else fnum(v, dec, c.sep) for v in values]
    if style == "range":
        return f"{labels[0]}–{labels[-1]}: " + ", ".join(vs)
    if style == "pairs":
        return ", ".join(f"{l} {v}" for l, v in zip(labels, vs))
    return " → ".join(f"{l} {v}" for l, v in zip(labels, vs))


# ----------------------------------------------------------------------------------------------
# URLs
# ----------------------------------------------------------------------------------------------

_HOSTS = ["docs.acme-cloud.example.com", "cdn.fernhill.example.com", "www.example.org", "media.example.net",
          "blog.northwind.example.com", "files.example.com", "static.brasa.example.com", "assets.lumen.example.io",
          "help.helpwave.example.com", "news.example.com"]
_SLUGS = "overview pricing release-notes getting-started security guide report q3-summary roadmap case-study faq changelog handbook annual-review benchmark".split()


def gen_url(c: Ctx, kind: str = "page", i: int = 0) -> str:
    rng = c.rng
    host = rng.choice(_HOSTS)
    slug = rng.choice(_SLUGS)
    if kind == "page":
        return f"https://{host}/{slug}/{rng.randint(2, 99)}" if rng.random() < 0.4 else f"https://{host}/{slug}"
    if kind == "image":
        return f"https://{host}/img/{rng.choice(_SLUGS)}-{rng.randint(1, 40):02d}.{rng.choice(['jpg', 'png', 'webp'])}"
    if kind == "video":
        if rng.random() < 0.5:
            vid = "".join(rng.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-") for _ in range(11))
            return f"https://www.youtube.com/watch?v={vid}"
        return f"https://{host}/video/{rng.choice(_SLUGS)}.mp4"
    if kind == "audio":
        return f"https://{host}/audio/{rng.choice(_SLUGS)}-{rng.randint(1, 30):02d}.mp3"
    if kind == "file":
        return f"https://{host}/files/{rng.choice(_SLUGS)}.{rng.choice(['pdf', 'xlsx', 'csv', 'zip'])}"
    return f"https://{host}/"


# ----------------------------------------------------------------------------------------------
# Piece + reply assembly
# ----------------------------------------------------------------------------------------------

@dataclass
class Piece:
    facts: str
    ask: str
    objs: list[dict]
    intro: str
    outro: str
    row: str
    ground: list[str] = field(default_factory=list)
    kinds: list[str] = field(default_factory=list)       # chart kinds in objs
    html_code: bool = False
    comps: list[str] = field(default_factory=list)       # extra: components expected (any_of); default top-level names
    lang: str = "en"
    string_ground: bool = False


def render_reply(parts: list) -> str:
    """parts: alternating prose / list[obj] (a dyui block).  Always starts and ends with prose."""
    out: list[str] = []
    for p in parts:
        if isinstance(p, str):
            out.append(p.strip())
        else:
            out.append("```dyui\n" + "\n".join(compact(o) for o in p) + "\n```")
    return "\n".join(out)


def piece_reply(p: Piece) -> str:
    return render_reply([p.intro, p.objs, p.outro])


_CASUAL = ["hey, ", "ok so ", "quick one: ", "", "", "", "hi! ", "btw "]
_FORMAL = ["Could you help me with this? ", "Please help with the following. ", "I would appreciate your help: ", "", ""]
_TAIL_CASUAL = ["", "", " thx", " thanks!", ""]


def assemble_user(c: Ctx, facts: str, ask: str, style: Optional[str] = None) -> str:
    """Combine data and request into a user turn, varying order and style."""
    rng = c.rng
    style = style or c.style
    facts, ask = facts.strip(), ask.strip()
    if facts and ask:
        order = rng.choice(["fa", "fa", "af", "a:f"])
        if order == "fa":
            text = f"{facts} {ask}" if "\n" not in facts else f"{facts}\n{ask}"
        elif order == "af":
            text = f"{ask}\n{facts}" if "\n" in facts or len(facts) > 120 else f"{ask} {facts}"
        else:
            text = f"{ask.rstrip('?.!:')}:\n{facts}" if "\n" in facts else f"{ask.rstrip('?.!:')}: {facts}"
    else:
        text = facts or ask
    if c.lang == "en":
        if style == "casual":
            pre = rng.choice(_CASUAL)
            if pre and text[:1].isupper() and not text[:2].isupper():
                text = pre + text[0].lower() + text[1:]
            elif pre:
                text = pre + text
            text += rng.choice(_TAIL_CASUAL)
        elif style == "formal":
            text = rng.choice(_FORMAL) + text
        elif style == "terse":
            text = text.replace("Could you ", "").replace("Please ", "")
    return text


def pct(part: float, total: float, dec: int = 0) -> str:
    return fnum(100 * part / total, dec, False)
