"""Convert text to SVG path data with fontTools (so brand SVGs render identically everywhere)."""
from __future__ import annotations

import io
from functools import lru_cache

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont


@lru_cache(maxsize=None)
def load(path: str, wght: float | None = None, wdth: float | None = None) -> TTFont:
    f = TTFont(path)
    if "fvar" in f and (wght or wdth):
        from fontTools.varLib.instancer import instantiateVariableFont

        loc = {}
        axes = {a.axisTag for a in f["fvar"].axes}
        if wght and "wght" in axes:
            loc["wght"] = wght
        if wdth and "wdth" in axes:
            loc["wdth"] = wdth
        f = instantiateVariableFont(f, loc)
        buf = io.BytesIO()
        f.save(buf)
        buf.seek(0)
        f = TTFont(buf)
    return f


@lru_cache(maxsize=None)
def _kern_pairs(path: str, wght: float | None, wdth: float | None) -> dict:
    """Very small GPOS pair-kerning reader (format 1 pairs only); good enough for short headlines."""
    font = load(path, wght, wdth)
    pairs: dict = {}
    if "GPOS" not in font:
        return pairs
    for lookup in font["GPOS"].table.LookupList.Lookup:
        for st in lookup.SubTable:
            if st.LookupType == 9:
                st = st.ExtSubTable
            if getattr(st, "LookupType", None) != 2 or st.Format != 1:
                continue
            cov = st.Coverage.glyphs
            for i, ps in enumerate(st.PairSet):
                for pvr in ps.PairValueRecord:
                    v = getattr(pvr.Value1, "XAdvance", 0) if pvr.Value1 else 0
                    if v:
                        pairs[(cov[i], pvr.SecondGlyph)] = v
    return pairs


PRECISION = 2   # decimals in outline coordinates; banners drop to 1 (still < 0.1px at display size)


def _num(v: float) -> str:
    return f"{v:.{PRECISION}f}".rstrip("0").rstrip(".")


def _layout(path, text, size, x, tracking, wght, wdth):
    """Yield (glyph name, pen x) for each drawable character, then (None, end x)."""
    font = load(path, wght, wdth)
    scale = size / font["head"].unitsPerEm
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    kp = _kern_pairs(path, wght, wdth)
    cx = x
    prev = None
    for ch in text:
        g = cmap.get(ord(ch))
        if g is None:
            cx += size * 0.3
            prev = None
            continue
        if prev is not None:
            cx += kp.get((prev, g), 0) * scale
        yield g, cx
        cx += hmtx[g][0] * scale + tracking * size
        prev = g
    yield None, cx


def text_path(path: str, text: str, size: float, x: float = 0, baseline: float = 0,
              tracking: float = 0.0, wght: float | None = None, wdth: float | None = None) -> tuple[str, float]:
    """Outline `text`; returns (path data, advance width). `tracking` is in em."""
    font = load(path, wght, wdth)
    scale = size / font["head"].unitsPerEm
    gs = font.getGlyphSet()
    out = []
    end = x
    for g, cx in _layout(path, text, size, x, tracking, wght, wdth):
        if g is None:
            end = cx
            break
        pen = SVGPathPen(gs, ntos=_num)
        gs[g].draw(TransformPen(pen, (scale, 0, 0, -scale, cx, baseline)))
        d = pen.getCommands()
        if d:
            out.append(d)
    return "".join(out), end - x


def text_bounds(path: str, text: str, size: float, tracking: float = 0.0,
                wght: float | None = None, wdth: float | None = None) -> tuple[float, float, float, float]:
    """Ink bounds (xmin, ymin, xmax, ymax) of `text` set at x=0 on baseline y=0, y pointing down."""
    font = load(path, wght, wdth)
    scale = size / font["head"].unitsPerEm
    gs = font.getGlyphSet()
    pen = BoundsPen(gs)
    for g, cx in _layout(path, text, size, 0, tracking, wght, wdth):
        if g is None:
            break
        gs[g].draw(TransformPen(pen, (scale, 0, 0, -scale, cx, 0)))
    return pen.bounds or (0, 0, 0, 0)


def cap_height(path: str, size: float) -> float:
    font = load(path)
    return font["OS/2"].sCapHeight * size / font["head"].unitsPerEm
