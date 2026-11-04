import { ChevronRight } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { Check } from "lucide-react";
import { dur, ease } from "../../../lib/motion";
import { BlurImage } from "../media/Image";
import { Bloom } from "../util/motion";
import { useInteraction } from "../util/hooks";
import { arr, isObj, optStr, safeMediaUrl, str } from "../util/props";
import { Skel, Spinner } from "../util/ui";
import type { DyProps } from "../util/types";
import "../styles/layout.css";

/** `list` — rows with optional thumbnail and meta; rows are clickable when they carry an action. */
export function List({ node, ctx }: DyProps) {
  const ia = useInteraction(node, ctx);
  const items = arr(node.props.items)
    .filter(isObj)
    .map((it) => ({
      title: str(it.title ?? it.label),
      subtitle: optStr(it.subtitle ?? it.description),
      image: safeMediaUrl(it.image),
      meta: optStr(it.meta),
      action: optStr(it.action),
      data: isObj(it.data) ? it.data : undefined,
    }));
  const anyImage = items.some((it) => it.image);
  const title = optStr(node.props.title);
  return (
    <Bloom className="dy-c dy-list dy-panel" data-dy-ui="list" data-state={ia.state}>
      {title && <div className="dy-list-title dy-eyebrow">{title}</div>}
      <ul>
        {items.map((it, i) => {
          const chosen = ia.resolved ? ia.resolved.label === it.title : ia.pending?.key === String(i);
          const dim = (ia.resolved || ia.pending) && !chosen;
          const inner = (
            <>
              {anyImage && (
                <span className="dy-row-img">
                  {it.image ? <BlurImage src={it.image} alt="" cover /> : <span className="dy-row-mono">{it.title.charAt(0)}</span>}
                </span>
              )}
              <span className="dy-row-main">
                <span className="dy-row-title">{it.title || <Skel w={140} h={10} />}</span>
                {it.subtitle && <span className="dy-row-sub dy-clamp-2">{it.subtitle}</span>}
              </span>
              {it.meta && <span className="dy-row-meta">{it.meta}</span>}
              {it.action && (
                <span className="dy-row-end" aria-hidden>
                  <AnimatePresence initial={false} mode="popLayout">
                    <motion.span
                      key={chosen ? (ia.resolved ? "c" : "s") : "a"}
                      initial={{ opacity: 0, scale: 0.6 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.6 }}
                      transition={{ duration: dur[2], ease }}
                      style={{ display: "inline-flex" }}
                    >
                      {chosen ? ia.resolved ? <Check width={16} height={16} strokeWidth={2.6} /> : <Spinner size={15} /> : <ChevronRight width={16} height={16} />}
                    </motion.span>
                  </AnimatePresence>
                </span>
              )}
            </>
          );
          return (
            <li key={i} className="dy-a-rise" style={{ ["--i" as any]: i }}>
              {it.action ? (
                <button
                  type="button"
                  className="dy-row"
                  data-clickable=""
                  data-chosen={chosen || undefined}
                  data-dim={dim || undefined}
                  disabled={ia.disabled}
                  onClick={() => ia.fire({ action: it.action!, label: it.title, data: it.data }, String(i))}
                >
                  {inner}
                </button>
              ) : (
                <div className="dy-row">{inner}</div>
              )}
            </li>
          );
        })}
        {ia.streaming && items.length === 0 &&
          [0, 1, 2].map((i) => (
            <li key={i} aria-hidden>
              <div className="dy-row">
                <span className="dy-row-main">
                  <Skel w={150} h={10} />
                  <Skel w={220} h={9} />
                </span>
              </div>
            </li>
          ))}
      </ul>
    </Bloom>
  );
}
