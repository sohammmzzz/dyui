"""DyUI logo exploration v1 — candidate marks on a 100x100 grid + contact boards.

Usage:  python explore.py <out_dir> [ids...]
Writes <out_dir>/<id>.svg (mark, currentColor) and <out_dir>/board-<id>.html, plus index.html.
Render boards to PNG with shoot.mjs (Playwright).
"""
from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "brand", "tools"))
from textpath import text_path  # noqa: E402

NM = os.path.join(ROOT, "web", "node_modules")
SERIF = os.path.join(NM, "@fontsource/instrument-serif/files/instrument-serif-latin-400-normal.woff2")

INDIGO, INDIGO_D = "#5B4FE0", "#8B80FF"
TEAL, TEAL_D = "#14A394", "#3DD6C3"
INK, PAPER, MIDNIGHT = "#1A1A1F", "#F7F6F3", "#0B0C10"


# ------------------------------------------------------------------ geometry helpers
def f(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s if s != "-0" else "0"


def rr(x: float, y: float, w: float, h: float, r: float | tuple) -> str:
    """Rounded rect path; r may be a 4-tuple (tl, tr, br, bl)."""
    tl, tr, br, bl = r if isinstance(r, tuple) else (r, r, r, r)
    p = [f"M{f(x + tl)} {f(y)}", f"H{f(x + w - tr)}"]
    if tr: p.append(f"A{f(tr)} {f(tr)} 0 0 1 {f(x + w)} {f(y + tr)}")
    p.append(f"V{f(y + h - br)}")
    if br: p.append(f"A{f(br)} {f(br)} 0 0 1 {f(x + w - br)} {f(y + h)}")
    p.append(f"H{f(x + bl)}")
    if bl: p.append(f"A{f(bl)} {f(bl)} 0 0 1 {f(x)} {f(y + h - bl)}")
    p.append(f"V{f(y + tl)}")
    if tl: p.append(f"A{f(tl)} {f(tl)} 0 0 1 {f(x + tl)} {f(y)}")
    return " ".join(p) + "Z"


def circle(cx: float, cy: float, r: float) -> str:
    return (f"M{f(cx - r)} {f(cy)}A{f(r)} {f(r)} 0 1 0 {f(cx + r)} {f(cy)}"
            f"A{f(r)} {f(r)} 0 1 0 {f(cx - r)} {f(cy)}Z")


def path(d: str, rule: str = "nonzero") -> str:
    return f'<path d="{d}" fill="currentColor" fill-rule="{rule}"/>'


# ------------------------------------------------------------------ candidates
# Each returns (title, idea, svg-inner) drawn in currentColor on a 0..100 grid.
def c_typing():
    # the "…" typing indicator resolves into an interface card
    return ("Typing → Card", "The typing indicator's last dot resolves into a UI card.",
            path(circle(13, 50, 8.5) + circle(36, 50, 8.5) + rr(52, 27, 46, 46, 13)))


def c_grow():
    # three steps on a rising diagonal: dot → bubble → card
    return ("Rising reply", "A dot grows into a bubble, then a card — a reply becoming an interface.",
            path(circle(15, 80, 9) + rr(30, 46, 26, 26, 13) + rr(54, 6, 40, 40, 11)))


def c_window_bubble():
    # chat bubble that is also a split-view window (sidebar | content)
    body = rr(8, 10, 84, 66, 16)
    tail = "M20 70 L14 94 L42 72 Z"
    gap = rr(35, 10, 7, 66, 0)
    return ("Window bubble", "A speech bubble that is also an app window (sidebar | content).",
            path(body + tail, "nonzero") + f'<path d="{gap}" fill="var(--bg)"/>')


def c_prompt():
    # chevron prompt + card:  › ▢
    chev = "M8 30 L30 50 L8 70"
    return ("Prompt → Card", "A prompt chevron followed by the interface it produced.",
            f'<path d="{chev}" fill="none" stroke="currentColor" stroke-width="13" stroke-linecap="round" stroke-linejoin="round"/>'
            + path(rr(44, 22, 54, 56, 14)))


def c_dbubble():
    # D whose bowl is a speech bubble and whose counter is a card (fixed construction:
    # bowl tangent to the stem, tail grows out of the stem's foot)
    outer = "M12 22 A12 12 0 0 1 24 10 H52 A40 40 0 0 1 52 90 H30 L12 100 Z"
    counter = rr(33, 31, 28, 38, 8)
    return ("D-bubble", "The D of DyUI is a speech bubble whose counter is a UI card.",
            path(outer + counter, "evenodd"))


def c_toggle():
    # a chat bubble shaped like a switch, its knob 'on'
    body = rr(6, 22, 88, 50, 25)
    tail = "M22 64 L14 88 L42 70 Z"
    knob = circle(69, 47, 16)
    return ("Switch bubble", "A speech bubble that is a switch turned on — conversation that becomes interactive.",
            path(body + tail + knob, "evenodd"))


def c_unfold():
    # a bubble whose lower-right corner unfolds into a card (two shapes, one moat)
    bubble = rr(6, 6, 52, 44, 22) + "M16 42 L10 60 L32 48 Z"
    card = rr(34, 34, 60, 60, 14)
    moat = rr(29, 29, 70, 70, 19)
    return ("Unfold", "A message bubble that opens into a card in front of it.",
            path(bubble) + f'<path d="{moat}" fill="var(--bg)"/>' + path(card))


def c_caret():
    # text caret that becomes the left edge of a card
    caret = rr(8, 14, 12, 72, 6)
    card = rr(30, 26, 64, 48, 12)
    return ("Caret → Card", "The blinking text caret, and the card it types into existence.",
            path(caret + card))


# ------------------------------------------------------------------ round 2 refinements
def c_typing2():
    # equal dots; the card keeps one tight corner (bottom-left) — the chat-bubble convention
    return ("Typing → Card (r2)", "Typing dots, then the answer arrives as a card — whose tight corner marks it as a message.",
            path(circle(11, 50, 9) + circle(35, 50, 9) + rr(52, 25, 46, 50, (14, 14, 14, 4))))


def c_typing3():
    # accelerating: dots grow toward the card
    return ("Typing → Card, growing (r2)", "The reply gathers momentum: small dot, larger dot, card.",
            path(circle(9, 50, 7) + circle(30, 50, 10) + rr(50, 24, 48, 52, (14, 14, 14, 4))))


def c_toggle2():
    # one continuous outline: pill + curved tail, knob cut out (true transparency)
    outer = ("M32 20 H68 A26 26 0 0 1 68 72 H42 C38 82 28 89 14 92 "
             "C19 85 19 76 13.6 64.4 A26 26 0 0 1 32 20 Z")
    knob = circle(68, 46, 16)
    return ("Switch bubble (r2)", "A speech bubble that is a switch turned on — conversation that becomes interface.",
            path(outer + knob, "evenodd"))


def c_dbubble2():
    outer = "M12 22 A12 12 0 0 1 24 10 H52 A40 40 0 0 1 52 90 H34 Q22 92 12 100 Z"
    counter = rr(35, 30, 29, 40, 9)
    return ("D-bubble (r2)", "The D of DyUI is a speech bubble whose counter is a UI card.",
            path(outer + counter, "evenodd"))


CANDIDATES = {
    "typing2": c_typing2, "typing3": c_typing3, "toggle2": c_toggle2, "dbubble2": c_dbubble2,
    "typing": c_typing, "grow": c_grow, "window": c_window_bubble, "prompt": c_prompt,
    "dbubble": c_dbubble, "toggle": c_toggle, "unfold": c_unfold, "caret": c_caret,
}


# ------------------------------------------------------------------ board
def svg(inner: str, color: str, bg: str, size: int | str = "100%") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="{size}" height="{size}" '
            f'style="color:{color};--bg:{bg}">{inner}</svg>')


def data_uri(inner: str, color: str, bg: str) -> str:
    import base64
    s = svg(inner, color, bg).replace("var(--bg)", bg)
    return "data:image/svg+xml;base64," + base64.b64encode(s.encode()).decode()


def lockup(inner: str, color: str, text: str, bg: str) -> str:
    d, w = text_path(SERIF, "DyUI", 62, x=96, baseline=66, tracking=-0.012)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {96 + w + 8:.0f} 84" height="64" style="--bg:{bg}">'
            f'<g transform="translate(4 6) scale(0.72)" style="color:{color}">{inner}</g>'
            f'<path d="{d}" fill="{text}"/></svg>')


CSS = """
body{margin:0;background:#E9E7E2;font:13px/1.4 'Instrument Sans',system-ui,sans-serif;color:#1A1A1F}
.board{width:1180px;padding:28px;box-sizing:border-box}
h2{margin:0 0 2px;font:400 26px 'Instrument Serif',Georgia,serif}
p.idea{margin:0 0 18px;color:#5F5E66}
.row{display:flex;gap:16px;align-items:stretch;margin-bottom:16px}
.tile{border-radius:14px;display:grid;place-items:center;position:relative}
.tile small{position:absolute;left:10px;top:8px;font-size:11px;opacity:.6}
.paper{background:#F7F6F3}.night{background:#0B0C10;color:#ECECF1}
.big{width:260px;height:260px}.big svg{width:150px;height:150px}
.icon{width:180px;height:180px}
.sizes{display:flex;gap:18px;align-items:center;padding:18px 22px}
canvas.px{width:64px;height:64px;image-rendering:pixelated;border:1px solid rgba(0,0,0,.08)}
.lock{padding:22px 28px;display:flex;align-items:center}
"""

JS = """
for (const c of document.querySelectorAll('canvas.px')) {
  const img = new Image(); img.onload = () => { const x = c.getContext('2d');
    x.fillStyle = c.dataset.bg; x.fillRect(0,0,16,16); x.drawImage(img,0,0,16,16); };
  img.src = c.dataset.src;
}
"""


def board(cid: str) -> str:
    title, idea, inner = CANDIDATES[cid]()
    tile_icon = (f'<svg viewBox="0 0 100 100" width="180" height="180"><defs><linearGradient id="g{cid}" x1="0" y1="0" x2="1" y2="1">'
                 f'<stop offset="0" stop-color="#6E62EC"/><stop offset=".6" stop-color="{INDIGO}"/><stop offset="1" stop-color="{TEAL}"/></linearGradient></defs>'
                 f'<rect width="100" height="100" rx="22" fill="url(#g{cid})"/>'
                 f'<g transform="translate(20 20) scale(.6)" style="color:#fff;--bg:{INDIGO}">{inner}</g></svg>')
    tile_icon_dark = (f'<svg viewBox="0 0 100 100" width="180" height="180"><rect width="100" height="100" rx="22" fill="#14151C" stroke="#24252F"/>'
                      f'<g transform="translate(20 20) scale(.6)" style="color:{INDIGO_D};--bg:#14151C">{inner}</g></svg>')

    def sizes(color, bg, cls):
        uri = data_uri(inner, color, bg)
        return (f'<div class="tile {cls} sizes"><img src="{uri}" width="64" height="64"><img src="{uri}" width="32" height="32">'
                f'<img src="{uri}" width="16" height="16"><canvas class="px" width="16" height="16" data-src="{uri}" data-bg="{bg}"></canvas></div>')

    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body><div class="board" id="board">
<h2>{title} <span style="font-size:14px;color:#8E8C94">· {cid}</span></h2><p class="idea">{idea}</p>
<div class="row">
 <div class="tile paper big"><small>indigo / paper</small>{svg(inner, INDIGO, PAPER)}</div>
 <div class="tile night big"><small>white / midnight</small>{svg(inner, '#FFFFFF', MIDNIGHT)}</div>
 <div class="tile paper big"><small>ink mono</small>{svg(inner, INK, PAPER)}</div>
 <div style="display:flex;flex-direction:column;gap:16px">{tile_icon}</div>
</div>
<div class="row">
 {sizes(INK, PAPER, 'paper')}
 {sizes('#FFFFFF', MIDNIGHT, 'night')}
 {sizes(INDIGO, PAPER, 'paper')}
 {tile_icon_dark.replace('width="180" height="180"', 'width="96" height="96"')}
</div>
<div class="row">
 <div class="tile paper lock">{lockup(inner, INDIGO, INK, PAPER)}</div>
 <div class="tile night lock">{lockup(inner, INDIGO_D, '#ECECF1', MIDNIGHT)}</div>
</div>
</div><script>{JS}</script></body></html>"""


def contact(ids: list[str], pick: str) -> str:
    cols = []
    for cid in ids:
        title, idea, inner = CANDIDATES[cid]()
        uri_ink, uri_white = data_uri(inner, INK, PAPER), data_uri(inner, "#FFFFFF", MIDNIGHT)
        badge = '<span class="pick">recommended</span>' if cid == pick else ""
        cols.append(f"""<div class="col"><h3>{title.replace(' (r2)', '')} {badge}</h3><p class="idea">{idea}</p>
<div class="tile paper sq">{svg(inner, INDIGO, PAPER, 150)}</div>
<div class="tile night sq">{svg(inner, '#FFFFFF', MIDNIGHT, 150)}</div>
<div class="tile paper sizes"><img src="{uri_ink}" width="32" height="32"><img src="{uri_ink}" width="16" height="16">
 <canvas class="px" width="16" height="16" data-src="{uri_ink}" data-bg="{PAPER}"></canvas>
 <svg viewBox="0 0 100 100" width="64" height="64"><rect width="100" height="100" rx="22" fill="{INDIGO}"/><g transform="translate(20 20) scale(.6)" style="color:#fff;--bg:{INDIGO}">{inner}</g></svg></div>
<div class="tile night sizes"><img src="{uri_white}" width="32" height="32"><img src="{uri_white}" width="16" height="16">
 <canvas class="px" width="16" height="16" data-src="{uri_white}" data-bg="{MIDNIGHT}"></canvas></div>
<div class="tile paper lock">{lockup(inner, INDIGO, INK, PAPER)}</div></div>""")
    css = CSS + """.board{width:1180px}.cols{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
.col{display:flex;flex-direction:column;gap:12px}.col h3{margin:0;font:400 24px 'Instrument Serif',Georgia,serif}
.col .idea{margin:0;min-height:38px}.sq{height:220px}.pick{font:600 11px system-ui;letter-spacing:.08em;text-transform:uppercase;
color:#fff;background:#5B4FE0;border-radius:99px;padding:3px 9px;vertical-align:middle}"""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body><div class="board" id="board">
<h2>DyUI mark — v1 shortlist</h2><p class="idea">Theme: dynamic UI — interfaces that arrive in conversation. Monochrome-first, 100×100 grid, indigo #5B4FE0.</p>
<div class="cols">{''.join(cols)}</div></div><script>{JS}</script></body></html>"""


def main() -> None:
    if sys.argv[1] == "--contact":
        out, pick, ids = sys.argv[2], sys.argv[3], sys.argv[4:]
        with open(os.path.join(out, "board-contact.html"), "w", encoding="utf-8") as fh:
            fh.write(contact(ids, pick))
        print("wrote contact")
        return
    out = sys.argv[1]
    ids = sys.argv[2:] or list(CANDIDATES)
    os.makedirs(out, exist_ok=True)
    for cid in ids:
        _, _, inner = CANDIDATES[cid]()
        with open(os.path.join(out, f"{cid}.svg"), "w", encoding="utf-8") as fh:
            fh.write(svg(inner, INDIGO, PAPER).replace("var(--bg)", PAPER))
        with open(os.path.join(out, f"board-{cid}.html"), "w", encoding="utf-8") as fh:
            fh.write(board(cid))
    print("wrote", ", ".join(ids))


if __name__ == "__main__":
    main()
