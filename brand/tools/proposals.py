"""Proposals for the DyUI mark — NOT applied. Writes brand/proposals/.

    python brand/tools/proposals.py                                  # 1. proposal SVGs + px-jobs.json
    node brand/tools/render.cjs brand/proposals/px-jobs.json         # 2. true-size favicon PNGs
    python brand/tools/proposals.py                                  # 3. contact sheet (embeds the PNGs, enlarged)
    node brand/tools/render.cjs brand/proposals/sheet-jobs.json      # 4. contact-sheet.png

Each direction is built with the same rules as the shipped identity (brandkit.py): mark, mono,
white, app icons, favicon, horizontal lockup light/dark. The shipped mark is brand_svgs.MARK
and is shown first on the sheet for comparison. Adopting a direction is described in
brand/proposals/README.md.
"""
from __future__ import annotations

import base64
import json
import os

import textpath

from brand_svgs import MARK as CURRENT
from brandkit import (BRAND, INDIGO, INDIGO_D, INK, MIDNIGHT, PAPER, SANS, SERIF, THEMES, Mark, app_icon_body,
                      app_icon_svg, circ, favicon_svg, lockup_parts, lockup_svg, n, rrect, square_svg, svg, text,
                      write)

OUT = os.path.join(BRAND, "proposals")

# ------------------------------------------------------------------ the three directions (100×100 grid)
# 1 — Refined. Same sentence, tuned. Dots r 9 → 10.5 (they were the first thing to go at 16px);
#     one gap rhythm (5 between dots, 7 to the card, was 6/8); card 46×50 → 42×54 so it reads as a
#     card rather than a square "stop" button; radii 14 with the tight corner 4 → 3.5.
#     On a 6-unit pixel (16px favicon) the card is exactly 7×9 px and the dots 3.5 px.
REFINED = Mark(
    name="Typing → Card, refined",
    d=circ(12.5, 50, 10.5) + circ(38.5, 50, 10.5) + rrect(56, 23, 42, 54, 14, 14, 14, 3.5),
    box=(2, 23, 96, 54), cx=52.5, icon_w=62, favicon_vb="2 -1 96 96",
)

# 2 — Crescendo. The same three elements, but they grow and share a baseline: a small dot, a
#     larger dot, the card. Text (an ellipsis on the line) swells into an interface; the tight
#     corner is where the card touches that line. Card 48×60; dots r 6.5 and r 10.
CRESCENDO = Mark(
    name="Crescendo",
    d=circ(9.5, 73.5, 6.5) + circ(32, 70, 10) + rrect(50, 20, 48, 60, 16, 16, 16, 4),
    box=(3, 20, 95, 60), cx=54.5, cy=50, icon_w=60, favicon_vb="2 2 96 96",
)

# 3 — Cursor d. A different idea: a text cursor standing next to a card makes a lowercase d.
#     The stem is the caret (where text is typed), the bowl is the card (what comes back).
#     Two elements; bowl 55×50 with the tight corner at the foot of the stem.
CURSOR_D = Mark(
    name="Cursor d",
    d=rrect(13, 40, 55, 50, 17, 17, 4, 17) + rrect(73, 10, 15, 80, 7.5),
    box=(13, 10, 75, 80), cx=50.5, cy=50, icon_w=47, lock_k=1.0, favicon_vb="8 10 80 80",
)

DIRECTIONS = [
    ("current", CURRENT, "Current", "shipped",
     ["Two typing dots, then the reply arrives as a", "card. Chosen 2026-11-05; unchanged here."]),
    ("1-refined", REFINED, "1  Refined", "optical refinement",
     ["Same idea. Larger dots, one gap rhythm, a card", "that is taller than wide, a tighter tight corner."]),
    ("2-crescendo", CRESCENDO, "2  Crescendo", "bolder evolution",
     ["The three elements grow along one baseline:", "an ellipsis swelling into an interface."]),
    ("3-cursor-d", CURSOR_D, "3  Cursor d", "alternative concept",
     ["A text cursor beside a card makes a lowercase d:", "what you type, and what comes back."]),
]

SHEET_BG = "#E9E7E1"
CHIP_L, CHIP_D = "#FFFFFF", "#202124"     # browser tab strips, light and dark


def write_direction(slug: str, mark: Mark) -> None:
    d = os.path.join(OUT, slug)
    write(os.path.join(d, "mark.svg"), square_svg(mark, INDIGO))
    write(os.path.join(d, "mark-mono.svg"), square_svg(mark, INK))
    write(os.path.join(d, "mark-white.svg"), square_svg(mark, "#FFFFFF"))
    write(os.path.join(d, "favicon.svg"), favicon_svg(mark))
    write(os.path.join(d, "app-icon-light.svg"), app_icon_svg(mark, False))
    write(os.path.join(d, "app-icon-dark.svg"), app_icon_svg(mark, True))
    write(os.path.join(d, "lockup.svg"), lockup_svg(mark, THEMES["light"]))
    write(os.path.join(d, "lockup-dark.svg"), lockup_svg(mark, THEMES["dark"]))


def favicon_src(slug: str) -> str:
    return "../favicon.svg" if slug == "current" else f"{slug}/favicon.svg"


def px_jobs() -> list[dict]:
    jobs = []
    for slug, *_ in DIRECTIONS:
        for size in (16, 32):
            for scheme, bg in (("light", CHIP_L), ("dark", CHIP_D)):
                jobs.append({"src": favicon_src(slug), "out": f"px/{slug}-{size}-{scheme}.png",
                             "width": size, "height": size, "bg": bg, "scheme": scheme})
    return jobs


def px_image(slug: str, size: int, scheme: str, x: float, y: float, zoom: int) -> str:
    """A rendered favicon PNG, embedded and enlarged with hard pixels (so the sheet shows real rasters)."""
    path = os.path.join(OUT, "px", f"{slug}-{size}-{scheme}.png")
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode()
    s = size * zoom
    return (f'<image x="{n(x)}" y="{n(y)}" width="{s}" height="{s}" style="image-rendering:pixelated" '
            f'href="data:image/png;base64,{b64}"/>')


def panel(x: float, y: float, w: float, h: float, fill: str) -> str:
    return f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" rx="14" fill="{fill}"/>'


def centred(mark: Mark, cx: float, cy: float, w: float, fill: str) -> str:
    """The mark `w` wide (per 96 grid units, so directions compare at one scale), optical centre on (cx, cy)."""
    k = w / 96
    return mark.path(fill, f"translate({n(cx - mark.cx * k)} {n(cy - mark.cy * k)}) scale({k:.4f})")


def caption(s: str, x: float, y: float, dark: bool = False) -> str:
    return text(SANS, s, 10.5, x, y, "#7C7E8C" if dark else "#8E8C94", tracking=0.06, wght=600)


def contact_sheet() -> str:
    CW, GAP, M = 344, 24, 40
    textpath.PRECISION = 1
    W = 2 * M + 4 * CW + 3 * GAP
    p: list[str] = [f'<rect width="{W}" height="1330" fill="{SHEET_BG}"/>']
    p.append(text(SERIF, "DyUI mark — current and three proposed directions", 36, M, 76, INK, tracking=-0.012))
    p.append(text(SANS, "Nothing here is applied. Every column is built by the same rules (brand/tools/brandkit.py): "
                        "100×100 grid, monochrome-first, indigo #5B4FE0 / #8B80FF.", 14, M, 104, "#5F5E66", wght=430))
    light, dark = THEMES["light"], THEMES["dark"]
    for i, (slug, mark, title, tag, lines) in enumerate(DIRECTIONS):
        x = M + i * (CW + GAP)
        p.append(text(SERIF, title, 27, x, 160, INK, tracking=-0.01))
        p.append(text(SANS, tag.upper(), 10.5, x + CW, 158, INDIGO if i == 0 else "#5F5E66", anchor="end",
                      tracking=0.08, wght=600))
        for k, line in enumerate(lines):
            p.append(text(SANS, line, 13, x, 184 + k * 18, "#5F5E66", wght=430))

        # large, on paper and on midnight
        y = 222
        p.append(panel(x, y, CW, 196, PAPER))
        p.append(centred(mark, x + CW / 2, y + 98, 168, INDIGO))
        y = 430
        p.append(panel(x, y, CW, 196, MIDNIGHT))
        p.append(centred(mark, x + CW / 2, y + 98, 168, INDIGO_D))

        # one colour
        y = 638
        hw = (CW - 12) / 2
        p.append(panel(x, y, hw, 92, PAPER))
        p.append(centred(mark, x + hw / 2, y + 46, 72, INK))
        p.append(panel(x + hw + 12, y, hw, 92, MIDNIGHT))
        p.append(centred(mark, x + hw + 12 + hw / 2, y + 46, 72, "#FFFFFF"))

        # app icons + favicon at true size (rendered on whole pixels — view this sheet at 100%)
        y = 742
        p.append(panel(x, y, CW, 118, PAPER))
        for j, dk in enumerate((False, True)):
            p.append(f'<svg x="{x + 18 + j * 78}" y="{y + 18}" width="64" height="64" viewBox="0 0 100 100">'
                     f'{app_icon_body(mark, dk, uid=f"tile-{i}")}</svg>')
        p.append(caption("APP ICON", x + 18, y + 104))
        for j, (scheme, chip) in enumerate((("light", CHIP_L), ("dark", CHIP_D))):
            cx = x + 180 + j * 78
            p.append(f'<rect x="{cx}" y="{y + 18}" width="70" height="64" rx="8" fill="{chip}" '
                     f'stroke="{"#E6E3DC" if j == 0 else chip}"/>')
            p.append(px_image(slug, 32, scheme, cx + 8, y + 34, 1))
            p.append(px_image(slug, 16, scheme, cx + 47, y + 42, 1))
        p.append(caption("FAVICON 32 · 16 PX", x + 180, y + 104))

        # the 16px favicon enlarged ×6, hard pixels
        y = 872
        p.append(panel(x, y, CW, 136, PAPER))
        p.append(f'<rect x="{x + 17.5}" y="{y + 19.5}" width="97" height="97" fill="none" stroke="#E6E3DC"/>')
        p.append(px_image(slug, 16, "light", x + 18, y + 20, 6))
        p.append(px_image(slug, 16, "dark", x + 126, y + 20, 6))
        p.append(caption("16 PX FAVICON", x + 238, y + 34))
        p.append(caption("ENLARGED ×6", x + 238, y + 50))
        p.append(caption("LIGHT · DARK TAB", x + 238, y + 66))

        # lockups
        for j, (t, bg) in enumerate(((light, PAPER), (dark, MIDNIGHT))):
            y = 1020 + j * 108
            p.append(panel(x, y, CW, 96, bg))
            body, lw, lh, _ = lockup_parts(mark, t, 46)
            k = 46 / lh
            p.append(f'<g transform="translate({n(x + CW / 2 - lw * k / 2)} {n(y + 48 - lh * k / 2)}) scale({k:.4f})">'
                     f'{body}</g>')
    p.append(text(SANS, "Rows: mark on paper · on midnight · one colour · app icons and favicon at true size · "
                        "16 px favicon enlarged · horizontal lockup on paper and on midnight.  "
                        "Rationale and what adopting each would change: brand/proposals/README.md",
                  12.5, M, 1272, "#5F5E66", wght=430))
    p.append(text(SANS, "Favicon cells are real 16/32 px renders from Chromium; the rest is vector.",
                  12.5, M, 1292, "#8E8C94", wght=430))
    textpath.PRECISION = 2
    return svg(W, 1330, "\n".join(s for s in p if s), "DyUI mark proposals — contact sheet", px=True)


def main() -> None:
    for slug, mark, *_ in DIRECTIONS[1:]:
        write_direction(slug, mark)
    write(os.path.join(OUT, "px-jobs.json"), json.dumps(px_jobs(), indent=1) + "\n")
    sheet = contact_sheet()
    write(os.path.join(OUT, "contact-sheet.svg"), sheet)
    w = int(sheet.split('width="')[1].split('"')[0])
    write(os.path.join(OUT, "sheet-jobs.json"), json.dumps(
        [{"src": "contact-sheet.svg", "out": "contact-sheet.png", "width": w, "height": 1330, "bg": SHEET_BG}],
        indent=1) + "\n")
    have = os.path.isdir(os.path.join(OUT, "px"))
    print("proposals written to", OUT, "" if have else "(favicon PNGs missing — run px-jobs.json, then re-run)")


if __name__ == "__main__":
    main()
