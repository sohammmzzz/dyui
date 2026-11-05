"""Generate every DyUI brand SVG from one mark definition.

    python brand/tools/brand_svgs.py

Needs `fonttools` + `brotli` (woff2) and the fonts from `web/node_modules` (`cd web && npm install`).

The mark — "Typing → Card": the typing indicator's dots, then the reply arriving as an
interface card (its one tight corner is the chat-bubble convention). Drawn on a 100×100
grid, monochrome-first; indigo is the identity colour, the indigo→teal gradient is only a
secondary treatment (app icon tile, hero accents).
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from textpath import text_path  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "brand")
NM = os.path.join(ROOT, "web", "node_modules")
SERIF = f"{NM}/@fontsource/instrument-serif/files/instrument-serif-latin-400-normal.woff2"
SERIF_I = f"{NM}/@fontsource/instrument-serif/files/instrument-serif-latin-400-italic.woff2"
SANS = f"{NM}/@fontsource-variable/instrument-sans/files/instrument-sans-latin-wght-normal.woff2"
MONO = f"{NM}/@fontsource-variable/geist-mono/files/geist-mono-latin-wght-normal.woff2"

INDIGO, INDIGO_D = "#5B4FE0", "#8B80FF"
TEAL, TEAL_D = "#14A394", "#3DD6C3"
INK, PAPER, MIDNIGHT = "#1A1A1F", "#F7F6F3", "#0B0C10"

THEMES = {
    "light": dict(bg=PAPER, surface="#FFFFFF", border="#E6E3DC", text=INK, muted="#5F5E66",
                  faint="#8E8C94", accent=INDIGO, teal=TEAL, bloom_op="0.20", card_shadow="0.07"),
    "dark": dict(bg=MIDNIGHT, surface="#14151C", border="#24252F", text="#ECECF1", muted="#A2A3B1",
                 faint="#6B6D7C", accent=INDIGO_D, teal=TEAL_D, bloom_op="0.30", card_shadow="0.5"),
}

# ------------------------------------------------------------------ the mark (100×100 grid)
# dots: r=9 at x=11 and x=35 (gap 6 — round-to-round reads wider, so it's set tighter than
# the 8-unit dot→card gap); card: 46×50 at (52,25), radii 14 except a 4 bottom-left corner.
# Optical box: x 2..98, y 25..75 (centred on 50,50).
MARK_D = (
    "M2 50A9 9 0 1 0 20 50A9 9 0 1 0 2 50Z"
    "M26 50A9 9 0 1 0 44 50A9 9 0 1 0 26 50Z"
    "M66 25H84A14 14 0 0 1 98 39V61A14 14 0 0 1 84 75H56A4 4 0 0 1 52 71V39A14 14 0 0 1 66 25Z"
)
MARK_BOX = (2, 25, 96, 50)  # x, y, w, h — the mark's tight bounds


def mark_path(fill: str, transform: str = "") -> str:
    t = f' transform="{transform}"' if transform else ""
    return f'<path d="{MARK_D}" fill="{fill}"{t}/>'


def mark(x: float, y: float, w: float, fill: str) -> str:
    """The mark placed with its tight box at (x, y), w units wide."""
    bx, by, bw, _ = MARK_BOX
    k = w / bw
    return mark_path(fill, f"translate({x:.2f} {y:.2f}) scale({k:.4f}) translate({-bx} {-by})")


def write(name: str, svg: str) -> None:
    with open(os.path.join(OUT, name), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(svg)


def square(fill: str, label: str = "DyUI") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" fill="none" role="img" aria-label="{label}">\n'
            f'  {mark_path(fill)}\n</svg>\n')


# ---------- marks
write("logo.svg", square(INDIGO))
write("mark-mono.svg", square(INK))
write("mark-white.svg", square("#FFFFFF"))

# favicon: indigo on light tab strips, lifted indigo on dark ones
write("favicon.svg", f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" fill="none">
  <style>path{{fill:{INDIGO}}}@media (prefers-color-scheme:dark){{path{{fill:{INDIGO_D}}}}}</style>
  <path d="{MARK_D}"/>
</svg>
''')

# app icons: rounded tile, mark inside an 18% safe area
def app_icon(dark: bool) -> str:
    if dark:
        tile = f'<rect x="0.5" y="0.5" width="99" height="99" rx="22.5" fill="#14151C" stroke="#24252F"/>'
        fill, defs = INDIGO_D, ""
    else:
        defs = (f'<defs><linearGradient id="dyui-tile" x1="0" y1="0" x2="100" y2="100" gradientUnits="userSpaceOnUse">'
                f'<stop offset="0" stop-color="#6E62EC"/><stop offset="0.62" stop-color="{INDIGO}"/>'
                f'<stop offset="1" stop-color="{TEAL}"/></linearGradient></defs>\n  ')
        tile = '<rect width="100" height="100" rx="22" fill="url(#dyui-tile)"/>'
        fill = "#FFFFFF"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" fill="none" role="img" aria-label="DyUI">\n'
            f'  {defs}{tile}\n  {mark(18, 50 - 64 * MARK_BOX[3] / MARK_BOX[2] / 2, 64, fill)}\n</svg>\n')


write("app-icon-light.svg", app_icon(False))
write("app-icon-dark.svg", app_icon(True))

# ---------- wordmark (mark + "DyUI" in Instrument Serif, outlined)
for name, t in THEMES.items():
    size, base = 46, 47
    gap = 14
    mw = 58                                   # mark width; height ≈ 30 (≈ cap height of the serif)
    d, w = text_path(SERIF, "DyUI", size, x=mw + gap, baseline=base, tracking=-0.012)
    W = mw + gap + w + 4
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} 64" fill="none" role="img" aria-label="DyUI">\n'
           f'  {mark(0, base - mw * MARK_BOX[3] / MARK_BOX[2] - 1, mw, t["accent"])}\n  <path d="{d}" fill="{t["text"]}"/>\n</svg>\n')
    write("wordmark.svg" if name == "light" else "wordmark-dark.svg", svg)

# ---------- README hero
W, H = 1280, 520
for name, t in THEMES.items():
    size = 72
    a, b = "Chatbots that answer in ", "interfaces."
    _, wa = text_path(SERIF, a, size, tracking=-0.015)
    _, wb = text_path(SERIF_I, b, size, tracking=-0.01)
    x0 = (W - (wa + wb)) / 2
    base = 268
    da, _ = text_path(SERIF, a, size, x=x0, baseline=base, tracking=-0.015)
    db, _ = text_path(SERIF_I, b, size, x=x0 + wa, baseline=base, tracking=-0.01)

    sub = "The Python framework for professional chatbots whose replies arrive as UI."
    _, ws = text_path(SANS, sub, 22, wght=420)
    ds, _ = text_path(SANS, sub, 22, x=(W - ws) / 2, baseline=318, wght=420)

    cmd = "pip install dyui   ·   dyui run app.py"
    _, wc = text_path(MONO, cmd, 17, wght=450)
    pill_w = wc + 48
    px = (W - pill_w) / 2
    dc, _ = text_path(MONO, cmd, 17, x=px + 24, baseline=388, wght=450)

    kick = "GENERATIVE-UI CHAT FOR PYTHON"
    _, wk = text_path(SANS, kick, 13, tracking=0.12, wght=600)
    dk, _ = text_path(SANS, kick, 13, x=(W - wk) / 2, baseline=176, tracking=0.12, wght=600)

    s1, _ = text_path(SANS, "REVENUE", 10.5, x=78, baseline=120, tracking=0.1, wght=600)
    s2, _ = text_path(SERIF, "$48.2k", 34, x=78, baseline=160, tracking=-0.01)
    s3, _ = text_path(SANS, "+12% vs Q2", 12, x=78, baseline=184, wght=500)
    c1, _ = text_path(SANS, "BOOKINGS BY WEEK", 10.5, x=1046, baseline=380, tracking=0.1, wght=600)
    bars = [26, 40, 33, 52, 46, 64]
    bar_svg = "".join(
        f'<rect x="{1046 + i*26}" y="{466 - h}" width="16" height="{h}" rx="4" fill="url(#bar-{name})" opacity="{0.55 + i*0.08:.2f}"/>'
        for i, h in enumerate(bars))
    _, wq1 = text_path(SANS, "Book the cheaper one", 13, wght=500)
    q1, _ = text_path(SANS, "Book the cheaper one", 13, x=118, baseline=447, wght=500)
    q2t = "Check hotels"
    _, wq2 = text_path(SANS, q2t, 13, wght=500)
    q2, _ = text_path(SANS, q2t, 13, x=118 + wq1 + 44, baseline=447, wght=500)

    mw = 76
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" fill="none" role="img" aria-label="DyUI — Chatbots that answer in interfaces.">
<defs>
  <linearGradient id="ink-{name}" x1="{x0 + wa}" y1="0" x2="{x0 + wa + wb}" y2="0" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="{t['accent']}"/><stop offset="1" stop-color="{t['teal']}"/></linearGradient>
  <linearGradient id="bar-{name}" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{t['accent']}"/><stop offset="1" stop-color="{t['teal']}"/></linearGradient>
  <filter id="blur-{name}" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="70"/></filter>
  <filter id="shadow-{name}" x="-20%" y="-20%" width="140%" height="160%">
    <feDropShadow dx="0" dy="10" stdDeviation="14" flood-color="#000" flood-opacity="{t['card_shadow']}"/></filter>
  <clipPath id="clip-{name}"><rect width="{W}" height="{H}" rx="28"/></clipPath>
</defs>
<g clip-path="url(#clip-{name})">
  <rect width="{W}" height="{H}" fill="{t['bg']}"/>
  <circle cx="300" cy="120" r="200" fill="{t['accent']}" opacity="{t['bloom_op']}" filter="url(#blur-{name})"/>
  <circle cx="1000" cy="420" r="210" fill="{t['teal']}" opacity="{t['bloom_op']}" filter="url(#blur-{name})"/>

  <g transform="rotate(-4 146 150)" filter="url(#shadow-{name})">
    <rect x="58" y="96" width="176" height="108" rx="16" fill="{t['surface']}" stroke="{t['border']}"/>
    <path d="{s1}" fill="{t['faint']}"/><path d="{s2}" fill="{t['text']}"/><path d="{s3}" fill="{t['teal']}"/>
  </g>
  <g transform="rotate(3 1124 414)" filter="url(#shadow-{name})">
    <rect x="1026" y="356" width="196" height="132" rx="16" fill="{t['surface']}" stroke="{t['border']}"/>
    <path d="{c1}" fill="{t['faint']}"/>{bar_svg}
  </g>
  <g filter="url(#shadow-{name})" opacity="0.95">
    <rect x="100" y="425" width="{wq1 + 36}" height="34" rx="17" fill="{t['surface']}" stroke="{t['border']}"/>
    <path d="{q1}" fill="{t['muted']}"/>
    <rect x="{118 + wq1 + 26}" y="425" width="{wq2 + 36}" height="34" rx="17" fill="{t['surface']}" stroke="{t['border']}"/>
    <path d="{q2}" fill="{t['muted']}"/>
  </g>

  {mark(W/2 - mw/2, 92, mw, t['accent'])}
  <path d="{dk}" fill="{t['accent']}" opacity="0.9"/>
  <path d="{da}" fill="{t['text']}"/>
  <path d="{db}" fill="url(#ink-{name})"/>
  <path d="{ds}" fill="{t['muted']}"/>
  <rect x="{px}" y="358" width="{pill_w}" height="46" rx="23" fill="{t['surface']}" stroke="{t['border']}"/>
  <path d="{dc}" fill="{t['text']}"/>
</g>
</svg>
'''
    write(f"readme-hero-{name}.svg", svg)

# ---------- shortlisted alternates (swap candidates for the owner)
ALTERNATES = {
    "typing-card.svg": MARK_D,
    "switch-bubble.svg": ("M32 20H68A26 26 0 0 1 68 72H42C38 82 28 89 14 92C19 85 19 76 13.6 64.4A26 26 0 0 1 32 20Z"
                          "M52 46A16 16 0 1 0 84 46A16 16 0 1 0 52 46Z"),
    "d-bubble.svg": ("M12 22A12 12 0 0 1 24 10H52A40 40 0 0 1 52 90H34Q22 92 12 100Z"
                     "M44 30H55A9 9 0 0 1 64 39V61A9 9 0 0 1 55 70H44A9 9 0 0 1 35 61V39A9 9 0 0 1 44 30Z"),
}
os.makedirs(os.path.join(OUT, "alternates"), exist_ok=True)
for fn, d in ALTERNATES.items():
    write(os.path.join("alternates", fn),
          f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" fill="none" role="img" aria-label="DyUI">\n'
          f'  <path d="{d}" fill="{INDIGO}" fill-rule="evenodd"/>\n</svg>\n')

print("generated brand SVGs in", OUT)
