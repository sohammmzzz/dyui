import { useMemo } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check, Copy, FileCode2 } from "lucide-react";
import { dur, ease } from "../../../lib/motion";
import { highlight, languageLabel } from "../util/highlight";
import { useCopy } from "../util/hooks";
import { cx } from "../util/props";
import "../styles/base.css";
import "../styles/content.css";

export function CopyButton({ text, label = true, className }: { text: string; label?: boolean; className?: string }) {
  const { copied, copy } = useCopy();
  return (
    <button
      type="button"
      className={cx("dy-copy", copied && "is-copied", className)}
      onClick={() => copy(text)}
      aria-label={copied ? "Copied" : "Copy to clipboard"}
    >
      <span className="dy-copy-icon">
        <AnimatePresence initial={false} mode="popLayout">
          {copied ? (
            <motion.span key="c" initial={{ opacity: 0, scale: 0.4, rotate: -20 }} animate={{ opacity: 1, scale: 1, rotate: 0 }} exit={{ opacity: 0, scale: 0.6 }} transition={{ duration: dur[2], ease }}>
              <Check width={14} height={14} strokeWidth={2.4} />
            </motion.span>
          ) : (
            <motion.span key="i" initial={{ opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.6 }} transition={{ duration: dur[2], ease }}>
              <Copy width={14} height={14} />
            </motion.span>
          )}
        </AnimatePresence>
      </span>
      {label && <span className="dy-copy-label">{copied ? "Copied" : "Copy"}</span>}
    </button>
  );
}

/** Highlighted code with header (filename / language) and copy. Used by `code` and markdown fences. */
export function CodeBlock({ code, language, filename, streaming, className }: { code: string; language?: string; filename?: string; streaming?: boolean; className?: string }) {
  const { nodes, language: lang } = useMemo(() => highlight(code, language), [code, language]);
  const lines = code.split("\n").length;
  const label = languageLabel(language || lang);
  const gutter = lines >= 3;
  return (
    <div className={cx("dy-code", className)}>
      <div className="dy-code-head">
        <span className="dy-code-name">
          {filename ? (
            <>
              <FileCode2 width={14} height={14} aria-hidden />
              <span className="dy-ellipsis">{filename}</span>
            </>
          ) : (
            <span className="dy-code-lang">{label ?? "Code"}</span>
          )}
        </span>
        {filename && label && <span className="dy-code-lang">{label}</span>}
        <CopyButton text={code} />
      </div>
      <div className="dy-code-body">
        {gutter && (
          <span className="dy-code-gutter" aria-hidden>
            {Array.from({ length: lines }, (_, i) => i + 1).join("\n")}
          </span>
        )}
        <pre className="dy-code-pre">
          <code className={cx("hljs", lang && `language-${lang}`)}>
            {nodes}
            {streaming && <span className="dy-code-caret" aria-hidden />}
          </code>
        </pre>
      </div>
    </div>
  );
}
