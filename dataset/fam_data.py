"""Piece builders, part 1: content + data components.

Each builder returns a :class:`kit.Piece` (user facts + ask, the gold component objects, intro/outro prose).
Signature: ``builder(c: Ctx, mode: 'min'|'typ'|'all', force: dict) -> Piece``.
"""
from __future__ import annotations

import json
import re
from typing import Any

from kit import (FMT, Ctx, Metric, Piece, cell_text, compact, fnum, gen_distinct_values, gen_entity, gen_series,
                 gen_table, gen_url, num, pairs_text, parse_cols, pct, rows_text, series_text)
from lang import DIRP, FR, MONTH_WORD, RISE, SENT

MONTH_FULL = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
              "November", "December"]


class Has:
    """Decides which optional props a builder includes for a mode."""

    def __init__(self, c: Ctx, mode: str, force_on: tuple = ()):
        self.c, self.mode, self.on = c, mode, set(force_on)
        self.used: set[str] = set()

    def __call__(self, prop: str) -> bool:
        if prop in self.on:
            r = True
        elif self.mode == "all":
            r = True
        elif self.mode == "min":
            r = False
        else:
            r = self.c.rng.random() < 0.5
        if r:
            self.used.add(prop)
        return r


def _fr(c: Ctx, fam: str, key: str, **kw) -> str:
    return c.rng.choice(FR[fam][c.lang][key]).format(**kw)


def _s(c: Ctx, seq) -> str:
    return c.rng.choice(seq)


def _fix(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


# ----------------------------------------------------------------------------------------------
# stat / stats
# ----------------------------------------------------------------------------------------------

def _change(c: Ctx, m: Metric) -> tuple[str, float]:
    d = force_dir = None
    return "", 0.0


def _dir_and_ch(c: Ctx, direction: str | None = None) -> tuple[str, float]:
    d = direction or c.pick(["up", "up", "down", "flat"])
    ch = 0.0 if d == "flat" else round(c.rng.uniform(0.4, 18.0), 1)
    return d, ch


def _delta_str(c: Ctx, d: str, ch: float, suffix: bool = True) -> str:
    if d == "flat":
        return "0%" + (" vs last month" if suffix else "")
    return f"{'+' if d == 'up' else '-'}{ch}%" + (" vs last month" if suffix else "")


def _sentiment(m: Metric, d: str) -> str:
    if d == "flat":
        return "steady"
    return "good" if d == m.good else "bad"


def stat_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    has = Has(c, mode, ("trend",) if force.get("trend") else ())
    m = force.get("metric") or c.metric()
    v = m.gen(c.rng)
    d, ch = _dir_and_ch(c, force.get("trend"))
    en = c.lang == "en"
    period = _s(c, MONTH_FULL) if en else ""
    vs = m.show(v, c.sep)
    label = f"{m.label} · {period}" if (en and has("period_in_label")) else m.label
    use_delta, use_trend, use_help = has("delta"), has("trend"), has("help")
    use_unit = has("unit") and bool(m.unit) and en
    target = None
    if use_help:
        target = m.show(round(v * c.rng.uniform(0.85, 1.15), m.dec) if m.dec else round(v * c.rng.uniform(0.85, 1.15)), c.sep)
    if not en:
        use_delta = True
        use_trend = use_trend or False
    dirtxt = {"up": f"up {ch}% vs last month", "down": f"down {ch}% vs last month", "flat": "unchanged vs last month"}[d]
    # ---- user facts
    if en:
        base = _s(c, [f"{m.label} for {period}: {vs}", f"We ended {period} with {m.label} at {vs}", f"{m.label} is {vs} right now",
                      f"{m.label} came in at {vs} in {period}", f"{period} {m.label}: {vs}"])
        tail = ""
        if use_delta:
            tail = f", {dirtxt}"
        elif use_trend:
            tail = f", trending {'flat' if d == 'flat' else d}"
        facts = base + tail + "."
        if use_help:
            facts += _s(c, [f" The target is {target}.", f" Our goal: {target}.", f" Target {target}."])
        ask = _s(c, ["How are we doing?", "Is that good?", "Where do we stand?", "Can you show that nicely?", "How does it look?",
                     "Give me the headline.", "Is this on track?"])
    else:
        dirp = DIRP[c.lang][d].format(ch=ch)
        facts = _fr(c, "stat", "facts", label=m.label, value=vs, dirp=dirp)
        ask = _fr(c, "stat", "ask")
        if use_help:
            facts += f" ({target})"
    # ---- the component
    obj: dict[str, Any] = {"ui": "stat", "label": label}
    if use_unit:
        obj["value"] = num(v, m.dec)
        obj["unit"] = m.unit
    else:
        obj["value"] = vs
    if use_delta:
        obj["delta"] = _delta_str(c, d, ch, suffix=en)
    if use_trend:
        obj["trend"] = d
    if use_help:
        obj["help"] = f"Target {target}"
    # ---- prose
    sent = _sentiment(m, d)
    if en:
        intro = _s(c, [f"Here is {m.label} for {period}.", f"{m.label} for {period} at a glance:", f"This is where {m.label} stands in {period}.",
                       f"Here's the {period} reading for {m.label}."])
        if sent == "good":
            outro = _s(c, [f"That is good news for {m.label}.", f"{m.label} is moving the right way.", f"Momentum on {m.label} looks healthy."])
        elif sent == "bad":
            outro = _s(c, [f"{m.label} is moving the wrong way, so it deserves a closer look.", f"That trend on {m.label} is worth watching."])
        else:
            outro = _s(c, [f"{m.label} is holding steady.", f"There was no real movement on {m.label} this month."])
        if use_delta and d != "flat" and c.rng.random() < 0.4:
            outro = f"{m.label} is {'up' if d == 'up' else 'down'} {ch}% on last month, which is " + {"good": "good news", "bad": "a concern", "steady": "stable"}[sent] + "."
    else:
        dirp = DIRP[c.lang][d].format(ch=ch)
        intro = _fr(c, "stat", "intro", label=m.label)
        outro = _fr(c, "stat", "outro", label=m.label, dirp=dirp, sent=SENT[c.lang][sent])
    ground = [obj["value"] if isinstance(obj["value"], str) else str(obj["value"])]
    return Piece(facts, ask, [obj], intro, outro, "headline_number", ground, lang=c.lang)


def stats_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    has = Has(c, mode)
    k = force.get("k") or c.rng.randint(2, 6)
    ms = c.metrics_k(k)
    en = c.lang == "en"
    forced_trends = list(force.get("trends") or [])
    items, parts = [], []
    biggest = (None, -1.0, "up", 0.0)
    for i, m in enumerate(ms):
        v = m.gen(c.rng)
        d, ch = _dir_and_ch(c, forced_trends[i] if i < len(forced_trends) else None)
        vs = m.show(v, c.sep)
        it: dict[str, Any] = {"label": m.label}
        use_d = has("delta") or not en
        use_t = has("trend") or i < len(forced_trends)
        use_u = has("unit") and bool(m.unit) and en and not use_d and not forced_trends
        use_h = has("help") and en
        if use_u:
            it["value"], it["unit"] = num(v, m.dec), m.unit
            txt = f"{m.label} {vs}"
        else:
            it["value"] = vs
            txt = f"{m.label} {vs}"
        if use_d:
            it["delta"] = _delta_str(c, d, ch, suffix=False)
            txt += f" ({'unchanged' if d == 'flat' else ('up ' if d == 'up' else 'down ') + str(ch) + '%'})" if en else \
                f" ({DIRP[c.lang][d].format(ch=ch)})"
        if use_t:
            it["trend"] = d
            if not use_d:
                txt += f" ({'flat' if d == 'flat' else d})" if en else ""
        if use_h:
            t = m.show(round(v * 1.1, m.dec) if m.dec else round(v * 1.1), c.sep)
            it["help"] = f"Target {t}"
            txt += f", target {t}"
        items.append(it)
        parts.append(txt)
        if use_d and ch > biggest[1]:
            biggest = (m, ch, d, ch)
    facts_items = _s(c, [", ", "; ", ", "]).join(parts)
    obj = {"ui": "stats", "items": items}
    if en:
        facts = _s(c, [f"This month: {facts_items}.", f"Numbers: {facts_items}.", f"{facts_items}.", f"Quick numbers for the review: {facts_items}."])
        ask = _s(c, ["Give me the overview.", "Can you summarise those?", "What's the picture?", "Show them as headline numbers."])
        intro = _s(c, [f"Here are the {k} headline numbers for the month.", f"These are the key figures at a glance.", f"Here is the summary of {k} indicators."])
        if biggest[0] is not None:
            bm, _, bd, bch = biggest
            outro = _s(c, [f"The biggest move is {bm.label}, {'up' if bd == 'up' else 'down' if bd == 'down' else 'flat'}"
                           + (f" {bch}%." if bd != "flat" else "."),
                           f"{bm.label} changed the most this month."])
        else:
            outro = _s(c, ["Read them together before drawing conclusions about any single metric.", "Together they give a quick health check of the month."])
    else:
        facts = _fr(c, "stats", "facts", items=facts_items)
        ask = _fr(c, "stats", "ask")
        intro = _fr(c, "stats", "intro", n=k)
        bm, _, bd, bch = biggest if biggest[0] is not None else (ms[0], 0, "flat", 0)
        outro = _fr(c, "stats", "outro", label=bm.label, dirp=DIRP[c.lang][bd if bd != 'flat' else 'flat'].format(ch=bch))
    ground = [str(it["value"]) for it in items]
    return Piece(facts, ask, [obj], intro, outro, "headline_numbers", ground, lang=c.lang)


# ----------------------------------------------------------------------------------------------
# charts
# ----------------------------------------------------------------------------------------------

def _topic(c: Ctx, m: Metric) -> str:
    return m.label[0].lower() + m.label[1:] if m.label[:2].upper() != m.label[:2] else m.label


def chart_trend_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    has = Has(c, mode)
    kind = force.get("kind") or c.pick(["line", "area"])
    m = force.get("metric") or c.metric()
    n = c.rng.randint(4, 8)
    en = c.lang == "en"
    use_days = en and c.rng.random() < 0.2 and m.fmt in ("count", "usd", "ms")
    if use_days:
        labels, n = c.days(7), 7
    else:
        labels = c.months(n)
    vals = gen_series(c.rng, m, n, force.get("direction"))
    topic = m.label
    series_s = series_text(c, labels, vals, m)
    use_labels, use_title, use_unit = has("labels"), has("title"), has("unit") and bool(m.unit)
    if not use_labels and mode == "min":
        pass
    obj: dict[str, Any] = {"ui": "chart", "kind": kind}
    if use_labels:
        obj["labels"] = labels
    obj["series"] = [{"name": m.label, "data": [num(v, m.dec) for v in vals]}]
    if use_title:
        obj["title"] = f"{m.label}, {labels[0]}–{labels[-1]}"
    if use_unit:
        obj["unit"] = m.unit
    rose = vals[-1] >= vals[0]
    if en:
        facts = _s(c, [f"{m.label} {series_s}", f"{m.label} over the period – {series_s}", f"Here is {m.label}. {series_s}"])
        if not facts.endswith("."):
            facts += "."
        ask = _s(c, ["How has it trended?", "Show me the trend.", "What's the trajectory?", "Has it been improving?", "Plot it for me."])
        if kind == "area" and c.rng.random() < 0.5:
            ask = _s(c, ["Show it as an area chart.", "Can I get that as an area graph?"])
        elif kind == "line" and c.rng.random() < 0.3:
            ask = "Make me a line chart of that."
        per = "days" if use_days else "months"
        intro = _s(c, [f"Here is {m.label} from {labels[0]} to {labels[-1]}.", f"This is how {m.label} moved from {labels[0]} to {labels[-1]}.",
                       f"{m.label} over the period, {labels[0]} to {labels[-1]}:"])
        nn = c.d(n) if not use_days else c.d(n)
        outro = _s(c, [f"{m.label} {'rose' if rose else 'fell'} from {m.bare(vals[0], c.sep)} to {m.bare(vals[-1], c.sep)} across {nn} {per}.",
                       f"Over {nn} {per}, {m.label} went from {m.bare(vals[0], c.sep)} to {m.bare(vals[-1], c.sep)}."])
    else:
        facts = _fr(c, "trend", "facts", topic=topic, first_l=labels[0], last_l=labels[-1], series=series_s)
        ask = _fr(c, "trend", "ask")
        intro = _fr(c, "trend", "intro", topic=topic, first_l=labels[0], last_l=labels[-1])
        rf = RISE[c.lang][0 if rose else 1]
        outro = _fr(c, "trend", "outro", n=c.d(n), mw=MONTH_WORD[c.lang], topic=topic, rf=rf,
                    v0=m.bare(vals[0], c.sep), vn=m.bare(vals[-1], c.sep))
    ground = [str(num(v, m.dec)) for v in vals]
    return Piece(facts, ask, [obj], intro, outro, "trend", ground, kinds=[kind], lang=c.lang)


_STACK_PAIRS = [("New", "Returning"), ("Online", "In person"), ("Self-serve", "Assisted"), ("Planned", "Unplanned"), ("Mobile", "Desktop")]


def chart_compare_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    has = Has(c, mode, ("stacked",) if force.get("stacked") else ())
    en = c.lang == "en"
    setname, labels = c.set_items(c.rng.randint(3, 6))
    m = c.metric()
    stacked = bool(force.get("stacked")) or (en and has("stacked") and c.rng.random() < 0.6)
    use_title, use_unit, use_labels = has("title"), has("unit") and bool(m.unit), True
    obj: dict[str, Any] = {"ui": "chart", "kind": "bar"}
    topic = f"{m.label} by {setname}"
    if stacked:
        a, b = c.pick(_STACK_PAIRS)
        va = [m.gen(c.rng) for _ in labels]
        vb = [m.gen(c.rng) for _ in labels]
        lines = [f"{l}: {m.bare(x, c.sep)} {a.lower()}, {m.bare(y, c.sep)} {b.lower()}" for l, x, y in zip(labels, va, vb)]
        facts_pairs = "; ".join(lines)
        series = [{"name": a, "data": [num(x, m.dec) for x in va]}, {"name": b, "data": [num(y, m.dec) for y in vb]}]
        tot = [x + y for x, y in zip(va, vb)]
        top_i = max(range(len(labels)), key=lambda i: tot[i])
        top, v1 = labels[top_i], round(tot[top_i], m.dec)
        bot_i = min(range(len(labels)), key=lambda i: tot[i])
        bottom, v2 = labels[bot_i], round(tot[bot_i], m.dec)
        v1s, v2s = c.d(fnum(v1, m.dec, c.sep)), c.d(fnum(v2, m.dec, c.sep))
    else:
        vals = gen_distinct_values(c.rng, len(labels), m.lo, m.hi, m.dec)
        facts_pairs = pairs_text(c, labels, vals, m)
        series = [{"name": m.label, "data": [num(x, m.dec) for x in vals]}]
        top_i = max(range(len(labels)), key=lambda i: vals[i])
        bot_i = min(range(len(labels)), key=lambda i: vals[i])
        top, bottom = labels[top_i], labels[bot_i]
        v1s, v2s = m.bare(vals[top_i], c.sep), m.bare(vals[bot_i], c.sep)
    obj["labels"] = labels
    obj["series"] = series
    if use_title:
        obj["title"] = topic
    if use_unit:
        obj["unit"] = m.unit
    if stacked:
        obj["stacked"] = True
    if en:
        facts = _s(c, [f"{_fix(topic)}: {facts_pairs}", f"{_fix(m.label)} per {setname} this quarter – {facts_pairs}", f"{_fix(topic)}\n{facts_pairs}"]) if "\n" not in facts_pairs else f"{_fix(topic)}:\n{facts_pairs}"
        ask = _s(c, ["Which one is ahead?", "Compare them for me.", "Who's leading?", "How do they stack up?", "Show me the comparison."])
        if stacked:
            ask = _s(c, ["Show how each splits into its two parts.", "Can you stack them so I see both parts per " + setname + "?"])
        intro = _s(c, [f"Here is {m.label} compared across {len(labels)} groups.", f"This compares {m.label} by {setname}.", f"Here's how the {setname} values line up."])
        outro = _s(c, [f"{top} leads with {v1s}, while {bottom} trails at {v2s}.", f"{top} is on top ({v1s}) and {bottom} is lowest ({v2s})."])
    else:
        facts = _fr(c, "compare", "facts", topic=_fix(topic), pairs=facts_pairs)
        ask = _fr(c, "compare", "ask")
        intro = _fr(c, "compare", "intro", topic=m.label, dim=setname, n=len(labels))
        outro = _fr(c, "compare", "outro", top=top, bottom=bottom, v1=v1s, v2=v2s)
    ground = [str(x) for s in series for x in s["data"]]
    return Piece(facts, ask, [obj], intro, outro, "compare", ground, kinds=["bar"], lang=c.lang)


def chart_shares_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    has = Has(c, mode)
    kind = force.get("kind") or c.pick(["donut", "pie"])
    en = c.lang == "en"
    setname, labels = c.set_items(c.rng.randint(3, 6))
    vals = [int(round(c.rng.uniform(300, 5200))) for _ in labels]
    m = Metric("Signups", "count", 0, 0, 0, "up")
    noun = c.pick(["signups", "orders", "leads", "visits", "units", "tickets"])
    total = sum(vals)
    top_i = max(range(len(labels)), key=lambda i: vals[i])
    p = c.d(pct(vals[top_i], total, 0))
    pairs = pairs_text(c, labels, vals, None, dec=0)
    obj: dict[str, Any] = {"ui": "chart", "kind": kind}
    if has("labels") or True:
        obj["labels"] = labels
    obj["series"] = [{"name": noun.capitalize() if en else noun, "data": vals}]
    topic = f"{noun} per {setname}"
    if has("title"):
        obj["title"] = _fix(topic)
    if has("unit"):
        obj["unit"] = noun
    if en:
        facts = _s(c, [f"{_fix(noun)} per {setname} last quarter: {pairs}.", f"{_fix(topic)} – {pairs}.", f"Last quarter's {noun}, by {setname}:\n{pairs}"])
        ask = _s(c, ["Where are they coming from?", "How is it split?", "What's the breakdown?", "Which one dominates?", "Show me the split."])
        if kind == "pie" and c.rng.random() < 0.5:
            ask = "Give me a pie chart of that."
        intro = _s(c, [f"Here is how {noun} split across {len(labels)} {setname} groups.", f"This is the share of {noun} by {setname}.", f"Here's the breakdown of {noun} by {setname}."])
        outro = _s(c, [f"{labels[top_i]} is the biggest slice at about {p}% of the total.", f"{labels[top_i]} accounts for roughly {p}% of everything."])
    else:
        facts = _fr(c, "shares", "facts", topic=_fix(topic), pairs=pairs)
        ask = _fr(c, "shares", "ask")
        intro = _fr(c, "shares", "intro", topic=topic, dim=setname)
        outro = _fr(c, "shares", "outro", top=labels[top_i], p=p)
    return Piece(facts, ask, [obj], intro, outro, "shares", [str(v) for v in vals], kinds=[kind], lang=c.lang)


def chart_scatter_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    has = Has(c, mode)
    rng = c.rng
    pairs_defs = [("ad spend ($k)", "leads", 1.5, 9.0, 40, 12), ("hours studied", "exam score", 2, 20, 52, 2.2),
                  ("temperature (C)", "ice-cream sales", 8, 34, 30, 11), ("team size", "tickets closed per week", 3, 15, 20, 7),
                  ("price ($)", "units sold", 10, 60, 900, -12), ("deploys per week", "incidents", 2, 30, 1, 0.5)]
    xn, yn, xlo, xhi, y0, slope = c.pick(pairs_defs)
    n = rng.randint(6, 9)
    xs = sorted(round(rng.uniform(xlo, xhi), 1) for _ in range(n))
    pts = [[x, round(max(1, y0 + slope * x * (3 if slope > 5 else 1) + rng.uniform(-0.15, 0.15) * abs(y0 + slope * x)), 1)] for x in xs]
    pts = [[x, int(y) if y == int(y) else y] for x, y in pts]
    pts = [[int(x) if x == int(x) else x, y] for x, y in pts]
    ptxt = ", ".join(f"({x}, {y})" for x, y in pts)
    positive = pts[-1][1] > pts[0][1]
    obj: dict[str, Any] = {"ui": "chart", "kind": "scatter", "series": [{"name": f"{_fix(yn)} vs {xn}", "data": pts}]}
    if has("title"):
        obj["title"] = f"{_fix(yn)} vs {xn}"
    if has("unit"):
        obj["unit"] = yn
    facts = _s(c, [f"Data points (x = {xn}, y = {yn}): {ptxt}.", f"{_fix(xn)} vs {yn}, one point per sample: {ptxt}."])
    ask = _s(c, ["Is there a relationship?", "Does one drive the other?", "Plot these against each other.", "Show me the correlation."])
    intro = _s(c, [f"Here is {yn} plotted against {xn}.", f"This scatter shows how {yn} relates to {xn}."])
    outro = (_s(c, [f"Higher {xn} goes with higher {yn} across these points.", f"The points slope upward, so {yn} grows with {xn}."]) if positive
             else _s(c, [f"Higher {xn} goes with lower {yn} across these points.", f"The points slope downward, so {yn} falls as {xn} rises."]))
    ground = [str(p[0]) for p in pts] + [str(p[1]) for p in pts]
    return Piece(facts, ask, [obj], intro, outro, "relationship", ground, kinds=["scatter"], lang="en")


# ----------------------------------------------------------------------------------------------
# table / keyvalue / timeline / plan / progress / json
# ----------------------------------------------------------------------------------------------

def table_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    has = Has(c, mode)
    en = c.lang == "en"
    nrows = force.get("nrows") or c.rng.randint(3, 8)
    title, cols, rows = gen_table(c, force.get("spec"), nrows, force.get("ncols"))
    obj: dict[str, Any] = {"ui": "table", "columns": cols, "rows": rows}
    if has("caption"):
        obj["caption"] = title
    rt = rows_text(c, cols, rows, force.get("rows_style"))
    # insight: highest numeric column
    num_cols = [i for i, _ in enumerate(cols) if all(isinstance(r[i], (int, float)) and not isinstance(r[i], bool) for r in rows)]
    if num_cols:
        ci = num_cols[-1]
        top = max(rows, key=lambda r: r[ci])
        who, col, val = str(top[0]), cols[ci], cell_text(top[ci], c.sep)
    else:
        who, col, val = str(rows[0][0]), cols[0], str(rows[0][0])
    if en:
        facts = _s(c, [f"{title}:\n{rt}", f"Here is the data for {title.lower()}.\n{rt}", f"{rt}"])
        ask = _s(c, ["Show me that cleanly.", "Put it in a table, please.", "Can you lay this out?", "Make it easy to scan.", "What does the list look like?"])
        intro = _s(c, [f"Here are {len(rows)} records for {title.lower()}.", f"This is {title.lower()} laid out in a table.", f"Here's the {title.lower()} list, row by row."]) \
            if False else _s(c, [f"Here is {title.lower()} laid out in a table.", f"This is the {title.lower()} list, one row per record.", f"Here's {title.lower()} in table form."])
        if num_cols:
            outro = _s(c, [f"{who} has the highest {col} at {val}.", f"The top {col} belongs to {who} ({val})."])
        else:
            outro = _s(c, [f"{who} is the first entry; the rest follow in the order you gave.", f"The rows keep the order you provided, starting with {who}."])
    else:
        facts = _fr(c, "table", "facts", rows=f"{title}:\n{rt}")
        ask = _fr(c, "table", "ask")
        intro = _fr(c, "table", "intro", topic=title.lower(), n=c.d(len(rows)))
        outro = _fr(c, "table", "outro", col=col, val=val, who=who)
    ground = [str(r[0]) for r in rows]
    return Piece(facts, ask, [obj], intro, outro, "records_table", ground, lang=c.lang, string_ground=True)


def keyvalue_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    en = c.lang == "en"
    title, items = gen_entity(c)
    k = c.rng.randint(3, len(items))
    items = items[:k]
    obj = {"ui": "keyvalue", "items": [{"key": kk, "value": vv} for kk, vv in items]}
    pairs = ", ".join(f"{kk} {cell_text(vv, c.sep)}" if c.rng.random() < 0.3 else f"{kk}: {cell_text(vv, c.sep)}" for kk, vv in items)
    pairs = "; ".join(f"{kk}: {cell_text(vv, c.sep)}" for kk, vv in items) if c.rng.random() < 0.5 else pairs
    ent = f"{title} {c.pick(['A-17', 'North', 'no. 4', 'Alpha', 'Beta', 'Delta'])}" if False else title
    tk, tv = items[-1]
    if en:
        facts = _s(c, [f"{ent}: {pairs}.", f"Details on the {ent.lower()} – {pairs}.", f"The {ent.lower()} has these details. {pairs}."])
        ask = _s(c, ["Summarise it.", "What are the key facts?", "Give me the rundown.", "Lay out the details.", "Show me the profile."])
        intro = _s(c, [f"Here are the key facts for this {ent.lower()}.", f"This is the {ent.lower()} at a glance.", f"Here's the {ent.lower()} profile."])
        outro = _s(c, [f"The one to watch is {tk}, currently {cell_text(tv, c.sep)}.", f"{tk} is {cell_text(tv, c.sep)} right now; everything else is as listed."])
    else:
        facts = _fr(c, "keyvalue", "facts", entity=ent, pairs=pairs)
        ask = _fr(c, "keyvalue", "ask")
        intro = _fr(c, "keyvalue", "intro", entity=ent)
        outro = _fr(c, "keyvalue", "outro", k=tk, v=cell_text(tv, c.sep))
    ground = [cell_text(vv, False) if isinstance(vv, (int, float)) else str(vv) for _, vv in items]
    return Piece(facts, ask, [obj], intro, outro, "entity_facts", ground, lang=c.lang, string_ground=True)


_TL_STATUSES = ["done", "active", "pending"]


def timeline_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    has = Has(c, mode)
    tasks = c.rng.sample(c.dom.tasks, c.rng.randint(3, 5))
    n = len(tasks)
    forced = list(force.get("statuses") or [])
    statuses = forced[:n]
    if len(statuses) < n:
        k_done = c.rng.randint(1, max(1, n - 2))
        base = ["done"] * k_done + ["active"] + ["pending"] * (n - k_done - 1)
        statuses = statuses + base[len(statuses):]
    if "active" in forced and "done" not in forced and n >= 3:
        pass
    start_m = c.rng.randrange(0, 9)
    day0 = c.rng.randint(1, 9)
    items, lines = [], []
    use_status, use_time, use_text = has("status"), has("time"), has("text")
    owners = [c.person() for _ in tasks]
    for i, t in enumerate(tasks):
        tm = f"{c.pick(['Mon', 'Tue', 'Wed', 'Thu', 'Fri'])} {c.rng.randint(8, 17):02d}:{c.pick(['00', '15', '30', '45'])}" if c.rng.random() < 0.0 else \
            f"{c.pick(__import__('bank').MONTHS['en'])} {day0 + i * 2}"
        it: dict[str, Any] = {"title": t}
        txt = t
        if use_time:
            it["time"] = tm
            txt = f"{tm}: {t}"
        if use_status or force.get("statuses"):
            it["status"] = statuses[i]
            txt += f" ({ {'done': 'done', 'active': 'in progress', 'pending': 'not started'}[statuses[i]] })"
        if use_text:
            it["text"] = f"Owner: {owners[i]}"
            txt += f", owner {owners[i]}"
        items.append(it)
        lines.append(txt)
    facts = _s(c, ["Timeline so far:\n", "Here's how it's going:\n", "Events in order:\n"]) + "\n".join("- " + l for l in lines)
    ask = _s(c, ["Lay that out as a timeline.", "Show me where we are.", "Put these in order for the stakeholders."])
    obj = {"ui": "timeline", "items": items}
    intro = _s(c, ["Here is the sequence from start to finish.", "This is the timeline in order.", "Here's the timeline as it stands."])
    done_n = statuses.count("done")
    if use_status or force.get("statuses"):
        outro = _s(c, [f"{c.d(done_n)} of {c.d(n)} steps are complete.", f"We are {c.d(done_n)} steps in, with {c.d(n - done_n)} to go."]) if done_n else \
            _s(c, ["Nothing is finished yet; the first step is under way.", "The first step is still in progress."])
    else:
        outro = _s(c, ["The steps run in the order listed.", "Each step follows the one before it."])
    ground = [t for t in tasks]
    return Piece(facts, ask, [obj], intro, outro, "events", ground, lang="en")


def plan_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    has = Has(c, mode)
    tasks = c.rng.sample(c.dom.tasks, c.rng.randint(4, 5)) if len(c.dom.tasks) >= 4 else list(c.dom.tasks)
    n = len(tasks)
    forced = list(force.get("statuses") or [])
    pool = ["done", "active", "pending", "error", "skipped"]
    statuses = forced[:n]
    while len(statuses) < n:
        statuses.append(c.rng.choice(pool) if mode != "min" else "pending")
    if not forced and "done" not in statuses:
        statuses[0] = "done"
    use_title = has("title")
    words = {"done": ["done", "finished", "completed"], "active": ["in progress", "running now", "underway"],
             "pending": ["not started", "still to do", "pending"], "error": ["failed", "errored out", "blocked by an error"],
             "skipped": ["skipped", "dropped", "not needed"]}
    lines = [f"{t} – {c.pick(words[s])}" for t, s in zip(tasks, statuses)]
    items = [{"title": t, "status": s} for t, s in zip(tasks, statuses)]
    obj: dict[str, Any] = {"ui": "plan"}
    if use_title:
        obj["title"] = f"{_fix(c.dom.title)} plan"
    obj["items"] = items
    facts = _s(c, ["Where the work stands:\n", "Status of the tasks:\n", "Current state of the work:\n"]) + "\n".join("- " + l for l in lines)
    ask = _s(c, ["Show it as a plan.", "Track this for me.", "Turn that into a live checklist.", "Give me the plan view."])
    intro = _s(c, ["Here is the plan with each step's status.", "This is the work plan as it stands.", "Here's the plan, step by step."])
    nd, ne = statuses.count("done"), statuses.count("error")
    if ne:
        outro = _s(c, [f"One step failed, so that is the blocker to clear first.", "A failed step is holding things up; fixing it comes first."]) if ne == 1 else \
            "The failed steps are what to clear before moving on."
    elif "active" in statuses:
        outro = _s(c, [f"{c.d(nd)} of {c.d(n)} steps are done and one is in progress.", f"The active step is next to finish; {c.d(nd)} are already done."])
    else:
        outro = _s(c, ["Everything that can run has run; the rest is waiting.", "The remaining steps are queued behind the current state."])
    return Piece(facts, ask, [obj], intro, outro, "work_sequence", [], lang="en")


def progress_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    has = Has(c, mode)
    en = c.lang == "en"
    goals = [("Fundraising goal", 20000, 120000, "usd"), ("Course completion", 3, 40, "lessons"), ("Migration", 200, 4800, "records"),
             ("Storage quota", 12, 480, "GB"), ("Hiring plan", 1, 14, "hires"), ("Sprint scope", 8, 60, "points"),
             ("Onboarding checklist", 2, 12, "steps"), ("Reading list", 3, 30, "books")]
    label, lo, hi, unit = c.pick(goals)
    mx = int(round(c.rng.uniform(lo * 1.5, hi) / 5) * 5) or hi
    mx = max(mx, 10)
    val = int(round(c.rng.uniform(0.1, 0.95) * mx))
    p = c.d(pct(val, mx, 0))
    rest = c.d(fnum(mx - val, 0, c.sep))
    sym = "$" if unit == "usd" else ""
    suf = "" if unit == "usd" else f" {unit}"
    use_label, use_max = has("label"), has("max")
    if mode == "min" or (not use_max and mx != 100):
        # percentage form: value alone, max defaults to 100
        pv = int(round(100 * val / mx))
        pv = max(1, min(99, pv))
        obj: dict[str, Any] = {"ui": "progress", "value": pv}
        if use_label:
            obj["label"] = label
        facts = _s(c, [f"{label} is {pv}% complete.", f"We're at {pv}% on the {label.lower()}."]) if en else f"{label}: {pv}%"
        p = c.d(100 - pv)
        outro = _s(c, [f"That leaves {p} percentage points to go.", f"{p} points remain to reach 100%."]) if en else f"{pv}%."
        if en:
            pass
        ground = [str(pv)]
        intro = _s(c, [f"Here is progress on the {label.lower()}.", f"This is how far along the {label.lower()} is."]) if en else _fr(c, "progress", "intro", label=label)
        ask = _s(c, ["How far along are we?", "Show me the progress."]) if en else _fr(c, "progress", "ask")
        return Piece(facts, ask, [obj], intro, outro, "goal_progress", ground, lang=c.lang)
    obj = {"ui": "progress", "value": val}
    if use_max or True:
        obj["max"] = mx
    if use_label:
        obj["label"] = label
    vs, ms = f"{sym}{fnum(val, 0, c.sep)}{suf}", f"{sym}{fnum(mx, 0, c.sep)}{suf}"
    if en:
        facts = _s(c, [f"{label}: {vs} of {ms} so far.", f"We've reached {vs} out of {ms} on the {label.lower()}.", f"{vs} done, {ms} total ({label.lower()})."])
        ask = _s(c, ["How far along are we?", "How much is left?", "Show me the progress.", "Where are we against the goal?"])
        intro = _s(c, [f"Here is progress toward the {label.lower()}.", f"This is how far the {label.lower()} has come.", f"Progress on the {label.lower()}:"])
        outro = _s(c, [f"We're about {p}% of the way there, with {rest} still to go.", f"That is roughly {p}% complete; {rest} remain."])
    else:
        facts = _fr(c, "progress", "facts", value=vs, max=ms, label=label)
        ask = _fr(c, "progress", "ask")
        intro = _fr(c, "progress", "intro", label=label)
        outro = _fr(c, "progress", "outro", p=p, rest=rest)
    return Piece(facts, ask, [obj], intro, outro, "goal_progress", [str(val), str(mx)], lang=c.lang)


def json_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    has = Has(c, mode)
    rng = c.rng
    title, items = gen_entity(c)
    data: dict[str, Any] = {}
    for k, v in items[:rng.randint(3, 5)]:
        data[re.sub(r"[^a-z0-9]+", "_", k.lower()).strip("_")] = v
    if rng.random() < 0.7:
        data["tags"] = rng.sample(["beta", "priority", "eu", "renewal", "vip", "trial", "audit"], 2)
    if rng.random() < 0.6:
        data["meta"] = {"version": rng.randint(2, 9), "dry_run": rng.random() < 0.3}
    pretty = json.dumps(data, indent=2, ensure_ascii=False)
    obj: dict[str, Any] = {"ui": "json", "data": data}
    if has("title"):
        obj["title"] = f"{title} payload"
    facts = _s(c, [f"The API returned this:\n{pretty}", f"Response body:\n{pretty}", f"Here's the payload from the webhook:\n{pretty}"])
    ask = _s(c, ["Can you show it as a readable tree?", "Make this explorable.", "Render the raw data so I can expand it.", "Show the structure."])
    intro = _s(c, ["Here is the response as a collapsible tree.", "This is the payload, expandable by key.", "Here's the raw data in a tree view."])
    outro = _s(c, [f"It has {c.d(len(data))} top-level fields; expand any of them to inspect the values.", f"The payload carries {c.d(len(data))} top-level keys, all shown above."])
    return Piece(facts, ask, [obj], intro, outro, "entity_facts", [], lang="en")


# ----------------------------------------------------------------------------------------------
# content: callout, code, markdown, quote, sources, badges, divider
# ----------------------------------------------------------------------------------------------

def callout_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    has = Has(c, mode)
    level = force.get("level") or c.pick(["info", "success", "warning", "error"])
    m = c.metric()
    v = m.gen(c.rng)
    thr = m.show(round(v * c.rng.uniform(0.7, 0.9), m.dec) if m.dec else round(v * c.rng.uniform(0.7, 0.9)), c.sep)
    vs = m.show(v, c.sep)
    task = c.pick(["nightly sync", "data export", "import job", "backup", "report refresh", "migration"])
    n = c.rng.randint(2, 9)
    task_t = c.pick(c.dom.tasks).lower()
    T = {
        "info": ([f"Note for the team: {m.label} is recalculated every {n} hours, so today's figure is provisional.",
                  f"Heads up that the {task} runs every {n} hours; numbers can lag in between."],
                 f"{_fix(m.label)} is recalculated every {n} hours, so today's figure is provisional.", "Good to know before you read the dashboard.", "tip"),
        "success": ([f"The {task} just finished and {m.label} is now {vs}, under the {thr} limit.", f"{_fix(task)} completed; {m.label} came back to {vs} (limit {thr})."],
                    f"The {task} finished and {m.label} is back to {vs}, within the {thr} limit.", "Nothing else needs doing on this one.", "outcome"),
        "warning": ([f"{_fix(m.label)} hit {vs}, above the {thr} threshold; it needs attention before Friday.", f"Warn the user: {m.label} is at {vs} and the limit is {thr}."],
                    f"{_fix(m.label)} is at {vs}, above the {thr} threshold. Review it before Friday.", "Acting early avoids a breach.", "risk"),
        "error": ([f"The {task} failed after {n} retries, so {m.label} could not be read.", f"{_fix(task)} errored out ({n} retries used); no {m.label} reading is available."],
                  f"The {task} failed after {n} retries, so {m.label} could not be read.", "The last good value is still shown elsewhere until it recovers.", "failure"),
    }[level]
    user_opts, text, outro_en, _ = T[0], T[1], T[2], T[3]
    explicit = c.rng.random() < 0.4
    facts = c.pick(user_opts)
    ask = _s(c, [f"Show the user a {level} notice.", "Write that up as a message for the customer.", "Flag it clearly in the chat."]) if explicit else \
        _s(c, ["Tell the user.", "How do we word this for the customer?", "Let them know in the app."])
    obj: dict[str, Any] = {"ui": "callout", "text": text}
    if has("level") or level != "info" or force.get("level"):
        obj["level"] = level
    if has("title"):
        obj["title"] = {"info": "Good to know", "success": "All set", "warning": "Needs attention", "error": "Something went wrong"}[level]
    intro = {"info": "Here is the note, worded for the customer.", "success": "Good news, so I'll mark it as a success.",
             "warning": "This one deserves a visible warning.", "error": "I'll flag it as an error so it stands out."}[level]
    outro = {"info": "It sets expectations about when numbers refresh.", "success": "No follow-up is required from the customer.",
             "warning": "Acting before the deadline keeps the metric inside its limit.", "error": "Retrying later or checking the job logs is the next step."}[level]
    ground = []
    return Piece(facts, ask, [obj], intro, outro, "note", ground, lang="en")


SNIPS = [
    ("bash", None, "git log --oneline -n 10", "What's the git command to see the last 10 commits, one per line?", "Here is the command.", "It prints each commit as a short hash and its subject."),
    ("python", "env.py", 'import os\n\napi_key = os.environ["API_KEY"]\nregion = os.environ.get("REGION", "eu-west-1")', "How do I read an env var in Python, with a default?", "Here is how to read environment variables in Python.", "`os.environ[...]` raises if the key is missing, while `.get` falls back to the default."),
    ("go", "main.go", 'package main\n\nimport (\n\t"fmt"\n\t"os"\n)\n\nfunc main() {\n\tfmt.Println(os.Getenv("API_KEY"))\n}', "Show me a minimal Go program that prints an env var called API_KEY.", "Here is a minimal Go program.", "`os.Getenv` returns an empty string when the variable is unset."),
    ("javascript", None, 'const key = process.env.API_KEY;\nif (!key) throw new Error("API_KEY is not set");', "Node: how do I read an env var and fail fast when it's missing?", "Here is the Node.js version.", "Failing at startup is easier to debug than a null key later."),
    ("sql", "monthly_orders.sql", "SELECT status, COUNT(*) AS n\nFROM orders\nWHERE created_at >= date_trunc('month', now())\nGROUP BY status\nORDER BY n DESC;", "Write SQL that counts this month's orders by status.", "Here is the query.", "It groups this month's orders by status and sorts the biggest group first."),
    ("yaml", ".github/workflows/ci.yml", "name: ci\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - run: npm ci && npm test", "Give me a minimal GitHub Actions workflow that runs npm tests on every push.", "Here is a minimal workflow.", "It checks out the repo, installs dependencies and runs the tests on each push."),
    ("dockerfile", "Dockerfile", "FROM python:3.12-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY . .\nCMD [\"python\", \"main.py\"]", "I need a Dockerfile for a small Python service.", "Here is a compact Dockerfile.", "Copying requirements first lets Docker cache the dependency layer."),
    ("json", "settings.json", '{"retries":3,"timeout_ms":5000,"verbose":false}', "What would a settings.json with retries, a timeout and a verbose flag look like?", "Here is a sample config.", "Adjust the values to your environment."),
    ("typescript", "types.ts", "interface Order {\n  id: string;\n  total: number;\n  status: \"open\" | \"paid\" | \"refunded\";\n}", "Define a TypeScript interface for an order with id, total and a status union.", "Here is the interface.", "The status union rejects any value outside the three allowed strings."),
    ("rust", "main.rs", 'use std::env;\n\nfn main() {\n    let key = env::var("API_KEY").unwrap_or_default();\n    println!("{key}");\n}', "How do I read an env var in Rust?", "Here is the Rust version.", "`env::var` returns a Result, so `unwrap_or_default` covers the unset case."),
    ("bash", None, "docker run --rm -p 8080:80 -v \"$PWD\":/usr/share/nginx/html:ro nginx:alpine", "One-liner to serve the current folder with nginx in Docker?", "Here is the command.", "The folder is mounted read-only, and the site is reachable on port 8080."),
    ("python", "fetch.py", "import requests\n\nresp = requests.get(url, timeout=10)\nresp.raise_for_status()\ndata = resp.json()", "How do I make a GET request in Python with a timeout and error check?", "Here is the pattern with requests.", "`raise_for_status` turns HTTP errors into exceptions you can catch."),
    ("nginx", "site.conf", "server {\n  listen 80;\n  server_name example.com;\n  location / {\n    proxy_pass http://127.0.0.1:3000;\n  }\n}", "Nginx config to proxy example.com to a local app on port 3000?", "Here is the server block.", "Requests to the domain are forwarded to the local app."),
    ("css", "button.css", ".btn {\n  padding: 0.5rem 1rem;\n  border-radius: 8px;\n  background: #4f46e5;\n  color: #fff;\n}", "Give me CSS for a rounded indigo button.", "Here is the style.", "Tweak the padding and radius to match your design system."),
    ("powershell", None, "Get-ChildItem -Recurse -Filter *.log | Where-Object Length -gt 1MB", "PowerShell: find log files bigger than 1 MB under the current folder.", "Here is the command.", "It recurses through subfolders and keeps only files over 1 MB."),
    ("java", "Config.java", 'String key = System.getenv("API_KEY");\nif (key == null) {\n    throw new IllegalStateException("API_KEY missing");\n}', "Java: read API_KEY from the environment and fail if it's absent.", "Here is the Java snippet.", "It fails fast with a clear message when the variable is not set."),
    ("ruby", None, 'key = ENV.fetch("API_KEY")', "Ruby way to read a required env var?", "Here is the Ruby version.", "`ENV.fetch` raises a KeyError if the variable is missing."),
    ("php", None, "<?php\n$key = getenv('API_KEY');", "How do I read an env var in PHP?", "Here is the PHP version.", "`getenv` returns false when the variable is not defined."),
    ("csharp", "Program.cs", 'var key = Environment.GetEnvironmentVariable("API_KEY");', "C#: read an environment variable called API_KEY.", "Here is the C# line.", "It returns null if the variable is not defined."),
    ("python", "models.py", "from dataclasses import dataclass\n\n@dataclass\nclass Order:\n    id: str\n    total: float\n    paid: bool = False", "Python dataclass for an order with id, total and a paid flag?", "Here is the dataclass.", "`paid` defaults to False, so only id and total are required."),
    ("bash", None, "tar -czf backup.tar.gz ./data && ls -lh backup.tar.gz", "Command to compress the data folder into a tar.gz and show its size?", "Here is the command.", "The `&&` makes sure the size is printed only if the archive was created."),
    ("toml", "pyproject.toml", '[project]\nname = "my-service"\nversion = "0.1.0"\nrequires-python = ">=3.10"\ndependencies = ["httpx"]', "Minimal pyproject.toml for a small service that needs httpx?", "Here is a minimal project file.", "Add more dependencies to the list as the service grows."),
    ("kotlin", "Main.kt", 'fun main() {\n    val key = System.getenv("API_KEY") ?: "missing"\n    println(key)\n}', "Kotlin: print an env var, with a fallback string.", "Here is the Kotlin version.", "The Elvis operator supplies the fallback when the variable is unset."),
    ("swift", None, 'let key = ProcessInfo.processInfo.environment["API_KEY"] ?? ""', "Swift: read an environment variable safely.", "Here is the Swift line.", "The nil-coalescing operator gives an empty string when it is unset."),
    ("c", "env.c", '#include <stdio.h>\n#include <stdlib.h>\n\nint main(void) {\n    const char *key = getenv("API_KEY");\n    printf("%s\\n", key ? key : "(unset)");\n    return 0;\n}', "C program that prints API_KEY or (unset)?", "Here is the C program.", "`getenv` returns NULL when the variable is missing, so the ternary guards it."),
    ("html", "button.html", '<button type="button" class="btn">Save</button>', "I want to see the HTML for a plain Save button.", "Here is the snippet.", "It is shown as code only; nothing here is rendered as markup.", True),
]


def code_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    has = Has(c, mode)
    pool = [s for s in SNIPS if len(s) < 7] if not force.get("allow_html") else SNIPS
    s = force.get("snip") or c.pick(pool)
    lang, fname, code, ask, intro, outro = s[:6]
    html = len(s) > 6
    obj: dict[str, Any] = {"ui": "code", "code": code}
    if has("language") or True:
        obj["language"] = lang
    if fname and has("filename"):
        obj["filename"] = fname
    return Piece("", ask, [obj], intro, outro, "code", [], html_code=html, lang="en")


def markdown_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    tasks = c.rng.sample(c.dom.tasks, min(len(c.dom.tasks), c.rng.randint(3, 4)))
    heading = _s(c, ["Next steps", "Checklist", "What happens next", "Handover notes"])
    lines = "\n".join(f"- **{t.split(' ')[0]}** {' '.join(t.split(' ')[1:])}" for t in tasks)
    text = f"### {heading}\n{lines}"
    facts = f"The {len(tasks)} steps are: " + "; ".join(t.lower() for t in tasks) + "."
    ask = _s(c, ["Write it up as a short formatted note with bold verbs.", "Format that as a brief note with a heading and bullets.", "Turn that into a tidy note."])
    intro = "Here is the note, formatted with a heading and bold lead words."
    outro = _s(c, ["The order of the bullets matches the order of the work.", "Paste it as-is into the handover thread."])
    return Piece(facts, ask, [{"ui": "markdown", "text": text}], intro, outro, "no_component" if False else "work_sequence", [], lang="en")


_QUOTES = ["The new dashboard saved me an hour a day.", "Setup took ten minutes and nothing broke.", "Support answered before I finished my coffee.",
           "We stopped arguing about the numbers once everyone saw the same chart.", "It is the first tool our whole team actually opens.",
           "Onboarding felt like a conversation, not a manual.", "I trust the alerts now, and that changed how we work.", "Finally, reports that explain themselves."]


def quote_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    has = Has(c, mode)
    text = c.pick(_QUOTES)
    author = c.person()
    role = c.pick(["Ops lead", "CFO", "Head of Support", "Founder", "Data analyst", "Product manager"])
    source = c.pick(["customer survey", "support interview", "annual review call", "community forum post", "onboarding feedback"])
    use_a, use_s = has("author"), has("source")
    obj: dict[str, Any] = {"ui": "quote", "text": text}
    uparts = f'"{text}"'
    if use_a:
        obj["author"] = f"{author}, {role}"
        uparts += f" — {author}, {role}"
    if use_s:
        obj["source"] = source.capitalize()
        uparts += f" ({source})"
    facts = _s(c, [f"A customer said: {uparts}", f"Feedback received: {uparts}", f"Pull quote from our files: {uparts}"])
    ask = _s(c, ["Show it as a quote for the landing page.", "Display that quote properly.", "Highlight it as a testimonial."])
    intro = _s(c, ["Here is the feedback as a quote.", "This is the testimonial, attributed as given."])
    outro = _s(c, ["Quotes like this work best next to the feature they praise.", "Short, specific praise like this tends to carry the most weight."])
    return Piece(facts, ask, [obj], intro, outro, "citing_sources", [], lang="en")


def sources_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    has = Has(c, mode)
    n = c.rng.randint(2, 4)
    titles = c.rng.sample(["Pricing overview", "Release notes", "Security whitepaper", "Benchmark report", "Customer case study", "Annual review",
                           "Getting started guide", "Compliance handbook", "Roadmap summary"], n)
    use_snip = has("snippet")
    items, lines = [], []
    for t in titles:
        url = gen_url(c, "page")
        it: dict[str, Any] = {"title": t, "url": url}
        ln = f"{t} – {url}"
        if use_snip:
            sn = c.pick(["covers the main changes", "explains the controls in plain language", "has the latest figures", "walks through the setup"])
            it["snippet"] = sn[0].upper() + sn[1:] + "."
            ln += f" ({sn})"
        items.append(it)
        lines.append(ln)
    facts = _s(c, ["I pulled these pages while researching:\n", "Sources I have:\n", "These are the references:\n"]) + "\n".join("- " + l for l in lines)
    ask = _s(c, ["Cite them in the answer.", "List them as sources.", "Show the references I can click."])
    obj = {"ui": "sources", "items": items}
    intro = _s(c, ["Here are the sources behind the answer.", "These are the references, in the order you gave them."])
    outro = _s(c, [f"Each of the {c.d(n)} links points to the page you shared.", "Only the pages you provided are cited."])
    return Piece(facts, ask, [obj], intro, outro, "citing_sources", [it["url"] for it in items], lang="en")


_BADGE_WORDS = {"gray": ["Draft", "Archived", "Unassigned"], "accent": ["Featured", "New", "Recommended"], "green": ["Stable", "Approved", "Healthy"],
                "amber": ["Beta", "Pending review", "At risk"], "red": ["Deprecated", "Blocked", "Overdue"], "blue": ["Internal", "In progress", "EU only"],
                "violet": ["Premium", "Experimental", "Staff pick"]}
_COLOR_PHRASE = {"gray": "gray", "accent": "accent colour", "green": "green", "amber": "amber", "red": "red", "blue": "blue", "violet": "violet"}


def badges_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    has = Has(c, mode)
    colors = list(force.get("colors") or c.sample(list(_BADGE_WORDS), c.rng.randint(2, 4)))
    items, parts = [], []
    for col in colors:
        lab = c.pick(_BADGE_WORDS[col])
        if has("color") or force.get("colors"):
            items.append({"label": lab, "color": col})
            parts.append(f"{lab} ({_COLOR_PHRASE[col]})")
        else:
            items.append({"label": lab})
            parts.append(lab)
    facts = _s(c, ["Label the release with: ", "Tags for this item: ", "Add these labels: "]) + ", ".join(parts) + "."
    ask = _s(c, ["Show them as small badges.", "Render them as tags.", "Make them pills I can see at a glance."])
    obj = {"ui": "badges", "items": items}
    intro = "Here are the labels as badges."
    outro = _s(c, ["Colours follow the ones you specified.", "They read at a glance when placed next to the title."]) if any("color" in i for i in items) else "They stay neutral because no colours were requested."
    return Piece(facts, ask, [obj], intro, outro, "note", [], lang="en")


def divider_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    has = Has(c, mode)
    lab = c.pick(["Next steps", "Details", "Outlook", "Open questions", "Appendix", "Risks"])
    obj: dict[str, Any] = {"ui": "divider"}
    if has("label") or mode != "min":
        obj["label"] = lab
    facts = _s(c, [f"Add a section break labelled \"{lab}\" before the next part.", f"I need a visual divider titled {lab} between sections."]) \
        if "label" in obj else _s(c, ["Add a plain section break before the next part.", "Insert an unlabelled divider between the two sections."])
    ask = ""
    intro = "Here is the section break."
    outro = f"The next section starts under \"{lab}\"." if "label" in obj else "The next section starts below the line."
    return Piece(facts, ask, [obj], intro, outro, "note", [], lang="en")
