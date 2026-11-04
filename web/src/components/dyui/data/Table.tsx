import { useMemo, useRef, useState, type ReactNode } from "react";
import { ArrowUp, Check, Minus } from "lucide-react";
import { Bloom } from "../util/motion";
import { arr, domainOf, fmtNum, isObj, optStr, parseNumberish, safeUrl, str } from "../util/props";
import { Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import "../styles/base.css";
import "../styles/data.css";

const NO_GROUP = /\b(year|yr|id|zip|code|no\.?|#|pin|ext)\b/i;

function Cell({ v, numeric, group }: { v: unknown; numeric: boolean; group: boolean }): ReactNode {
  if (v === null || v === undefined || v === "") return <span className="dy-cell-null">—</span>;
  if (typeof v === "boolean")
    return (
      <span className="dy-cell-bool" data-on={v || undefined} aria-label={v ? "Yes" : "No"}>
        {v ? <Check width={15} height={15} strokeWidth={2.4} /> : <Minus width={15} height={15} />}
      </span>
    );
  if (typeof v === "number") {
    const s = fmtNum(v, { group });
    return v < 0 && numeric ? <span className="dy-table-neg">{s}</span> : s;
  }
  if (typeof v === "string") {
    const url = /^(https?:\/\/|mailto:|\/api\/files\/)/.test(v) ? safeUrl(v) : null;
    if (url)
      return (
        <a href={url} target="_blank" rel="noopener noreferrer">
          {domainOf(url) || v}
        </a>
      );
    return v;
  }
  return <code>{JSON.stringify(v)}</code>;
}

/** `table` — sortable, numeric-aware, sticky header, scrolls past 400px. */
export function Table({ node }: DyProps) {
  const p = node.props;
  const streaming = node.status === "streaming";
  const columns = arr(p.columns).map((c) => (isObj(c) ? str(c.label ?? c.name ?? c.key) : str(c)));
  const rows: unknown[][] = arr(p.rows).map((r) => (Array.isArray(r) ? r : isObj(r) ? columns.map((c) => r[c]) : [r]));
  const caption = optStr(p.caption ?? p.title);
  const [sort, setSort] = useState<{ col: number; dir: 1 | -1 } | null>(null);
  // rows present at first paint stagger in; rows streamed in later bloom on arrival
  const initialCount = useRef<number | null>(null);
  if (initialCount.current === null && rows.length) initialCount.current = rows.length;

  const numeric = useMemo(
    () =>
      columns.map((_, ci) => {
        let n = 0;
        let t = 0;
        for (const r of rows) {
          const v = r[ci];
          if (v === null || v === undefined || v === "") continue;
          t++;
          if (typeof v === "number" || (typeof v === "string" && parseNumberish(v) !== null)) n++;
        }
        return t > 0 && n / t >= 0.7;
      }),
    [columns.join("\u0001"), rows],
  );

  const order = useMemo(() => {
    const idx = rows.map((_, i) => i);
    if (!sort) return idx;
    const { col, dir } = sort;
    const key = (v: unknown) => (numeric[col] ? parseNumberish(v as any) : v === null || v === undefined ? null : String(v));
    return idx.sort((a, b) => {
      const ka = key(rows[a][col]);
      const kb = key(rows[b][col]);
      if (ka === null && kb === null) return 0;
      if (ka === null) return 1;
      if (kb === null) return -1;
      if (typeof ka === "number" && typeof kb === "number") return (ka - kb) * dir;
      return String(ka).localeCompare(String(kb), undefined, { numeric: true, sensitivity: "base" }) * dir;
    });
  }, [rows, sort, numeric]);

  const toggle = (col: number) =>
    setSort((s) => (!s || s.col !== col ? { col, dir: numeric[col] ? -1 : 1 } : s.dir === (numeric[col] ? -1 : 1) ? { col, dir: (s.dir * -1) as 1 | -1 } : null));

  const noCols = columns.length === 0;
  return (
    <Bloom className="dy-c dy-table dy-panel" data-dy-ui="table">
      {caption && (
        <div className="dy-table-cap">
          <span className="dy-eyebrow">{caption}</span>
          {rows.length > 0 && (
            <span className="dy-table-count">
              {rows.length} {rows.length === 1 ? "row" : "rows"}
            </span>
          )}
        </div>
      )}
      <div className="dy-table-scroll" tabIndex={0} role="region" aria-label={caption || "Table"}>
        <table>
          {caption && <caption className="dy-sr">{caption}</caption>}
          <thead>
            <tr>
              {noCols
                ? [0, 1, 2].map((i) => (
                    <th key={i}>
                      <span className="dy-th-btn">
                        <Skel w={56 + i * 14} h={9} />
                      </span>
                    </th>
                  ))
                : columns.map((c, i) => {
                    const active = sort?.col === i;
                    return (
                      <th
                        key={i}
                        className={numeric[i] ? "is-num" : undefined}
                        aria-sort={active ? (sort!.dir === 1 ? "ascending" : "descending") : "none"}
                      >
                        <button
                          type="button"
                          className="dy-th-btn"
                          data-active={active || undefined}
                          data-dir={active ? sort!.dir : undefined}
                          onClick={() => toggle(i)}
                          title={`Sort by ${c}`}
                        >
                          <span>{c}</span>
                          <ArrowUp className="dy-th-sort" strokeWidth={2.2} aria-hidden />
                        </button>
                      </th>
                    );
                  })}
            </tr>
          </thead>
          <tbody>
            {order.map((ri, k) => {
              const row = rows[ri];
              const late = initialCount.current !== null && ri >= initialCount.current;
              return (
                <tr key={ri} className="dy-a-rise" style={{ ["--i" as any]: late ? 0 : k }}>
                  {columns.map((c, ci) => {
                    const missing = streaming && ri === rows.length - 1 && ci >= row.length;
                    return (
                      <td key={ci} className={numeric[ci] ? "is-num" : undefined}>
                        {missing ? <Skel w={numeric[ci] ? 40 : 72} h={9} className="dy-skel-inline" /> : <Cell v={row[ci]} numeric={numeric[ci]} group={!NO_GROUP.test(c)} />}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
            {streaming && rows.length === 0 &&
              [0, 1, 2].map((r) => (
                <tr key={`sk${r}`} aria-hidden>
                  {(noCols ? [0, 1, 2] : columns).map((_, ci) => (
                    <td key={ci}>
                      <Skel w={ci === 0 ? 96 : 60} h={9} className="dy-skel-inline" />
                    </td>
                  ))}
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </Bloom>
  );
}
