import { ArrowDownRight, ArrowRight, ArrowUpRight } from "lucide-react";
import { Bloom, useBloomDelay } from "../util/motion";
import { useCountUp } from "../util/hooks";
import { formatSplit, optStr, splitNumeric, str } from "../util/props";
import { Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import "../styles/base.css";
import "../styles/data.css";

/** A number that counts up from zero into its original formatting ("$48.2k" stays "$48.2k"). */
export function CountUp({ value, settled = true, delay = 0, duration = 1100 }: { value: unknown; settled?: boolean; delay?: number; duration?: number }) {
  const split = splitNumeric(value);
  const final = typeof value === "number" && split ? formatSplit(split, value) : str(value);
  const v = useCountUp(settled && split ? split.value : null, { delay, duration });
  if (!split) return <>{final}</>;
  const shown = v === null || v === split.value ? final : formatSplit(split, v);
  return (
    <span className="dy-countup">
      <span className="dy-countup-ghost" aria-hidden>
        {final}
      </span>
      <span className="dy-countup-live" aria-hidden>
        {shown}
      </span>
      <span className="dy-sr">{final}</span>
    </span>
  );
}

export type Trend = "up" | "down" | "flat";
export function inferTrend(trend: unknown, delta?: string): Trend | undefined {
  if (trend === "up" || trend === "down" || trend === "flat") return trend;
  if (!delta) return undefined;
  const d = delta.trim();
  if (/^[+▲↑]/.test(d)) return "up";
  if (/^[-−–▼↓]/.test(d)) return "down";
  if (/^0(\.0+)?%?$/.test(d)) return "flat";
  return undefined;
}

export function Delta({ delta, trend }: { delta: string; trend?: Trend }) {
  const Icon = trend === "up" ? ArrowUpRight : trend === "down" ? ArrowDownRight : ArrowRight;
  return (
    <span className="dy-delta" data-trend={trend ?? "flat"}>
      <Icon strokeWidth={2.3} aria-hidden />
      {delta}
    </span>
  );
}

/** Label / value / delta stack shared by `stat` and `stats`. */
export function StatBody({ p, settled, delay = 0 }: { p: Record<string, any>; settled: boolean; delay?: number }) {
  const label = optStr(p.label);
  const value = p.value;
  const hasValue = value !== undefined && value !== null && value !== "";
  const unit = optStr(p.unit);
  const delta = optStr(p.delta);
  const help = optStr(p.help);
  const trend = inferTrend(p.trend, delta);
  return (
    <div className="dy-stat-body">
      <div className="dy-eyebrow dy-ellipsis">{label ?? <Skel w={80} h={9} />}</div>
      <div className="dy-stat-row">
        <span className="dy-stat-value">{hasValue && settled ? <CountUp value={value} delay={delay * 1000 + 120} /> : <Skel w={110} h={30} style={{ marginTop: 4, marginBottom: 3 }} />}</span>
        {unit && hasValue && settled && <span className="dy-stat-unit">{unit}</span>}
      </div>
      {(delta || help) && (
        <div className="dy-stat-foot">
          {delta && <Delta delta={delta} trend={trend} />}
          {help && <span className="dy-stat-help">{help}</span>}
        </div>
      )}
    </div>
  );
}

/** `stat` — one headline number that counts up. */
export function Stat({ node }: DyProps) {
  const delay = useBloomDelay();
  return (
    <Bloom className="dy-c dy-stat dy-panel" data-dy-ui="stat">
      <StatBody p={node.props} settled={node.status !== "streaming"} delay={delay} />
    </Bloom>
  );
}
