"""Geometry + boolean helpers for hand-built marks (100x100 grid)."""
from __future__ import annotations
import math, sys
sys.path.insert(0, "/tmp/claude-0/-home-user-dyui/71a4dc0e-e780-5e7c-b26a-c61d6b2260ca/scratchpad/pylib")
sys.path.insert(0, "/tmp/claude-0/-home-user-dyui/71a4dc0e-e780-5e7c-b26a-c61d6b2260ca/scratchpad/tools")
import pathops
from pathops import Path, op, PathOp
from fontTools.svgLib.path import parse_path
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.basePen import BasePen

K = 0.5522847498  # cubic circle constant

def f(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s

def circle(cx, cy, r):
    return (f"M{f(cx-r)} {f(cy)}A{f(r)} {f(r)} 0 1 1 {f(cx+r)} {f(cy)}"
            f"A{f(r)} {f(r)} 0 1 1 {f(cx-r)} {f(cy)}Z")

def ellipse(cx, cy, rx, ry):
    return (f"M{f(cx-rx)} {f(cy)}A{f(rx)} {f(ry)} 0 1 1 {f(cx+rx)} {f(cy)}"
            f"A{f(rx)} {f(ry)} 0 1 1 {f(cx-rx)} {f(cy)}Z")

def rrect(x, y, w, h, r):
    """Rounded rect; r = number or (tl, tr, br, bl)."""
    tl, tr, br, bl = (r, r, r, r) if isinstance(r, (int, float)) else r
    d = f"M{f(x+tl)} {f(y)}H{f(x+w-tr)}"
    d += f"A{f(tr)} {f(tr)} 0 0 1 {f(x+w)} {f(y+tr)}" if tr else ""
    d += f"V{f(y+h-br)}"
    d += f"A{f(br)} {f(br)} 0 0 1 {f(x+w-br)} {f(y+h)}" if br else ""
    d += f"H{f(x+bl)}"
    d += f"A{f(bl)} {f(bl)} 0 0 1 {f(x)} {f(y+h-bl)}" if bl else ""
    d += f"V{f(y+tl)}"
    d += f"A{f(tl)} {f(tl)} 0 0 1 {f(x+tl)} {f(y)}" if tl else ""
    return d + "Z"

def poly(points):
    return "M" + "L".join(f"{f(x)} {f(y)}" for x, y in points) + "Z"

def poly_round(points, radii):
    """Polygon with per-vertex fillet radii (0 = sharp). Points in drawing order."""
    n = len(points)
    if isinstance(radii, (int, float)): radii = [radii] * n
    segs = []
    for i in range(n):
        p0, p1, p2 = points[i-1], points[i], points[(i+1) % n]
        r = radii[i]
        if not r:
            segs.append(("pt", p1)); continue
        v1 = (p0[0]-p1[0], p0[1]-p1[1]); v2 = (p2[0]-p1[0], p2[1]-p1[1])
        l1 = math.hypot(*v1); l2 = math.hypot(*v2)
        u1 = (v1[0]/l1, v1[1]/l1); u2 = (v2[0]/l2, v2[1]/l2)
        ang = math.acos(max(-1, min(1, u1[0]*u2[0] + u1[1]*u2[1])))
        t = r / math.tan(ang/2)
        a = (p1[0]+u1[0]*t, p1[1]+u1[1]*t); b = (p1[0]+u2[0]*t, p1[1]+u2[1]*t)
        cross = u1[0]*u2[1] - u1[1]*u2[0]
        sweep = 1 if cross < 0 else 0
        segs.append(("arc", a, b, r, sweep))
    d = ""
    for i, s in enumerate(segs):
        if s[0] == "pt":
            d += ("M" if i == 0 else "L") + f"{f(s[1][0])} {f(s[1][1])}"
        else:
            _, a, b, r, sw = s
            d += ("M" if i == 0 else "L") + f"{f(a[0])} {f(a[1])}"
            d += f"A{f(r)} {f(r)} 0 0 {sw} {f(b[0])} {f(b[1])}"
    return d + "Z"

# ---------- pathops bridge ----------
def P(d) -> Path:
    if isinstance(d, Path): return d
    p = Path(); parse_path(d, p.getPen()); return p

class _DPen(BasePen):
    def __init__(self): super().__init__(None); self.out = []
    def _moveTo(self, p): self.out.append(f"M{f(p[0])} {f(p[1])}")
    def _lineTo(self, p): self.out.append(f"L{f(p[0])} {f(p[1])}")
    def _curveToOne(self, a, b, c): self.out.append(f"C{f(a[0])} {f(a[1])} {f(b[0])} {f(b[1])} {f(c[0])} {f(c[1])}")
    def _qCurveToOne(self, a, b): self.out.append(f"Q{f(a[0])} {f(a[1])} {f(b[0])} {f(b[1])}")
    def _closePath(self): self.out.append("Z")
    def _endPath(self): pass

def D(p) -> str:
    if isinstance(p, str): p = P(p)
    pen = _DPen(); p.draw(pen); return "".join(pen.out)

def _clean(p):
    try: return pathops.simplify(p, fix_winding=True)
    except Exception: return p

def union(*ds):
    acc = P(ds[0])
    for d in ds[1:]: acc = op(acc, P(d), PathOp.UNION)
    return D(_clean(acc))

def diff(a, *bs):
    acc = P(a)
    for b in bs: acc = op(acc, P(b), PathOp.DIFFERENCE)
    return D(_clean(acc))

def inter(a, b):
    return D(_clean(op(P(a), P(b), PathOp.INTERSECTION)))

def xform(d, a=1, b=0, c=0, dd=1, e=0, f_=0):
    p = Path(); parse_path(d, TransformPen(p.getPen(), (a, b, c, dd, e, f_))); return D(p)

def rotate(d, deg, cx=50, cy=50):
    t = math.radians(deg); co, si = math.cos(t), math.sin(t)
    return xform(d, co, si, -si, co, cx - co*cx + si*cy, cy - si*cx - co*cy)

def translate(d, dx, dy): return xform(d, 1, 0, 0, 1, dx, dy)
def scale(d, s, cx=50, cy=50): return xform(d, s, 0, 0, s, cx - s*cx, cy - s*cy)

def bounds(d):
    return P(d).bounds  # (xmin, ymin, xmax, ymax)

def area(d):
    p = P(d); return abs(p.area) if hasattr(p, "area") else None
