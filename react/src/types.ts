/**
 * Core types shared across the DyUI React runtime. These mirror the Python
 * `UIEvent` model exactly so the wire format stays in lockstep on both ends.
 */
import type { ComponentType } from "react";

export type CardStatus = "pending" | "active" | "done" | "error";

/** A UI instruction as it arrives off the wire (one SSE `ui` frame). */
export interface DyUIEvent {
  id: string;
  component: string;
  props: Record<string, unknown>;
  status: CardStatus;
  surface: string;
  title?: string | null;
  icon?: string | null;
  accent?: string | null;
  error?: string | null;
  replace?: boolean;
  ttl_ms?: number | null;
  ts?: number;
  meta?: Record<string, unknown>;
}

/** A card held in the store. Identical shape to the event, kept separate for
 * clarity and so we can extend it (e.g. local-only flags) without touching the
 * wire type. */
export interface DyUICard extends DyUIEvent {}

/** Props every card component receives. `props`/`status` are convenience
 * mirrors of `card.props`/`card.status`. */
export interface CardComponentProps<P = Record<string, unknown>> {
  card: DyUICard;
  props: P;
  status: CardStatus;
}

export type CardComponent<P = Record<string, unknown>> = ComponentType<
  CardComponentProps<P>
>;

/** Maps a `component` key to the React component that renders it. */
export type CardRegistry = Record<string, CardComponent<any>>;

/** Frames emitted by the streaming client. */
export type StreamFrame =
  | { type: "ui"; data: DyUIEvent }
  | { type: "token"; data: { text: string; node?: string | null } }
  | { type: "error"; data: { message: string } }
  | { type: "done"; data: Record<string, never> };

export type ConnectionStatus = "idle" | "streaming" | "done" | "error";
