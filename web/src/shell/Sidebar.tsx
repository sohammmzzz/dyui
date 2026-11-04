import { memo, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { PanelLeftClose, Pencil, SquarePen, Trash2, X } from "lucide-react";
import type { AppConfig, ThreadSummary } from "@/lib/types";
import { groupThreads } from "@/lib/store";
import { Logo } from "./Logo";
import { cx, useMotionKit } from "./anim";

const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

type ItemProps = {
  t: ThreadSummary;
  active: boolean;
  index: number;
  onOpen: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => Promise<void>;
};

const ThreadItem = memo(function ThreadItem({ t, active, index, onOpen, onRename, onDelete }: ItemProps) {
  const kit = useMotionKit();
  const [mode, setMode] = useState<"idle" | "rename" | "confirm">("idle");
  const [draft, setDraft] = useState(t.title);
  const [deleting, setDeleting] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const confirmBtn = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (mode === "rename") {
      input.current?.focus();
      input.current?.select();
    } else if (mode === "confirm") confirmBtn.current?.focus();
  }, [mode]);

  const commit = () => {
    setMode("idle");
    if (draft.trim() && draft.trim() !== t.title) onRename(t.id, draft.trim());
    else setDraft(t.title);
  };

  return (
    <motion.li
      layout={kit.reduced ? false : "position"}
      variants={kit.delayed(kit.rise, Math.min(index, 8) * 0.035)}
      initial="hidden"
      animate="show"
      exit={{ opacity: 0, transition: { duration: 0.16 } }}
      transition={kit.spring}
      className={cx("sh-item", active && "is-active", mode !== "idle" && `is-${mode}`)}
    >
      {mode === "rename" ? (
        <form
          className="sh-item-rename"
          onSubmit={(e) => {
            e.preventDefault();
            commit();
          }}
        >
          <label className="sr-only" htmlFor={`rename-${t.id}`}>
            Rename chat
          </label>
          <input
            id={`rename-${t.id}`}
            ref={input}
            value={draft}
            maxLength={120}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                setDraft(t.title);
                setMode("idle");
              }
            }}
          />
        </form>
      ) : (
        <>
          <button
            type="button"
            className="sh-item-main"
            onClick={() => onOpen(t.id)}
            aria-current={active ? "page" : undefined}
            title={t.title}
          >
            <span className="sh-item-title">{t.title || "Untitled chat"}</span>
          </button>
          <span className="sh-item-tools">
            <button type="button" className="sh-item-tool" aria-label={`Rename “${t.title}”`} onClick={() => setMode("rename")}>
              <Pencil size={13} strokeWidth={1.9} />
            </button>
            <button type="button" className="sh-item-tool" aria-label={`Delete “${t.title}”`} onClick={() => setMode("confirm")}>
              <Trash2 size={13} strokeWidth={1.9} />
            </button>
          </span>
        </>
      )}
      <AnimatePresence initial={false}>
        {mode === "confirm" && (
          <motion.div
            className="sh-item-confirm"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: kit.reduced ? 0.01 : 0.26, ease: [0.22, 1, 0.36, 1] }}
            onKeyDown={(e) => e.key === "Escape" && setMode("idle")}
          >
            <div className="sh-item-confirm-inner">
              <span>Delete this chat?</span>
              <div>
                <button type="button" className="sh-btn is-ghost is-sm" onClick={() => setMode("idle")}>
                  Cancel
                </button>
                <button
                  ref={confirmBtn}
                  type="button"
                  className="sh-btn is-danger is-sm"
                  disabled={deleting}
                  onClick={async () => {
                    setDeleting(true);
                    await onDelete(t.id);
                    setDeleting(false);
                    setMode("idle");
                  }}
                >
                  Delete
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.li>
  );
});

export function Sidebar({
  config,
  threads,
  loaded,
  activeId,
  mock,
  onNew,
  onOpen,
  onRename,
  onDelete,
  onCollapse,
  drawer,
}: {
  config: AppConfig;
  threads: ThreadSummary[];
  loaded: boolean;
  activeId: string | null;
  mock: boolean;
  onNew: () => void;
  onOpen: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => Promise<void>;
  onCollapse: () => void;
  drawer: boolean;
}) {
  const kit = useMotionKit();
  // regroup at most once a minute so "Today" rolls over without re-rendering on every tick
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(t);
  }, []);
  const groups = useMemo(() => groupThreads(threads, now), [threads, now]);
  let idx = 0;

  return (
    <div className="sh-sidebar-inner">
      <div className="sh-side-head">
        <div className="sh-brand">
          <Logo src={config.logo} size={22} />
          <span className="sh-brand-name">{config.title}</span>
        </div>
        <button
          type="button"
          className="sh-icon-btn"
          onClick={onCollapse}
          aria-label={drawer ? "Close sidebar" : "Collapse sidebar"}
          data-tip={drawer ? "Close" : "Collapse"}
          data-tip-pos="bottom"
        >
          {drawer ? <X size={18} strokeWidth={1.9} /> : <PanelLeftClose size={18} strokeWidth={1.8} />}
        </button>
      </div>

      <div className="sh-side-new">
        <motion.button type="button" className="sh-new" onClick={onNew} {...kit.press}>
          <SquarePen size={16} strokeWidth={1.9} aria-hidden="true" />
          <span>New chat</span>
          <kbd className="sh-kbd" aria-hidden="true">
            {isMac ? "⌘" : "Ctrl"} ⇧ O
          </kbd>
        </motion.button>
      </div>

      <nav className="sh-threads" aria-label="Conversations">
        {!loaded ? (
          <div className="sh-threads-loading" aria-hidden="true">
            {[72, 88, 64, 80, 56].map((w, i) => (
              <span key={i} className="sh-skel" style={{ width: `${w}%` }} />
            ))}
          </div>
        ) : groups.length === 0 ? (
          <motion.div className="sh-threads-empty" variants={kit.bloom} initial="hidden" animate="show">
            <p className="sh-empty-title">No conversations yet</p>
            <p>Your chats will appear here.</p>
          </motion.div>
        ) : (
          groups.map((g) => (
            <section key={g.label} className="sh-group" aria-label={g.label}>
              <h2 className="sh-eyebrow sh-group-label">{g.label}</h2>
              <ul>
                <AnimatePresence initial={false}>
                  {g.threads.map((t) => (
                    <ThreadItem
                      key={t.id}
                      t={t}
                      index={idx++}
                      active={t.id === activeId}
                      onOpen={onOpen}
                      onRename={onRename}
                      onDelete={onDelete}
                    />
                  ))}
                </AnimatePresence>
              </ul>
            </section>
          ))
        )}
      </nav>

      <footer className="sh-side-foot">
        <span>
          Built with <span className="sh-foot-brand">DyUI</span>
        </span>
        <span className="sh-foot-meta">
          {mock && <span className="sh-pill" title="Scripted replies; no backend connected">Demo</span>}
          <span className="sh-mono">v{config.version}</span>
        </span>
      </footer>
    </div>
  );
}
