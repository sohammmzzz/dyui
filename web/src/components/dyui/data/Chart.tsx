/**
 * `chart` — hand-built SVG: bar / line / area / pie / donut / scatter.
 * Thin marks, 4px rounded data ends, 2px surface gaps, hairline grid, legend for 2+ series,
 * crosshair + tooltip, a table-view twin, responsive via ResizeObserver.
 * Bars grow from the baseline, lines draw left→right, pies sweep clockwise.
 */
import { useId, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { ChartColumn, Table2 } from "lucide-react";
import { Bloom } from "../util/motion";
import { svgId, useWidth } from "../util/hooks";
import { arr, bool, fmtNum, isObj, num, optStr, str } from "../util/props";
import { Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import { arcPath, barPath, monotonePath, niceTicks, textWidth } from "./chartMath";
import "../styles/data.css";
import "../styles/chart.css";

const KINDS = ["bar", "line", "area", "pie", "donut", "scatter"] as const;
type Kind = (typeof KINDS)[number];
const H = 248;

type Series = { name: string; idx: number; values: (number | null)[]; points: [number, number][] };
type Tip = { x: number; y: number; title?: string; rows: { color: string; name: string; value: string; shape: "line" | "box" | "dot" }[] };

const color = (idx: number) => `var(--dy-chart-${(idx % 8) + 1})`;

function makeFmt(unit?: string) {
  const u = unit?.trim();
  const prefix = u && /^[$€£¥₹]$/.test(u) ? u : "";
  const pct = u === "%";
  const suffix = u && !prefix ? (pct ? "%" : ` ${u}`) : "";
  const sign = (v: number) => (v < 0 ? "−" : "");
  return {
    value: (v: number) => `${sign(v)}${prefix}${fmtNum(Math.abs(v))}${suffix}`,
    tick: (v: number, compact: boolean) => `${sign(v)}${prefix}${fmtNum(Math.abs(v), { compact })}${pct ? "%" : ""}`,
    axisUnit: u && !prefix && !pct ? u : undefined,
  };
}

function readSeries(raw: unknown[]): Series[] {
  return raw.filter(isObj).map((s, i) => {
    const data = arr(s.data ?? s.values);
    const values: (number | null)[] = [];
    const points: [number, number][] = [];
    data.forEach((d, j) => {
      if (Array.isArray(d)) {
        const x = num(d[0]);
        const y = num(d[1]);
        if (x !== undefined && y !== undefined) points.push([x, y]);
        values.push(y ?? null);
      } else if (isObj(d)) {
        const x = num(d.x);
        const y = num(d.y ?? d.value);
        if (x !== undefined && y !== undefined) points.push([x, y]);
        values.push(y ?? null);
      } else {
        const v = num(d);
        values.push(v ?? null);
        if (v !== undefined) points.push([j, v]);
      }
    });
    return { name: str(s.name ?? s.label) || `Series ${i + 1}`, idx: i, values, points };
  });
}

/* ------------------------------------------------------------------ tooltip */
function Tooltip({ tip, width }: { tip: Tip | null; width: number }) {
  if (!tip) return null;
  const flip = tip.x > width * 0.62;
  return (
    <div
      className="dy-chart-tip"
      role="status"
      style={{ left: flip ? tip.x - 12 : tip.x + 12, top: tip.y, transform: flip ? "translateX(-100%)" : undefined }}
    >
      {tip.title && <div className="dy-chart-tip-title">{tip.title}</div>}
      {tip.rows.map((r, i) => (
        <div className="dy-chart-tip-row" key={i}>
          <span className={`dy-chart-key dy-chart-key--${r.shape}`} style={{ background: r.color }} />
          <span className="dy-chart-tip-val">{r.value}</span>
          <span className="dy-chart-tip-name">{r.name}</span>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ main */
export function Chart({ node }: DyProps) {
  const p = node.props;
  const streaming = node.status === "streaming";
  const kind: Kind = (KINDS as readonly string[]).includes(p.kind) ? p.kind : "bar";
  const isPie = kind === "pie" || kind === "donut";
  const title = optStr(p.title);
  const unit = optStr(p.unit);
  const stacked = bool(p.stacked);
  const labels = arr(p.labels).map((l) => str(l));
  const series = useMemo(() => readSeries(arr(p.series)), [p.series]);
  const fmt = useMemo(() => makeFmt(unit), [unit]);
  const wrapRef = useRef<HTMLDivElement>(null);
  const width = useWidth(wrapRef);
  const [hidden, setHidden] = useState<number[]>([]);
  const [view, setView] = useState<"chart" | "table">("chart");
  const uid = svgId(useId());
  const hasData = series.some((s) => s.values.some((v) => v !== null));
  const ready = !streaming && hasData;

  // pie slices: first series × labels, or one slice per single-value series
  const slices = useMemo(() => {
    if (!isPie) return [];
    let out: { label: string; value: number; idx: number }[] =
      series.length > 1 && series.every((s) => s.values.length <= 1)
        ? series.map((s, i) => ({ label: s.name, value: s.values[0] ?? 0, idx: i }))
        : (series[0]?.values ?? []).map((v, i) => ({ label: labels[i] ?? `Item ${i + 1}`, value: v ?? 0, idx: i }));
    out = out.filter((s) => s.value > 0);
    if (out.length > 8) {
      const sorted = [...out].sort((a, b) => b.value - a.value);
      const rest = sorted.slice(7).reduce((a, b) => a + b.value, 0);
      out = [...sorted.slice(0, 7), { label: "Other", value: rest, idx: 7 }];
    }
    return out;
  }, [isPie, series, labels]);

  const visible = series.filter((s) => !hidden.includes(s.idx));
  const singleName = series.length === 1 ? series[0].name : undefined;
  const eyebrow = title ?? singleName ?? (isPie ? "Breakdown" : "Chart");

  // headline: latest value for single-series line/area
  let headline: { value: string; label: string } | null = null;
  if ((kind === "line" || kind === "area") && visible.length === 1 && ready) {
    const vals = visible[0].values;
    for (let i = vals.length - 1; i >= 0; i--)
      if (vals[i] !== null) {
        headline = { value: fmt.value(vals[i]!), label: labels[i] ?? "" };
        break;
      }
  }

  const toggleSeries = (idx: number) =>
    setHidden((h) => (h.includes(idx) ? h.filter((x) => x !== idx) : series.length - h.length > 1 ? [...h, idx] : h));

  const legendShape = kind === "line" ? "line" : kind === "scatter" ? "dot" : "box";
  const showLegend = !isPie && series.length > 1;

  return (
    <Bloom className="dy-c dy-chart dy-panel" data-dy-ui="chart" data-kind={kind}>
      <div className="dy-chart-head">
        <div className="dy-chart-titles">
          <span className="dy-eyebrow">
            {eyebrow}
            {fmt.axisUnit && <span className="dy-chart-unit"> · {fmt.axisUnit}</span>}
          </span>
          {headline && (
            <div className="dy-chart-headline dy-a-fade" style={{ ["--d" as any]: "200ms" }}>
              <span className="dy-chart-headline-val">{headline.value}</span>
              {headline.label && <span className="dy-chart-headline-sub">{headline.label}</span>}
            </div>
          )}
        </div>
        {ready && (
          <button
            type="button"
            className="dy-copy dy-chart-view"
            onClick={() => setView((v) => (v === "chart" ? "table" : "chart"))}
            aria-pressed={view === "table"}
            aria-label={view === "chart" ? "Show as table" : "Show as chart"}
            title={view === "chart" ? "Show as table" : "Show as chart"}
          >
            {view === "chart" ? <Table2 width={15} height={15} /> : <ChartColumn width={15} height={15} />}
          </button>
        )}
      </div>

      {showLegend && view === "chart" && (
        <div className="dy-chart-legend" role="group" aria-label="Series">
          {series.map((s, i) => (
            <button
              key={s.idx}
              type="button"
              className="dy-chart-legend-item dy-a-rise"
              style={{ ["--i" as any]: i }}
              aria-pressed={!hidden.includes(s.idx)}
              onClick={() => toggleSeries(s.idx)}
            >
              <span className={`dy-chart-key dy-chart-key--${legendShape}`} style={{ background: color(s.idx) }} />
              {s.name}
            </button>
          ))}
        </div>
      )}

      <div ref={wrapRef} className="dy-chart-wrap">
        {!ready || width === null ? (
          streaming || width === null ? (
            <ChartSkeleton pie={isPie} />
          ) : (
            <div className="dy-chart-empty">No data to display</div>
          )
        ) : view === "table" ? (
          <ChartTable kind={kind} series={series} labels={labels} slices={slices} fmt={fmt} />
        ) : isPie ? (
          <Pie slices={slices} width={width} donut={kind === "donut"} fmt={fmt} uid={uid} />
        ) : kind === "scatter" ? (
          <Scatter series={visible} width={width} fmt={fmt} />
        ) : (
          <Cartesian kind={kind} series={visible} labels={labels} stacked={stacked} width={width} fmt={fmt} uid={uid} title={eyebrow} />
        )}
      </div>
    </Bloom>
  );
}

/* ------------------------------------------------------------------ skeleton / empty / table */
function ChartSkeleton({ pie }: { pie: boolean }) {
  if (pie)
    return (
      <div className="dy-chart-skel dy-chart-skel--pie" aria-hidden>
        <Skel w={170} h={170} round />
        <div style={{ display: "flex", flexDirection: "column", gap: 10, flex: 1, maxWidth: 220 }}>
          {[80, 64, 72, 52].map((w, i) => (
            <Skel key={i} w={`${w}%`} h={10} />
          ))}
        </div>
      </div>
    );
  const hs = [42, 64, 50, 78, 58, 86, 70];
  return (
    <div className="dy-chart-skel" aria-hidden style={{ height: H }}>
      {hs.map((h, i) => (
        <Skel key={i} h={`${h}%`} style={{ flex: 1, maxWidth: 24, borderRadius: "5px 5px 2px 2px" }} />
      ))}
    </div>
  );
}

function ChartTable({ kind, series, labels, slices, fmt }: { kind: Kind; series: Series[]; labels: string[]; slices: { label: string; value: number; idx: number }[]; fmt: ReturnType<typeof makeFmt> }) {
  if (kind === "pie" || kind === "donut") {
    const total = slices.reduce((a, b) => a + b.value, 0) || 1;
    return (
      <div className="dy-chart-table dy-a-fade">
        <table>
          <thead>
            <tr>
              <th>Label</th>
              <th className="is-num">Value</th>
              <th className="is-num">Share</th>
            </tr>
          </thead>
          <tbody>
            {slices.map((s) => (
              <tr key={s.idx}>
                <td>{s.label}</td>
                <td className="is-num">{fmt.value(s.value)}</td>
                <td className="is-num">{((s.value / total) * 100).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  if (kind === "scatter") {
    return (
      <div className="dy-chart-table dy-a-fade">
        <table>
          <thead>
            <tr>
              <th>Series</th>
              <th className="is-num">x</th>
              <th className="is-num">y</th>
            </tr>
          </thead>
          <tbody>
            {series.flatMap((s) =>
              s.points.map((pt, i) => (
                <tr key={`${s.idx}-${i}`}>
                  <td>{s.name}</td>
                  <td className="is-num">{fmtNum(pt[0])}</td>
                  <td className="is-num">{fmt.value(pt[1])}</td>
                </tr>
              )),
            )}
          </tbody>
        </table>
      </div>
    );
  }
  const n = Math.max(labels.length, ...series.map((s) => s.values.length));
  return (
    <div className="dy-chart-table dy-a-fade">
      <table>
        <thead>
          <tr>
            <th />
            {series.map((s) => (
              <th key={s.idx} className="is-num">
                {s.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: n }, (_, i) => (
            <tr key={i}>
              <td>{labels[i] ?? i + 1}</td>
              {series.map((s) => (
                <td key={s.idx} className="is-num">
                  {s.values[i] === null || s.values[i] === undefined ? "—" : fmt.value(s.values[i]!)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------------ bar / line / area */
function Cartesian({
  kind,
  series,
  labels,
  stacked,
  width,
  fmt,
  uid,
  title,
}: {
  kind: "bar" | "line" | "area";
  series: Series[];
  labels: string[];
  stacked: boolean;
  width: number;
  fmt: ReturnType<typeof makeFmt>;
  uid: string;
  title: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const n = Math.max(1, labels.length, ...series.map((s) => s.values.length));
  const stackMode = stacked && (kind === "bar" || kind === "area");

  // domain
  let lo = Infinity;
  let hi = -Infinity;
  for (let i = 0; i < n; i++) {
    let pos = 0;
    let neg = 0;
    for (const s of series) {
      const v = s.values[i];
      if (v === null || v === undefined) continue;
      if (stackMode) {
        if (v >= 0) pos += v;
        else neg += v;
        hi = Math.max(hi, pos);
        lo = Math.min(lo, neg);
      } else {
        hi = Math.max(hi, v);
        lo = Math.min(lo, v);
      }
    }
  }
  if (!Number.isFinite(lo)) {
    lo = 0;
    hi = 1;
  }
  const includeZero = kind !== "line" || (lo >= 0 && lo <= hi * 0.45) || hi <= 0;
  if (includeZero) {
    lo = Math.min(lo, 0);
    hi = Math.max(hi, 0);
  }
  const { lo: d0, hi: d1, ticks } = niceTicks(lo, hi, 4);
  const compact = Math.max(Math.abs(d0), Math.abs(d1)) >= 10000;
  const tickText = ticks.map((t) => fmt.tick(t, compact));
  const left = Math.max(...tickText.map((t) => textWidth(t, 11))) + 14;
  const right = 8;
  const top = 12;
  const bottom = 30;
  const plotW = Math.max(40, width - left - right);
  const plotH = H - top - bottom;
  const y = (v: number) => top + plotH * (1 - (v - d0) / (d1 - d0 || 1));
  const baseY = y(Math.max(d0, Math.min(0, d1)));

  const band = plotW / n;
  const inset = kind === "bar" ? 0 : 4;
  const cx = (i: number) => (kind === "bar" ? left + band * (i + 0.5) : left + inset + (n === 1 ? (plotW - 2 * inset) / 2 : ((plotW - 2 * inset) * i) / (n - 1)));
  const label = (i: number) => labels[i] ?? String(i + 1);

  // x labels: thin out to fit
  const short = (s: string) => (s.length > 14 ? s.slice(0, 13) + "…" : s);
  const maxLW = Math.max(...Array.from({ length: n }, (_, i) => textWidth(short(label(i)), 11.5)));
  const slots = Math.max(1, Math.floor(plotW / (maxLW + 14)));
  const step = Math.max(1, Math.ceil(n / slots));

  const tipFor = (i: number): Tip => ({
    x: cx(i),
    y: top,
    title: label(i),
    rows: series
      .filter((s) => s.values[i] !== null && s.values[i] !== undefined)
      .map((s) => ({ color: color(s.idx), name: s.name, value: fmt.value(s.values[i]!), shape: kind === "line" ? "line" : "box" })),
  });

  const onMove = (e: PointerEvent<SVGRectElement>) => {
    const r = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
    const px = e.clientX - r.left;
    let i: number;
    if (kind === "bar") i = Math.floor((px - left) / band);
    else i = Math.round(((px - left - inset) / (plotW - 2 * inset || 1)) * (n - 1));
    setHover(Math.max(0, Math.min(n - 1, i)));
  };
  const onKey = (e: KeyboardEvent<SVGSVGElement>) => {
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      setHover((h) => Math.max(0, Math.min(n - 1, (h ?? -1) + (e.key === "ArrowRight" ? 1 : -1))));
    } else if (e.key === "Escape") setHover(null);
  };

  // bars
  const gap = 2;
  const k = Math.max(1, series.length);
  const barW = stackMode ? Math.max(2, Math.min(24, band * 0.56)) : Math.max(2, Math.min(24, (band * 0.72 - (k - 1) * gap) / k));
  const groupW = stackMode ? barW : k * barW + (k - 1) * gap;

  // single-series bar: label the extreme only
  let maxI = -1;
  if (kind === "bar" && series.length === 1 && !stackMode) {
    let m = -Infinity;
    series[0].values.forEach((v, i) => {
      if (v !== null && v > m) {
        m = v;
        maxI = i;
      }
    });
  }

  // line/area geometry
  const lines = useMemo(() => {
    if (kind === "bar") return [];
    let cum: (number | null)[] = Array(n).fill(0);
    return series.map((s) => {
      const lower = cum.slice();
      const upper = Array.from({ length: n }, (_, i) => {
        const v = s.values[i];
        if (v === null || v === undefined) return null;
        return stackMode ? (lower[i] ?? 0) + v : v;
      });
      if (stackMode) cum = upper.map((u, i) => (u === null ? lower[i] : u));
      // runs of non-null points
      const runs: number[][] = [];
      let cur: number[] = [];
      upper.forEach((u, i) => {
        if (u === null) {
          if (cur.length) runs.push(cur);
          cur = [];
        } else cur.push(i);
      });
      if (cur.length) runs.push(cur);
      const lineD = runs.map((r) => monotonePath(r.map((i) => [cx(i), y(upper[i]!)]))).join("");
      const areaD = runs
        .map((r) => {
          const topPath = monotonePath(r.map((i) => [cx(i), y(upper[i]!)]));
          if (stackMode) {
            const back = monotonePath(r.slice().reverse().map((i) => [cx(i), y(lower[i] ?? 0)])).replace(/^M/, "L");
            return `${topPath}${back}Z`;
          }
          return `${topPath}L${cx(r[r.length - 1])},${baseY}L${cx(r[0])},${baseY}Z`;
        })
        .join("");
      const lastRun = runs[runs.length - 1];
      const end = lastRun ? lastRun[lastRun.length - 1] : -1;
      return { s, upper, lineD, areaD, end };
    });
  }, [kind, series, n, width, d0, d1, stackMode]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="dy-chart-plot" style={{ height: H }} onPointerLeave={() => setHover(null)}>
      <svg
        width={width}
        height={H}
        viewBox={`0 0 ${width} ${H}`}
        role="img"
        aria-label={`${title}: ${kind} chart of ${series.map((s) => s.name).join(", ")}`}
        tabIndex={0}
        onKeyDown={onKey}
        onFocus={() => setHover((h) => h ?? n - 1)}
        onBlur={() => setHover(null)}
      >
        <defs>
          {kind === "area" &&
            series.map((s) => (
              <linearGradient key={s.idx} id={`${uid}-g${s.idx}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" style={{ stopColor: color(s.idx), stopOpacity: stackMode ? 0.28 : 0.2 }} />
                <stop offset="1" style={{ stopColor: color(s.idx), stopOpacity: stackMode ? 0.1 : 0.02 }} />
              </linearGradient>
            ))}
          <clipPath id={`${uid}-reveal`}>
            <rect className="dy-chart-reveal" x={left - 6} y={0} width={plotW + 12} height={H} />
          </clipPath>
        </defs>

        {/* grid + y ticks */}
        <g className="dy-chart-grid" aria-hidden>
          {ticks.map((t, i) => (
            <g key={i}>
              <line x1={left} x2={left + plotW} y1={y(t)} y2={y(t)} className={t === 0 ? "is-zero" : undefined} />
              <text x={left - 10} y={y(t)} dy="0.34em" textAnchor="end">
                {tickText[i]}
              </text>
            </g>
          ))}
        </g>

        {/* x labels */}
        <g className="dy-chart-xlabels" aria-hidden>
          {Array.from({ length: n }, (_, i) => {
            if (i % step !== 0) return null;
            const t = short(label(i));
            const w = textWidth(t, 11.5);
            const x = Math.min(width - w / 2 - 2, Math.max(w / 2 + 2, cx(i)));
            return (
              <text key={i} x={x} y={H - 9} textAnchor="middle" className={hover === i ? "is-on" : undefined}>
                {t}
              </text>
            );
          })}
        </g>

        {/* hover band (bars) / crosshair (lines) */}
        {hover !== null && kind === "bar" && <rect className="dy-chart-band" x={cx(hover) - band / 2 + 2} y={top} width={Math.max(0, band - 4)} height={plotH} rx={7} />}
        {hover !== null && kind !== "bar" && <line className="dy-chart-cross" x1={cx(hover)} x2={cx(hover)} y1={top} y2={top + plotH} />}

        {kind === "bar" &&
          Array.from({ length: n }, (_, i) => {
            const x0 = cx(i) - groupW / 2;
            let pos = 0;
            let neg = 0;
            const vis = series.map((s) => s.values[i]).map((v) => (v === null || v === undefined ? 0 : v));
            const topPos = stackMode ? vis.reduce((acc, v, j) => (v > 0 ? j : acc), -1) : -1;
            const topNeg = stackMode ? vis.reduce((acc, v, j) => (v < 0 ? j : acc), -1) : -1;
            return (
              <g key={i} className="dy-chart-grow" style={{ transformOrigin: `${cx(i)}px ${baseY}px`, ["--i" as any]: i }} data-dim={hover !== null && hover !== i ? "" : undefined}>
                {series.map((s, j) => {
                  const v = vis[j];
                  if (!v) return null;
                  if (!stackMode) {
                    return <path key={s.idx} d={barPath(x0 + j * (barW + gap), baseY, y(v), barW)} style={{ fill: color(s.idx) }} />;
                  }
                  const a = v >= 0 ? pos : neg;
                  const b = a + v;
                  if (v >= 0) pos = b;
                  else neg = b;
                  const isEnd = v >= 0 ? j === topPos : j === topNeg;
                  const ya = y(a) + (a !== 0 ? (v >= 0 ? -1 : 1) : 0);
                  const yb = y(b) + (isEnd ? 0 : v >= 0 ? 1 : -1);
                  return <path key={s.idx} d={barPath(x0, ya, yb, barW, 4, isEnd)} style={{ fill: color(s.idx) }} />;
                })}
                {i === maxI && (
                  <text className="dy-chart-vlabel" x={cx(i)} y={y(series[0].values[i]!) - 7} textAnchor="middle">
                    {fmt.tick(series[0].values[i]!, compact)}
                  </text>
                )}
              </g>
            );
          })}

        {kind !== "bar" && (
          <g clipPath={`url(#${uid}-reveal)`}>
            {kind === "area" &&
              lines.map((l) => <path key={`a${l.s.idx}`} className="dy-chart-area" d={l.areaD} style={{ fill: `url(#${uid}-g${l.s.idx})` }} />)}
          </g>
        )}
        {kind !== "bar" &&
          lines.map((l) => (
            <path
              key={`l${l.s.idx}`}
              className="dy-chart-line"
              d={l.lineD}
              pathLength={1}
              style={{ stroke: color(l.s.idx), opacity: hover !== null ? 0.9 : 1 }}
            />
          ))}
        {kind !== "bar" &&
          hover === null &&
          lines.map((l) =>
            l.end >= 0 ? (
              <circle key={`e${l.s.idx}`} className="dy-chart-dot dy-a-pop" cx={cx(l.end)} cy={y(l.upper[l.end]!)} r={4} style={{ fill: color(l.s.idx), ["--d" as any]: "620ms" }} />
            ) : null,
          )}
        {kind !== "bar" &&
          hover !== null &&
          lines.map((l) =>
            l.upper[hover] !== null && l.upper[hover] !== undefined ? (
              <circle key={`h${l.s.idx}`} className="dy-chart-dot" cx={cx(hover)} cy={y(l.upper[hover]!)} r={4.5} style={{ fill: color(l.s.idx) }} />
            ) : null,
          )}

        {/* hit layer */}
        <rect x={left} y={top} width={plotW} height={plotH + bottom - 6} fill="transparent" onPointerMove={onMove} onPointerDown={onMove} />
      </svg>
      <Tooltip tip={hover !== null ? tipFor(hover) : null} width={width} />
    </div>
  );
}

/* ------------------------------------------------------------------ scatter */
function Scatter({ series, width, fmt }: { series: Series[]; width: number; fmt: ReturnType<typeof makeFmt> }) {
  const [hover, setHover] = useState<{ s: number; i: number } | null>(null);
  const all = series.flatMap((s) => s.points);
  const xs = all.map((p) => p[0]);
  const ys = all.map((p) => p[1]);
  const X = niceTicks(Math.min(...xs), Math.max(...xs), Math.max(2, Math.floor(width / 110)));
  const Y = niceTicks(Math.min(...ys), Math.max(...ys), 4);
  const compactY = Math.max(Math.abs(Y.lo), Math.abs(Y.hi)) >= 10000;
  const compactX = Math.max(Math.abs(X.lo), Math.abs(X.hi)) >= 10000;
  const yText = Y.ticks.map((t) => fmt.tick(t, compactY));
  const left = Math.max(...yText.map((t) => textWidth(t, 11))) + 14;
  const right = 14;
  const top = 12;
  const bottom = 30;
  const plotW = Math.max(40, width - left - right);
  const plotH = H - top - bottom;
  const sx = (v: number) => left + plotW * ((v - X.lo) / (X.hi - X.lo || 1));
  const sy = (v: number) => top + plotH * (1 - (v - Y.lo) / (Y.hi - Y.lo || 1));

  const onMove = (e: PointerEvent<SVGRectElement>) => {
    const r = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
    const px = e.clientX - r.left;
    const py = e.clientY - r.top;
    let best: { s: number; i: number } | null = null;
    let bd = 28 * 28;
    series.forEach((s, si) =>
      s.points.forEach((pt, i) => {
        const d = (sx(pt[0]) - px) ** 2 + (sy(pt[1]) - py) ** 2;
        if (d < bd) {
          bd = d;
          best = { s: si, i };
        }
      }),
    );
    setHover(best);
  };
  const hp = hover ? series[hover.s]?.points[hover.i] : null;
  let order = 0;
  return (
    <div className="dy-chart-plot" style={{ height: H }} onPointerLeave={() => setHover(null)}>
      <svg width={width} height={H} viewBox={`0 0 ${width} ${H}`} role="img" aria-label={`Scatter plot of ${series.map((s) => s.name).join(", ")}`}>
        <g className="dy-chart-grid" aria-hidden>
          {Y.ticks.map((t, i) => (
            <g key={i}>
              <line x1={left} x2={left + plotW} y1={sy(t)} y2={sy(t)} />
              <text x={left - 10} y={sy(t)} dy="0.34em" textAnchor="end">
                {yText[i]}
              </text>
            </g>
          ))}
        </g>
        <g className="dy-chart-xlabels" aria-hidden>
          {X.ticks.map((t, i) => (
            <text key={i} x={Math.min(width - 12, Math.max(12, sx(t)))} y={H - 9} textAnchor="middle">
              {fmtNum(t, { compact: compactX })}
            </text>
          ))}
        </g>
        {series.map((s) => (
          <g key={s.idx}>
            {s.points.map((pt, i) => (
              <circle
                key={i}
                className="dy-chart-dot dy-chart-pt dy-a-pop"
                cx={sx(pt[0])}
                cy={sy(pt[1])}
                r={hover && series[hover.s]?.idx === s.idx && hover.i === i ? 6.5 : 4.5}
                style={{ fill: color(s.idx), ["--d" as any]: `${Math.min(order++, 40) * 12}ms` }}
              />
            ))}
          </g>
        ))}
        <rect x={left - 8} y={top - 8} width={plotW + 16} height={plotH + 16} fill="transparent" onPointerMove={onMove} onPointerDown={onMove} />
      </svg>
      <Tooltip
        tip={
          hover && hp
            ? {
                x: sx(hp[0]),
                y: Math.max(0, sy(hp[1]) - 30),
                title: series[hover.s].name,
                rows: [
                  { color: color(series[hover.s].idx), name: "x", value: fmtNum(hp[0]), shape: "dot" },
                  { color: color(series[hover.s].idx), name: "y", value: fmt.value(hp[1]), shape: "dot" },
                ],
              }
            : null
        }
        width={width}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ pie / donut */
function Pie({ slices, width, donut, fmt, uid }: { slices: { label: string; value: number; idx: number }[]; width: number; donut: boolean; fmt: ReturnType<typeof makeFmt>; uid: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const total = slices.reduce((a, b) => a + b.value, 0) || 1;
  const side = width >= 430;
  const D = side ? 196 : Math.min(200, width - 24);
  const pad = 8;
  const S = D + pad * 2;
  const c = S / 2;
  const R = D / 2;
  const ir = donut ? R * 0.64 : 0;
  let a = 0;
  const arcs = slices.map((s) => {
    const a0 = a;
    const a1 = a + (s.value / total) * Math.PI * 2;
    a = a1;
    return { ...s, a0, a1, mid: (a0 + a1) / 2 };
  });
  const hs = hover !== null ? arcs.find((x) => x.idx === hover) : null;
  const centerVal = hs ? fmt.value(hs.value) : fmt.value(total);
  const centerLabel = hs ? `${((hs.value / total) * 100).toFixed(hs.value / total < 0.1 ? 1 : 0)}% · ${hs.label}` : "Total";
  const rm = R + pad;
  return (
    <div className="dy-chart-pie" data-layout={side ? "side" : "stack"} onPointerLeave={() => setHover(null)}>
      <div className="dy-chart-pie-fig" style={{ width: S, height: S }}>
        <svg width={S} height={S} viewBox={`0 0 ${S} ${S}`} role="img" aria-label={`${donut ? "Donut" : "Pie"} chart: ${slices.map((s) => `${s.label} ${fmt.value(s.value)}`).join(", ")}`}>
          <defs>
            <mask id={`${uid}-sweep`}>
              <circle className="dy-chart-sweep" cx={c} cy={c} r={rm / 2} fill="none" stroke="#fff" strokeWidth={rm} pathLength={1} transform={`rotate(-90 ${c} ${c})`} />
            </mask>
          </defs>
          <g mask={`url(#${uid}-sweep)`}>
            {arcs.map((s) => {
              const on = hover === s.idx;
              const dx = on ? Math.sin(s.mid) * 4 : 0;
              const dy = on ? -Math.cos(s.mid) * 4 : 0;
              return (
                <path
                  key={s.idx}
                  className="dy-chart-slice"
                  d={arcPath(c, c, R, ir, s.a0, s.a1)}
                  data-dim={hover !== null && !on ? "" : undefined}
                  style={{ fill: color(s.idx), transform: `translate(${dx}px, ${dy}px)` }}
                  onPointerEnter={() => setHover(s.idx)}
                />
              );
            })}
          </g>
        </svg>
        {donut && (
          <div className="dy-chart-center" aria-hidden>
            <span className="dy-chart-center-val">{centerVal}</span>
            <span className="dy-chart-center-label">{centerLabel}</span>
          </div>
        )}
      </div>
      <ul className="dy-chart-pie-legend">
        {arcs.map((s, i) => (
          <li key={s.idx} className="dy-a-rise" style={{ ["--i" as any]: i, ["--d" as any]: "120ms" }}>
            <button
              type="button"
              className="dy-chart-pie-row"
              data-on={hover === s.idx || undefined}
              data-dim={hover !== null && hover !== s.idx ? "" : undefined}
              onPointerEnter={() => setHover(s.idx)}
              onFocus={() => setHover(s.idx)}
              onBlur={() => setHover(null)}
            >
              <span className="dy-chart-key dy-chart-key--box" style={{ background: color(s.idx) }} />
              <span className="dy-chart-pie-label dy-ellipsis">{s.label}</span>
              <span className="dy-chart-pie-val">{fmt.value(s.value)}</span>
              <span className="dy-chart-pie-pct">{Math.round((s.value / total) * 100)}%</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

