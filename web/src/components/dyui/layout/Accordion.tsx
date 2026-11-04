import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ChevronDown } from "lucide-react";
import { dur, ease } from "../../../lib/motion";
import { NodeList } from "../NodeView";
import { Bloom } from "../util/motion";
import { Prose } from "../util/Markdown";
import { arr, childNodes, isObj, optStr, str } from "../util/props";
import { Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import "../styles/layout.css";

/** `accordion` — expandable sections with smooth height. */
export function Accordion({ node, ctx }: DyProps) {
  const raw = arr(node.props.items).filter(isObj);
  const items = raw.map((it, i) => ({
    title: str(it.title ?? it.label),
    nodes: childNodes(it.children ?? it.content, `${node.id}.i${i}`, node.status === "streaming" && i === raw.length - 1 ? "streaming" : undefined),
    text: optStr(it.text ?? (typeof it.content === "string" ? it.content : undefined)),
  }));
  const [open, setOpen] = useState<number[]>([0]);
  const reduced = useReducedMotion();
  const toggle = (i: number) => setOpen((o) => (o.includes(i) ? o.filter((x) => x !== i) : [...o, i]));
  return (
    <Bloom className="dy-c dy-accordion dy-panel" data-dy-ui="accordion">
      {items.map((it, i) => {
        const isOpen = open.includes(i);
        const hid = `${node.id}-acc-${i}`;
        return (
          <div key={i} className="dy-acc-item dy-a-rise" data-open={isOpen || undefined} style={{ ["--i" as any]: i }}>
            <h3 className="dy-acc-h">
              <button type="button" id={`${hid}-h`} className="dy-acc-trigger" aria-expanded={isOpen} aria-controls={`${hid}-p`} onClick={() => toggle(i)}>
                <span className="dy-acc-title">{it.title || <Skel w={160} h={11} />}</span>
                <ChevronDown className="dy-acc-chev" width={16} height={16} aria-hidden />
              </button>
            </h3>
            <AnimatePresence initial={false}>
              {isOpen && (
                <motion.div
                  id={`${hid}-p`}
                  role="region"
                  aria-labelledby={`${hid}-h`}
                  className="dy-acc-panel"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: reduced ? 0.01 : dur[3], ease }}
                >
                  <div className="dy-acc-body">{it.nodes.length ? <NodeList nodes={it.nodes} ctx={ctx} /> : it.text ? <Prose text={it.text} /> : null}</div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        );
      })}
    </Bloom>
  );
}
