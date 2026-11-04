/**
 * Shell motion helpers on top of lib/motion.ts presets. Everything goes through
 * `useMotionKit()` so prefers-reduced-motion swaps transforms/blur for short fades.
 */
import { useMemo } from "react";
import { useReducedMotion, type Transition, type Variants } from "motion/react";
import { bloom, dur, ease, fade, rise, spring } from "@/lib/motion";

const reducedV: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: 0.12 } },
  exit: { opacity: 0, transition: { duration: 0.1 } },
};

export type MotionKit = {
  reduced: boolean;
  bloom: Variants;
  rise: Variants;
  fade: Variants;
  spring: Transition;
  /** a copy of `v` whose `show` waits `delay` seconds */
  delayed: (v: Variants, delay: number) => Variants;
  press: { whileTap?: { scale: number } };
};

function delayed(v: Variants, delay: number): Variants {
  if (!delay) return v;
  const show = v.show as Record<string, any>;
  return { ...v, show: { ...show, transition: { ...(show?.transition || {}), delay } } };
}

const FULL: MotionKit = {
  reduced: false,
  bloom,
  rise,
  fade,
  spring,
  delayed,
  press: { whileTap: { scale: 0.97 } },
};

const REDUCED: MotionKit = {
  reduced: true,
  bloom: reducedV,
  rise: reducedV,
  fade: reducedV,
  spring: { duration: 0.12 },
  delayed: (v) => v,
  press: {},
};

export function useMotionKit(): MotionKit {
  const reduced = useReducedMotion() ?? false;
  return useMemo(() => (reduced ? REDUCED : FULL), [reduced]);
}

/** Height auto-animation for collapsibles. */
export const collapse: Variants = {
  closed: { height: 0, opacity: 0, transition: { duration: dur[2], ease } },
  open: { height: "auto", opacity: 1, transition: { duration: dur[3], ease } },
};

export const collapseReduced: Variants = {
  closed: { height: 0, opacity: 0, transition: { duration: 0.01 } },
  open: { height: "auto", opacity: 1, transition: { duration: 0.01 } },
};

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}
