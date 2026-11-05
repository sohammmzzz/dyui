import math, sys
from geo import *
from shapes import *
from explore import sheet

# ---------------- C1 speech drop ----------------
c1 = []
base, tip = qdrop(50, 50, 40, 135)                      # BL square corner: fills 10..90 box
c1.append(("a plain bubble-drop, tip 135", base))
card = rrect(38, 30, 32, 32, 7)
c1.append(("b + card counter (32, r7) offset NE", diff(base, card)))
card2 = rrect(36, 34, 30, 30, 4)
c1.append(("c + card counter sharp BL corner", diff(base, rrect(36, 34, 30, 30, (6, 6, 6, 0)))))
c1.append(("d + waterline slit", diff(base, rrect(0, 52, 100, 6, 0))))
b2, _ = qdrop(54, 46, 34, 135, k=1.75, tip_r=1.2)
c1.append(("e sharper tail (k1.75) + card", diff(b2, rrect(42, 30, 26, 26, 6))))
b3, _ = qdrop(50, 58, 34, 270, k=math.sqrt(2), tip_r=0)
c1.append(("f tip-up drop + card", diff(b3, rrect(37, 46, 26, 26, 6))))
b4, _ = qdrop(54, 46, 36, 150, k=1.6, tip_r=1)
c1.append(("g tilted 150, inner circle", diff(b4, circle(58, 42, 13))))
# detaching tip: cut a gap perpendicular to the tip axis
b5, _ = qdrop(54, 46, 36, 135, k=math.sqrt(2))
gap = rotate(rrect(-20, 47, 140, 5, 0), 45, 54, 46)   # line at 45deg through... offset
gap = translate(rotate(rrect(0, 0, 140, 5.5, 0), -45, 0, 0), 0, 0)
c1.append(("h + single text line (pill) inside", diff(base, pill(32, 46, 40, 10))))
sheet("c1", c1)

# ---------------- C2 ink card ----------------
c2 = []
card = rrect(10, 10, 80, 80, (24, 0, 24, 24))
c2.append(("a card, TR sharp", card))
c2.append(("b lines->block (neg)", diff(card, pill(24, 30, 34, 8), pill(24, 44, 24, 8), rrect(24, 58, 42, 18, 6))))
c2.append(("c line + card (neg)", diff(card, pill(26, 28, 30, 9), rrect(26, 45, 48, 29, 8))))
c2.append(("d thin->thick progression", diff(card, pill(24, 28, 30, 5), pill(24, 39, 40, 8), rrect(24, 53, 52, 22, 7))))
rot = center_bbox(rotate(rrect(18, 18, 64, 64, (20, 0, 20, 20)), -45))
c2.append(("e tilted, tip up", rot))
c2.append(("f tilted + text lines", diff(rot, pill(37, 50, 26, 7), pill(32, 62, 36, 7))))
card3 = rrect(10, 10, 80, 80, (30, 0, 30, 30))
c2.append(("g r30 + 2 lines", diff(card3, pill(26, 40, 38, 9), pill(26, 56, 24, 9))))
c2.append(("h r24 + stair (line -> card)", diff(card, rrect(24, 28, 22, 9, 4.5), rrect(24, 44, 36, 9, 4.5), rrect(24, 60, 50, 16, 6))))
sheet("c2", c2)

# ---------------- C3 D-card ----------------
def Dshape(L=16, T=12, H=76, R=38, X=46):
    return union(rrect(L, T, X - L, H, 0), circle(X, T + H / 2, R))
c3 = []
D0 = Dshape()
c3.append(("a D + card counter", diff(D0, rrect(34, 28, 28, 44, 7))))
c3.append(("b + header bar", diff(D0, rrect(34, 28, 28, 11, (7, 7, 2, 2)), rrect(34, 44, 28, 28, (2, 2, 7, 7)))))
c3.append(("c heavier, smaller card", diff(Dshape(), rrect(36, 32, 22, 36, 6))))
D2 = union(rrect(16, 12, 30, 76, (8, 0, 0, 0)), circle(46, 50, 38))
c3.append(("d TL rounded (bubble-D)", diff(D2, rrect(34, 28, 28, 44, 7))))
side = rrect(16, 12, 12, 76, 0)
bowl = diff(Dshape(L=34), rrect(46, 28, 18, 44, 6))
c3.append(("e sidebar | panel D", union(side, bowl)))
c3.append(("f sidebar | solid bowl", union(side, Dshape(L=34))))
D3 = Dshape(L=18, T=10, H=80, R=40, X=44)
c3.append(("g card w/ header (window)", diff(D3, rrect(36, 26, 26, 12, (6, 6, 1.5, 1.5)), rrect(36, 43, 26, 31, (1.5, 1.5, 6, 6)))))
c3.append(("h counter card shifted up-right", diff(D0, rrect(36, 24, 28, 40, 7))))
sheet("c3", c3)

# ---------------- C5 quarter bloom ----------------
def quad(cx, cy, r, q, g):
    # q: 0=TL,1=TR,2=BR,3=BL ; corner at (cx,cy) offset by g/2
    sx = -1 if q in (0, 3) else 1; sy = -1 if q in (0, 1) else 1
    ox, oy = cx + sx * g / 2, cy + sy * g / 2
    sq = rrect(min(ox, ox + sx * r), min(oy, oy + sy * r), r, r, 0)
    return inter(circle(ox, oy, r), sq)
def bloom(rs, g=6, cx=50, cy=50):
    return union(*[quad(cx, cy, r, q, g) for q, r in enumerate(rs)])
c5 = []
for lab, rs, g in [("a spiral 24/30/36/42", (42, 24, 30, 36), 6), ("b diag 40/26", (40, 26, 40, 26), 6),
                   ("c 3 big 1 small", (40, 40, 24, 40), 6), ("d 1 big 3 small", (42, 28, 28, 28), 6),
                   ("e phi spiral 22/28/36/46", (46, 22, 28, 36), 6), ("f diag 42/30 g8", (42, 30, 42, 30), 8),
                   ("g two-step 40/40/28/28", (40, 40, 28, 28), 6), ("h 42/34/26/34", (42, 34, 26, 34), 6)]:
    c5.append((lab, center_bbox(bloom(rs, g))))
sheet("c5", c5)

# ---------------- C6 layered emergence ----------------
c6 = []
c6.append(("a left stack line/line/card", union(pill(12, 14, 46, 12), pill(12, 32, 66, 12), rrect(12, 50, 76, 36, 12))))
c6.append(("b drop: dot/pill/card", union(circle(50, 18, 7), pill(32, 32, 36, 13), rrect(14, 52, 72, 36, 14))))
c6.append(("c line swells into card", union(pill(10, 44, 50, 12), rrect(40, 20, 50, 60, 16))))
c6.append(("d rows w/ arc envelope", union(pill(14, 14, 34, 14), rrect(14, 34, 56, 20, 10), rrect(14, 60, 72, 28, 14))))
c6.append(("e diagonal line->card", union(pill(10, 74, 34, 12), rrect(36, 12, 54, 54, 16))))
c6.append(("f stair right-aligned", union(pill(52, 14, 36, 12), pill(30, 32, 58, 12), rrect(12, 50, 76, 38, 14))))
c6.append(("g line + card (caret)", union(rrect(12, 14, 10, 72, 5), rrect(30, 14, 58, 72, 16))))
c6.append(("h card w/ line on top, joined", union(pill(10, 14, 44, 12), rrect(10, 34, 80, 54, 16))))
sheet("c6", c6)
