/**
 * A live demo of one built-in component, rendered by the real DyUI component
 * library (../web/src/components/dyui) with the shared fixtures. Interactions
 * are captured and shown as the action the server would receive.
 */
import { useCallback, useState } from "react";
import { NodeView, staticContext } from "@/components/dyui";
import { FIXTURES } from "@/fixtures/nodes";
import type { UINode } from "@/lib/types";

type Sent = { kind: "action"; action: string; label?: string; data?: unknown; values?: unknown } | { kind: "reply"; text: string };

function mapNodes(list: UINode[], id: string, f: (n: UINode) => UINode): UINode[] {
  return list.map((n) => (n.id === id ? f(n) : n.children ? { ...n, children: mapNodes(n.children, id, f) } : n));
}

export default function ComponentDemo({ name, limit }: { name: string; limit?: number }) {
  const initial = (FIXTURES[name] ?? []).slice(0, limit ?? undefined);
  const [nodes, setNodes] = useState<UINode[]>(initial);
  const [run, setRun] = useState(0);
  const [sent, setSent] = useState<Sent | null>(null);

  const replay = useCallback(() => {
    setNodes(initial);
    setSent(null);
    setRun((r) => r + 1);
  }, [initial]);

  const ctx = staticContext({
    messageId: "docs",
    onAction: (req) => {
      setSent({ kind: "action", action: req.action, label: req.label, data: req.data, values: req.values });
      // resolve optimistically, like the chat app does
      setNodes((all) => mapNodes(all, req.component_id, (n) => ({ ...n, props: { ...n.props, __resolved__: { label: req.label, values: req.values } } })));
    },
    onReply: (text) => setSent({ kind: "reply", text }),
  });

  if (!initial.length) return null;
  const payload = sent?.kind === "action" ? JSON.stringify({ data: sent.data ?? undefined, values: sent.values ?? undefined }) : "";

  return (
    <figure className="dy-root dd-demo not-content" data-component={name}>
      <div className="dd-stage" key={run}>
        {nodes.map((n) => (
          <NodeView key={n.id} node={n} ctx={ctx} />
        ))}
      </div>
      <figcaption className="dd-bar">
        <span className="dd-log" aria-live="polite">
          {!sent && <span className="dd-hint">Live component, rendered by the DyUI web app.</span>}
          {sent?.kind === "action" && (
            <>
              Sent <code>{sent.action}</code> to the server{payload !== "{}" && <> with <code>{payload}</code></>}
            </>
          )}
          {sent?.kind === "reply" && (
            <>
              Sent the message <code>{JSON.stringify(sent.text)}</code>
            </>
          )}
        </span>
        <button type="button" className="dd-replay" onClick={replay}>
          Replay
        </button>
      </figcaption>
    </figure>
  );
}
