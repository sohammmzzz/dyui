/**
 * Shell-rendered parts: live steps, collapsible reasoning, file chips, and the
 * wrapper that blooms every `ui` part into place through the component library.
 */
import { isInlineSafe } from "@/lib/api";
import { safeLink } from "@/lib/url";
import { Component, memo, useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Brain, ChevronRight, FileText, FileImage, FileArchive, FileCode, FileSpreadsheet, File as FileIcon, X, Check, CircleAlert } from "lucide-react";
import { NodeView } from "@/components/dyui";
import type { FileRef, NodeContext, Step, UINode } from "@/lib/types";
import { toMs } from "@/lib/store";
import { collapse, collapseReduced, cx, useMotionKit } from "./anim";

/* --------------------------------------------------------------- utilities */

export function formatDuration(ms: number | undefined | null): string {
  if (ms === undefined || ms === null || !Number.isFinite(ms)) return "";
  if (ms < 1000) return `${Math.max(0, Math.round(ms / 10) * 10)} ms`;
  const s = ms / 1000;
  if (s < 10) return `${s.toFixed(1)}s`;
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${Math.round(s % 60)}s`;
}

export function formatBytes(n: number): string {
  if (!Number.isFinite(n) || n < 0) return "";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / 1024 / 1024).toFixed(n < 10 * 1024 * 1024 ? 1 : 0)} MB`;
}

export function fileKind(type: string, name: string): string {
  const ext = name.split(".").pop()?.toUpperCase() ?? "";
  if (ext && ext.length <= 5 && ext !== name.toUpperCase()) return ext;
  const sub = type.split("/")[1];
  return (sub || "File").toUpperCase().slice(0, 6);
}

function fileIcon(type: string, name: string) {
  if (type.startsWith("image/")) return FileImage;
  if (/zip|tar|gzip|compressed/.test(type)) return FileArchive;
  if (/csv|sheet|excel/.test(type) || /\.(csv|xlsx?)$/i.test(name)) return FileSpreadsheet;
  if (/json|javascript|typescript|python|x-sh|xml/.test(type) || /\.(py|js|ts|json|sh|go|rs)$/i.test(name)) return FileCode;
  if (/pdf|text|word|document/.test(type)) return FileText;
  return FileIcon;
}

/** Re-render every `ms` while `on` (live durations). */
function useTicker(on: boolean, ms = 100) {
  const [, setT] = useState(0);
  useEffect(() => {
    if (!on) return;
    const t = setInterval(() => setT((x) => x + 1), ms);
    return () => clearInterval(t);
  }, [on, ms]);
}

/* ------------------------------------------------------------------- steps */

function StepIcon({ status }: { status: Step["status"] }) {
  const m = useMotionKit();
  return (
    <span className={cx("sh-step-icon", `is-${status}`)} aria-hidden="true">
      <AnimatePresence initial={false} mode="popLayout">
        <motion.span
          key={status}
          className="sh-step-glyph"
          initial={m.reduced ? { opacity: 0 } : { opacity: 0, scale: 0.6 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={m.reduced ? { opacity: 0 } : { opacity: 0, scale: 0.6 }}
          transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
        >
          {status === "running" && <span className="sh-spinner" />}
          {status === "pending" && <span className="sh-step-dot" />}
          {status === "done" && <Check size={11} strokeWidth={3} />}
          {status === "error" && <X size={11} strokeWidth={3} />}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}

function pretty(v: unknown): string {
  if (typeof v === "string") return v;
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

const StepRow = memo(function StepRow({ step, depth }: { step: Step; depth: number }) {
  const m = useMotionKit();
  const [open, setOpen] = useState(false);
  const id = useId();
  const running = step.status === "running";
  useTicker(running, 100);
  const started = toMs(step.started_at);
  const elapsed = step.duration_ms ?? (running && started ? Date.now() - started : undefined);
  const hasDetail = step.input !== undefined || step.output !== undefined || (step.logs?.length ?? 0) > 0;
  const statusText = { pending: "Pending", running: "Running", done: "Done", error: "Failed" }[step.status];
  return (
    <motion.li className={cx("sh-step", `is-${step.status}`)} style={{ "--depth": depth } as React.CSSProperties} variants={m.rise} initial="hidden" animate="show">
      <button
        type="button"
        className="sh-step-row"
        onClick={() => hasDetail && setOpen((o) => !o)}
        aria-expanded={hasDetail ? open : undefined}
        aria-controls={hasDetail ? id : undefined}
        disabled={!hasDetail}
      >
        <StepIcon status={step.status} />
        <span className={cx("sh-step-title", running && "sh-shimmer-text")}>{step.title}</span>
        <span className="sr-only">{statusText}</span>
        {step.type && step.type !== "tool" && <span className="sh-step-type">{step.type}</span>}
        <span className="sh-step-time">{elapsed !== undefined ? formatDuration(elapsed) : ""}</span>
        {hasDetail ? <ChevronRight className="sh-step-chev" size={14} aria-hidden="true" /> : <span className="sh-step-chev" />}
      </button>
      <AnimatePresence initial={false}>
        {open && hasDetail && (
          <motion.div
            id={id}
            className="sh-step-detail"
            variants={m.reduced ? collapseReduced : collapse}
            initial="closed"
            animate="open"
            exit="closed"
          >
            <div className="sh-step-detail-inner">
              {step.input !== undefined && (
                <div>
                  <div className="sh-eyebrow">Input</div>
                  <pre>{pretty(step.input)}</pre>
                </div>
              )}
              {(step.logs?.length ?? 0) > 0 && (
                <div>
                  <div className="sh-eyebrow">Log</div>
                  <pre>{step.logs!.join("\n")}</pre>
                </div>
              )}
              {step.output !== undefined && (
                <div>
                  <div className="sh-eyebrow">{step.status === "error" ? "Error" : "Output"}</div>
                  <pre>{pretty(step.output)}</pre>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.li>
  );
});

/** A run of consecutive step parts, nested by parent_id. */
export function StepGroup({ steps }: { steps: Step[] }) {
  const ordered = useMemo(() => {
    const ids = new Set(steps.map((s) => s.id));
    const kids = new Map<string, Step[]>();
    const roots: Step[] = [];
    for (const s of steps) {
      if (s.parent_id && ids.has(s.parent_id)) {
        const arr = kids.get(s.parent_id) ?? [];
        arr.push(s);
        kids.set(s.parent_id, arr);
      } else roots.push(s);
    }
    const out: { step: Step; depth: number }[] = [];
    const walk = (s: Step, d: number) => {
      out.push({ step: s, depth: Math.min(d, 3) });
      for (const k of kids.get(s.id) ?? []) walk(k, d + 1);
    };
    roots.forEach((r) => walk(r, 0));
    return out;
  }, [steps]);
  const doneCount = steps.filter((s) => s.status === "done").length;
  return (
    <ol className="sh-steps" aria-label={`Steps, ${doneCount} of ${steps.length} done`}>
      {ordered.map(({ step, depth }) => (
        <StepRow key={step.id} step={step} depth={depth} />
      ))}
    </ol>
  );
}

/* --------------------------------------------------------------- reasoning */

export const Reasoning = memo(function Reasoning({
  text,
  active,
  durationMs,
}: {
  text: string;
  active: boolean;
  durationMs?: number;
}) {
  const m = useMotionKit();
  const id = useId();
  const [open, setOpen] = useState(active);
  const startedAt = useRef<number | null>(active ? Date.now() : null);
  const [measured, setMeasured] = useState<number | undefined>(undefined);
  const wasActive = useRef(active);
  useEffect(() => {
    if (active && startedAt.current === null) startedAt.current = Date.now();
    if (wasActive.current && !active) {
      if (startedAt.current) setMeasured(Date.now() - startedAt.current);
      setOpen(false); // settle closed once the answer starts
    }
    if (active) setOpen(true);
    wasActive.current = active;
  }, [active]);
  const ms = durationMs ?? measured;
  const label = active ? "Thinking" : ms && ms >= 1000 ? `Thought for ${formatDuration(ms)}` : "Thoughts";
  return (
    <div className={cx("sh-reason", active && "is-active", open && "is-open")}>
      <button type="button" className="sh-reason-head" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-controls={id}>
        <Brain size={14} strokeWidth={1.9} aria-hidden="true" className={active ? "sh-breathe" : undefined} />
        <span className={active ? "sh-shimmer-text" : undefined}>{label}</span>
        <ChevronRight size={13} className="sh-reason-chev" aria-hidden="true" />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div id={id} className="sh-reason-wrap" variants={m.reduced ? collapseReduced : collapse} initial="closed" animate="open" exit="closed">
            <div className={cx("sh-reason-body", active && "is-live")}>
              <div className="sh-reason-text">{text.trim()}</div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
});

/* ------------------------------------------------------------------- files */

export function FileChip({ file, compact = false }: { file: FileRef; compact?: boolean }) {
  const Icon = fileIcon(file.type, file.name);
  // Only types the server serves inline open in a tab (and get a thumbnail);
  // HTML/SVG/scripts/etc. are served as attachments, so they download.
  const inline = isInlineSafe(file.type);
  const href = safeLink(file.url) ?? undefined;
  // the thumbnail uses the vetted URL too (never the raw one)
  const isImage = inline && file.type.startsWith("image/") && !!href;
  return (
    <a
      className={cx("sh-file", compact && "is-compact")}
      href={href}
      {...(inline ? { target: "_blank", rel: "noopener noreferrer" } : { download: file.name })}
      title={inline ? file.name : `Download ${file.name}`}
    >
      <span className="sh-file-icon">
        {isImage ? <img src={href} alt="" loading="lazy" /> : <Icon size={16} strokeWidth={1.8} aria-hidden="true" />}
      </span>
      <span className="sh-file-text">
        <span className="sh-file-name">{file.name}</span>
        <span className="sh-file-meta">
          {fileKind(file.type, file.name)}
          {file.size ? ` · ${formatBytes(file.size)}` : ""}
        </span>
      </span>
    </a>
  );
}

/* ---------------------------------------------------------------------- ui */

class NodeBoundary extends Component<{ children: ReactNode; node: UINode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  componentDidUpdate(prev: { node: UINode }) {
    if (this.state.error && prev.node !== this.props.node) this.setState({ error: null });
  }
  componentDidCatch(error: Error) {
    console.warn(`[dyui] component "${this.props.node.ui}" failed to render`, error);
  }
  render() {
    if (this.state.error)
      return (
        <div className="sh-node-error" role="note">
          <CircleAlert size={14} aria-hidden="true" />
          <span>Couldn’t display this {this.props.node.ui.replace(/_/g, " ")}</span>
        </div>
      );
    return this.props.children;
  }
}

export const UIPart = memo(function UIPart({ node, ctx }: { node: UINode; ctx: NodeContext }) {
  const m = useMotionKit();
  return (
    <motion.div className="sh-part-ui" variants={m.bloom} initial="hidden" animate="show">
      <NodeBoundary node={node}>
        <NodeView node={node} ctx={ctx} />
      </NodeBoundary>
    </motion.div>
  );
});
