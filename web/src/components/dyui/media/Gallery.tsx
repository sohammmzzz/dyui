import { useState } from "react";
import { Bloom } from "../util/motion";
import { arr, isObj, optStr, safeMediaUrl, str } from "../util/props";
import { Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import { BlurImage } from "./Image";
import { Lightbox, type LightboxImage } from "./Lightbox";
import "../styles/media.css";

const MAX = 6;

/** `gallery` — a calm grid of images with a keyboard-navigable lightbox. */
export function Gallery({ node }: DyProps) {
  const streaming = node.status === "streaming";
  const images: LightboxImage[] = arr(node.props.images ?? node.props.items)
    .map((it) => (isObj(it) ? { src: safeMediaUrl(it.src ?? it.url), alt: optStr(it.alt), caption: optStr(it.caption) } : { src: safeMediaUrl(str(it)) }))
    .filter((it): it is LightboxImage => !!it.src);
  const [open, setOpen] = useState<number | null>(null);
  const n = images.length;
  const shown = n > MAX ? images.slice(0, MAX) : images;
  const cols = n <= 1 ? 1 : n === 2 || n === 4 ? 2 : 3;
  const title = optStr(node.props.title);
  return (
    <Bloom className="dy-c dy-gallery" data-dy-ui="gallery">
      {title && <div className="dy-eyebrow dy-gallery-title">{title}</div>}
      <div className="dy-gallery-grid" data-cols={cols} data-count={Math.min(n, MAX)}>
        {shown.map((im, i) => {
          const more = i === MAX - 1 && n > MAX ? n - MAX + 1 : 0;
          return (
            <button
              key={i}
              type="button"
              className="dy-gallery-tile dy-a-bloom"
              style={{ ["--i" as any]: i }}
              onClick={() => setOpen(i)}
              aria-label={more ? `Show all ${n} images` : im.alt ? `Open image: ${im.alt}` : `Open image ${i + 1}`}
            >
              <BlurImage src={im.src} alt={im.alt} cover />
              {more > 0 && <span className="dy-gallery-more">+{more}</span>}
              {im.caption && !more && <span className="dy-gallery-cap">{im.caption}</span>}
            </button>
          );
        })}
        {streaming &&
          Array.from({ length: Math.max(0, (n === 0 ? 3 : 1)) }, (_, i) => (
            <div key={`s${i}`} className="dy-gallery-tile" aria-hidden>
              <Skel className="dy-img-skel" />
            </div>
          ))}
      </div>
      <Lightbox images={images} index={open} onClose={() => setOpen(null)} onIndex={setOpen} />
    </Bloom>
  );
}
