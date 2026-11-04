import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { ChevronRight, ChevronsDownUp, ChevronsUpDown } from "lucide-react";
import { Bloom } from "../util/motion";
import { isObj, optStr } from "../util/props";
import { SkelLines } from "../util/ui";
import { CopyButton } from "../content/CodeBlock";
import type { DyProps } from "../util/types";
import "../styles/data.css";

const Gen = createContext<{ gen: number; open: boolean | null }>({ gen: 0, open: null });
const PAGE = 50;

function summary(v: unknown) {
  if (Array.isArray(v)) return `${v.length} ${v.length === 1 ? "item" : "items"}`;
  if (isObj(v)) {
    const n = Object.keys(v).length;
    return `${n} ${n === 1 ? "key" : "keys"}`;
  }
  return "";
}

function Leaf({ v }: { v: unknown }) {
  if (typeof v === "string") return <span className="dy-jn-str">"{v}"</span>;
  if (typeof v === "number") return <span className="dy-jn-num">{String(v)}</span>;
  if (typeof v === "boolean") return <span className="dy-jn-bool">{String(v)}</span>;
  return <span className="dy-jn-null">null</span>;
}

function JNode({ k, v, depth, isIndex }: { k?: string; v: unknown; depth: number; isIndex?: boolean }) {
  const { gen, open: forced } = useContext(Gen);
  const branch = Array.isArray(v) || isObj(v);
  const [open, setOpen] = useState(depth < 2);
  const [limit, setLimit] = useState(PAGE);
  useEffect(() => {
    if (forced !== null) setOpen(forced);
  }, [gen]); // eslint-disable-line react-hooks/exhaustive-deps

  const keyEl =
    k !== undefined ? (
      <>
        <span className={isIndex ? "dy-jn-idx" : "dy-jn-key"}>{isIndex ? k : `"${k}"`}</span>
        <span className="dy-jn-punct">:&nbsp;</span>
      </>
    ) : null;

  if (!branch)
    return (
      <div className="dy-jn">
        <div className="dy-jn-row">
          <span className="dy-jn-spacer" />
          {keyEl}
          <Leaf v={v} />
        </div>
      </div>
    );

  const entries: [string, unknown][] = Array.isArray(v) ? v.map((x, i) => [String(i), x]) : Object.entries(v as object);
  const [o, c] = Array.isArray(v) ? ["[", "]"] : ["{", "}"];
  return (
    <div className="dy-jn">
      <div className="dy-jn-row">
        <button type="button" className="dy-jn-toggle" aria-expanded={open} aria-label={open ? "Collapse" : "Expand"} onClick={() => setOpen((x) => !x)}>
          <ChevronRight width={13} height={13} strokeWidth={2.4} />
        </button>
        {keyEl}
        <span className="dy-jn-punct">{o}</span>
        {!open && (
          <>
            <span className="dy-jn-punct">…{c}</span>
            <span className="dy-jn-preview">{summary(v)}</span>
          </>
        )}
      </div>
      {open && (
        <div className="dy-jn-children dy-a-fade">
          {entries.slice(0, limit).map(([ck, cv]) => (
            <JNode key={ck} k={ck} v={cv} depth={depth + 1} isIndex={Array.isArray(v)} />
          ))}
          {entries.length > limit && (
            <button type="button" className="dy-copy dy-jn-more" onClick={() => setLimit((l) => l + PAGE)}>
              Show {Math.min(PAGE, entries.length - limit)} more of {entries.length - limit}
            </button>
          )}
        </div>
      )}
      {open && (
        <div className="dy-jn-row">
          <span className="dy-jn-spacer" />
          <span className="dy-jn-punct">{c}</span>
        </div>
      )}
    </div>
  );
}

/** `json` — collapsible tree for structured data. */
export function Json({ node }: DyProps) {
  const p = node.props;
  const streaming = node.status === "streaming";
  const data = useMemo(() => {
    if (typeof p.data === "string") {
      try {
        return JSON.parse(p.data);
      } catch {
        return p.data;
      }
    }
    return p.data;
  }, [p.data]);
  const [g, setG] = useState({ gen: 0, open: null as boolean | null });
  const text = useMemo(() => {
    try {
      return JSON.stringify(data, null, 2) ?? "";
    } catch {
      return "";
    }
  }, [data]);
  const allOpen = g.open === true;
  return (
    <Bloom className="dy-c dy-json dy-panel" data-dy-ui="json">
      <div className="dy-json-head">
        <span className="dy-eyebrow">{optStr(p.title) ?? "JSON"}</span>
        <span className="dy-json-meta">{data !== undefined ? (Array.isArray(data) ? `Array · ${summary(data)}` : isObj(data) ? `Object · ${summary(data)}` : typeof data) : ""}</span>
        <button
          type="button"
          className="dy-copy"
          onClick={() => setG((s) => ({ gen: s.gen + 1, open: !allOpen }))}
          aria-label={allOpen ? "Collapse all" : "Expand all"}
          title={allOpen ? "Collapse all" : "Expand all"}
        >
          {allOpen ? <ChevronsDownUp width={14} height={14} /> : <ChevronsUpDown width={14} height={14} />}
        </button>
        <CopyButton text={text} label={false} />
      </div>
      <div className="dy-json-body" tabIndex={0} role="tree" aria-label={optStr(p.title) ?? "JSON data"}>
        {data === undefined && streaming ? (
          <SkelLines lines={4} />
        ) : (
          <Gen.Provider value={g}>
            <JNode v={data ?? null} depth={0} />
          </Gen.Provider>
        )}
      </div>
    </Bloom>
  );
}
