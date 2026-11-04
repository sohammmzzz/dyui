import { useState, type KeyboardEvent } from "react";
import { Star, ThumbsDown, ThumbsUp } from "lucide-react";
import { Bloom } from "../util/motion";
import { useInteraction } from "../util/hooks";
import { num, optStr } from "../util/props";
import { ResolvedNote } from "../util/ui";
import type { DyProps } from "../util/types";
import "../styles/interactive.css";

/** `rating` — stars or thumbs. values: {rating: number} (thumbs: 1 / -1) */
export function Rating({ node, ctx }: DyProps) {
  const p = node.props;
  const ia = useInteraction(node, ctx);
  const max = Math.max(2, Math.min(10, Math.round(num(p.max) ?? 5)));
  const thumbs = p.style === "thumbs";
  const action = optStr(p.action) ?? "rating";
  const label = optStr(p.label);
  const [hover, setHover] = useState(0);
  const r = ia.resolved ?? ia.pending;
  const value = num(r?.values?.rating) ?? 0;
  const shown = hover || value;
  const rate = (n: number, l: string) => ia.fire({ action, label: l, values: { rating: n } }, String(n));
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (ia.disabled) return;
    const cur = hover || value || 0;
    if (e.key === "ArrowRight" || e.key === "ArrowUp") {
      e.preventDefault();
      setHover(Math.min(max, cur + 1));
    } else if (e.key === "ArrowLeft" || e.key === "ArrowDown") {
      e.preventDefault();
      setHover(Math.max(1, cur - 1));
    } else if ((e.key === "Enter" || e.key === " ") && cur) {
      e.preventDefault();
      rate(cur, `Rated ${cur} of ${max}`);
    }
  };
  return (
    <Bloom className="dy-c dy-rating dy-panel" data-dy-ui="rating" data-state={ia.state}>
      {label && <div className="dy-rating-label">{label}</div>}
      <div className="dy-rating-row">
        {thumbs ? (
          <div className="dy-thumbs" role="group" aria-label={label || "Rate"}>
            {[
              { n: 1, l: "Helpful", I: ThumbsUp },
              { n: -1, l: "Not helpful", I: ThumbsDown },
            ].map(({ n, l, I }, i) => (
              <button
                key={n}
                type="button"
                className="dy-thumb dy-a-rise"
                style={{ ["--i" as any]: i }}
                aria-label={l}
                aria-pressed={value === n}
                data-on={value === n || undefined}
                data-dim={r && value !== n ? "" : undefined}
                disabled={ia.disabled}
                onClick={() => rate(n, l)}
              >
                <I width={17} height={17} />
              </button>
            ))}
          </div>
        ) : (
          <div
            className="dy-stars"
            role="radiogroup"
            aria-label={label || "Rating"}
            tabIndex={ia.disabled ? -1 : 0}
            onKeyDown={onKey}
            onPointerLeave={() => setHover(0)}
            onBlur={() => setHover(0)}
          >
            {Array.from({ length: max }, (_, i) => {
              const n = i + 1;
              const on = n <= shown;
              return (
                <button
                  key={n}
                  type="button"
                  tabIndex={-1}
                  role="radio"
                  aria-checked={value === n}
                  aria-label={`${n} of ${max}`}
                  className="dy-star dy-a-rise"
                  style={{ ["--i" as any]: i }}
                  data-on={on || undefined}
                  data-preview={hover > 0 && on ? "" : undefined}
                  disabled={ia.disabled}
                  onPointerEnter={() => !ia.disabled && setHover(n)}
                  onClick={() => rate(n, `Rated ${n} of ${max}`)}
                >
                  <Star width={22} height={22} strokeWidth={1.6} />
                </button>
              );
            })}
          </div>
        )}
        {r && <ResolvedNote label="Thanks for the feedback" sending={ia.state === "sending"} />}
      </div>
    </Bloom>
  );
}
