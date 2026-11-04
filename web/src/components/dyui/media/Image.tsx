import { useEffect, useRef, useState } from "react";
import { ImageOff, Maximize2 } from "lucide-react";
import { Bloom } from "../util/motion";
import { cx, optStr, safeMediaUrl } from "../util/props";
import { Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import { Lightbox } from "./Lightbox";
import "../styles/media.css";

/** An image that blurs up into focus once loaded. */
export function BlurImage({ src, alt, className, onLoaded, cover }: { src: string; alt?: string; className?: string; onLoaded?: (w: number, h: number) => void; cover?: boolean }) {
  const ref = useRef<HTMLImageElement>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (el && el.complete && el.naturalWidth) {
      setLoaded(true);
      onLoaded?.(el.naturalWidth, el.naturalHeight);
    }
  }, [src]); // eslint-disable-line react-hooks/exhaustive-deps
  if (error)
    return (
      <span className={cx("dy-img-fallback", className)}>
        <ImageOff width={18} height={18} aria-hidden />
        <span>Image unavailable</span>
      </span>
    );
  return (
    <>
      {!loaded && <Skel className="dy-img-skel" />}
      <img
        ref={ref}
        src={src}
        alt={alt ?? ""}
        loading="lazy"
        decoding="async"
        referrerPolicy="no-referrer"
        className={cx("dy-img", cover && "dy-img--cover", loaded && "is-loaded", className)}
        onLoad={(e) => {
          setLoaded(true);
          onLoaded?.(e.currentTarget.naturalWidth, e.currentTarget.naturalHeight);
        }}
        onError={() => setError(true)}
      />
    </>
  );
}

/** `image` — blur-up on load; click to open a lightbox. */
export function Image({ node }: DyProps) {
  const p = node.props;
  const src = safeMediaUrl(p.src ?? p.url);
  const alt = optStr(p.alt);
  const caption = optStr(p.caption);
  const [ratio, setRatio] = useState<number | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const streaming = node.status === "streaming";
  return (
    <Bloom className="dy-c dy-image" data-dy-ui="image">
      <figure className="dy-image-fig">
        {src ? (
          <button
            type="button"
            className="dy-image-frame"
            data-loaded={ratio ? "" : undefined}
            style={ratio ? { aspectRatio: String(ratio) } : undefined}
            onClick={() => ratio && setOpen(0)}
            aria-label={alt ? `Open image: ${alt}` : "Open image"}
          >
            <BlurImage src={src} alt={alt} onLoaded={(w, h) => setRatio(w / h)} cover />
            <span className="dy-image-zoom" aria-hidden>
              <Maximize2 width={14} height={14} />
            </span>
          </button>
        ) : (
          <div className="dy-image-frame" aria-hidden>
            {streaming ? <Skel className="dy-img-skel" /> : <span className="dy-img-fallback"><ImageOff width={18} height={18} /><span>Image unavailable</span></span>}
          </div>
        )}
        {caption && <figcaption className="dy-media-caption">{caption}</figcaption>}
      </figure>
      {src && <Lightbox images={[{ src, alt, caption }]} index={open} onClose={() => setOpen(null)} />}
    </Bloom>
  );
}
