import math
from geo import *
from shapes import *
from explore import sheet

# ---------- C1 quote-drop ----------
c1 = []
for lab, kw in [("a ball36 tail t95", dict(a=10, t=95, b=130, R2=2.2)),
                ("b shorter tail t85 b125", dict(a=15, t=85, b=125, R2=2.0)),
                ("c longer hook t105", dict(a=5, t=105, b=135, R2=2.4)),
                ("d slim tail b140", dict(a=20, t=100, b=140, R2=2.1)),
                ("e fat tail a0 b120", dict(a=0, t=92, b=120, R2=2.3))]:
    d, info = quote_drop(0, 0, 1, **kw)
    c1.append((lab, fit(d, 80)))
d, info = quote_drop(0, 0, 1, a=10, t=95, b=130, R2=2.2)
q = fit(d, 80)
x0, y0, x1, y1 = bounds(q)
# ball centre after fit: find by solving — approximate: ball is the top part; use circle r ~ (x1-x0)/(2.374)*1
c1.append(("f + square counter", diff(q, rrect(52, 22, 18, 18, 4))))
c1.append(("g + slit (tail separated)", q))
c1.append(("h double: user+bot", union(fit(d, 52, 34, 40), fit(d, 52, 66, 60))))
sheet("c1b", c1)

# ---------- C3 D-card (fixed) ----------
def Dsh(L, T, H, W, rl=0):
    R = H / 2; X = L + W - R
    return union(rrect(L, T, X - L + 0.01, H, (rl, 0, 0, rl)), inter(circle(X, T + R, R), rrect(X, T, R, H, 0)))
c3 = []
D = Dsh(14, 12, 76, 72)
c3.append(("a D72 + card 30x44 r8", diff(D, rrect(32, 28, 30, 44, 8))))
c3.append(("b card 26x40 r7", diff(D, rrect(32, 30, 26, 40, 7))))
c3.append(("c landscape card 32x30", diff(D, rrect(32, 35, 32, 30, 8))))
c3.append(("d D rl6 + card", diff(Dsh(14, 12, 76, 72, 6), rrect(32, 28, 30, 44, 8))))
Dt = union(Dsh(16, 10, 72, 70, 0), poly([(16, 70), (16, 92), (34, 82)]))
c3.append(("e bubble-D (tail) + card", diff(Dt, rrect(33, 26, 28, 40, 8))))
c3.append(("f card w/ sharp TL", diff(D, rrect(32, 28, 30, 44, (0, 8, 8, 8)))))
c3.append(("g thin ring D", diff(D, rrect(28, 24, 38, 52, 10))))
c3.append(("h card offset low (chin)", diff(D, rrect(32, 24, 30, 40, 8))))
sheet("c3b", c3)

# ---------- C2 ink card ----------
c2 = []
card = rrect(10, 10, 80, 80, (26, 0, 26, 26))
c2.append(("a leaf card + 1 line", diff(card, pill(26, 44, 36, 10))))
c2.append(("b leaf + line + small card", diff(card, pill(24, 30, 30, 9), rrect(24, 46, 30, 24, 7))))
c2.append(("c leaf + nested drop", diff(card, rrect(26, 42, 30, 30, (10, 0, 10, 10)))))
tl = rrect(10, 10, 80, 80, (0, 26, 26, 26))
c2.append(("d TL sharp + 2 lines R", diff(tl, pill(36, 36, 38, 9), pill(50, 52, 24, 9))))
rot = center_bbox(rotate(rrect(16, 16, 68, 68, (24, 0, 24, 24)), -45), dy=2)
c2.append(("e tilted + 3 lines", diff(rot, pill(38, 40, 24, 7), pill(30, 52, 40, 7), pill(36, 64, 28, 7))))
c2.append(("f tilted + line + card", diff(rot, pill(36, 42, 28, 7), rrect(33, 54, 34, 18, 6))))
c2.append(("g leaf + chart bars", diff(card, rrect(26, 52, 9, 22, 3), rrect(40, 40, 9, 34, 3), rrect(54, 30, 9, 44, 3))))
c2.append(("h leaf + L corner cut", diff(card, rrect(24, 24, 52, 52, (12, 0, 12, 12)), ) if False else diff(card, pill(26, 30, 40, 9), pill(26, 46, 26, 9), pill(26, 62, 14, 9))))
sheet("c2b", c2)

# ---------- C6 emergence ----------
c6 = []
g = 6
c6.append(("a bento: drop + bar + card", union(circle(27, 27, 17), rrect(50, 10, 40, 34, 12), rrect(10, 50, 80, 40, 14))))
c6.append(("b bento: dot + tall card + bar", union(circle(26, 26, 16), rrect(48, 10, 42, 80, 16), rrect(10, 48, 32, 42, 14))))
c6.append(("c horizon: card rising from line", union(rrect(26, 14, 48, 48, 14), pill(10, 70, 80, 12))))
c6.append(("d line splits into card", union(pill(10, 44, 34, 12), rrect(50, 22, 40, 56, 14))))
c6.append(("e stair diag 3", union(pill(10, 12, 30, 12), rrect(10, 32, 50, 22, 11), rrect(10, 60, 80, 30, 14))))
c6.append(("f text lines + card in col", union(pill(10, 12, 80, 10), pill(10, 28, 52, 10), rrect(10, 46, 80, 44, 14))))
c6.append(("g dot->pill->card diag", union(circle(20, 20, 10), pill(10, 38, 44, 16), rrect(10, 62, 80, 28, 14)) ))
c6.append(("h stacked cards depth", union(rrect(30, 10, 60, 40, 12), rrect(10, 56, 80, 34, 14))))
sheet("c6b", c6)

# ---------- C5 bloom ----------
def quad(cx, cy, r, q, gg, rc=0):
    sx = -1 if q in (0, 3) else 1; sy = -1 if q in (0, 1) else 1
    ox, oy = cx + sx * gg / 2, cy + sy * gg / 2
    sq = rrect(min(ox, ox + sx * r), min(oy, oy + sy * r), r, r, 0)
    sh = inter(circle(ox, oy, r), sq)
    if rc:
        # round the right-angle corner
        corner = rrect(min(ox, ox + sx * r), min(oy, oy + sy * r), r, r,
                       tuple(rc if (q == i) else 0 for i in (2, 3, 0, 1)))
        sh = inter(sh, corner)
    return sh
def bloom(rs, gg=6, rc=0):
    return union(*[quad(50, 50, r, q, gg, rc) for q, r in enumerate(rs)])
def centroid_center(d):
    import pathops
    # approximate centroid via sampling
    p = P(d); x0, y0, x1, y1 = p.bounds
    sx = sy = n = 0
    from fontTools.pens.pointInsidePen import PointInsidePen
    pts = []
    N = 120
    for i in range(N):
        for j in range(N):
            x = x0 + (x1 - x0) * (i + .5) / N; y = y0 + (y1 - y0) * (j + .5) / N
            if p.contains((x, y)): sx += x; sy += y; n += 1
    return translate(d, 50 - sx / n, 50 - sy / n)
c5 = []
for lab, rs, gg, rc in [("a phi 46/22/28/36 g6", (46, 22, 28, 36), 6, 0), ("b phi g5 rc2", (46, 22, 28, 36), 5, 2),
                        ("c phi 44/24/30/37 g7", (44, 24, 30, 37), 7, 0), ("d spiral ccw", (36, 28, 22, 46), 6, 0),
                        ("e biggest BL", (36, 46, 22, 28)[::-1], 6, 0), ("f 1.2 ratio 42/24/29/35", (42, 24, 29, 35), 6, 0),
                        ("g phi g8 (16px)", (46, 22, 28, 36), 8, 0), ("h big BR", (28, 36, 46, 22), 6, 0)]:
    c5.append((lab, centroid_center(bloom(rs, gg, rc))))
sheet("c5b", c5)
