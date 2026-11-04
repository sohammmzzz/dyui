import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check, ChevronRight, CircleDashed, X } from "lucide-react";
import { dur, ease } from "../../../lib/motion";
import { Bloom } from "../util/motion";
import { formatDuration, optStr, str } from "../util/props";
import { Spinner } from "../util/ui";
import type { DyProps } from "../util/types";
import "../styles/agent.css";

export type StatusKind = "pending" | "running" | "active" | "done" | "error" | "skipped";

/** Status glyph shared by step & plan; cross-fades between states. */
export function StatusIcon({ status }: { status: StatusKind }) {
  return (
    <span className="dy-status" data-status={status} aria-hidden>
      <AnimatePresence initial={false} mode="popLayout">
        <motion.span
          key={status}
          className="dy-status-inner"
          initial={{ opacity: 0, scale: 0.5 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.5 }}
          transition={{ duration: dur[2], ease }}
        >
          {status === "done" ? (
            <Check width={11} height={11} strokeWidth={3} />
          ) : status === "error" ? (
            <X width={11} height={11} strokeWidth={3} />
          ) : status === "running" ? (
            <Spinner size={14} />
          ) : status === "active" ? (
            <span className="dy-status-dot dy-breathe" />
          ) : status === "skipped" ? (
            <span className="dy-status-dash" />
          ) : (
            <CircleDashed width={14} height={14} strokeWidth={1.8} />
          )}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}

const show = (v: unknown) => (typeof v === "string" ? v : JSON.stringify(v, null, 2));

/** `step` — a tool/agent step: pending → running → done / error, with input/output. */
export function Step({ node }: DyProps) {
  const p = node.props;
  const status: StatusKind = ["pending", "running", "done", "error"].includes(p.status) ? p.status : "pending";
  const title = str(p.title) || "Step";
  const type = optStr(p.type);
  const duration = formatDuration(p.duration_ms);
  const hasDetail = p.input !== undefined || p.output !== undefined;
  const [open, setOpen] = useState(false);
  return (
    <Bloom className="dy-c dy-step" data-dy-ui="step" data-status={status}>
      <button type="button" className="dy-step-row" onClick={() => hasDetail && setOpen((o) => !o)} aria-expanded={hasDetail ? open : undefined} disabled={!hasDetail}>
        <StatusIcon status={status} />
        <span className={status === "running" ? "dy-step-title dy-text-shimmer" : "dy-step-title"}>{title}</span>
        {type && <span className="dy-step-type">{type}</span>}
        <span className="dy-step-meta">{status === "error" ? "Failed" : duration ?? (status === "running" ? "Running" : "")}</span>
        {hasDetail && <ChevronRight className="dy-step-chev" width={14} height={14} aria-hidden />}
      </button>
      <AnimatePresence initial={false}>
        {open && hasDetail && (
          <motion.div className="dy-step-detail" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: dur[3], ease }}>
            <div className="dy-step-io">
              {p.input !== undefined && (
                <div>
                  <div className="dy-eyebrow">Input</div>
                  <pre>{show(p.input)}</pre>
                </div>
              )}
              {p.output !== undefined && (
                <div>
                  <div className="dy-eyebrow">Output</div>
                  <pre>{show(p.output)}</pre>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Bloom>
  );
}
