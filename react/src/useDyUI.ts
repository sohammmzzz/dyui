/**
 * `useDyUIAgent` -- the one hook most apps need.
 *
 * It connects to a DyUI agent endpoint, maintains the live card list, exposes
 * streamed tokens, and hands back a `run()` to (re)launch the agent. Auto
 * dismissal of cards with a `ttl_ms` is handled here so the store stays pure.
 */
import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";

import { streamAgent } from "./client";
import {
  DyUIState,
  initialState,
  reducer,
  selectCards,
  selectSurfaces,
} from "./store";
import type { ConnectionStatus, DyUICard } from "./types";

export interface UseDyUIOptions {
  /** Stream endpoint URL. */
  url: string;
  /** Extra request headers (auth, etc.). */
  headers?: Record<string, string>;
  /** Run automatically on mount with this input. */
  autoRunInput?: unknown;
  /** Forward streamed LLM tokens into `tokens`. Default true. */
  collectTokens?: boolean;
}

export interface UseDyUIResult {
  /** All live cards, in arrival order. */
  cards: DyUICard[];
  /** Cards grouped by surface name. */
  bySurface: Record<string, DyUICard[]>;
  /** List of surfaces currently in use. */
  surfaces: string[];
  /** Concatenated streamed token text (if any). */
  tokens: string;
  /** Connection lifecycle. */
  status: ConnectionStatus;
  /** Last error message, if status === "error". */
  error: string | null;
  /** Launch (or relaunch) the agent. Cancels any in-flight run first. */
  run: (input?: unknown, config?: Record<string, unknown>) => void;
  /** Cancel the in-flight run. */
  stop: () => void;
  /** Remove a single card (e.g. user dismissed it). */
  dismiss: (id: string) => void;
  /** Clear all cards and tokens. */
  reset: () => void;
}

export function useDyUIAgent(options: UseDyUIOptions): UseDyUIResult {
  const { url, headers, autoRunInput, collectTokens = true } = options;
  const [state, dispatch] = useReducer(reducer, initialState);
  const [status, setStatus] = useState<ConnectionStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: string) => {
    dispatch({ kind: "dismiss", id });
  }, []);

  const reset = useCallback(() => dispatch({ kind: "reset" }), []);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const run = useCallback(
    (input?: unknown, config?: Record<string, unknown>) => {
      stop();
      dispatch({ kind: "reset" });
      setError(null);
      setStatus("streaming");
      const controller = new AbortController();
      abortRef.current = controller;

      streamAgent(
        { url, input, config, headers, signal: controller.signal },
        (frame) => {
          if (frame.type === "ui") {
            dispatch({ kind: "ui", event: frame.data });
          } else if (frame.type === "token" && collectTokens) {
            dispatch({ kind: "token", text: frame.data.text });
          } else if (frame.type === "error") {
            setError(frame.data.message);
            setStatus("error");
          }
        }
      )
        .then(() => setStatus((s) => (s === "error" ? s : "done")))
        .catch((e: unknown) => {
          if ((e as Error)?.name === "AbortError") return;
          setError((e as Error)?.message ?? String(e));
          setStatus("error");
        });
    },
    [url, headers, collectTokens, stop]
  );

  // Auto-dismiss cards that carry a ttl once they reach a terminal status.
  useEffect(() => {
    for (const card of selectCards(state)) {
      const ttl = card.ttl_ms;
      if (
        ttl &&
        ttl > 0 &&
        (card.status === "done" || card.status === "error") &&
        !timers.current.has(card.id)
      ) {
        const t = setTimeout(() => {
          timers.current.delete(card.id);
          dispatch({ kind: "dismiss", id: card.id });
        }, ttl);
        timers.current.set(card.id, t);
      }
    }
  }, [state]);

  // Run on mount if requested.
  const didAutoRun = useRef(false);
  useEffect(() => {
    if (autoRunInput !== undefined && !didAutoRun.current) {
      didAutoRun.current = true;
      run(autoRunInput);
    }
  }, [autoRunInput, run]);

  // Cleanup on unmount.
  useEffect(() => {
    const timersMap = timers.current;
    return () => {
      abortRef.current?.abort();
      timersMap.forEach((t) => clearTimeout(t));
      timersMap.clear();
    };
  }, []);

  const cards = useMemo(() => selectCards(state), [state]);
  const surfaces = useMemo(() => selectSurfaces(state), [state]);
  const bySurface = useMemo(() => {
    const out: Record<string, DyUICard[]> = {};
    for (const c of cards) (out[c.surface] ??= []).push(c);
    return out;
  }, [cards]);

  return {
    cards,
    bySurface,
    surfaces,
    tokens: state.tokens,
    status,
    error,
    run,
    stop,
    dismiss,
    reset,
  };
}

export type { DyUIState };
