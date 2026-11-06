/**
 * Lazy highlight.js. The highlighter (~100 kB min) loads on first use; until then
 * code renders as plain text and re-renders highlighted when it arrives.
 */
import { useEffect, useSyncExternalStore } from "react";
import type { HLJSApi } from "highlight.js";

let api: HLJSApi | null = null;
let pending: Promise<HLJSApi> | null = null;
const listeners = new Set<() => void>();

/** The loaded highlighter, or null while it is still loading. */
export const getHljs = (): HLJSApi | null => api;

/** Start loading (idempotent); resolves with the registered highlighter. */
export function loadHljs(): Promise<HLJSApi> {
  if (!pending) {
    pending = import("./hljs-languages").then((m) => {
      api = m.default;
      listeners.forEach((fn) => fn());
      return api;
    });
    pending.catch(() => {
      pending = null; // allow a retry on the next render (e.g. after a flaky network)
    });
  }
  return pending;
}

const subscribe = (fn: () => void) => {
  listeners.add(fn);
  return () => listeners.delete(fn);
};

/** Subscribe a component to the highlighter; triggers the load on first use. */
export function useHljs(): HLJSApi | null {
  const value = useSyncExternalStore(subscribe, getHljs, getHljs);
  useEffect(() => {
    if (!api) loadHljs().catch(() => undefined);
  }, []);
  return value;
}
