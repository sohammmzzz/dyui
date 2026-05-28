/**
 * A small, framework-free reducer that turns a sequence of DyUI events into an
 * ordered list of live cards. Kept pure so it can be unit-tested without React.
 */
import type { DyUICard, DyUIEvent } from "./types";

export interface DyUIState {
  /** Insertion-ordered card ids. */
  order: string[];
  /** Cards keyed by id. */
  cards: Record<string, DyUICard>;
  /** Streamed LLM token text, concatenated. */
  tokens: string;
}

export const initialState: DyUIState = { order: [], cards: {}, tokens: "" };

export type DyUIAction =
  | { kind: "ui"; event: DyUIEvent }
  | { kind: "token"; text: string }
  | { kind: "dismiss"; id: string }
  | { kind: "reset" };

export function reducer(state: DyUIState, action: DyUIAction): DyUIState {
  switch (action.kind) {
    case "ui": {
      const ev = action.event;
      const existing = state.cards[ev.id];
      const replace = ev.replace !== false;
      const nextProps =
        existing && !replace
          ? { ...existing.props, ...ev.props }
          : ev.props;

      const card: DyUICard = {
        ...existing,
        ...ev,
        props: nextProps,
      };

      const order = existing ? state.order : [...state.order, ev.id];
      return { ...state, order, cards: { ...state.cards, [ev.id]: card } };
    }
    case "token":
      return { ...state, tokens: state.tokens + action.text };
    case "dismiss": {
      if (!state.cards[action.id]) return state;
      const cards = { ...state.cards };
      delete cards[action.id];
      return {
        ...state,
        cards,
        order: state.order.filter((id) => id !== action.id),
      };
    }
    case "reset":
      return initialState;
    default:
      return state;
  }
}

/** Selector: ordered cards for a given surface (or all). */
export function selectCards(state: DyUIState, surface?: string): DyUICard[] {
  const cards = state.order.map((id) => state.cards[id]).filter(Boolean);
  return surface ? cards.filter((c) => c.surface === surface) : cards;
}

/** Selector: the set of surfaces currently in use. */
export function selectSurfaces(state: DyUIState): string[] {
  const seen = new Set<string>();
  for (const id of state.order) {
    const c = state.cards[id];
    if (c) seen.add(c.surface);
  }
  return [...seen];
}
