/**
 * Motion helpers built on the shared presets in lib/motion.ts.
 * Bloom = the default component entrance; nested layouts pass a stagger delay
 * down through context so children bloom one after another.
 */
import { createContext, useContext, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { motion, useReducedMotion, type HTMLMotionProps, type Variants } from "motion/react";
import { bloom, dur, ease, rise } from "../../../lib/motion";

const DelayCtx = createContext(0);
export const BloomDelay = DelayCtx.Provider;
export const useBloomDelay = () => useContext(DelayCtx);

const reducedFade: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: 0.12 } },
  exit: { opacity: 0, transition: { duration: 0.12 } },
};

function withDelay(v: Variants, delay: number): Variants {
  const show = v.show as any;
  return {
    ...v,
    show: {
      ...show,
      transition: { ...(show.transition || {}), delay },
      transitionEnd: { filter: "none" },
    },
  };
}

/** The reduced-motion aware bloom variants (optionally delayed). */
export function useBloomVariants(extraDelay = 0, kind: "bloom" | "rise" = "bloom"): Variants {
  const reduced = useReducedMotion();
  const ctxDelay = useBloomDelay();
  const d = ctxDelay + extraDelay;
  return useMemo(() => (reduced ? withDelay(reducedFade, Math.min(d, 0.1)) : withDelay(kind === "rise" ? rise : bloom, d)), [reduced, d, kind]);
}

type BloomProps = HTMLMotionProps<"div"> & { delay?: number; kind?: "bloom" | "rise" };

/** Component root wrapper: blooms in once on mount. */
export function Bloom({ delay = 0, kind = "bloom", children, ...rest }: BloomProps) {
  const variants = useBloomVariants(delay, kind);
  return (
    <motion.div variants={variants} initial="hidden" animate="show" {...rest}>
      {children}
    </motion.div>
  );
}

/** Small bloom-in for content that replaces a skeleton (no layout change). */
export function Reveal({ children, className, as = "span", delay = 0 }: { children: ReactNode; className?: string; as?: "span" | "div"; delay?: number }) {
  const reduced = useReducedMotion();
  const M = as === "div" ? motion.div : motion.span;
  return (
    <M
      className={className}
      initial={reduced ? { opacity: 0 } : { opacity: 0, filter: "blur(4px)" }}
      animate={reduced ? { opacity: 1 } : { opacity: 1, filter: "blur(0px)", transitionEnd: { filter: "none" } }}
      transition={{ duration: reduced ? 0.12 : dur[3], ease, delay }}
    >
      {children}
    </M>
  );
}

/**
 * Animates its height to fit its content (form → summary swaps, streaming growth).
 * Overflow is clipped only while animating so focus rings are never cut off.
 */
export function AutoHeight({ children, className, disabled }: { children: ReactNode; className?: string; disabled?: boolean }) {
  const inner = useRef<HTMLDivElement>(null);
  const [h, setH] = useState<number | "auto">("auto");
  const [animating, setAnimating] = useState(false);
  const reduced = useReducedMotion();
  useLayoutEffect(() => {
    const el = inner.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => setH(el.offsetHeight));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  if (disabled) return <div className={className}>{children}</div>;
  return (
    <motion.div
      className={className}
      initial={false}
      animate={{ height: h }}
      transition={{ duration: reduced ? 0 : dur[3], ease }}
      onAnimationStart={() => setAnimating(true)}
      onAnimationComplete={() => setAnimating(false)}
      style={{ overflow: animating ? "hidden" : "visible" }}
    >
      <div ref={inner}>{children}</div>
    </motion.div>
  );
}

export { useReducedMotion };
