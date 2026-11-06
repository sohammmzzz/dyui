/**
 * A slow strip of real, rendered components for the landing page.
 * Pauses on hover/focus; static under prefers-reduced-motion.
 */
import { NodeView, staticContext } from "@/components/dyui";
import { FIXTURES } from "@/fixtures/nodes";
import type { UINode } from "@/lib/types";

const PICK: Array<[string, number]> = [
  ["stat", 0], ["badges", 0], ["progress", 0], ["timeline", 0], ["rating", 1],
  ["callout", 1], ["plan", 0], ["buttons", 0], ["quick_replies", 0],
];

const items = PICK.map(([name, i]) => ({ name, node: FIXTURES[name]?.[i] })).filter((x): x is { name: string; node: UINode } => !!x.node);
const ctx = staticContext({ messageId: "marquee", interactive: false });

function Row({ hidden }: { hidden?: boolean }) {
  return (
    <ul className="mq-row" aria-hidden={hidden || undefined} {...(hidden ? { inert: true } : {})}>
      {items.map(({ name, node }) => (
        <li key={name} className="mq-item">
          <NodeView node={{ ...node, id: `${hidden ? "mq2" : "mq"}_${node.id}` }} ctx={ctx} />
          <span className="mq-name">{name}</span>
        </li>
      ))}
    </ul>
  );
}

export default function Marquee() {
  return (
    <div className="mq dy-root not-content" aria-label="Some of DyUI's components">
      <div className="mq-track">
        <Row />
        <Row hidden />
      </div>
    </div>
  );
}
