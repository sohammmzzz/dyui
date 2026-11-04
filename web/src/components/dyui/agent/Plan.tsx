import { motion } from "motion/react";
import { ease } from "../../../lib/motion";
import { Bloom } from "../util/motion";
import { arr, isObj, optStr, str } from "../util/props";
import { Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import { StatusIcon, type StatusKind } from "./Step";
import "../styles/agent.css";

/** `plan` — a live checklist; status changes cross-fade in place. */
export function Plan({ node }: DyProps) {
  const items = arr(node.props.items)
    .filter(isObj)
    .map((it) => ({
      title: str(it.title ?? it.label),
      status: (["pending", "active", "done", "error", "skipped"].includes(it.status) ? it.status : "pending") as StatusKind,
    }));
  const title = optStr(node.props.title) ?? "Plan";
  const done = items.filter((i) => i.status === "done" || i.status === "skipped").length;
  const pct = items.length ? done / items.length : 0;
  return (
    <Bloom className="dy-c dy-plan dy-panel" data-dy-ui="plan">
      <div className="dy-plan-head">
        <div className="dy-plan-title">{title}</div>
        <span className="dy-plan-count">
          {done} of {items.length}
        </span>
      </div>
      <div className="dy-plan-bar" aria-hidden>
        <motion.span initial={{ scaleX: 0 }} animate={{ scaleX: pct }} transition={{ duration: 0.7, ease }} />
      </div>
      <ol className="dy-plan-list">
        {items.map((it, i) => (
          <li key={i} className="dy-plan-item dy-a-rise" data-status={it.status} style={{ ["--i" as any]: i }} aria-current={it.status === "active" ? "step" : undefined}>
            <StatusIcon status={it.status} />
            <span className="dy-plan-text">{it.title || <Skel w={160} h={10} />}</span>
            <span className="dy-sr">{it.status}</span>
          </li>
        ))}
      </ol>
    </Bloom>
  );
}
