import { useCallback, useEffect, useImperativeHandle, useRef, useState, type Ref } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowUp, CircleAlert, Paperclip, X } from "lucide-react";
import { describeError, isAbortError, type Transport } from "@/lib/api";
import type { FileRef } from "@/lib/types";
import { cx, useMotionKit } from "./anim";
import { fileKind, formatBytes } from "./Parts";

export type ComposerHandle = { addFiles: (files: FileList | File[]) => void; focus: () => void };

type Attachment = {
  key: string;
  file: File;
  progress: number;
  ref?: FileRef;
  error?: string;
  ctrl: AbortController;
  preview?: string;
};

const MAX_FILES = 10;

export function Composer({
  handle,
  transport,
  placeholder,
  busy,
  disabled,
  uploads,
  autoFocusKey,
  onSend,
  onStop,
}: {
  handle?: Ref<ComposerHandle>;
  transport: Transport;
  placeholder: string;
  busy: boolean;
  disabled?: boolean;
  uploads: boolean;
  /** refocus the textarea when this changes (new chat, thread switch) */
  autoFocusKey: string | number;
  onSend: (text: string, files: FileRef[]) => void;
  onStop: () => void;
}) {
  const kit = useMotionKit();
  const [text, setText] = useState("");
  const [atts, setAtts] = useState<Attachment[]>([]);
  const ta = useRef<HTMLTextAreaElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const resize = useCallback(() => {
    const el = ta.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 240)}px`;
  }, []);
  useEffect(resize, [text, resize]);

  useEffect(() => {
    if (window.matchMedia?.("(pointer: fine)").matches) ta.current?.focus({ preventScroll: true });
  }, [autoFocusKey]);

  // release object URLs
  useEffect(() => () => atts.forEach((a) => a.preview && URL.revokeObjectURL(a.preview)), []); // eslint-disable-line react-hooks/exhaustive-deps

  const addFiles = useCallback(
    (list: FileList | File[]) => {
      if (!uploads) return;
      const files = Array.from(list).slice(0, MAX_FILES);
      const next: Attachment[] = files.map((file) => ({
        key: Math.random().toString(36).slice(2),
        file,
        progress: 0,
        ctrl: new AbortController(),
        preview: file.type.startsWith("image/") ? URL.createObjectURL(file) : undefined,
      }));
      setAtts((a) => [...a, ...next].slice(0, MAX_FILES));
      for (const att of next) {
        transport
          .upload(att.file, {
            signal: att.ctrl.signal,
            onProgress: (p) => setAtts((a) => a.map((x) => (x.key === att.key ? { ...x, progress: p } : x))),
          })
          .then((ref) => setAtts((a) => a.map((x) => (x.key === att.key ? { ...x, progress: 1, ref } : x))))
          .catch((e) => {
            if (isAbortError(e)) return;
            setAtts((a) => a.map((x) => (x.key === att.key ? { ...x, error: describeError(e) } : x)));
          });
      }
      ta.current?.focus();
    },
    [transport, uploads],
  );

  useImperativeHandle(handle, () => ({ addFiles, focus: () => ta.current?.focus() }), [addFiles]);

  const remove = (key: string) =>
    setAtts((a) => {
      const it = a.find((x) => x.key === key);
      it?.ctrl.abort();
      if (it?.preview) URL.revokeObjectURL(it.preview);
      return a.filter((x) => x.key !== key);
    });

  const uploading = atts.some((a) => !a.ref && !a.error);
  const ready = atts.filter((a) => a.ref).map((a) => a.ref!);
  const canSend = !disabled && !busy && !uploading && (text.trim().length > 0 || ready.length > 0);

  const submit = () => {
    if (!canSend) return;
    onSend(text, ready);
    setText("");
    atts.forEach((a) => a.preview && URL.revokeObjectURL(a.preview));
    setAtts([]);
  };

  const state = busy ? "stop" : canSend ? "send" : "idle";

  return (
    <div className={cx("sh-composer", disabled && "is-disabled")}>
      <AnimatePresence initial={false}>
        {atts.length > 0 && (
          <motion.div
            className="sh-atts"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: kit.reduced ? 0.01 : 0.28, ease: [0.22, 1, 0.36, 1] }}
          >
            <ul className="sh-atts-inner" aria-label="Attachments">
              <AnimatePresence initial={false}>
                {atts.map((a) => (
                  <motion.li
                    key={a.key}
                    className={cx("sh-att", a.error && "is-error", !a.ref && !a.error && "is-uploading")}
                    variants={kit.bloom}
                    initial="hidden"
                    animate="show"
                    exit="exit"
                    layout={kit.reduced ? false : "position"}
                  >
                    <span className="sh-att-icon">
                      {a.preview ? <img src={a.preview} alt="" /> : <span className="sh-att-ext">{fileKind(a.file.type, a.file.name).slice(0, 4)}</span>}
                    </span>
                    <span className="sh-att-text">
                      <span className="sh-att-name" title={a.file.name}>
                        {a.file.name}
                      </span>
                      <span className="sh-att-meta">
                        {a.error ? (
                          <>
                            <CircleAlert size={11} aria-hidden="true" /> {a.error}
                          </>
                        ) : a.ref ? (
                          formatBytes(a.file.size)
                        ) : (
                          `Uploading ${Math.round(a.progress * 100)}%`
                        )}
                      </span>
                    </span>
                    <button type="button" className="sh-att-remove" onClick={() => remove(a.key)} aria-label={`Remove ${a.file.name}`}>
                      <X size={12} strokeWidth={2.4} />
                    </button>
                    {!a.ref && !a.error && (
                      <span className="sh-att-bar" aria-hidden="true">
                        <span style={{ transform: `scaleX(${Math.max(0.04, a.progress)})` }} />
                      </span>
                    )}
                  </motion.li>
                ))}
              </AnimatePresence>
            </ul>
          </motion.div>
        )}
      </AnimatePresence>

      <label htmlFor="dy-composer" className="sr-only">
        Message
      </label>
      <textarea
        id="dy-composer"
        ref={ta}
        className="sh-input"
        value={text}
        rows={1}
        placeholder={placeholder}
        disabled={disabled}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            submit();
          }
        }}
        onPaste={(e) => {
          if (uploads && e.clipboardData.files.length) {
            e.preventDefault();
            addFiles(e.clipboardData.files);
          }
        }}
        aria-describedby="dy-composer-hint"
      />
      <span id="dy-composer-hint" className="sr-only">
        Enter to send, Shift and Enter for a new line.
      </span>

      <div className="sh-composer-bar">
        <div className="sh-composer-tools">
          {uploads && (
            <>
              <button
                type="button"
                className="sh-icon-btn is-round"
                onClick={() => fileInput.current?.click()}
                aria-label="Attach files"
                data-tip="Attach files"
                disabled={disabled}
              >
                <Paperclip size={17} strokeWidth={1.9} />
              </button>
              <input
                ref={fileInput}
                type="file"
                multiple
                hidden
                onChange={(e) => {
                  if (e.target.files?.length) addFiles(e.target.files);
                  e.target.value = "";
                }}
              />
            </>
          )}
        </div>
        <motion.button
          type="button"
          className={cx("sh-send", `is-${state}`)}
          onClick={() => (busy ? onStop() : submit())}
          disabled={state === "idle"}
          aria-label={busy ? "Stop generating" : "Send message"}
          data-tip={busy ? "Stop" : undefined}
          {...(state !== "idle" ? kit.press : {})}
        >
          <AnimatePresence initial={false} mode="popLayout">
            {busy ? (
              <motion.span
                key="stop"
                className="sh-send-glyph"
                initial={kit.reduced ? { opacity: 0 } : { opacity: 0, scale: 0.5, rotate: -90 }}
                animate={{ opacity: 1, scale: 1, rotate: 0 }}
                exit={kit.reduced ? { opacity: 0 } : { opacity: 0, scale: 0.5, rotate: 90 }}
                transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
              >
                <span className="sh-stop-square" />
              </motion.span>
            ) : (
              <motion.span
                key="send"
                className="sh-send-glyph"
                initial={kit.reduced ? { opacity: 0 } : { opacity: 0, scale: 0.5, y: 6 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={kit.reduced ? { opacity: 0 } : { opacity: 0, scale: 0.5, y: -6 }}
                transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
              >
                <ArrowUp size={18} strokeWidth={2.2} />
              </motion.span>
            )}
          </AnimatePresence>
        </motion.button>
      </div>
    </div>
  );
}
