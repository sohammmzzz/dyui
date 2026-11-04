import type { NodeContext, UINode } from "@/lib/types";

/** TEMPORARY STUB — renders the node as JSON until the real library lands. */
export function NodeView({ node }: { node: UINode; ctx: NodeContext }) {
  return <pre style={{ fontSize: 12, opacity: 0.7 }}>{JSON.stringify(node, null, 2)}</pre>;
}
