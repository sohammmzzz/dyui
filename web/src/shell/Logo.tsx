/**
 * The one place the brand mark is rendered (sidebar, header, welcome, avatar, gate, boot).
 *
 * The DyUI mark — "Typing → Card": two typing dots, then the reply arriving as an interface
 * card (its one tight corner is the chat-bubble convention). It is drawn inline so it takes
 * the app's accent (`--dy-accent`, which follows theme + `accent=`) and so its parts can move:
 * the welcome mark assembles dot → dot → card, and the assistant avatar "types" while thinking.
 * A custom `logo` from the app config is always shown as-is with an <img>.
 *
 * Geometry is shared with `brand/tools/brand_svgs.py` (100×100 grid; optical box x 2..98, y 25..75).
 */
import { useId } from "react";
import type { CSSProperties } from "react";
import { motion } from "motion/react";
import { useMotionKit, cx } from "./anim";

const DOT_1 = { cx: 11, cy: 50, r: 9 };
const DOT_2 = { cx: 35, cy: 50, r: 9 };
const CARD = "M66 25H84A14 14 0 0 1 98 39V61A14 14 0 0 1 84 75H56A4 4 0 0 1 52 71V39A14 14 0 0 1 66 25Z";
/** Tight crop of the mark (2:1) for places that want it wide rather than in a square box. */
const WIDE_BOX = "0 23 100 54";

type MarkProps = {
  size?: number;
  className?: string;
  /** "square": 100×100 box (drops into square slots). "wide": cropped 2:1, `size` is the width. */
  box?: "square" | "wide";
  /** Fill with the accent→teal bloom gradient instead of the flat accent. */
  gradient?: boolean;
  /** Entrance: dots arrive, then the card blooms in. */
  assemble?: boolean;
};

/** The DyUI mark, inline, in the current accent colour. */
export function DyMark({ size = 24, className, box = "square", gradient = false, assemble = false }: MarkProps) {
  const m = useMotionKit();
  const gid = `dy-mark-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const fill = gradient ? `url(#${gid})` : "var(--dy-accent)";
  const wide = box === "wide";
  const ease = [0.22, 1, 0.36, 1] as const;
  const play = assemble && !m.reduced;
  const part = (delay: number) =>
    play
      ? { initial: { opacity: 0, scale: 0.4 }, animate: { opacity: 1, scale: 1 }, transition: { duration: 0.5, delay, ease } }
      : {};
  return (
    <svg
      className={cx("sh-mark", className)}
      viewBox={wide ? WIDE_BOX : "0 0 100 100"}
      width={size}
      height={wide ? (size * 54) / 100 : size}
      aria-hidden="true"
      focusable="false"
    >
      {gradient && (
        <defs>
          <linearGradient id={gid} x1="0" y1="25" x2="100" y2="75" gradientUnits="userSpaceOnUse">
            <stop offset="0" style={{ stopColor: "var(--dy-accent)" }} />
            <stop offset="0.6" style={{ stopColor: "var(--dy-accent)" }} />
            <stop offset="1" style={{ stopColor: "var(--dy-teal)" }} />
          </linearGradient>
        </defs>
      )}
      <motion.circle className="sh-mark-dot" {...DOT_1} fill={fill} style={{ transformOrigin: "11px 50px" }} {...part(0)} />
      <motion.circle className="sh-mark-dot" {...DOT_2} fill={fill} style={{ transformOrigin: "35px 50px" }} {...part(0.12)} />
      <motion.path
        className="sh-mark-card"
        d={CARD}
        fill={fill}
        style={{ transformOrigin: "52px 75px" }}
        {...(play
          ? {
              initial: { opacity: 0, scale: 0.55, filter: "blur(6px)" },
              animate: { opacity: 1, scale: 1, filter: "blur(0px)" },
              transition: { duration: 0.7, delay: 0.3, ease },
            }
          : {})}
      />
    </svg>
  );
}

type LogoProps = { src?: string | null; size?: number; className?: string; alt?: string };

/** The app's logo from config, or the DyUI mark (square box, `size`×`size`). */
export function Logo({ src, size = 24, className, alt = "" }: LogoProps) {
  if (!src) return <DyMark size={size} className={cx("sh-logo", className)} />;
  return (
    <img
      className={cx("sh-logo", className)}
      src={src}
      width={size}
      height={size}
      alt={alt}
      draggable={false}
      decoding="async"
    />
  );
}

/**
 * Assistant avatar. The default mark uses the bloom gradient and, while the reply is
 * thinking, its dots "type" and the card breathes. A custom logo shows as-is.
 */
export function AvatarMark({ src, size = 28, thinking = false }: { src?: string | null; size?: number; thinking?: boolean }) {
  const style = { "--sh-avatar-size": `${size}px` } as CSSProperties;
  return (
    <span className={cx("sh-avatar", thinking && "is-thinking", !src && "is-mark")} style={style} aria-hidden="true">
      {src ? (
        <img src={src} alt="" width={size} height={size} draggable={false} />
      ) : (
        <DyMark size={size} gradient className="sh-avatar-mark" />
      )}
    </span>
  );
}

/** Welcome / gate mark: the DyUI mark assembles (dot → dot → card) over a soft glow; custom logos bloom in. */
export function BloomLogo({ src, size = 60 }: { src?: string | null; size?: number }) {
  const m = useMotionKit();
  const ease = [0.22, 1, 0.36, 1] as const;
  const glow = (
    <motion.span
      className="sh-bloom-glow"
      initial={m.reduced ? { opacity: 0 } : { opacity: 0, scale: 0.55 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: m.reduced ? 0.12 : 1.6, ease }}
    />
  );
  if (!src) {
    // the mark is 2:1 — give it ~1.6× the slot width so its visual weight matches a square logo
    const w = Math.round(size * 1.6);
    return (
      <div className="sh-bloom-logo is-mark" style={{ width: w, height: size }} aria-hidden="true">
        {glow}
        <motion.div
          className="sh-bloom-mark"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: m.reduced ? 0.12 : 0.2 }}
        >
          <DyMark size={w} box="wide" assemble />
        </motion.div>
      </div>
    );
  }
  return (
    <div className="sh-bloom-logo" style={{ width: size, height: size }} aria-hidden="true">
      {glow}
      {!m.reduced && (
        <motion.span
          className="sh-bloom-ripple"
          initial={{ opacity: 0.55, scale: 0.7 }}
          animate={{ opacity: 0, scale: 2.1 }}
          transition={{ duration: 1.9, delay: 0.25, ease }}
        />
      )}
      <motion.div
        className="sh-bloom-mark"
        initial={m.reduced ? { opacity: 0 } : { opacity: 0, scale: 0.86, filter: "blur(10px)" }}
        animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
        transition={{ duration: m.reduced ? 0.12 : 0.95, ease }}
      >
        <Logo src={src} size={size} />
      </motion.div>
    </div>
  );
}
