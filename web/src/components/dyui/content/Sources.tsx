import { useState } from "react";
import { ArrowUpRight } from "lucide-react";
import { Bloom } from "../util/motion";
import { arr, domainOf, isObj, optStr, safeUrl, settled, str } from "../util/props";
import { DyButton, Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import "../styles/content.css";

/** Site favicon (from the site itself) over a monogram fallback. */
export function Favicon({ url, size = 16 }: { url: string | null; size?: number }) {
  const domain = domainOf(url);
  const [ok, setOk] = useState(false);
  const [failed, setFailed] = useState(false);
  const letter = (domain || "•").charAt(0);
  const src = domain && url && /^https?:/.test(url) ? `${new URL(url).origin}/favicon.ico` : null;
  return (
    <span className="dy-favicon" style={{ width: size, height: size }} aria-hidden>
      {letter}
      {src && !failed && (
        <img
          src={src}
          alt=""
          loading="lazy"
          referrerPolicy="no-referrer"
          className={ok ? "is-loaded" : undefined}
          onLoad={(e) => (e.currentTarget.naturalWidth > 1 ? setOk(true) : setFailed(true))}
          onError={() => setFailed(true)}
        />
      )}
    </span>
  );
}

const MAX = 6;

/** `sources` — numbered citation cards with favicons. */
export function Sources({ node }: DyProps) {
  const streaming = node.status === "streaming";
  const items = arr(node.props.items).filter(isObj);
  const [all, setAll] = useState(false);
  const shown = all || items.length <= MAX ? items : items.slice(0, MAX - 1);
  return (
    <Bloom className="dy-c dy-sources" data-dy-ui="sources">
      <div className="dy-sources-head">
        <span className="dy-eyebrow">Sources</span>
        {items.length > 0 && <span className="dy-eyebrow" style={{ opacity: 0.7 }}>{items.length}</span>}
      </div>
      <ol className="dy-sources-grid" style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {shown.map((it, i) => {
          const url = safeUrl(it.url);
          const title = str(it.title) || domainOf(url) || "Untitled source";
          const snippet = optStr(it.snippet);
          const done = settled(i, items.length, streaming);
          const inner = (
            <>
              <span className="dy-source-top">
                <span className="dy-source-num">{i + 1}</span>
                <Favicon url={url} />
                <span className="dy-source-domain dy-ellipsis">{domainOf(url) || (url ? "File" : "")}</span>
                {url && <ArrowUpRight className="dy-source-ext" width={14} height={14} aria-hidden />}
              </span>
              <span className="dy-source-title dy-clamp-2">{done || it.title ? title : <Skel w="80%" h={11} />}</span>
              {snippet && <span className="dy-source-snippet dy-clamp-2">{snippet}</span>}
            </>
          );
          return (
            <li key={i} className="dy-a-rise" style={{ ["--i" as any]: i, display: "flex", minWidth: 0 }}>
              {url ? (
                <a className="dy-source" style={{ flex: 1 }} href={url} target="_blank" rel="noopener noreferrer" title={title}>
                  {inner}
                </a>
              ) : (
                <div className="dy-source" style={{ flex: 1 }}>
                  {inner}
                </div>
              )}
            </li>
          );
        })}
        {streaming && items.length === 0 &&
          [0, 1].map((i) => (
            <li key={`s${i}`} className="dy-source" aria-hidden>
              <Skel w="50%" h={10} />
              <Skel w="85%" h={11} />
            </li>
          ))}
      </ol>
      {!all && items.length > MAX && (
        <DyButton size="sm" variant="ghost" className="dy-sources-more" onClick={() => setAll(true)}>
          Show {items.length - shown.length} more
        </DyButton>
      )}
    </Bloom>
  );
}
