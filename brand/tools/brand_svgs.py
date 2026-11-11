"""Generate every shipped DyUI brand asset from one mark definition.

    python brand/tools/brand_svgs.py                      # all SVGs (+ the favicon copy in web/public)
    node brand/tools/render.cjs brand/tools/render-jobs.json   # the PNGs (social cards, app icons)

Needs `fonttools` + `brotli` (woff2) and the fonts from `web/node_modules` (`cd web && npm install`,
or point DYUI_NODE_MODULES at any node_modules that has the three @fontsource packages).
The PNG step needs `playwright` resolvable by node (NODE_PATH or a local install).

The mark — "Typing → Card": the typing indicator's dots, then the reply arriving as an
interface card (its one tight corner is the chat-bubble convention). Drawn on a 100×100
grid, monochrome-first; indigo is the identity colour, the indigo→teal pairing is only a
secondary treatment (the two chart series in the hero).

Nothing in brand/ is hand-edited: change this file (or brandkit.py) and re-run.
Proposed changes to the mark itself live in proposals.py → brand/proposals/ and are not applied here.
"""
from __future__ import annotations

import json
import os

import textpath

from brandkit import (BRAND, INDIGO, INK, MONO, ROOT, SANS, SERIF, SERIF_I, THEMES, Mark, app_icon_svg, circ,
                      favicon_svg, lockup_parts, lockup_svg, n, rrect, square_svg, stacked_svg, svg, text,
                      text_width, write)

# ------------------------------------------------------------------ the mark (100×100 grid)
# dots: r=9 at x=11 and x=35 (gap 6 — round-to-round reads wider, so it's set tighter than
# the 8-unit dot→card gap); card: 46×50 at (52,25), radii 14 except a 4 bottom-left corner.
# Tight box: x 2..98, y 25..75. This geometry is shared with web/src/shell/Logo.tsx — do not
# change one without the other.
MARK_D = (
    "M2 50A9 9 0 1 0 20 50A9 9 0 1 0 2 50Z"
    "M26 50A9 9 0 1 0 44 50A9 9 0 1 0 26 50Z"
    "M66 25H84A14 14 0 0 1 98 39V61A14 14 0 0 1 84 75H56A4 4 0 0 1 52 71V39A14 14 0 0 1 66 25Z"
)
MARK = Mark(
    name="Typing → Card",
    d=MARK_D,
    box=(2, 25, 96, 50),
    # the card is ~4/5 of the ink, so the eye centres the mark right of its box middle (50);
    # 52 splits the difference between box centre and centre of mass (65)
    cx=52.0,
    icon_w=64.0,
    # x origin 2: the card's left edge and its top/bottom land on whole pixels at 16 and 32px
    favicon_vb="2 0 100 100",
)


def out(name: str, content: str) -> None:
    write(os.path.join(BRAND, name), content)


# ------------------------------------------------------------------ hero / social scene
def scene(t: dict, uid: str) -> str:
    """A question, then the mark's own sentence at full size: two typing dots → a reply card.

    484×392 local units. The card is drawn in the product's component language (eyebrow,
    serif stat, delta chip, two-series bar chart) and keeps the mark's corner logic: generous
    radii, one tight corner at the bottom-left. Dot size, dot spacing and the dot→card gap are
    the mark's proportions ×1.3.
    """
    p: list[str] = []
    # the user's message (right-aligned, tight corner towards its author)
    q, qs = "How did Q3 go?", 17
    bw = text_width(SANS, q, qs, wght=450) + 38
    p.append(f'<path d="{rrect(484 - bw, 0, bw, 44, 22, 22, 7, 22)}" fill="{t["bubble"]}" stroke="{t["bubble_edge"]}"/>')
    p.append(text(SANS, q, qs, 484 - bw + 19, 28.2, t["text"], wght=450))

    # typing dots → card
    cx0, cy0, cw, ch = 84, 68, 400, 324
    r, mid = 11.7, cy0 + ch / 2
    p.append(f'<path d="{circ(cx0 - 10.4 - r - 31.2, mid, r)}{circ(cx0 - 10.4 - r, mid, r)}" fill="{t["accent"]}"/>')
    p.append(f'<path d="{rrect(cx0, cy0, cw, ch, 30, 30, 30, 8)}" fill="{t["surface"]}" stroke="{t["border"]}" '
             f'filter="url(#shadow-{uid})"/>')

    # card content
    x, y, pad = cx0, cy0, 30
    p.append(text(SANS, "Q3 REVENUE", 12.5, x + pad, y + 47, t["faint"], tracking=0.09, wght=600))
    chip, cs = "+14.2%", 13.5
    chw = text_width(SANS, chip, cs, wght=600) + 22
    p.append(f'<rect x="{n(x + cw - pad - chw)}" y="{n(y + 29)}" width="{n(chw)}" height="27" rx="13.5" '
             f'fill="{t["teal"]}" opacity="0.14"/>')
    p.append(text(SANS, chip, cs, x + cw - pad - chw + 11, y + 47.3, t["teal"], wght=600))
    num = "$2.84M"
    p.append(text(SERIF, num, 58, x + pad - 1, y + 117, t["text"], tracking=-0.015))
    nw = text_width(SERIF, num, 58, tracking=-0.015)
    p.append(text(SANS, "vs $2.49M in Q2", 15, x + pad + nw + 14, y + 117, t["muted"], wght=450))

    # chart: Q2 (indigo) and Q3 (teal) by region
    top, base = y + 152, y + 268
    for i in range(3):
        gy = base - i * (base - top) / 2
        p.append(f'<path d="M{n(x + pad)} {n(gy + 0.5)}H{n(x + cw - pad)}" stroke="{t["border"]}"/>')
    data = [("NA", 1620, 1710), ("EMEA", 1180, 1460), ("APAC", 980, 1090), ("LATAM", 450, 560)]
    gw, bar, gap = (cw - 2 * pad) / len(data), 25, 4
    for i, (label, a, b) in enumerate(data):
        gx = x + pad + i * gw + (gw - 2 * bar - gap) / 2
        for j, (v, col) in enumerate(((a, t["accent"]), (b, t["teal"]))):
            h = v / 1800 * (base - top)
            p.append(f'<path d="{rrect(gx + j * (bar + gap), base - h, bar, h, 5, 5, 0, 0)}" fill="{col}"/>')
        p.append(text(SANS, label, 12.5, x + pad + i * gw + gw / 2, y + 291, t["faint"], anchor="middle", wght=500))
    return "\n    ".join(p)


def banner(t: dict, W: int, H: int, *, radius: float, left: float, lock_y: float, lock_size: float,
           head: float, head_y: float, sub: float, pill_y: float, scene_xy: tuple[float, float]) -> str:
    """Hero / social card: lockup, tagline, one line of what it is, the install command — and the scene."""
    uid = f'{t["name"]}{W}'
    textpath.PRECISION = 1
    sx, sy = scene_xy
    lock, _, _, _ = lockup_parts(MARK, t, lock_size)

    lead = head * 1.04
    l1 = text(SERIF, "Chatbots that answer", head, left - head * 0.03, head_y, t["text"], tracking=-0.018)
    in_w = text_width(SERIF, "in ", head, tracking=-0.018) + head * 0.02
    l2a = text(SERIF, "in", head, left, head_y + lead, t["text"], tracking=-0.018)
    l2b = text(SERIF_I, "interfaces.", head, left + in_w, head_y + lead, t["accent"], tracking=-0.012)

    sub_y = head_y + lead + sub * 2.3
    s1 = text(SANS, "The Python framework for chatbots whose replies", sub, left, sub_y, t["muted"], wght=430)
    s2 = text(SANS, "arrive as tables, charts, cards and forms.", sub, left, sub_y + sub * 1.5, t["muted"], wght=430)

    ms = sub * 0.8
    cmd_w = text_width(MONO, "pip install dyui", ms, wght=450)
    ph = ms * 2.75
    pill = (f'<rect x="{n(left + 0.5)}" y="{n(pill_y + 0.5)}" width="{n(cmd_w + ms * 3.5)}" height="{n(ph)}" '
            f'rx="{n(ph / 2)}" fill="{t["surface"]}" stroke="{t["border_strong"]}"/>\n  '
            + text(MONO, "$", ms, left + ms * 1.15, pill_y + ph / 2 + ms * 0.34, t["faint"], wght=450) + "\n  "
            + text(MONO, "pip install dyui", ms, left + ms * 2.35, pill_y + ph / 2 + ms * 0.34, t["text"], wght=450))

    frame = (f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="{radius}" fill="{t["bg"]}" stroke="{t["border"]}"/>'
             if radius else f'<rect width="{W}" height="{H}" fill="{t["bg"]}"/>')
    # one quiet wash of dye behind the card — a plain radial gradient, no blur filter
    wx, wy = sx + 284, sy + 230
    body = f'''<defs>
  <radialGradient id="wash-{uid}" cx="{n(wx)}" cy="{n(wy)}" r="{n(H * 0.82)}" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="{t["accent"]}" stop-opacity="{t["wash"]}"/>
    <stop offset="0.55" stop-color="{t["accent"]}" stop-opacity="{float(t["wash"]) * 0.32:.3f}"/>
    <stop offset="1" stop-color="{t["accent"]}" stop-opacity="0"/></radialGradient>
  <filter id="shadow-{uid}" x="-15%" y="-15%" width="130%" height="145%">
    <feDropShadow dx="0" dy="14" stdDeviation="20" flood-color="{t["shadow_color"]}" flood-opacity="{t["shadow"]}"/></filter>
  <clipPath id="clip-{uid}"><rect width="{W}" height="{H}" rx="{radius}"/></clipPath>
</defs>
<g clip-path="url(#clip-{uid})">
  {frame}
  <rect width="{W}" height="{H}" fill="url(#wash-{uid})"/>
  <g transform="translate({n(left - 2)} {n(lock_y)})">
{lock}
  </g>
  {l1}
  {l2a}
  {l2b}
  {s1}
  {s2}
  {pill}
  <g transform="translate({n(sx)} {n(sy)})">
    {scene(t, uid)}
  </g>
</g>'''
    textpath.PRECISION = 2
    return svg(W, H, body, "DyUI — Chatbots that answer in interfaces.")


def main() -> None:
    light, dark = THEMES["light"], THEMES["dark"]

    # ---------- marks
    out("logo.svg", square_svg(MARK, INDIGO))
    out("mark-mono.svg", square_svg(MARK, INK))
    out("mark-white.svg", square_svg(MARK, "#FFFFFF"))

    # ---------- favicon (the same file is served by the app and the docs site)
    fav = favicon_svg(MARK)
    out("favicon.svg", fav)
    write(os.path.join(ROOT, "web", "public", "favicon.svg"), fav)
    # docs/public/favicon.svg is copied from brand/favicon.svg by docs/scripts/prebuild.mjs

    # ---------- app icons
    out("app-icon-light.svg", app_icon_svg(MARK, False))
    out("app-icon-dark.svg", app_icon_svg(MARK, True))
    out("app-icon-maskable.svg", app_icon_svg(MARK, False, maskable=True))

    # ---------- lockups (wordmark*.svg is the horizontal lockup; the docs site uses it as its logo)
    out("wordmark.svg", lockup_svg(MARK, light))
    out("wordmark-dark.svg", lockup_svg(MARK, dark))
    out("lockup-stacked.svg", stacked_svg(MARK, light))
    out("lockup-stacked-dark.svg", stacked_svg(MARK, dark))

    # ---------- README hero (shown at ~900px wide on GitHub) and social card (1200×630)
    for t in (light, dark):
        out(f'readme-hero-{t["name"]}.svg',
            banner(t, 1280, 520, radius=28, left=84, lock_y=58, lock_size=38, head=77, head_y=232,
                   sub=20.5, pill_y=424, scene_xy=(712, 64)))
        out(f'social-card-{t["name"]}.svg',
            banner(t, 1200, 630, radius=0, left=76, lock_y=74, lock_size=42, head=74, head_y=286,
                   sub=21, pill_y=506, scene_xy=(652, 119)))

    # ---------- shortlisted alternates from the v1 exploration (kept for reference)
    alternates = {
        "typing-card.svg": MARK_D,
        "switch-bubble.svg": ("M32 20H68A26 26 0 0 1 68 72H42C38 82 28 89 14 92C19 85 19 76 13.6 64.4A26 26 0 0 1 32 20Z"
                              "M52 46A16 16 0 1 0 84 46A16 16 0 1 0 52 46Z"),
        "d-bubble.svg": ("M12 22A12 12 0 0 1 24 10H52A40 40 0 0 1 52 90H34Q22 92 12 100Z"
                         "M44 30H55A9 9 0 0 1 64 39V61A9 9 0 0 1 55 70H44A9 9 0 0 1 35 61V39A9 9 0 0 1 44 30Z"),
    }
    for fn, d in alternates.items():
        out(os.path.join("alternates", fn),
            svg(100, 100, f'  <path d="{d}" fill="{INDIGO}" fill-rule="evenodd"/>'))

    # ---------- PNG jobs for render.cjs (paths relative to brand/tools/)
    jobs = [
        {"src": "../social-card-light.svg", "out": "../social-card-light.png", "width": 1200, "height": 630},
        {"src": "../social-card-dark.svg", "out": "../social-card-dark.png", "width": 1200, "height": 630},
        {"src": "../app-icon-light.svg", "out": "../png/app-icon-512.png", "width": 512, "height": 512},
        {"src": "../app-icon-light.svg", "out": "../png/app-icon-192.png", "width": 192, "height": 192},
        {"src": "../app-icon-maskable.svg", "out": "../png/app-icon-maskable-512.png", "width": 512, "height": 512},
    ]
    write(os.path.join(BRAND, "tools", "render-jobs.json"), json.dumps(jobs, indent=2) + "\n")
    print("generated brand SVGs in", BRAND)


if __name__ == "__main__":
    main()
