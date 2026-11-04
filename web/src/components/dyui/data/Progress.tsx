import { motion, useReducedMotion } from "motion/react";
import { Check } from "lucide-react";
import { ease } from "../../../lib/motion";
import { Bloom, useBloomDelay } from "../util/motion";
import { useCountUp } from "../util/hooks";
import { fmtNum, num, optStr } from "../util/props";
import type { DyProps } from "../util/types";
import "../styles/data.css";

/** `progress` — a calm meter that fills from zero. */
export function Progress({ node }: DyProps) {
  const p = node.props;
  const value = num(p.value);
  const max = num(p.max) && num(p.max)! > 0 ? num(p.max)! : 100;
  const label = optStr(p.label);
  const streaming = node.status === "streaming";
  const pct = value === undefined ? 0 : Math.max(0, Math.min(1, value / max));
  const reduced = useReducedMotion();
  const delay = useBloomDelay() + 0.15;
  const shownPct = useCountUp(value === undefined ? null : pct * 100, { duration: 900, delay: delay * 1000 });
  const complete = value !== undefined && pct >= 1;
  const valText = value === undefined ? "" : max === 100 ? `${Math.round(shownPct ?? pct * 100)}%` : `${fmtNum(value)} / ${fmtNum(max)}`;
  return (
    <Bloom className="dy-c dy-progress dy-panel" data-dy-ui="progress" data-complete={complete || undefined}>
      {(label || valText) && (
        <div className="dy-progress-top">
          <span className="dy-progress-label">{label}</span>
          <span className="dy-progress-val">
            {complete && (
              <span className="dy-progress-done dy-a-pop" style={{ ["--d" as any]: "900ms" }}>
                <Check width={14} height={14} strokeWidth={2.6} />
              </span>
            )}
            {valText}
          </span>
        </div>
      )}
      <div
        className="dy-progress-track"
        role="progressbar"
        aria-label={label || "Progress"}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
        data-indeterminate={value === undefined && streaming ? "" : undefined}
      >
        {value === undefined && streaming ? (
          <span className="dy-progress-fill" />
        ) : (
          <motion.span
            className="dy-progress-fill"
            initial={{ scaleX: 0 }}
            animate={{ scaleX: pct }}
            transition={{ duration: reduced ? 0.12 : 0.9, ease, delay: reduced ? 0 : delay }}
          />
        )}
      </div>
    </Bloom>
  );
}
