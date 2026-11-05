"""Exploration sheets: many candidate marks per concept, judged large / 32px / 16px pixelated."""
import base64, subprocess, os
HERE = os.path.dirname(os.path.abspath(__file__))
IND, IND_D, TEAL, TEAL_D, INK, PAPER, MID = "#5B4FE0", "#8B80FF", "#14A394", "#3DD6C3", "#1A1A1F", "#F7F6F3", "#0B0C10"

def svg(layers, vb="0 0 100 100"):
    """layers: str d (one colour = currentColor) or list of (d, fill)."""
    if isinstance(layers, str): layers = [(layers, "currentColor")]
    body = "".join(f'<path d="{d}" fill="{c}" fill-rule="evenodd"/>' for d, c in layers)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}">{body}</svg>'

def uri(s): return "data:image/svg+xml;base64," + base64.b64encode(s.encode()).decode()

def mono(d, col):
    return svg([(d, col)] if isinstance(d, str) else [(x, col) for x, _ in d])

JS = """
document.querySelectorAll('canvas[data-src]').forEach(c=>{const im=new Image();im.onload=()=>{const x=c.getContext('2d');
x.fillStyle=c.dataset.bg;x.fillRect(0,0,c.width,c.height);x.drawImage(im,0,0,c.width,c.height)};im.src=c.dataset.src});
"""

def sheet(name, cands, cols=4):
    cells = []
    for label, d in cands:
        small = d[1] if isinstance(d, tuple) else d
        big = d[0] if isinstance(d, tuple) else d
        col = svg(big if isinstance(big, list) else [(big, IND)])
        wht = mono(big, "#FFFFFF") if isinstance(big, str) else mono(big, "#fff")
        s_ink = mono(small, INK) if isinstance(small, str) else mono(small, INK)
        s_wht = mono(small, "#FFFFFF")
        cells.append(f'''<div class="cell"><div class="lab">{label}</div>
<div class="row"><div class="big" style="background:{PAPER}"><img src="{uri(col)}"></div>
<div class="big" style="background:{MID}"><img src="{uri(wht)}"></div></div>
<div class="row sm"><img src="{uri(s_ink)}" style="width:32px"><img src="{uri(s_ink)}" style="width:16px">
<canvas width=16 height=16 data-bg="{PAPER}" data-src="{uri(s_ink)}" class="px"></canvas>
<canvas width=16 height=16 data-bg="{MID}" data-src="{uri(s_wht)}" class="px"></canvas>
<canvas width=32 height=32 data-bg="{PAPER}" data-src="{uri(s_ink)}" class="px"></canvas></div></div>''')
    html = f'''<html><head><link rel="stylesheet" href="fonts.css"><style>
body{{margin:0;padding:24px;background:#E9E7E2;font-family:"Instrument Sans";color:{INK}}}
.grid{{display:grid;grid-template-columns:repeat({cols},1fr);gap:18px}}
.cell{{background:{PAPER};padding:12px;border-radius:6px}} .lab{{font-size:13px;margin-bottom:8px}}
.row{{display:flex;gap:8px;align-items:center}} .big{{width:170px;height:170px;display:grid;place-items:center;border-radius:4px}}
.big img{{width:150px;height:150px}} .sm{{margin-top:10px}} .px{{width:64px;height:64px;image-rendering:pixelated;border:1px solid #ddd}}
</style></head><body><div class="grid">{"".join(cells)}</div><script>{JS}</script></body></html>'''
    p = os.path.join(HERE, f"x-{name}.html"); open(p, "w").write(html)
    out = os.path.join(HERE, f"x-{name}.png")
    w = cols * 380 + 60
    subprocess.run(["node", os.path.join(HERE, "shoot.cjs"), p, out, str(w), "1"], check=True,
                   env={**os.environ, "NODE_PATH": subprocess.check_output(["npm", "root", "-g"]).decode().strip()})
    return out
