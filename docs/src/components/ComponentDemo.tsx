/**
 * A live demo of one built-in component, rendered by the real DyUI component
 * library (../web/src/components/dyui) with the shared fixtures. Interactions
 * are captured and shown as the action the server would receive.
 */
import { useCallback, useState } from "react";
import { NodeView, Prose, staticContext } from "@/components/dyui";
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
      <div className="dd-head">
        <span className="dd-label">
          <span className="dd-live" aria-hidden="true" />
          Live preview
        </span>
        <button type="button" className="dd-replay" onClick={replay}>
          <svg aria-hidden="true" viewBox="0 0 16 16" width="12" height="12">
            <path d="M2.5 8a5.5 5.5 0 1 0 1.7-4M2.5 2.5V5H5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Replay
        </button>
      </div>
      <div className="dd-stage" key={run}>
        <div className="dd-stage-inner">
          {nodes.map((n) => (
            <NodeView key={n.id} node={n} ctx={ctx} />
          ))}
        </div>
      </div>
      <figcaption className="dd-bar">
        <span className="dd-log" aria-live="polite">
          {!sent && <span className="dd-hint">Rendered by the DyUI web app. Interactions are captured here instead of reaching a server.</span>}
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
      </figcaption>
    </figure>
  );
}

/**
 * One component rendered from the exact props a model would send (used on the
 * landing page's "how it works" sequence), optionally preceded by reply prose.
 */
export function Rendered({ ui, props, text }: { ui: string; props: Record<string, unknown>; text?: string }) {
  const node: UINode = { id: `rendered_${ui}`, ui, props, status: "done" };
  const ctx = staticContext({ messageId: "rendered", interactive: false });
  return (
    <div className="dy-root rd not-content">
      <div className="rd-chrome" aria-hidden="true">
        <span className="lc-dot" />
        <span className="lc-dot" />
        <span className="lc-dot" />
        <span className="rd-title">What the user sees</span>
      </div>
      <div className="rd-body">
        {text ? <Prose text={text} /> : null}
        <NodeView node={node} ctx={ctx} />
      </div>
    </div>
  );
}
