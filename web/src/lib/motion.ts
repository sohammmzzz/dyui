/**
 * DyUI motion language — "bloom, settle, breathe" (SPEC.md §1.6).
 * Shared presets for the `motion` library. Every component's entrance and
 * interaction feedback should come from here so the whole app moves as one.
 */
import type { Transition, Variants } from "motion/react";

export const ease = [0.22, 1, 0.36, 1] as const; // settle
export const easeInOut = [0.65, 0, 0.35, 1] as const;

export const dur = { 1: 0.12, 2: 0.22, 3: 0.38, 4: 0.64 } as const;

/** Calm spring — no visible overshoot. */
export const spring: Transition = { type: "spring", stiffness: 260, damping: 30, mass: 0.9 };
export const softSpring: Transition = { type: "spring", stiffness: 180, damping: 28, mass: 1 };

/** Default entrance: a drop of dye blooming into focus. */
export const bloom: Variants = {
  hidden: { opacity: 0, y: 6, scale: 0.985, filter: "blur(6px)" },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    filter: "blur(0px)",
    transition: { duration: dur[3], ease },
  },
  exit: { opacity: 0, y: -4, filter: "blur(4px)", transition: { duration: dur[2], ease } },
};

/** Smaller entrance for chips, rows, inline bits. */
export const rise: Variants = {
  hidden: { opacity: 0, y: 4 },
  show: { opacity: 1, y: 0, transition: { duration: dur[2], ease } },
  exit: { opacity: 0, transition: { duration: dur[1] } },
};

export const fade: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: dur[2], ease } },
  exit: { opacity: 0, transition: { duration: dur[1] } },
};

/** Parent variant that staggers children (cap the visual stagger at ~8 items). */
export const stagger = (gap = 0.04, delay = 0): Variants => ({
  hidden: {},
  show: { transition: { staggerChildren: gap, delayChildren: delay } },
});

/** Delay helper for manual staggering with a cap. */
export const staggerDelay = (index: number, gap = 0.04, cap = 8) => Math.min(index, cap) * gap;

/** Press / hover feedback for buttons and clickable surfaces. */
export const press = { whileTap: { scale: 0.97 }, transition: { duration: dur[1] } } as const;

/** Respect prefers-reduced-motion in JS-driven animations (count-ups, chart draws). */
export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
