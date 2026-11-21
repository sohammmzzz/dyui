/**
 * The docs-site embed of the demo build (`vite build --mode demo` → dist-demo → the docs'
 * /demo/). Only imported behind `import.meta.env.MODE === "demo"` checks, so the normal
 * build — and the Python package's _static bundle — never contain it. No top-level side
 * effects, so it tree-shakes away completely.
 *
 * Messages to the parent page (`parent.postMessage(msg, "*")`), sent only when framed:
 *
 *   { source: "dyui-demo", type: "wheel", deltaX, deltaY, deltaMode }
 *       A wheel event inside the demo that nothing under the pointer can scroll any
 *       further in its direction (or with no scroll container at all). Wheel events never
 *       leave an iframe, so without this the page's own scrolling would stall over the
 *       demo. The values are the WheelEvent's own (deltaMode 0 = pixels, 1 = lines,
 *       2 = pages). Pinch-zoom wheels (ctrlKey) are not forwarded.
 *
 *   { source: "dyui-demo", type: "touch", phase: "move", deltaY }
 *   { source: "dyui-demo", type: "touch", phase: "end", deltaY: 0 }
 *       A vertical touch drag that nothing under the finger can scroll further: deltaY is
 *       the finger movement since the previous move, in CSS pixels, positive = scroll
 *       down (finger moving up), the same sign as a wheel. "end" follows a gesture that
 *       sent at least one "move", so the parent can settle (snap) on release.
 *
 * Messages from the parent page:
 *
 *   { source: "dyui-docs", type: "theme", theme: "light" | "dark" }
 *       Follow the page's theme. The first theme comes from the `?theme=` query.
 */
import type { ThemeMode } from "@/lib/types";

const OUT = "dyui-demo";
const IN = "dyui-docs";

/* ------------------------------------------------------------------- theme */

let memoryTheme: ThemeMode | null | undefined;

/** The demo never touches localStorage: its theme is the parent's, held in memory. */
export function demoStoredTheme(): ThemeMode | null {
  if (memoryTheme === undefined) {
    const q = typeof location === "undefined" ? null : new URLSearchParams(location.search).get("theme");
    memoryTheme = q === "light" || q === "dark" ? q : null;
  }
  return memoryTheme;
}

export function demoStoreTheme(mode: ThemeMode) {
  memoryTheme = mode;
}

/** Call `apply` whenever the parent page switches theme. Returns an unsubscribe. */
export function onParentTheme(apply: (mode: ThemeMode) => void): () => void {
  const on = (e: MessageEvent) => {
    if (e.source !== window.parent || e.source === window) return;
    const d = e.data;
    if (!d || d.source !== IN || d.type !== "theme") return;
    if (d.theme !== "light" && d.theme !== "dark") return;
    memoryTheme = d.theme;
    apply(d.theme);
  };
  window.addEventListener("message", on);
  return () => window.removeEventListener("message", on);
}

/* ---------------------------------------------------------- scroll forwarding */

function scrollableY(el: Element): boolean {
  const oy = getComputedStyle(el).overflowY;
  return (oy === "auto" || oy === "scroll" || oy === "overlay") && el.scrollHeight > el.clientHeight + 1;
}

function scrollableX(el: Element): boolean {
  const ox = getComputedStyle(el).overflowX;
  return (ox === "auto" || ox === "scroll" || ox === "overlay") && el.scrollWidth > el.clientWidth + 1;
}

/** Can anything from `target` up to the document scroll by (dx, dy)? */
export function canScroll(target: EventTarget | null, dx: number, dy: number): boolean {
  const vertical = Math.abs(dy) >= Math.abs(dx);
  let el: Element | null = target instanceof Element ? target : target instanceof Node ? target.parentElement : null;
  for (; el; el = el.parentElement) {
    if (vertical) {
      if (dy === 0 || !scrollableY(el)) continue;
      if (dy < 0 ? el.scrollTop > 0.5 : el.scrollTop + el.clientHeight < el.scrollHeight - 1) return true;
    } else {
      if (!scrollableX(el)) continue;
      if (dx < 0 ? el.scrollLeft > 0.5 : el.scrollLeft + el.clientWidth < el.scrollWidth - 1) return true;
    }
  }
  const doc = document.scrollingElement;
  if (!doc) return false;
  if (vertical) return dy < 0 ? doc.scrollTop > 0.5 : doc.scrollTop + window.innerHeight < doc.scrollHeight - 1;
  return dx < 0 ? doc.scrollLeft > 0.5 : doc.scrollLeft + window.innerWidth < doc.scrollWidth - 1;
}

function post(msg: Record<string, unknown>) {
  try {
    window.parent.postMessage({ source: OUT, ...msg }, "*");
  } catch {
    /* parent gone */
  }
}

/** Install the parent-page scroll forwarding. A no-op when the demo is not framed. */
export function installScrollForwarding(): () => void {
  if (typeof window === "undefined" || window.parent === window) return () => {};

  const onWheel = (e: WheelEvent) => {
    if (e.ctrlKey || e.defaultPrevented) return;
    if (canScroll(e.target, e.deltaX, e.deltaY)) return;
    post({ type: "wheel", deltaX: e.deltaX, deltaY: e.deltaY, deltaMode: e.deltaMode });
  };

  let lastY: number | null = null;
  let lastX = 0;
  let target: EventTarget | null = null;
  let forwarded = false;
  const onStart = (e: TouchEvent) => {
    if (e.touches.length !== 1) return void (lastY = null);
    lastY = e.touches[0].clientY;
    lastX = e.touches[0].clientX;
    target = e.target;
    forwarded = false;
  };
  const onMove = (e: TouchEvent) => {
    if (lastY === null || e.touches.length !== 1) return;
    const t = e.touches[0];
    const dy = lastY - t.clientY;
    const dx = lastX - t.clientX;
    lastY = t.clientY;
    lastX = t.clientX;
    if (Math.abs(dy) < 0.5 || Math.abs(dx) > Math.abs(dy)) return;
    if (canScroll(target, 0, dy)) return;
    forwarded = true;
    post({ type: "touch", phase: "move", deltaY: dy });
  };
  const onEnd = () => {
    if (forwarded) post({ type: "touch", phase: "end", deltaY: 0 });
    lastY = null;
    forwarded = false;
  };

  // wheel bubbles to window, so a component that handles (preventDefault) its own wheel wins
  const wheelOpts: AddEventListenerOptions = { passive: true };
  const opts: AddEventListenerOptions = { passive: true, capture: true };
  window.addEventListener("wheel", onWheel, wheelOpts);
  window.addEventListener("touchstart", onStart, opts);
  window.addEventListener("touchmove", onMove, opts);
  window.addEventListener("touchend", onEnd, opts);
  window.addEventListener("touchcancel", onEnd, opts);
  return () => {
    window.removeEventListener("wheel", onWheel, wheelOpts);
    window.removeEventListener("touchstart", onStart, opts);
    window.removeEventListener("touchmove", onMove, opts);
    window.removeEventListener("touchend", onEnd, opts);
    window.removeEventListener("touchcancel", onEnd, opts);
  };
}
