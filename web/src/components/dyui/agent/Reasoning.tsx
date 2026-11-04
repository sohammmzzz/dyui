import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ChevronRight, Sparkles } from "lucide-react";
import { dur, ease } from "../../../lib/motion";
import { Bloom } from "../util/motion";
import { Prose } from "../util/Markdown";
import { formatDuration, str } from "../util/props";
import type { DyProps } from "../util/types";
import "../styles/agent.css";

/** `reasoning` — collapsible "thinking"; open while streaming. */
export function Reasoning({ node }: DyProps) {
  const text = str(node.props.text);
  const streaming = node.status === "streaming";
  const d = formatDuration(node.props.duration_ms);
  const [open, setOpen] = useState<boolean | null>(null);
  const isOpen = open ?? streaming;
  return (
    <Bloom className="dy-c dy-reasoning" data-dy-ui="reasoning" data-open={isOpen || undefined}>
      <button type="button" className="dy-reasoning-head" aria-expanded={isOpen} onClick={() => setOpen(!isOpen)}>
        <Sparkles width={14} height={14} className={streaming ? "dy-breathe" : undefined} aria-hidden />
        <span className={streaming ? "dy-text-shimmer" : undefined}>{streaming ? "Thinking…" : d ? `Thought for ${d}` : "Reasoning"}</span>
        <ChevronRight className="dy-step-chev" width={14} height={14} aria-hidden />
      </button>
      <AnimatePresence initial={false}>
        {isOpen && text && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: dur[3], ease }} style={{ overflow: "hidden" }}>
            <div className="dy-reasoning-body">
              <Prose text={text} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Bloom>
  );
}
