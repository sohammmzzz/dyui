import { useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { dur, ease, spring } from "../../../lib/motion";
import { NodeList } from "../NodeView";
import { AutoHeight, Bloom } from "../util/motion";
import { Prose } from "../util/Markdown";
import { arr, childNodes, isObj, optStr, str } from "../util/props";
import { Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import "../styles/layout.css";

/** `tabs` — segmented tabs with a sliding indicator; each tab holds nodes. */
export function Tabs({ node, ctx }: DyProps) {
  const raw = arr(node.props.tabs ?? node.props.items).filter(isObj);
  const tabs = raw.map((t, i) => ({
    label: str(t.label ?? t.title) || `Tab ${i + 1}`,
    nodes: childNodes(t.children ?? t.content, `${node.id}.t${i}`, node.status === "streaming" && i === raw.length - 1 ? "streaming" : undefined),
    text: optStr(t.text),
  }));
  const [active, setActive] = useState(0);
  const cur = Math.min(active, Math.max(0, tabs.length - 1));
  const listRef = useRef<HTMLDivElement>(null);
  const [ind, setInd] = useState<{ x: number; w: number } | null>(null);
  const reduced = useReducedMotion();

  useLayoutEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const measure = () => {
      const b = list.querySelectorAll<HTMLElement>("[role=tab]")[cur];
      if (b) setInd({ x: b.offsetLeft, w: b.offsetWidth });
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(measure);
    ro.observe(list);
    return () => ro.disconnect();
  }, [cur, tabs.length, tabs.map((t) => t.label).join("|")]); // eslint-disable-line react-hooks/exhaustive-deps

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const n = tabs.length;
    let next = cur;
    if (e.key === "ArrowRight") next = (cur + 1) % n;
    else if (e.key === "ArrowLeft") next = (cur - 1 + n) % n;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = n - 1;
    else return;
    e.preventDefault();
    setActive(next);
    listRef.current?.querySelectorAll<HTMLElement>("[role=tab]")[next]?.focus();
  };

  const tab = tabs[cur];
  return (
    <Bloom className="dy-c dy-tabs" data-dy-ui="tabs">
      <div className="dy-tablist-scroll">
        <div ref={listRef} className="dy-tablist" role="tablist" onKeyDown={onKey}>
          {ind && (
            <motion.span
              className="dy-tab-ind"
              aria-hidden
              initial={false}
              animate={{ x: ind.x, width: ind.w }}
              transition={reduced ? { duration: 0 } : spring}
            />
          )}
          {tabs.map((t, i) => (
            <button
              key={i}
              type="button"
              role="tab"
              id={`${node.id}-tab-${i}`}
              aria-selected={i === cur}
              aria-controls={`${node.id}-panel`}
              tabIndex={i === cur ? 0 : -1}
              className="dy-tab"
              onClick={() => setActive(i)}
            >
              {t.label}
            </button>
          ))}
          {tabs.length === 0 && <Skel w={180} h={28} style={{ borderRadius: 9 }} />}
        </div>
      </div>
      <div className="dy-tabpanel" role="tabpanel" id={`${node.id}-panel`} aria-labelledby={`${node.id}-tab-${cur}`}>
        <AutoHeight>
          <AnimatePresence mode="wait" initial={false}>
            {tab && (
              <motion.div
                key={cur}
                initial={reduced ? { opacity: 0 } : { opacity: 0, y: 6, filter: "blur(4px)" }}
                animate={reduced ? { opacity: 1 } : { opacity: 1, y: 0, filter: "blur(0px)", transitionEnd: { filter: "none" } }}
                exit={reduced ? { opacity: 0 } : { opacity: 0, y: -3, filter: "blur(2px)" }}
                transition={{ duration: dur[2], ease }}
              >
                {tab.nodes.length ? <NodeList nodes={tab.nodes} ctx={ctx} /> : tab.text ? <Prose text={tab.text} /> : null}
              </motion.div>
            )}
          </AnimatePresence>
        </AutoHeight>
      </div>
    </Bloom>
  );
}
