/**
 * Presentational components that render the live cards.
 *
 * `DyUICard` wraps one card with a header (title/icon/status badge) and a body
 * that switches on lifecycle: a skeleton while `pending`, the error message on
 * `error`, otherwise the registered component. `DyUISurface` lays out a list of
 * cards. Both are intentionally simple and fully styleable via `dyui-*` classes
 * (see `styles.css`) -- copy and restyle freely.
 */
import * as React from "react";

import { defaultRegistry } from "./registry";
import type { CardRegistry, DyUICard as Card } from "./types";

function Skeleton() {
  return (
    <div className="dyui-skeleton">
      <span className="dyui-skeleton-line" style={{ width: "85%" }} />
      <span className="dyui-skeleton-line" style={{ width: "70%" }} />
      <span className="dyui-skeleton-line" style={{ width: "55%" }} />
    </div>
  );
}

const STATUS_LABEL: Record<string, string> = {
  pending: "running",
  active: "working",
  done: "done",
  error: "failed",
};

export interface DyUICardProps {
  card: Card;
  registry?: CardRegistry;
  onDismiss?: (id: string) => void;
  /** Hide the header bar entirely (just render the body). */
  bare?: boolean;
}

export function DyUICard({ card, registry = defaultRegistry, onDismiss, bare }: DyUICardProps) {
  const Component = registry[card.component];
  const accentStyle = card.accent
    ? ({ ["--dyui-accent" as any]: card.accent } as React.CSSProperties)
    : undefined;

  let body: React.ReactNode;
  if (card.status === "pending") {
    body = <Skeleton />;
  } else if (card.status === "error") {
    body = <div className="dyui-error">{card.error ?? "Something went wrong."}</div>;
  } else if (Component) {
    body = <Component card={card} props={card.props} status={card.status} />;
  } else {
    // Unknown component key -> graceful fallback so nothing silently vanishes.
    body = (
      <pre className="dyui-json">
        {`[no card registered for "${card.component}"]\n` +
          JSON.stringify(card.props, null, 2)}
      </pre>
    );
  }

  return (
    <div
      className={`dyui-card dyui-status-${card.status}`}
      style={accentStyle}
      data-component={card.component}
    >
      {!bare && (
        <div className="dyui-card-header">
          {card.icon ? <span className="dyui-card-icon" data-icon={card.icon} /> : null}
          <span className="dyui-card-title">{card.title ?? card.component}</span>
          <span className={`dyui-card-badge dyui-badge-${card.status}`}>
            {STATUS_LABEL[card.status] ?? card.status}
          </span>
          {onDismiss && (card.status === "done" || card.status === "error") ? (
            <button
              className="dyui-card-close"
              onClick={() => onDismiss(card.id)}
              aria-label="Dismiss"
            >
              ×
            </button>
          ) : null}
        </div>
      )}
      <div className="dyui-card-body">{body}</div>
    </div>
  );
}

export interface DyUISurfaceProps {
  /** Cards to render (already filtered to one surface if desired). */
  cards: Card[];
  registry?: CardRegistry;
  onDismiss?: (id: string) => void;
  /** Optional empty-state node when there are no cards. */
  empty?: React.ReactNode;
  className?: string;
}

export function DyUISurface({
  cards,
  registry = defaultRegistry,
  onDismiss,
  empty,
  className,
}: DyUISurfaceProps) {
  if (cards.length === 0 && empty) {
    return <div className={`dyui-surface dyui-surface-empty ${className ?? ""}`}>{empty}</div>;
  }
  return (
    <div className={`dyui-surface ${className ?? ""}`}>
      {cards.map((card) => (
        <DyUICard key={card.id} card={card} registry={registry} onDismiss={onDismiss} />
      ))}
    </div>
  );
}
