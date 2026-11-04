import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { dur, ease } from "../../../lib/motion";
import "../styles/base.css";
import "../styles/media.css";

export type LightboxImage = { src: string; alt?: string; caption?: string };

/** Full-screen image viewer: Esc closes, ←/→ navigate, focus is returned on close. */
export function Lightbox({ images, index, onClose, onIndex }: { images: LightboxImage[]; index: number | null; onClose: () => void; onIndex?: (i: number) => void }) {
  const [mounted, setMounted] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);
  const lastFocus = useRef<HTMLElement | null>(null);
  const reduced = useReducedMotion();
  const open = index !== null && !!images[index];
  const many = images.length > 1;

  useEffect(() => setMounted(true), []);
  useEffect(() => {
    if (!open) return;
    lastFocus.current = document.activeElement as HTMLElement;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const t = setTimeout(() => closeRef.current?.focus(), 30);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (many && onIndex && e.key === "ArrowRight") onIndex(((index ?? 0) + 1) % images.length);
      else if (many && onIndex && e.key === "ArrowLeft") onIndex(((index ?? 0) - 1 + images.length) % images.length);
    };
    window.addEventListener("keydown", onKey);
    return () => {
      clearTimeout(t);
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, index, images.length, many, onClose, onIndex]);
  useEffect(() => {
    if (!open && lastFocus.current) {
      lastFocus.current.focus?.();
      lastFocus.current = null;
    }
  }, [open]);

  if (!mounted) return null;
  const img = open ? images[index!] : null;
  return createPortal(
    <AnimatePresence>
      {open && img && (
        <motion.div
          className="dy-c dy-lightbox"
          role="dialog"
          aria-modal="true"
          aria-label={img.alt || "Image viewer"}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: dur[2], ease }}
          onClick={onClose}
        >
          <div className="dy-lightbox-bar" onClick={(e) => e.stopPropagation()}>
            {many && (
              <span className="dy-lightbox-count">
                {index! + 1} / {images.length}
              </span>
            )}
            <button ref={closeRef} type="button" className="dy-lightbox-btn" onClick={onClose} aria-label="Close">
              <X width={18} height={18} />
            </button>
          </div>
          {many && onIndex && (
            <>
              <button
                type="button"
                className="dy-lightbox-btn dy-lightbox-nav dy-lightbox-prev"
                aria-label="Previous image"
                onClick={(e) => {
                  e.stopPropagation();
                  onIndex((index! - 1 + images.length) % images.length);
                }}
              >
                <ChevronLeft width={20} height={20} />
              </button>
              <button
                type="button"
                className="dy-lightbox-btn dy-lightbox-nav dy-lightbox-next"
                aria-label="Next image"
                onClick={(e) => {
                  e.stopPropagation();
                  onIndex((index! + 1) % images.length);
                }}
              >
                <ChevronRight width={20} height={20} />
              </button>
            </>
          )}
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.figure
              key={img.src + index}
              className="dy-lightbox-fig"
              initial={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.97, filter: "blur(8px)" }}
              animate={reduced ? { opacity: 1 } : { opacity: 1, scale: 1, filter: "blur(0px)" }}
              exit={{ opacity: 0 }}
              transition={{ duration: dur[3], ease }}
              onClick={(e) => e.stopPropagation()}
            >
              <img src={img.src} alt={img.alt ?? ""} />
              {(img.caption || img.alt) && <figcaption>{img.caption || img.alt}</figcaption>}
            </motion.figure>
          </AnimatePresence>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
