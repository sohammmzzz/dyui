import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ChevronDown, CircleAlert } from "lucide-react";
import { dur, ease } from "../../../lib/motion";
import { Bloom } from "../util/motion";
import { str } from "../util/props";
import type { DyProps } from "../util/types";
import "../styles/agent.css";

/** `invalid` — a quiet, collapsible chip; prose is never lost and details stay available. */
export function Invalid({ node }: DyProps) {
  const [open, setOpen] = useState(false);
  const p = node.props ?? {};
  const error = str(p.error) || node.error || "This component could not be displayed.";
  const raw = p.raw ?? (node.ui !== "invalid" ? { ui: node.ui, ...p } : undefined);
  const rawText = typeof raw === "string" ? raw : raw === undefined ? "" : JSON.stringify(raw, null, 2);
  return (
    <Bloom className="dy-c dy-invalid" data-dy-ui="invalid" data-open={open || undefined}>
      <button type="button" className="dy-invalid-chip" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <CircleAlert width={14} height={14} aria-hidden />
        <span>Couldn't display this component</span>
        <ChevronDown className="dy-invalid-chev" width={14} height={14} aria-hidden />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: dur[2], ease }} style={{ overflow: "hidden" }}>
            <div className="dy-invalid-detail">
              <div className="dy-invalid-err">{error}</div>
              {rawText && <pre>{rawText}</pre>}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Bloom>
  );
}
