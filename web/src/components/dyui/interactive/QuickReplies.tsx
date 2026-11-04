import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowUpRight, Check } from "lucide-react";
import { dur, ease } from "../../../lib/motion";
import { Bloom } from "../util/motion";
import { arr, isObj, str } from "../util/props";
import { Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import "../styles/interactive.css";

/** `quick_replies` — suggested replies; a click sends the text as the user's message. */
export function QuickReplies({ node, ctx }: DyProps) {
  const options = arr(node.props.options ?? node.props.items)
    .map((o) => (isObj(o) ? str(o.label ?? o.text) : str(o)))
    .filter(Boolean);
  const resolvedLabel = isObj(node.props.__resolved__) ? str(node.props.__resolved__.label) : "";
  const [chosen, setChosen] = useState<string | null>(null);
  const picked = resolvedLabel || chosen;
  const streaming = node.status === "streaming";
  const disabled = !!picked || ctx.interactive === false || streaming;
  return (
    <Bloom className="dy-c dy-qr" data-dy-ui="quick_replies" role="group" aria-label="Suggested replies">
      {options.map((o, i) => {
        const on = picked === o;
        return (
          <button
            key={i}
            type="button"
            className="dy-qr-chip dy-a-rise"
            style={{ ["--i" as any]: i }}
            data-state={on ? "chosen" : picked ? "dim" : undefined}
            disabled={disabled}
            onClick={() => {
              if (disabled) return;
              setChosen(o);
              ctx.onReply(o);
            }}
          >
            <span>{o}</span>
            <span className="dy-qr-icon" aria-hidden>
              <AnimatePresence initial={false} mode="popLayout">
                {on ? (
                  <motion.span key="c" initial={{ opacity: 0, scale: 0.5 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: dur[2], ease }}>
                    <Check width={13} height={13} strokeWidth={2.6} />
                  </motion.span>
                ) : (
                  <motion.span key="a" exit={{ opacity: 0, scale: 0.5 }}>
                    <ArrowUpRight width={13} height={13} />
                  </motion.span>
                )}
              </AnimatePresence>
            </span>
          </button>
        );
      })}
      {streaming && <Skel w={120} h={34} round />}
    </Bloom>
  );
}
