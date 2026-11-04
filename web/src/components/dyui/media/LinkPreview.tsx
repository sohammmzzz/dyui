import { ArrowUpRight } from "lucide-react";
import { Bloom } from "../util/motion";
import { domainOf, optStr, safeMediaUrl, safeUrl } from "../util/props";
import { Skel } from "../util/ui";
import { Favicon } from "../content/Sources";
import type { DyProps } from "../util/types";
import { BlurImage } from "./Image";
import "../styles/media.css";

/** `link_preview` — a rich link card. */
export function LinkPreview({ node }: DyProps) {
  const p = node.props;
  const url = safeUrl(p.url);
  const domain = domainOf(url);
  const title = optStr(p.title) ?? domain ?? "Link";
  const description = optStr(p.description);
  const image = safeMediaUrl(p.image);
  const site = optStr(p.site) ?? domain;
  const streaming = node.status === "streaming";
  let path = "";
  try {
    if (url) path = new URL(url).pathname.replace(/\/$/, "");
  } catch {
    /* ignore */
  }
  const body = (
    <>
      <span className="dy-link-main">
        <span className="dy-link-site">
          <Favicon url={url} />
          <span className="dy-ellipsis">{site}</span>
        </span>
        <span className="dy-link-title dy-clamp-2">{p.title || !streaming ? title : <Skel w="70%" h={12} />}</span>
        {description && <span className="dy-link-desc dy-clamp-2">{description}</span>}
        {url && (
          <span className="dy-link-url">
            <span className="dy-ellipsis">
              {domain}
              {path}
            </span>
            <ArrowUpRight width={13} height={13} aria-hidden />
          </span>
        )}
      </span>
      {image && (
        <span className="dy-link-thumb">
          <BlurImage src={image} alt="" cover />
        </span>
      )}
    </>
  );
  return (
    <Bloom className="dy-c dy-link-wrap" data-dy-ui="link_preview">
      {url ? (
        <a className="dy-link dy-panel" href={url} target="_blank" rel="noopener noreferrer" data-thumb={image ? "" : undefined}>
          {body}
        </a>
      ) : (
        <div className="dy-link dy-panel">{body}</div>
      )}
    </Bloom>
  );
}
