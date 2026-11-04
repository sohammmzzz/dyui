import { useCallback, useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";
import type { NodeContext, UINode } from "../../../lib/types";
import { prefersReducedMotion } from "../../../lib/motion";
import { isObj } from "./props";

export type Resolved = { label?: string; values?: Record<string, any> };
export type Pending = { action: string; label?: string; values?: Record<string, any>; key?: string };

/**
 * Shared state machine for interactive components:
 *   idle → (click) sending (local, optimistic) → resolved (props.__resolved__ from the server)
 */
export function useInteraction(node: UINode, ctx: NodeContext) {
  const resolved: Resolved | null = isObj(node.props?.__resolved__) ? (node.props.__resolved__ as Resolved) : null;
  const [pending, setPending] = useState<Pending | null>(null);
  const streaming = node.status === "streaming";
  const live = ctx.interactive !== false && !streaming;
  const locked = !!resolved || !!pending;
  const disabled = !live || locked;

  const fire = useCallback(
    (req: { action: string; label?: string; data?: Record<string, any>; values?: Record<string, any> }, key?: string) => {
      if (disabled) return;
      setPending({ action: req.action, label: req.label, values: req.values, key });
      try {
        ctx.onAction({ component_id: node.id, action: req.action, label: req.label, data: req.data, values: req.values });
      } catch (e) {
        console.error(e);
      }
    },
    [ctx, node.id, disabled],
  );

  const state: "idle" | "sending" | "resolved" = resolved ? "resolved" : pending ? "sending" : "idle";
  return { resolved, pending, setPending, disabled, live, streaming, fire, state };
}

/** Width of an element, tracked with ResizeObserver (null until measured). */
export function useWidth(ref: RefObject<HTMLElement | null>): number | null {
  const [w, setW] = useState<number | null>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    setW(el.getBoundingClientRect().width);
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => {
      const cw = entries[0]?.contentRect.width;
      if (cw) setW((prev) => (prev !== null && Math.abs(prev - cw) < 0.5 ? prev : cw));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return w;
}

/** Count from 0 → target with a settle ease; respects reduced motion. */
export function useCountUp(target: number | null, opts: { duration?: number; delay?: number; enabled?: boolean } = {}) {
  const { duration = 1100, delay = 0, enabled = true } = opts;
  const [v, setV] = useState<number | null>(() => (target === null ? null : enabled ? 0 : target));
  const raf = useRef(0);
  useEffect(() => {
    if (target === null) {
      setV(null);
      return;
    }
    if (!enabled || prefersReducedMotion()) {
      setV(target);
      return;
    }
    let start = 0;
    const from = 0;
    const tick = (t: number) => {
      if (!start) start = t;
      const p = Math.min(1, Math.max(0, (t - start - delay) / duration));
      const e = 1 - Math.pow(1 - p, 4); // ease-out quart: settles, never overshoots
      setV(from + (target - from) * e);
      if (p < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [target, duration, delay, enabled]);
  return v;
}

/** Copy to clipboard with a transient "copied" flag. */
export function useCopy(timeout = 1600) {
  const [copied, setCopied] = useState(false);
  const t = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => () => clearTimeout(t.current), []);
  const copy = useCallback(
    async (text: string) => {
      try {
        await navigator.clipboard.writeText(text);
      } catch {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        try {
          document.execCommand("copy");
        } catch {
          /* ignore */
        }
        ta.remove();
      }
      setCopied(true);
      clearTimeout(t.current);
      t.current = setTimeout(() => setCopied(false), timeout);
    },
    [timeout],
  );
  return { copied, copy };
}

/** Sanitized id for SVG url(#id) references. */
export function svgId(raw: string) {
  return "dy" + raw.replace(/[^a-zA-Z0-9_-]/g, "");
}
