/**
 * The one place the brand mark is rendered. Swap `@/styles/logo.svg` and every
 * surface (sidebar, welcome, avatar, gate, boot) follows — nothing here depends
 * on the mark's inner geometry.
 */
import type { CSSProperties } from "react";
import { motion } from "motion/react";
import defaultLogo from "@/styles/logo.svg";
import { useMotionKit, cx } from "./anim";

type LogoProps = { src?: string | null; size?: number; className?: string; alt?: string };

/** Full-colour mark (app logo from config, or the DyUI mark). */
export function Logo({ src, size = 24, className, alt = "" }: LogoProps) {
  return (
    <img
      className={cx("sh-logo", className)}
      src={src || defaultLogo}
      width={size}
      height={size}
      alt={alt}
      draggable={false}
      decoding="async"
    />
  );
}

/**
 * Assistant avatar. The default mark is drawn as a silhouette filled with the
 * bloom gradient (so it follows the app's accent); a custom logo shows as-is.
 */
export function AvatarMark({ src, size = 28, thinking = false }: { src?: string | null; size?: number; thinking?: boolean }) {
  const style = { "--sh-avatar-size": `${size}px`, "--sh-logo-url": `url("${defaultLogo}")` } as CSSProperties;
  return (
    <span className={cx("sh-avatar", thinking && "is-thinking")} style={style} aria-hidden="true">
      {src ? <img src={src} alt="" width={size} height={size} draggable={false} /> : <span className="sh-avatar-mark" />}
    </span>
  );
}

/** Welcome / gate mark: shape-agnostic bloom (scale, blur, opacity) over a soft radial glow and one ripple. */
export function BloomLogo({ src, size = 60 }: { src?: string | null; size?: number }) {
  const m = useMotionKit();
  return (
    <div className="sh-bloom-logo" style={{ width: size, height: size }} aria-hidden="true">
      <motion.span
        className="sh-bloom-glow"
        initial={m.reduced ? { opacity: 0 } : { opacity: 0, scale: 0.55 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: m.reduced ? 0.12 : 1.6, ease: [0.22, 1, 0.36, 1] }}
      />
      {!m.reduced && (
        <motion.span
          className="sh-bloom-ripple"
          initial={{ opacity: 0.55, scale: 0.7 }}
          animate={{ opacity: 0, scale: 2.1 }}
          transition={{ duration: 1.9, delay: 0.25, ease: [0.22, 1, 0.36, 1] }}
        />
      )}
      <motion.div
        className="sh-bloom-mark"
        initial={m.reduced ? { opacity: 0 } : { opacity: 0, scale: 0.86, filter: "blur(10px)" }}
        animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
        transition={{ duration: m.reduced ? 0.12 : 0.95, ease: [0.22, 1, 0.36, 1] }}
      >
        <Logo src={src} size={size} />
      </motion.div>
    </div>
  );
}
