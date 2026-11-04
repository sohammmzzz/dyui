import type { ReactNode } from "react";
import { Bloom } from "../util/motion";
import { arr, domainOf, fmtNum, isObj, optStr, safeUrl, str } from "../util/props";
import { Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import "../styles/data.css";

function Value({ v }: { v: unknown }): ReactNode {
  if (v === null || v === undefined || v === "") return <span className="dy-faint">—</span>;
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (typeof v === "number") return fmtNum(v);
  if (typeof v === "string") {
    const url = /^(https?:\/\/|mailto:|\/api\/files\/)/.test(v) ? safeUrl(v) : null;
    if (url)
      return (
        <a href={url} target="_blank" rel="noopener noreferrer">
          {url.startsWith("mailto:") ? v.replace(/^mailto:/, "") : domainOf(url) || v}
        </a>
      );
    return v;
  }
  if (Array.isArray(v) && v.every((x) => typeof x === "string" || typeof x === "number")) return v.join(", ");
  return <code>{JSON.stringify(v)}</code>;
}

/** `keyvalue` — a quiet definition list. Accepts items: [{key, value}] or data: {k: v}. */
export function KeyValue({ node }: DyProps) {
  const p = node.props;
  const streaming = node.status === "streaming";
  let items: { key: string; value: unknown }[] = arr(p.items)
    .filter(isObj)
    .map((it) => ({ key: str(it.key ?? it.label ?? it.name), value: it.value }));
  if (!items.length && isObj(p.data)) items = Object.entries(p.data).map(([key, value]) => ({ key, value }));
  const title = optStr(p.title);
  return (
    <Bloom className="dy-c dy-kv dy-panel" data-dy-ui="keyvalue">
      {title && <div className="dy-eyebrow" style={{ padding: "12px 0 2px" }}>{title}</div>}
      <dl>
        {items.map((it, i) => (
          <div key={i} className="dy-kv-row dy-a-rise" style={{ ["--i" as any]: i }}>
            <dt>{it.key}</dt>
            <dd>{streaming && i === items.length - 1 && it.value === undefined ? <Skel w={90} h={10} className="dy-skel-inline" /> : <Value v={it.value} />}</dd>
          </div>
        ))}
        {streaming && items.length === 0 &&
          [0, 1, 2].map((i) => (
            <div key={i} className="dy-kv-row" aria-hidden>
              <dt>
                <Skel w={70} h={9} />
              </dt>
              <dd>
                <Skel w={110 - i * 18} h={10} />
              </dd>
            </div>
          ))}
      </dl>
    </Bloom>
  );
}
