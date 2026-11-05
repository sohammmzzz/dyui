"""Shared primitive constructions."""
import math
from geo import *

def qdrop(cx, cy, r, tip_deg, k=math.sqrt(2), tip_r=0.0):
    """Circle r at (cx,cy) plus tangent wedge to a tip at distance r*k in direction tip_deg (screen coords)."""
    th = math.radians(tip_deg); phi = math.acos(1 / k)
    tip = (cx + r * k * math.cos(th), cy + r * k * math.sin(th))
    t1 = (cx + r * math.cos(th + phi), cy + r * math.sin(th + phi))
    t2 = (cx + r * math.cos(th - phi), cy + r * math.sin(th - phi))
    wedge = poly_round([t1, tip, t2, (cx, cy)], [0, tip_r, 0, 0])
    return union(circle(cx, cy, r), wedge), tip

def center_bbox(d, cx=50, cy=50, dx=0, dy=0):
    x0, y0, x1, y1 = bounds(d)
    return translate(d, cx - (x0 + x1) / 2 + dx, cy - (y0 + y1) / 2 + dy)

def fit(d, size=80, cx=50, cy=50):
    x0, y0, x1, y1 = bounds(d)
    s = size / max(x1 - x0, y1 - y0)
    d = xform(d, s, 0, 0, s, 0, 0)
    return center_bbox(d, cx, cy)

def pill(x, y, w, h):
    return rrect(x, y, w, h, h / 2)

def quote_drop(cx, cy, r, a=10, t=95, b=130, R2=2.2, tip_r=0.0):
    """Ball (circle r) + hooked tail. Outer tail edge: arc of radius R2*r internally tangent to the ball
    at angle a; tip at angle t on that arc; inner edge: arc externally tangent to the ball at angle b
    passing through the tip (radius solved). Angles in screen degrees (y down)."""
    import math
    ua = (math.cos(math.radians(a)), math.sin(math.radians(a)))
    ub = (math.cos(math.radians(b)), math.sin(math.radians(b)))
    O2 = ((1 - R2) * ua[0], (1 - R2) * ua[1])
    T = (O2[0] + R2 * math.cos(math.radians(t)), O2[1] + R2 * math.sin(math.radians(t)))
    Tu = T[0] * ub[0] + T[1] * ub[1]; TT = T[0] ** 2 + T[1] ** 2
    R3 = (2 * Tu - TT - 1) / (2 - 2 * Tu)
    S = lambda p: (cx + p[0] * r, cy + p[1] * r)
    A = S(ua); B = S(ub); Tp = S(T)
    d = (f"M{f(A[0])} {f(A[1])}A{f(R2*r)} {f(R2*r)} 0 0 1 {f(Tp[0])} {f(Tp[1])}"
         f"A{f(R3*r)} {f(R3*r)} 0 0 0 {f(B[0])} {f(B[1])}"
         f"A{f(r)} {f(r)} 0 1 1 {f(A[0])} {f(A[1])}Z")
    return d, dict(A=A, B=B, T=Tp, R3=R3 * r, O2=S(O2))
