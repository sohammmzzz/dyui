import { ShieldCheck, TriangleAlert, X } from "lucide-react";
import { Bloom } from "../util/motion";
import { useInteraction } from "../util/hooks";
import { bool, isObj, optStr, str } from "../util/props";
import { DyButton, ResolvedNote, Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import "../styles/interactive.css";

/** `confirm` — an approval step (human-in-the-loop). values: {confirmed: bool} */
export function Confirm({ node, ctx }: DyProps) {
  const p = node.props;
  const ia = useInteraction(node, ctx);
  const title = str(p.title);
  const text = optStr(p.text);
  const danger = bool(p.danger);
  const yes = optStr(p.confirm_label) ?? "Confirm";
  const no = optStr(p.cancel_label) ?? "Cancel";
  const action = optStr(p.action) ?? "confirm";
  const data = isObj(p.data) ? p.data : undefined;
  const r = ia.resolved ?? ia.pending;
  const confirmed = r ? (typeof r.values?.confirmed === "boolean" ? r.values.confirmed : r.label === yes) : null;
  return (
    <Bloom className="dy-c dy-confirm dy-panel" data-dy-ui="confirm" data-danger={danger || undefined} data-state={ia.state} role="group" aria-label={title || "Confirm"}>
      <div className="dy-confirm-top">
        <span className="dy-confirm-icon dy-a-pop" style={{ ["--d" as any]: "140ms" }} aria-hidden>
          {danger ? <TriangleAlert width={18} height={18} /> : <ShieldCheck width={18} height={18} />}
        </span>
        <div className="dy-confirm-copy">
          <div className="dy-confirm-title">{title || <Skel w={200} h={18} />}</div>
          {text && <p className="dy-confirm-text">{text}</p>}
        </div>
      </div>
      <div className="dy-confirm-foot">
        {r ? (
          confirmed ? (
            <ResolvedNote label={r.label || yes} sending={ia.state === "sending"} tone={danger ? "danger" : "success"} />
          ) : (
            <ResolvedNote label={r.label || no} sending={ia.state === "sending"} tone="muted">
              <X width={12} height={12} strokeWidth={2.6} />
            </ResolvedNote>
          )
        ) : (
          <>
            <DyButton variant="secondary" disabled={ia.disabled} onClick={() => ia.fire({ action, label: no, data, values: { confirmed: false } }, "no")}>
              {no}
            </DyButton>
            <DyButton variant={danger ? "danger" : "primary"} disabled={ia.disabled} onClick={() => ia.fire({ action, label: yes, data, values: { confirmed: true } }, "yes")}>
              {yes}
            </DyButton>
          </>
        )}
      </div>
    </Bloom>
  );
}
