/** Small shared primitives: skeletons, spinner, buttons, resolved note. */
import { forwardRef, type ButtonHTMLAttributes, type CSSProperties, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check, LoaderCircle } from "lucide-react";
import { dur, ease } from "../../../lib/motion";
import { cx } from "./props";
import "../styles/base.css";

export function Skel({ w, h, className, round, style }: { w?: number | string; h?: number | string; className?: string; round?: boolean; style?: CSSProperties }) {
  return <span aria-hidden className={cx("dy-skel", round && "dy-skel--round", className)} style={{ width: w, height: h, ...style }} />;
}

/** A few lines of text skeleton with natural, varied widths. */
export function SkelLines({ lines = 3, gap = 9, h = 11 }: { lines?: number; gap?: number; h?: number }) {
  const widths = ["92%", "78%", "86%", "64%", "72%"];
  return (
    <span aria-hidden style={{ display: "flex", flexDirection: "column", gap }}>
      {Array.from({ length: lines }, (_, i) => (
        <Skel key={i} w={i === lines - 1 ? "48%" : widths[i % widths.length]} h={h} />
      ))}
    </span>
  );
}

export function Spinner({ size = 15, className }: { size?: number; className?: string }) {
  return <LoaderCircle aria-hidden width={size} height={size} className={cx("dy-spin", className)} strokeWidth={2.2} />;
}

export type BtnStyle = "primary" | "secondary" | "ghost" | "danger";
export const btnStyle = (s: unknown, fallback: BtnStyle = "secondary"): BtnStyle =>
  s === "primary" || s === "secondary" || s === "ghost" || s === "danger" ? s : fallback;

type DyBtnProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: BtnStyle;
  size?: "sm" | "md";
  icon?: ReactNode;
  /** visual state inside an interactive group */
  state?: "idle" | "sending" | "chosen" | "dim";
};

/** Button with an icon slot that cross-fades to a spinner (sending) or a check (chosen). */
export const DyButton = forwardRef<HTMLButtonElement, DyBtnProps>(function DyButton(
  { variant = "secondary", size = "md", icon, state = "idle", className, children, disabled, ...rest },
  ref,
) {
  const lead = state === "sending" ? "spin" : state === "chosen" ? "check" : icon ? "icon" : null;
  return (
    <button
      ref={ref}
      type="button"
      className={cx("dy-btn", `dy-btn--${state === "chosen" ? "secondary" : variant}`, size === "sm" && "dy-btn--sm", className)}
      data-state={state === "idle" ? undefined : state}
      aria-busy={state === "sending" || undefined}
      disabled={disabled}
      {...rest}
    >
      <AnimatePresence initial={false} mode="popLayout">
        {lead && (
          <motion.span
            key={lead}
            style={{ display: "inline-flex" }}
            initial={{ opacity: 0, scale: 0.6 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.6 }}
            transition={{ duration: dur[2], ease }}
          >
            {lead === "spin" ? <Spinner size={size === "sm" ? 14 : 15} /> : lead === "check" ? <Check strokeWidth={2.4} /> : icon}
          </motion.span>
        )}
      </AnimatePresence>
      {children}
    </button>
  );
});

/** A calm confirmation line shown once an interactive component resolves. */
export function ResolvedNote({ label, tone = "success", sending, children }: { label?: ReactNode; tone?: "success" | "muted" | "danger"; sending?: boolean; children?: ReactNode }) {
  return (
    <motion.div
      className={cx("dy-resolved", `dy-resolved--${tone}`)}
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: dur[2], ease }}
      role="status"
    >
      <span className="dy-resolved-icon">
        <AnimatePresence initial={false} mode="popLayout">
          {sending ? (
            <motion.span key="s" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, scale: 0.6 }}>
              <Spinner size={13} />
            </motion.span>
          ) : (
            <motion.span key="c" initial={{ opacity: 0, scale: 0.5 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: dur[2], ease }}>
              {children ?? <Check width={13} height={13} strokeWidth={2.6} />}
            </motion.span>
          )}
        </AnimatePresence>
      </span>
      <span className="dy-resolved-label">{sending ? "Sending…" : label}</span>
    </motion.div>
  );
}
