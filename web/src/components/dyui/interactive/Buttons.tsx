import { Bloom } from "../util/motion";
import { useInteraction } from "../util/hooks";
import { arr, isObj, str } from "../util/props";
import { btnStyle, DyButton, ResolvedNote, Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import "../styles/interactive.css";

export type ButtonItem = { label: string; action: string; data?: Record<string, any>; style?: string };

export function readButtons(raw: unknown): ButtonItem[] {
  return arr(raw)
    .filter(isObj)
    .map((b) => ({ label: str(b.label ?? b.text), action: str(b.action) || "button", data: isObj(b.data) ? b.data : undefined, style: str(b.style) || undefined }))
    .filter((b) => b.label);
}

/** A row of action buttons with sending → resolved states. Used by `buttons` and card actions. */
export function ActionRow({ items, ia, align }: { items: ButtonItem[]; ia: ReturnType<typeof useInteraction>; align?: "start" | "end" }) {
  const { resolved, pending } = ia;
  const matched = resolved ? items.some((b) => b.label === resolved.label) : true;
  return (
    <div className="dy-actions" role="group" data-align={align}>
      {items.map((b, i) => {
        const chosen = resolved ? resolved.label === b.label : pending?.key === String(i);
        const state = chosen ? (resolved ? "chosen" : "sending") : resolved || pending ? "dim" : "idle";
        const fallback = i === 0 && (items.length === 1 || !items.some((x) => x.style)) ? "primary" : "secondary";
        return (
          <DyButton
            key={i}
            className="dy-a-rise"
            style={{ ["--i" as any]: i }}
            variant={btnStyle(b.style, fallback)}
            state={state}
            disabled={ia.disabled}
            aria-pressed={chosen || undefined}
            onClick={() => ia.fire({ action: b.action, label: b.label, data: b.data }, String(i))}
          >
            {b.label}
          </DyButton>
        );
      })}
      {resolved && !matched && <ResolvedNote label={resolved.label} />}
    </div>
  );
}

/** `buttons` — actions the user can take. */
export function Buttons({ node, ctx }: DyProps) {
  const ia = useInteraction(node, ctx);
  const items = readButtons(node.props.items ?? node.props.buttons);
  return (
    <Bloom className="dy-c dy-buttons" data-dy-ui="buttons" data-state={ia.state}>
      {items.length === 0 && ia.streaming ? (
        <div className="dy-actions">
          <Skel w={96} h={36} style={{ borderRadius: 10 }} />
          <Skel w={84} h={36} style={{ borderRadius: 10 }} />
        </div>
      ) : (
        <ActionRow items={items} ia={ia} />
      )}
    </Bloom>
  );
}
