import { staggerDelay } from "../../../lib/motion";
import { NodeView } from "../NodeView";
import { Bloom, BloomDelay } from "../util/motion";
import { childNodes, num } from "../util/props";
import { Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import "../styles/layout.css";

/** `grid` — 1–4 columns; collapses to one column below 560px of container width. */
export function Grid({ node, ctx }: DyProps) {
  const children = childNodes(node.children ?? node.props.children, node.id, node.status);
  const cols = Math.max(1, Math.min(4, Math.round(num(node.props.columns) ?? 2)));
  return (
    <Bloom className="dy-c dy-grid" data-dy-ui="grid">
      <div className="dy-grid-inner" data-cols={cols} style={{ ["--cols" as any]: cols }}>
        {children.map((c, i) => (
          <BloomDelay key={c.id} value={0.05 + staggerDelay(i, 0.05)}>
            <NodeView node={c} ctx={ctx} />
          </BloomDelay>
        ))}
        {node.status === "streaming" && children.length === 0 && Array.from({ length: cols }, (_, i) => <Skel key={i} h={120} style={{ borderRadius: 16 }} />)}
      </div>
    </Bloom>
  );
}
