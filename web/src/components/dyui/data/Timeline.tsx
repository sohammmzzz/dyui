import { Check } from "lucide-react";
import { Bloom } from "../util/motion";
import { arr, isObj, optStr, str } from "../util/props";
import { Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import "../styles/data.css";

/** `timeline` — vertical events with done / active / pending states. */
export function Timeline({ node }: DyProps) {
  const streaming = node.status === "streaming";
  const items = arr(node.props.items).filter(isObj);
  const anyStatus = items.some((it) => it.status);
  return (
    <Bloom className="dy-c dy-timeline dy-panel" data-dy-ui="timeline">
      <ol>
        {items.map((it, i) => {
          const status = ["done", "active", "pending"].includes(it.status) ? it.status : anyStatus ? "pending" : "none";
          const last = i === items.length - 1 && !streaming;
          return (
            <li key={i} className="dy-tl-item dy-a-rise" data-status={status} style={{ ["--i" as any]: i }} aria-current={status === "active" ? "step" : undefined}>
              <div className="dy-tl-rail" aria-hidden>
                <span className="dy-tl-dot">{status === "done" && <Check strokeWidth={2.8} />}</span>
                {!last && <span className="dy-tl-line" />}
              </div>
              <div className="dy-tl-body">
                <div className="dy-tl-head">
                  <span className="dy-tl-title">{str(it.title) || <Skel w={140} h={10} className="dy-skel-inline" />}</span>
                  {optStr(it.time) && <span className="dy-tl-time">{str(it.time)}</span>}
                </div>
                {optStr(it.text) && <p className="dy-tl-text">{str(it.text)}</p>}
                {status !== "none" && <span className="dy-sr">{status}</span>}
              </div>
            </li>
          );
        })}
        {streaming && items.length === 0 &&
          [0, 1].map((i) => (
            <li key={i} className="dy-tl-item" data-status="pending" aria-hidden>
              <div className="dy-tl-rail">
                <span className="dy-tl-dot" />
                <span className="dy-tl-line" />
              </div>
              <div className="dy-tl-body">
                <Skel w={150} h={10} />
              </div>
            </li>
          ))}
      </ol>
    </Bloom>
  );
}
