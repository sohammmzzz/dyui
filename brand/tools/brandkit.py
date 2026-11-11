"""Shared building blocks for the DyUI brand generators (`brand_svgs.py`, `proposals.py`).

Everything that depends on the shape of the mark goes through a `Mark`, so the shipped
identity and any proposed one are built by exactly the same rules (lockup, app icon, favicon).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from textpath import cap_height, text_bounds, text_path  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
BRAND = os.path.join(ROOT, "brand")


def _node_modules() -> str:
    """Fonts come from the @fontsource packages the web app already depends on."""
    tried = []
    for base in (os.environ.get("DYUI_NODE_MODULES"), os.path.join(ROOT, "web", "node_modules"),
                 os.path.join(ROOT, "docs", "node_modules")):
        if not base:
            continue
        tried.append(base)
        if os.path.isdir(os.path.join(base, "@fontsource", "instrument-serif")):
            return base
    sys.exit("brand tools: fonts not found. Run `npm install` in web/ (or set DYUI_NODE_MODULES to a "
             "node_modules that has @fontsource/instrument-serif, @fontsource-variable/instrument-sans and "
             "@fontsource-variable/geist-mono). Looked in: " + ", ".join(tried))


NM = _node_modules()
SERIF = f"{NM}/@fontsource/instrument-serif/files/instrument-serif-latin-400-normal.woff2"
SERIF_I = f"{NM}/@fontsource/instrument-serif/files/instrument-serif-latin-400-italic.woff2"
SANS = f"{NM}/@fontsource-variable/instrument-sans/files/instrument-sans-latin-wght-normal.woff2"
MONO = f"{NM}/@fontsource-variable/geist-mono/files/geist-mono-latin-wght-normal.woff2"

# ---------------------------------------------------------------- colour (web/src/styles/tokens.css)
INDIGO, INDIGO_D = "#5B4FE0", "#8B80FF"
TEAL, TEAL_D = "#14A394", "#3DD6C3"
INK, PAPER, MIDNIGHT = "#1A1A1F", "#F7F6F3", "#0B0C10"

THEMES = {
    "light": dict(name="light", bg=PAPER, subtle="#F1EFEA", surface="#FFFFFF", border="#E6E3DC",
                  border_strong="#D6D2C8", text=INK, muted="#5F5E66", faint="#8E8C94",
                  accent=INDIGO, teal=TEAL, wash="0.16", shadow="0.09", shadow_color="#17153A", bubble="#ECEAFB", bubble_edge="#DDD9F6"),
    "dark": dict(name="dark", bg=MIDNIGHT, subtle="#101117", surface="#14151C", border="#24252F",
                 border_strong="#323442", text="#ECECF1", muted="#A2A3B1", faint="#6B6D7C",
                 accent=INDIGO_D, teal=TEAL_D, wash="0.20", shadow="0.6", shadow_color="#000000", bubble="#1D1C33", bubble_edge="#2C2A4D"),
}

WORD = "DyUI"
WORD_TRACK = -0.012   # em; Instrument Serif at display sizes wants a hair of tightening


# ---------------------------------------------------------------- small geometry helpers
def n(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def circ(cx: float, cy: float, r: float) -> str:
    """A circle as path data (two arcs), so a whole mark can be one <path>."""
    return f"M{n(cx - r)} {n(cy)}A{n(r)} {n(r)} 0 1 0 {n(cx + r)} {n(cy)}A{n(r)} {n(r)} 0 1 0 {n(cx - r)} {n(cy)}Z"


def rrect(x: float, y: float, w: float, h: float, tl: float, tr: float | None = None,
          br: float | None = None, bl: float | None = None) -> str:
    """Rounded rectangle with a radius per corner (top-left, top-right, bottom-right, bottom-left)."""
    tr = tl if tr is None else tr
    br = tl if br is None else br
    bl = tl if bl is None else bl
    return (f"M{n(x + tl)} {n(y)}H{n(x + w - tr)}A{n(tr)} {n(tr)} 0 0 1 {n(x + w)} {n(y + tr)}"
            f"V{n(y + h - br)}A{n(br)} {n(br)} 0 0 1 {n(x + w - br)} {n(y + h)}"
            f"H{n(x + bl)}A{n(bl)} {n(bl)} 0 0 1 {n(x)} {n(y + h - bl)}"
            f"V{n(y + tl)}A{n(tl)} {n(tl)} 0 0 1 {n(x + tl)} {n(y)}Z")


def text(font: str, s: str, size: float, x: float, base: float, fill: str, *, anchor: str = "start",
         tracking: float = 0.0, wght: float | None = None, opacity: float | None = None) -> str:
    """Outlined text as a <path>; anchor is start | middle | end."""
    if anchor != "start":
        w = text_width(font, s, size, tracking=tracking, wght=wght)
        x -= w if anchor == "end" else w / 2
    d, _ = text_path(font, s, size, x=x, baseline=base, tracking=tracking, wght=wght)
    op = f' opacity="{opacity}"' if opacity is not None else ""
    return f'<path d="{d}" fill="{fill}"{op}/>'


def text_width(font: str, s: str, size: float, *, tracking: float = 0.0, wght: float | None = None) -> float:
    return text_path(font, s, size, tracking=tracking, wght=wght)[1] - tracking * size


# ---------------------------------------------------------------- the mark abstraction
@dataclass(frozen=True)
class Mark:
    """A mark on the 100x100 grid.

    box        tight ink bounds (x, y, w, h)
    cx, cy     optical centre: where the eye puts the middle (heavier side pulls it), used to
               centre the mark in tiles and above the wordmark
    icon_w     width of the mark inside a 100-unit app-icon tile (leaves the ~18% safe area)
    lock_k     mark height in the horizontal lockup, as a multiple of the wordmark's cap height
    favicon_vb viewBox for the favicon, chosen so the main edges land on whole pixels at 16/32px
    """
    name: str
    d: str
    box: tuple[float, float, float, float]
    cx: float = 50.0
    cy: float = 50.0
    icon_w: float = 64.0
    lock_k: float = 1.0
    favicon_vb: str = "0 0 100 100"
    evenodd: bool = False

    def path(self, fill: str, transform: str = "") -> str:
        t = f' transform="{transform}"' if transform else ""
        fr = ' fill-rule="evenodd"' if self.evenodd else ""
        return f'<path d="{self.d}" fill="{fill}"{fr}{t}/>'

    def place(self, x: float, y: float, fill: str, *, w: float | None = None, h: float | None = None) -> str:
        """The mark with its tight box at (x, y), scaled to width `w` or height `h`."""
        bx, by, bw, bh = self.box
        k = (w / bw) if w is not None else (h / bh)
        return self.path(fill, f"translate({n(x)} {n(y)}) scale({k:.4f}) translate({n(-bx)} {n(-by)})")

    def size(self, *, w: float | None = None, h: float | None = None) -> tuple[float, float]:
        _, _, bw, bh = self.box
        k = (w / bw) if w is not None else (h / bh)
        return bw * k, bh * k


def svg(w: float, h: float, body: str, label: str | None = "DyUI", *, px: bool = False) -> str:
    aria = f' role="img" aria-label="{label}"' if label else ""
    dims = f' width="{n(w)}" height="{n(h)}"' if px else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg"{dims} viewBox="0 0 {n(w)} {n(h)}" fill="none"{aria}>\n{body}\n</svg>\n'


def write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


# ---------------------------------------------------------------- mark files
def square_svg(mark: Mark, fill: str) -> str:
    return svg(100, 100, "  " + mark.path(fill))


def favicon_svg(mark: Mark) -> str:
    """Bare mark, indigo on light tab strips and lifted indigo on dark ones."""
    fr = ' fill-rule="evenodd"' if mark.evenodd else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{mark.favicon_vb}" fill="none">\n'
            f'  <style>path{{fill:{INDIGO}}}@media (prefers-color-scheme:dark){{path{{fill:{INDIGO_D}}}}}</style>\n'
            f'  <path d="{mark.d}"{fr}/>\n</svg>\n')


def _centred(mark: Mark, fill: str, w: float) -> str:
    """The mark `w` wide with its optical centre on (50, 50) of a 100-unit tile."""
    k = w / mark.box[2]
    return mark.path(fill, f"translate({n(50 - mark.cx * k)} {n(50 - mark.cy * k)}) scale({k:.4f})")


def app_icon_body(mark: Mark, dark: bool, *, maskable: bool = False, uid: str = "dyui-tile") -> str:
    """Rounded tile (rx 22.5%), mark inside the safe area — the contents of a 100×100 viewBox.

    Light: indigo with a quiet top-to-bottom shade (depth, not decoration), white mark.
    Dark: surface tile with a hairline edge, lifted-indigo mark.
    Maskable: full-bleed square; the mark is drawn smaller so it stays inside the 80% circle
    that Android/PWA launchers are allowed to crop to.
    """
    w = mark.icon_w * (0.84 if maskable else 1)
    if dark:
        tile = ('<rect width="100" height="100" fill="#14151C"/>' if maskable else
                '<rect x="0.5" y="0.5" width="99" height="99" rx="22" fill="#14151C" stroke="#2A2B37"/>')
        defs, fill = "", INDIGO_D
    else:
        defs = (f'  <defs><linearGradient id="{uid}" x1="0" y1="0" x2="0" y2="100" gradientUnits="userSpaceOnUse">'
                f'<stop offset="0" stop-color="#6A5EEA"/><stop offset="1" stop-color="#5145D4"/></linearGradient></defs>\n')
        rx = "" if maskable else ' rx="22.5"'
        tile = f'<rect width="100" height="100"{rx} fill="url(#{uid})"/>'
        fill = "#FFFFFF"
    return f'{defs}  {tile}\n  {_centred(mark, fill, w)}'


def app_icon_svg(mark: Mark, dark: bool, *, maskable: bool = False) -> str:
    return svg(100, 100, app_icon_body(mark, dark, maskable=maskable))


# ---------------------------------------------------------------- lockups
def lockup_parts(mark: Mark, t: dict, size: float = 46, *, mark_fill: str | None = None,
                 text_fill: str | None = None) -> tuple[str, float, float, float]:
    """Horizontal lockup: mark + "DyUI" in Instrument Serif.

    The mark stands on the baseline and is as tall as the capitals (x `lock_k`), so its card
    and the D share a top and a bottom line. The gap is half the mark's height — clearly more
    than the mark's own inner gaps, so the mark still reads as one unit. The cap band is
    centred in the box (equal room above the caps and below the baseline), which is what makes
    the lockup sit level next to other things on a line.
    Returns (svg body, width, height, baseline y).
    """
    cap = cap_height(SERIF, size)
    x0, _, x1, y1 = text_bounds(SERIF, WORD, size, tracking=WORD_TRACK)
    mw, mh = mark.size(h=cap * mark.lock_k)
    gap = 0.5 * min(mh, cap * 1.1)
    pad = 2.0
    above = max(y1, mh - cap) + pad          # y1 = depth of the y's descender
    base = above + cap
    height = cap + 2 * above
    tx = pad + mw + gap - x0
    d, _ = text_path(SERIF, WORD, size, x=tx, baseline=base, tracking=WORD_TRACK)
    body = (f'  {mark.place(pad, base - mh, mark_fill or t["accent"], h=mh)}\n'
            f'  <path d="{d}" fill="{text_fill or t["text"]}"/>')
    return body, pad + mw + gap + (x1 - x0) + pad, height, base


def lockup_svg(mark: Mark, t: dict, size: float = 46) -> str:
    body, w, h, _ = lockup_parts(mark, t, size)
    return svg(w, h, body)


def stacked_svg(mark: Mark, t: dict, size: float = 46) -> str:
    """Stacked lockup: the mark above the wordmark, both set to the same width."""
    cap = cap_height(SERIF, size)
    x0, _, x1, y1 = text_bounds(SERIF, WORD, size, tracking=WORD_TRACK)
    tw = x1 - x0
    mw, mh = mark.size(w=tw)
    pad = 4.0
    gap = 0.62 * cap
    base = pad + mh + gap + cap
    d, _ = text_path(SERIF, WORD, size, x=pad - x0, baseline=base, tracking=WORD_TRACK)
    body = f'  {mark.place(pad, pad, t["accent"], w=mw)}\n  <path d="{d}" fill="{t["text"]}"/>'
    return svg(tw + 2 * pad, base + y1 + pad, body)
