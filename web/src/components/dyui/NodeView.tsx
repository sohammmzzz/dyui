/**
 * NodeView — renders any UINode (SPEC §7). Unknown `ui` → the `invalid` chip.
 * Each node renders inside an error boundary so one bad component never
 * takes down a message.
 */
import { Component as ReactComponent, type ErrorInfo, type ReactNode } from "react";
import type { NodeContext, UINode } from "../../lib/types";
import { staggerDelay } from "../../lib/motion";
import { registry } from "./registry";
import { Invalid } from "./developer/Invalid";
import { BloomDelay } from "./util/motion";
import { cx, normalizeNode } from "./util/props";
import type { DyProps } from "./util/types";
import "./styles/base.css";

class NodeBoundary extends ReactComponent<{ node: UINode; ctx: NodeContext; children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    if (typeof console !== "undefined") console.warn(`[dyui] "${this.props.node.ui}" failed to render`, error, info.componentStack);
  }
  componentDidUpdate(prev: { node: UINode }) {
    // streaming updates may fix a transient render error — try again on new props
    if (this.state.error && prev.node !== this.props.node) this.setState({ error: null });
  }
  render() {
    if (this.state.error) {
      const n = this.props.node;
      return (
        <Invalid
          node={{ id: n.id, ui: "invalid", status: "error", props: { raw: { ui: n.ui, ...n.props }, error: `Render error: ${this.state.error.message}` } }}
          ctx={this.props.ctx}
        />
      );
    }
    return this.props.children;
  }
}

export function NodeView({ node, ctx }: DyProps) {
  const n = normalizeNode(node, (node as any)?.id || "node");
  if (!n) return null;
  if (n.ui === "invalid" || n.status === "error") return <Invalid node={n} ctx={ctx} />;
  const C = registry[n.ui];
  if (!C) {
    return (
      <Invalid
        node={{ id: n.id, ui: "invalid", status: "error", props: { raw: { ui: n.ui, ...n.props }, error: `Unknown component "${n.ui}"` } }}
        ctx={ctx}
      />
    );
  }
  return (
    <NodeBoundary node={n} ctx={ctx}>
      <C node={n} ctx={ctx} />
    </NodeBoundary>
  );
}

/** Renders a list of nodes as a vertical stack; children bloom in a capped stagger. */
export function NodeList({
  nodes,
  ctx,
  className,
  gap,
  baseDelay = 0,
}: {
  nodes: UINode[];
  ctx: NodeContext;
  className?: string;
  gap?: number;
  baseDelay?: number;
}) {
  return (
    <div className={cx("dy-stack", className)} style={gap !== undefined ? { gap } : undefined}>
      {nodes.map((n, i) => (
        <BloomDelay key={n.id} value={baseDelay + staggerDelay(i, 0.045)}>
          <NodeView node={n} ctx={ctx} />
        </BloomDelay>
      ))}
    </div>
  );
}

/** A no-op context for static rendering (docs, previews). */
export function staticContext(overrides: Partial<NodeContext> = {}): NodeContext {
  return {
    messageId: "static",
    threadId: null,
    onAction: () => {},
    onReply: () => {},
    interactive: true,
    ...overrides,
  };
}
