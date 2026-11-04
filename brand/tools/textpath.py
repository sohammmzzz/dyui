"""Convert text to SVG path data with fontTools (so brand SVGs render identically everywhere)."""
from __future__ import annotations
import io
from functools import lru_cache
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

@lru_cache(maxsize=None)
def load(path: str, wght: float | None = None, wdth: float | None = None) -> TTFont:
    f = TTFont(path)
    if "fvar" in f and (wght or wdth):
        from fontTools.varLib.instancer import instantiateVariableFont
        loc = {}
        axes = {a.axisTag for a in f["fvar"].axes}
        if wght and "wght" in axes: loc["wght"] = wght
        if wdth and "wdth" in axes: loc["wdth"] = wdth
        f = instantiateVariableFont(f, loc)
        buf = io.BytesIO(); f.save(buf); buf.seek(0); f = TTFont(buf)
    return f

def kern_pairs(font: TTFont) -> dict:
    """Very small GPOS pair-kerning reader (format 1 pairs only); good enough for short headlines."""
    pairs = {}
    if "GPOS" not in font: return pairs
    for lookup in font["GPOS"].table.LookupList.Lookup:
        for st in lookup.SubTable:
            if st.LookupType == 9: st = st.ExtSubTable
            if getattr(st, "LookupType", None) != 2 or st.Format != 1: continue
            cov = st.Coverage.glyphs
            for i, ps in enumerate(st.PairSet):
                for pvr in ps.PairValueRecord:
                    v = getattr(pvr.Value1, "XAdvance", 0) if pvr.Value1 else 0
                    if v: pairs[(cov[i], pvr.SecondGlyph)] = v
    return pairs

def text_path(path: str, text: str, size: float, x: float = 0, baseline: float = 0,
              tracking: float = 0.0, wght: float | None = None, wdth: float | None = None) -> tuple[str, float]:
    font = load(path, wght, wdth)
    upem = font["head"].unitsPerEm
    scale = size / upem
    cmap = font.getBestCmap(); gs = font.getGlyphSet(); hmtx = font["hmtx"]
    kp = kern_pairs(font)
    out = []; cx = x; prev = None
    for ch in text:
        g = cmap.get(ord(ch))
        if g is None: cx += size * 0.3; prev = None; continue
        if prev is not None: cx += kp.get((prev, g), 0) * scale
        pen = SVGPathPen(gs)
        gs[g].draw(TransformPen(pen, (scale, 0, 0, -scale, cx, baseline)))
        d = pen.getCommands()
        if d: out.append(d)
        cx += hmtx[g][0] * scale + tracking * size
        prev = g
    return " ".join(out), cx - x
