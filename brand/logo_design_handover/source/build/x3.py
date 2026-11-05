import math
from geo import *
from shapes import *
from explore import sheet

def cub(p0, c1, c2, p3): return f"C{f(c1[0])} {f(c1[1])} {f(c2[0])} {f(c2[1])} {f(p3[0])} {f(p3[1])}"
def M(p): return f"M{f(p[0])} {f(p[1])}"
def L(p): return f"L{f(p[0])} {f(p[1])}"

# ---------------- C4 Dy ligature ----------------
def D_serif(x0=14, top=14, base=72, stem=10.5, hair=4.2, bowl=11.5, W=40, serif=True):
    H = base - top; cy = (top + base) / 2
    ox = x0 + W * 0.42                      # straight run of the hairlines before the bowl
    rx = x0 + W - ox; ry = H / 2
    outer = union(rrect(x0, top, ox - x0 + .01, H, 0), inter(ellipse(ox, cy, rx, ry), rrect(ox, top, rx, H, 0)))
    irx = rx - bowl; iry = ry - hair; icx = ox
    inner = union(rrect(x0 + stem, top + hair, icx - x0 - stem + .01, H - 2 * hair, 0),
                  inter(ellipse(icx, cy, irx, iry), rrect(icx, top, irx + 1, H, 0)))
    d = diff(outer, inner)
    if serif:
        s = 5.0
        # bracketed serifs to the left of the stem (top & bottom), Instrument-like
        d = union(d, poly_round([(x0 - s, top), (x0 + 1, top), (x0 + 1, top + hair + 4), (x0, top + hair + 4), (x0 - .5, top + hair + .3), (x0 - s, top + hair)], [0, 0, 0, 0, 2.5, 1.2]))
        d = union(d, poly_round([(x0 - s, base), (x0 + 1, base), (x0 + 1, base - hair - 4), (x0, base - hair - 4), (x0 - .5, base - hair - .3), (x0 - s, base - hair)], [0, 0, 0, 0, 2.5, 1.2]))
    return d

def y_lig(xh=34, base=72, lx=51, thick=10.5, thin=3.6, rx_top=84, tail_tip=(22, 92), tail_mode=0):
    # thick arm: top-left (lx..lx+thick, xh) down-right with slope k
    k = 0.30
    crotch_y = base - 4
    a0 = (lx, xh); a1 = (lx + thick, xh)
    b0 = (lx + k * (crotch_y - xh), crotch_y); b1 = (b0[0] + thick, crotch_y)
    # thin arm from top-right down-left to the thick arm
    t0 = (rx_top - thin, xh); t1 = (rx_top, xh)
    join = (b1[0] - 1.5, crotch_y - 10)
    thin_arm = poly([t0, t1, (join[0] + thin * 1.1, join[1] + 2), (join[0], join[1])])
    # descender: continue thick stroke down, sweep left into a pointed bubble tail
    tip = tail_tip
    if tail_mode == 0:
        desc = (M(b0) + L(b1) + cub(b1, (b1[0] + 1.5, crotch_y + 12), (b1[0] - 8, base + 19), (tip[0] + 18, base + 21))
                + cub(None, (tip[0] + 10, base + 21.5), (tip[0] + 4, tip[1] - 1), tip)
                + cub(None, (tip[0] + 9, tip[1] - 5), (b0[0] - 2, base + 12), (b0[0] - .5, crotch_y + 3)) + "Z")
    else:
        desc = (M(b0) + L(b1) + cub(b1, (b1[0] + 1.0, crotch_y + 14), (b1[0] - 4, tip[1] - 2), tip)
                + cub(None, (b0[0] - 1, tip[1] - 9), (b0[0] - 1, crotch_y + 10), (b0[0] - .2, crotch_y + 3)) + "Z")
    arm = poly([a0, a1, b1, b0])
    serif_r = rrect(t0[0] - 4.5, xh, thin + 9, 3.6, 1.2)
    return union(arm, thin_arm, desc, serif_r)

c4 = []
D1 = D_serif()
c4.append(("a D serif", D1))
c4.append(("b Dy sweep left", union(D1, y_lig())))
c4.append(("c Dy tail down-left", union(D1, y_lig(tail_tip=(44, 96), tail_mode=1))))
c4.append(("d Dy sweep long", union(D1, y_lig(tail_tip=(12, 90)))))
D2 = D_serif(stem=13, hair=6, bowl=14, serif=False)
c4.append(("e heavy sans-serif D", D2))
c4.append(("f heavy Dy", union(D2, y_lig(thick=13, thin=5, lx=50, tail_tip=(20, 92)))))
sheet("c4", [(l, fit(d, 82)) for l, d in c4], cols=3)

# ---------------- C1 quote-drop details ----------------
c1 = []
d, info = quote_drop(50, 50, 30, a=15, t=85, b=125, R2=2.0)
c1.append(("a base b", center_bbox(d)))
d2, i2 = quote_drop(50, 50, 30, a=12, t=88, b=122, R2=1.85)
c1.append(("b blunter tail R1.85", center_bbox(d2)))
# square corner on ball opposite the tail (TR)
sq = union(d, rrect(50, 20, 30, 30, 0))
c1.append(("c ball w/ TR square corner", center_bbox(sq)))
c1.append(("d slit: text line", center_bbox(diff(d, pill(36, 44, 30, 8)))))
gapc = diff(circle(50, 50, 33.5), circle(50, 50, 30))
c1.append(("e tail detached (gap)", center_bbox(union(circle(50, 50, 30), diff(d, circle(50, 50, 33.5))))))
c1.append(("f rounded tip", center_bbox(union(d2, circle(i2['T'][0] + 1.6, i2['T'][1] - 1.2, 2.2)))))
sheet("c1c", c1, cols=3)

# ---------------- C3 refinements ----------------
def Dsh(L, T, H, W, rl=0):
    R = H / 2; X = L + W - R
    return union(rrect(L, T, X - L + 0.01, H, (rl, 0, 0, rl)), inter(circle(X, T + R, R), rrect(X, T, R, H, 0)))
c3 = []
D = Dsh(14, 12, 76, 72, 4)
c3.append(("a rl4 card 28x42 r9", diff(D, rrect(32, 29, 28, 42, 9))))
# bubble D: tail as quarter-circle concave wedge at bottom-left
Db = Dsh(16, 10, 70, 70, 0)
tail = M((16, 80)) + L((16, 94)) + f"A30 30 0 0 1 {f(38)} {f(80)}Z"
c3.append(("b bubble-D curved tail", diff(union(Db, tail), rrect(33, 25, 27, 40, 8))))
tail2 = M((16, 78)) + L((16, 92)) + L((32, 80)) + "Z"
c3.append(("c bubble-D straight tail", diff(union(Db, tail2), rrect(33, 25, 27, 40, 8))))
# contrast D: stem 18, hairlines 12, bowl 20
c3.append(("d contrast card", diff(D, rrect(33, 26, 26, 48, 8))))
c3.append(("e square card", diff(D, rrect(32, 34, 30, 32, 8))))
c3.append(("f D card + dot (cursor)", diff(D, rrect(32, 29, 28, 42, 9))))
sheet("c3c", c3, cols=3)

# ---------------- C2 ----------------
c2 = []
rot = center_bbox(rotate(rrect(16, 16, 68, 68, (24, 0, 24, 24)), -45), dy=2)
c2.append(("a drop: line, line, card", diff(rot, pill(41, 38, 18, 6.5), pill(34, 49, 32, 6.5), rrect(30, 61, 40, 14, 5))))
c2.append(("b drop: line + card", diff(rot, pill(37, 44, 26, 7), rrect(31, 57, 38, 18, 6))))
leaf = rrect(10, 10, 80, 80, (26, 0, 26, 26))
lc = union(pill(26, 30, 40, 9), rrect(26, 30, 22, 9, (4.5, 0, 0, 4.5)), rrect(26, 30, 9, 44, (4.5, 0, 4.5, 4.5)))
c2.append(("c leaf + L line", diff(leaf, lc)))
c2.append(("d leaf + mouth slit", diff(leaf, rrect(-5, 46, 52, 9, 4.5))))
c2.append(("e leaf + line->card neg", diff(leaf, pill(26, 28, 30, 9), rrect(26, 44, 48, 30, (4.5, 9, 9, 9)))))
c2.append(("f drop-card tip up rounded", diff(rot, pill(33, 50, 34, 8))))
sheet("c2c", c2, cols=3)

# ---------------- C6 ----------------
c6 = []
c6.append(("a horizon + reflection", union(diff(rrect(24, 12, 52, 52, 15), rrect(0, 55, 100, 100, 0)), pill(10, 61, 80, 10), pill(32, 77, 36, 8))))
c6.append(("b sliced card 8/16/rest", union(inter(rrect(10, 10, 80, 80, 20), rrect(0, 10, 100, 9, 0)), inter(rrect(10, 10, 80, 80, 20), rrect(0, 25, 100, 15, 0)), inter(rrect(10, 10, 80, 80, 20), rrect(0, 46, 100, 60, 0)))))
c6.append(("c progression dot/pill/card", union(circle(19, 19, 9), pill(10, 36, 46, 14), rrect(10, 58, 80, 32, 14))))
dropc = center_bbox(qdrop(50, 50, 38, 270)[0])
c6.append(("d sliced drop", union(inter(dropc, rrect(0, 0, 100, 34, 0)), inter(dropc, rrect(0, 40, 100, 14, 0)), inter(dropc, rrect(0, 60, 100, 60, 0)))))
c6.append(("e progression card right", union(circle(19, 19, 9), pill(10, 36, 46, 14), rrect(10, 58, 80, 32, 14))))
c6.append(("f line rises into card", union(pill(10, 72, 40, 12), rrect(40, 12, 50, 72, (16, 16, 16, 6)))))
sheet("c6c", c6, cols=3)
