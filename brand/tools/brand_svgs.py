"""Generate outlined brand SVGs (wordmark + README hero) in light and dark variants."""
import sys
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else __import__("os").path.dirname(__file__))
from textpath import text_path

NM = "/home/user/dyui/web/node_modules"
SERIF = f"{NM}/@fontsource/instrument-serif/files/instrument-serif-latin-400-normal.woff2"
SERIF_I = f"{NM}/@fontsource/instrument-serif/files/instrument-serif-latin-400-italic.woff2"
SANS = f"{NM}/@fontsource-variable/instrument-sans/files/instrument-sans-latin-wght-normal.woff2"
MONO = f"{NM}/@fontsource-variable/geist-mono/files/geist-mono-latin-wght-normal.woff2"
OUT = "/home/user/dyui/brand"

THEMES = {
    "light": dict(bg="#F7F6F3", surface="#FFFFFF", border="#E6E3DC", text="#1A1A1F", muted="#5F5E66",
                  faint="#8E8C94", accent="#5B4FE0", teal="#14A394", bloom_op="0.20", card_shadow="0.07"),
    "dark": dict(bg="#0B0C10", surface="#14151C", border="#24252F", text="#ECECF1", muted="#A2A3B1",
                 faint="#6B6D7C", accent="#8B80FF", teal="#3DD6C3", bloom_op="0.30", card_shadow="0.5"),
}

def mark(x, y, s, gid):
    k = s / 64
    return f'''<g transform="translate({x} {y}) scale({k})">
  <defs><linearGradient id="{gid}" x1="14" y1="6" x2="52" y2="60" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="#7B6FF2"/><stop offset="0.55" stop-color="#5B4FE0"/><stop offset="1" stop-color="#14A394"/></linearGradient></defs>
  <path d="M32 5C32 5 11 25.5 11 39a21 21 0 0 0 42 0C53 25.5 32 5 32 5Z" fill="url(#{gid})"/>
  <circle cx="32" cy="40" r="5" fill="#FFFFFF" fill-opacity="0.92"/>
  <circle cx="32" cy="40" r="10.5" stroke="#FFFFFF" stroke-opacity="0.55" stroke-width="2" fill="none"/>
  <circle cx="32" cy="40" r="16" stroke="#FFFFFF" stroke-opacity="0.22" stroke-width="1.5" fill="none"/>
</g>'''

# ---------- wordmark ----------
for name, t in THEMES.items():
    d, w = text_path(SERIF, "DyUI", 46, x=0, baseline=0, tracking=-0.012)
    W = 70 + w + 6
    d, _ = text_path(SERIF, "DyUI", 46, x=70, baseline=47, tracking=-0.012)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} 64" fill="none" role="img" aria-label="DyUI">
{mark(0, 0, 64, "dyui-w-" + name)}
<path d="{d}" fill="{t['text']}"/>
</svg>
'''
    fn = f"{OUT}/wordmark.svg" if name == "light" else f"{OUT}/wordmark-dark.svg"
    open(fn, "w").write(svg)

# ---------- README hero ----------
W, H = 1280, 520
def centered(path_font, text, size, baseline, **kw):
    _, w = text_path(path_font, text, size, **kw)
    return w

for name, t in THEMES.items():
    # headline: "Chatbots that answer in " + italic "interfaces."
    size = 72
    a = "Chatbots that answer in "
    b = "interfaces."
    _, wa = text_path(SERIF, a, size, tracking=-0.015)
    _, wb = text_path(SERIF_I, b, size, tracking=-0.01)
    x0 = (W - (wa + wb)) / 2
    base = 268
    da, _ = text_path(SERIF, a, size, x=x0, baseline=base, tracking=-0.015)
    db, _ = text_path(SERIF_I, b, size, x=x0 + wa, baseline=base, tracking=-0.01)

    sub = "The Python framework for professional chatbots whose replies bloom into UI."
    _, ws = text_path(SANS, sub, 22, wght=420)
    ds, _ = text_path(SANS, sub, 22, x=(W - ws) / 2, baseline=318, wght=420)

    cmd = "pip install dyui   ·   dyui run app.py"
    _, wc = text_path(MONO, cmd, 17, wght=450)
    pill_w = wc + 48; px = (W - pill_w) / 2
    dc, _ = text_path(MONO, cmd, 17, x=px + 24, baseline=388, wght=450)

    # eyebrow kicker above headline
    kick = "GENERATIVE-UI CHAT FOR PYTHON"
    _, wk = text_path(SANS, kick, 13, tracking=0.12, wght=600)
    dk, _ = text_path(SANS, kick, 13, x=(W - wk) / 2, baseline=176, tracking=0.12, wght=600)

    # floating stat card (left)
    s1, _ = text_path(SANS, "REVENUE", 10.5, x=78, baseline=120, tracking=0.1, wght=600)
    s2, _ = text_path(SERIF, "$48.2k", 34, x=78, baseline=160, tracking=-0.01)
    s3, _ = text_path(SANS, "+12% vs Q2", 12, x=78, baseline=184, wght=500)
    # floating chart card (right)
    c1, _ = text_path(SANS, "BOOKINGS BY WEEK", 10.5, x=1046, baseline=380, tracking=0.1, wght=600)
    bars = [26, 40, 33, 52, 46, 64]
    bar_svg = "".join(
        f'<rect x="{1046 + i*26}" y="{466 - h}" width="16" height="{h}" rx="4" fill="url(#bar-{name})" opacity="{0.55 + i*0.08:.2f}"/>'
        for i, h in enumerate(bars))
    # floating quick replies (bottom-left)
    q1, wq1 = text_path(SANS, "Book the cheaper one", 13, wght=500)
    q1, _ = text_path(SANS, "Book the cheaper one", 13, x=118, baseline=447, wght=500)
    q2t = "Check hotels"
    q2, wq2 = text_path(SANS, q2t, 13, wght=500)
    q2, _ = text_path(SANS, q2t, 13, x=118 + wq1 + 44, baseline=447, wght=500)

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
  <circle cx="640" cy="260" r="120" fill="{t['accent']}" opacity="calc({t['bloom_op']} / 3)" filter="url(#blur-{name})"/>

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

  {mark(W/2 - 30, 64, 60, "dyui-h-" + name)}
  <path d="{dk}" fill="{t['accent']}" opacity="0.9"/>
  <path d="{da}" fill="{t['text']}"/>
  <path d="{db}" fill="url(#ink-{name})"/>
  <path d="{ds}" fill="{t['muted']}"/>
  <rect x="{px}" y="358" width="{pill_w}" height="46" rx="23" fill="{t['surface']}" stroke="{t['border']}"/>
  <path d="{dc}" fill="{t['text']}"/>
</g>
</svg>
'''
    open(f"{OUT}/readme-hero-{name}.svg", "w").write(svg)
print("generated")
