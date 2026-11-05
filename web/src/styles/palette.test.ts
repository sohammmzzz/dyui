/**
 * Chart palette guard (SPEC §1.3): slots 5–6 must stay distinguishable from every
 * other slot under colour-vision-deficiency simulation (Machado 2009, severity 1),
 * measured with CIEDE2000, for both the light and dark default accents.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

type Lab = [number, number, number];
const SIM: Record<string, number[][]> = {
  normal: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
  protan: [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
  deutan: [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.01182, 0.04294, 0.968881]],
  tritan: [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.3039]],
};
const lin = (c: number) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
function toLab(hex: string, mode: string): Lab {
  const rgb = [1, 3, 5].map((i) => lin(parseInt(hex.slice(i, i + 2), 16) / 255));
  const [r, g, b] = SIM[mode].map((row) => Math.min(1, Math.max(0, row[0] * rgb[0] + row[1] * rgb[1] + row[2] * rgb[2])));
  const [x, y, z] = [0.4124 * r + 0.3576 * g + 0.1805 * b, 0.2126 * r + 0.7152 * g + 0.0722 * b, 0.0193 * r + 0.1192 * g + 0.9505 * b];
  const f = (t: number) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
  const [fx, fy, fz] = [f(x / 0.95047), f(y), f(z / 1.08883)];
  return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
}
function de2000([L1, a1, b1]: Lab, [L2, a2, b2]: Lab): number {
  const rad = Math.PI / 180;
  const C1 = Math.hypot(a1, b1), C2 = Math.hypot(a2, b2), Cb = (C1 + C2) / 2;
  const G = 0.5 * (1 - Math.sqrt(Cb ** 7 / (Cb ** 7 + 25 ** 7)));
  const a1p = a1 * (1 + G), a2p = a2 * (1 + G);
  const C1p = Math.hypot(a1p, b1), C2p = Math.hypot(a2p, b2);
  const hue = (b: number, a: number) => { const x = Math.atan2(b, a) / rad; return x < 0 ? x + 360 : x; };
  const h1 = hue(b1, a1p), h2 = hue(b2, a2p);
  let dh = h2 - h1;
  if (C1p * C2p === 0) dh = 0; else if (dh > 180) dh -= 360; else if (dh < -180) dh += 360;
  const dL = L2 - L1, dC = C2p - C1p, dH = 2 * Math.sqrt(C1p * C2p) * Math.sin((dh / 2) * rad);
  const Lb = (L1 + L2) / 2, Cbp = (C1p + C2p) / 2;
  let hb = h1 + h2;
  if (C1p * C2p !== 0) hb = Math.abs(h1 - h2) > 180 ? (h1 + h2 + 360) / 2 : (h1 + h2) / 2;
  const T = 1 - 0.17 * Math.cos((hb - 30) * rad) + 0.24 * Math.cos(2 * hb * rad) + 0.32 * Math.cos((3 * hb + 6) * rad) - 0.2 * Math.cos((4 * hb - 63) * rad);
  const dTh = 30 * Math.exp(-(((hb - 275) / 25) ** 2));
  const RC = 2 * Math.sqrt(Cbp ** 7 / (Cbp ** 7 + 25 ** 7));
  const SL = 1 + (0.015 * (Lb - 50) ** 2) / Math.sqrt(20 + (Lb - 50) ** 2), SC = 1 + 0.045 * Cbp, SH = 1 + 0.015 * Cbp * T;
  const RT = -Math.sin(2 * dTh * rad) * RC;
  return Math.sqrt((dL / SL) ** 2 + (dC / SC) ** 2 + (dH / SH) ** 2 + RT * (dC / SC) * (dH / SH));
}

const css = readFileSync(resolve(__dirname, "tokens.css"), "utf8");
const token = (name: string) => {
  const m = css.match(new RegExp(`--dy-chart-${name}:\\s*(#[0-9a-fA-F]{6})`));
  return m ? m[1] : null;
};
// slots 1–2 follow the accent/teal tokens; use the default light and dark values
const LIGHT_HEAD = ["#5B4FE0", "#14A394"];
const DARK_HEAD = ["#8B80FF", "#3DD6C3"];
const rest = [3, 4, 5, 6, 7, 8].map((n) => token(String(n)));

describe("chart palette", () => {
  it("defines slots 3–8 as hex colours", () => {
    expect(rest.every(Boolean)).toBe(true);
  });

  for (const [theme, head] of [["light", LIGHT_HEAD], ["dark", DARK_HEAD]] as const) {
    it(`slots 5–6 are separable under CVD simulation (${theme})`, () => {
      const pal = [...head, ...(rest as string[])];
      let worst = Infinity;
      let where = "";
      for (const mode of Object.keys(SIM))
        for (const i of [4, 5])
          pal.forEach((c, j) => {
            if (j === i || (j === 4 && i === 5)) return;
            const d = de2000(toLab(pal[i], mode), toLab(c, mode));
            if (d < worst) [worst, where] = [d, `${mode} ${i + 1}-${j + 1}`];
          });
      expect(worst, `closest pair: ${where}`).toBeGreaterThanOrEqual(9.5);
    });
  }
});
