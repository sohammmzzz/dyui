import { Bloom } from "../util/motion";
import { domainOf, optStr, safeUrl, str } from "../util/props";
import { SkelLines } from "../util/ui";
import type { DyProps } from "../util/types";
import "../styles/content.css";

/** `quote` — a pull quote set in the display serif. */
export function Quote({ node }: DyProps) {
  const p = node.props;
  const text = str(p.text).trim().replace(/^["“”]+|["“”]+$/g, "");
  const author = optStr(p.author);
  const source = optStr(p.source);
  const sourceUrl = safeUrl(source);
  const size = text.length > 260 ? "s" : text.length > 140 ? "m" : "l";
  const streaming = node.status === "streaming";
  return (
    <Bloom className="dy-c dy-quote" data-dy-ui="quote" data-size={size}>
      <span className="dy-quote-rail" aria-hidden />
      <figure style={{ margin: 0 }}>
        <blockquote className="dy-quote-text" style={{ margin: 0 }}>
          {text ? (
            <>
              <span className="dy-quote-mark" aria-hidden>
                “
              </span>
              {text}
              <span className="dy-quote-close" aria-hidden>
                ”
              </span>
            </>
          ) : streaming ? (
            <SkelLines lines={2} h={16} gap={12} />
          ) : null}
        </blockquote>
        {(author || source) && (
          <figcaption className="dy-quote-cite">
            {author && <span className="dy-quote-author">{author}</span>}
            {source && (
              <span className="dy-quote-source">
                {sourceUrl ? (
                  <a href={sourceUrl} target="_blank" rel="noopener noreferrer">
                    {domainOf(sourceUrl) || source}
                  </a>
                ) : (
                  source
                )}
              </span>
            )}
          </figcaption>
        )}
      </figure>
    </Bloom>
  );
}
