import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check, Copy } from "lucide-react";
import { cx, useMotionKit } from "./anim";

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // fallback for insecure contexts
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      ta.remove();
      return ok;
    } catch {
      return false;
    }
  }
}

/** Copy icon that morphs into a check for a moment. */
export function CopyIcon({ copied, size = 15 }: { copied: boolean; size?: number }) {
  const m = useMotionKit();
  const anim = m.reduced
    ? { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 } }
    : {
        initial: { opacity: 0, scale: 0.6, filter: "blur(2px)" },
        animate: { opacity: 1, scale: 1, filter: "blur(0px)" },
        exit: { opacity: 0, scale: 0.6, filter: "blur(2px)" },
      };
  return (
    <span className="sh-swap" style={{ width: size, height: size }}>
      <AnimatePresence initial={false} mode="popLayout">
        {copied ? (
          <motion.span key="check" className="sh-swap-item is-ok" {...anim} transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}>
            <Check size={size} strokeWidth={2.25} />
          </motion.span>
        ) : (
          <motion.span key="copy" className="sh-swap-item" {...anim} transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}>
            <Copy size={size} strokeWidth={1.9} />
          </motion.span>
        )}
      </AnimatePresence>
    </span>
  );
}

export function useCopied(ms = 1600): [boolean, (text: string) => void] {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);
  const copy = (text: string) => {
    void copyText(text).then((ok) => {
      if (!ok) return;
      setCopied(true);
      clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), ms);
    });
  };
  return [copied, copy];
}

/** Code-block style copy button: icon + label. */
export function CopyButton({ text, className, label = "Copy" }: { text: string; className?: string; label?: string }) {
  const [copied, copy] = useCopied();
  return (
    <button type="button" className={cx("sh-copy", copied && "is-copied", className)} onClick={() => copy(text)} aria-label={copied ? "Copied" : `${label} code`}>
      <CopyIcon copied={copied} size={13} />
      <span aria-hidden="true">{copied ? "Copied" : label}</span>
    </button>
  );
}
