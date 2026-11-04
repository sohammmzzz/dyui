import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { staggerDelay } from "../../../lib/motion";
import { NodeView } from "../NodeView";
import { Bloom, BloomDelay } from "../util/motion";
import { childNodes, optStr } from "../util/props";
import { Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import "../styles/layout.css";

/** `carousel` — horizontal scroll-snap track with arrows and dots. */
export function Carousel({ node, ctx }: DyProps) {
  const children = childNodes(node.children ?? node.props.children ?? node.props.items, node.id, node.status);
  const track = useRef<HTMLDivElement>(null);
  const [idx, setIdx] = useState(0);
  const [edges, setEdges] = useState({ start: true, end: false });
  const n = children.length;
  const title = optStr(node.props.title);

  const sync = useCallback(() => {
    const el = track.current;
    if (!el) return;
    const slides = Array.from(el.children) as HTMLElement[];
    const x = el.scrollLeft;
    let best = 0;
    let bd = Infinity;
    slides.forEach((s, i) => {
      const d = Math.abs(s.offsetLeft - el.offsetLeft - x);
      if (d < bd) {
        bd = d;
        best = i;
      }
    });
    const end = x + el.clientWidth >= el.scrollWidth - 4;
    setIdx(end ? slides.length - 1 : best);
    setEdges({ start: x <= 4, end });
  }, []);

  useEffect(() => {
    sync();
    const el = track.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(sync);
    ro.observe(el);
    return () => ro.disconnect();
  }, [sync, n]);

  const go = (i: number) => {
    const el = track.current;
    const s = el?.children[Math.max(0, Math.min(n - 1, i))] as HTMLElement | undefined;
    if (!el || !s) return;
    el.scrollTo({ left: s.offsetLeft - el.offsetLeft, behavior: "smooth" });
  };
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.target !== e.currentTarget) return;
    if (e.key === "ArrowRight") {
      e.preventDefault();
      go(idx + 1);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      go(idx - 1);
    }
  };

  return (
    <Bloom className="dy-c dy-carousel" data-dy-ui="carousel">
      {title && <div className="dy-eyebrow dy-carousel-title">{title}</div>}
      <div className="dy-carousel-viewport" data-start={edges.start || undefined} data-end={edges.end || undefined}>
        <div ref={track} className="dy-carousel-track" tabIndex={0} role="region" aria-roledescription="carousel" aria-label={title ?? "Carousel"} onScroll={sync} onKeyDown={onKey}>
          {children.map((c, i) => (
            <div key={c.id} className="dy-carousel-slide" role="group" aria-roledescription="slide" aria-label={`${i + 1} of ${n}`}>
              <BloomDelay value={staggerDelay(i, 0.06)}>
                <NodeView node={c} ctx={ctx} />
              </BloomDelay>
            </div>
          ))}
          {node.status === "streaming" && (
            <div className="dy-carousel-slide" aria-hidden>
              <Skel h={180} style={{ borderRadius: 16 }} />
            </div>
          )}
        </div>
        {n > 1 && (
          <>
            <button type="button" className="dy-carousel-arrow" data-dir="prev" onClick={() => go(idx - 1)} disabled={edges.start} aria-label="Previous slide">
              <ChevronLeft width={18} height={18} />
            </button>
            <button type="button" className="dy-carousel-arrow" data-dir="next" onClick={() => go(idx + 1)} disabled={edges.end} aria-label="Next slide">
              <ChevronRight width={18} height={18} />
            </button>
          </>
        )}
      </div>
      {n > 1 && (
        <div className="dy-carousel-dots" role="group" aria-label="Choose slide">
          {children.map((c, i) => (
            <button key={c.id} type="button" className="dy-dot" aria-current={i === idx || undefined} aria-label={`Go to slide ${i + 1}`} onClick={() => go(i)} />
          ))}
        </div>
      )}
    </Bloom>
  );
}
