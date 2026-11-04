import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowDown, Paperclip } from "lucide-react";
import type { Transport } from "@/lib/api";
import type { AppConfig, ThemeMode } from "@/lib/types";
import { Composer, type ComposerHandle } from "./Composer";
import { Header } from "./Header";
import { MessageList, ThreadSkeleton, useStickToBottom } from "./MessageList";
import { Sidebar } from "./Sidebar";
import { useToast } from "./Toasts";
import { useChat } from "./useChat";
import { Welcome } from "./Welcome";
import { cx, useMotionKit } from "./anim";

function useMediaQuery(q: string): boolean {
  const get = () => typeof window !== "undefined" && !!window.matchMedia?.(q).matches;
  const [v, setV] = useState(get);
  useEffect(() => {
    const mql = window.matchMedia?.(q);
    if (!mql) return;
    const on = () => setV(mql.matches);
    on();
    mql.addEventListener("change", on);
    return () => mql.removeEventListener("change", on);
  }, [q]);
  return v;
}

const COLLAPSE_KEY = "dyui:sidebar";

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSE_KEY) === "collapsed";
  } catch {
    return false;
  }
}

export function AppShell({
  transport,
  config,
  theme,
  onTheme,
  onUnauthorized,
}: {
  transport: Transport;
  config: AppConfig;
  theme: ThemeMode;
  onTheme: (m: ThemeMode) => void;
  onUnauthorized: () => void;
}) {
  const kit = useMotionKit();
  const toast = useToast();
  const { state, busy, viewKey, actions } = useChat(transport, config, { toast, onUnauthorized });
  const history = config.features.history;
  const narrow = useMediaQuery("(max-width: 899px)");
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [drawer, setDrawer] = useState(false);
  const [dragging, setDragging] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const composer = useRef<ComposerHandle>(null);
  const { away, scrolled, toBottom, pin } = useStickToBottom(scrollRef, contentRef);

  const sidebarVisible = history && (narrow ? drawer : !collapsed);

  const toggleCollapsed = useCallback((v: boolean) => {
    setCollapsed(v);
    try {
      localStorage.setItem(COLLAPSE_KEY, v ? "collapsed" : "open");
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    if (!narrow) setDrawer(false);
  }, [narrow]);

  const thread = state.threads.find((t) => t.id === state.threadId);
  const title = state.threadId ? (thread?.title ?? null) : null;

  // document title follows the open conversation
  useEffect(() => {
    document.title = title && title !== "New chat" ? `${title} · ${config.title}` : config.title;
  }, [title, config.title]);

  const newChat = useCallback(() => {
    actions.newChat();
    setDrawer(false);
    composer.current?.focus();
  }, [actions]);

  const openThread = useCallback(
    (id: string) => {
      actions.openThread(id);
      setDrawer(false);
    },
    [actions],
  );

  const send = useCallback(
    (text: string, files: Parameters<typeof actions.send>[1] = []) => {
      actions.send(text, files);
      requestAnimationFrame(() => toBottom(true));
    },
    [actions, toBottom],
  );

  // keyboard: ⌘/Ctrl ⇧ O new chat · Esc closes the drawer
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === "o") {
        e.preventDefault();
        newChat();
      } else if (e.key === "Escape" && drawer) {
        setDrawer(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [newChat, drawer]);

  // drag & drop files anywhere over the window
  useEffect(() => {
    if (!config.features.uploads) return;
    let depth = 0;
    const hasFiles = (e: DragEvent) => Array.from(e.dataTransfer?.types ?? []).includes("Files");
    const enter = (e: DragEvent) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      depth++;
      setDragging(true);
    };
    const over = (e: DragEvent) => {
      if (hasFiles(e)) e.preventDefault();
    };
    const leave = (e: DragEvent) => {
      if (!hasFiles(e)) return;
      depth = Math.max(0, depth - 1);
      if (depth === 0) setDragging(false);
    };
    const drop = (e: DragEvent) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      depth = 0;
      setDragging(false);
      if (e.dataTransfer?.files.length) composer.current?.addFiles(e.dataTransfer.files);
    };
    window.addEventListener("dragenter", enter);
    window.addEventListener("dragover", over);
    window.addEventListener("dragleave", leave);
    window.addEventListener("drop", drop);
    return () => {
      window.removeEventListener("dragenter", enter);
      window.removeEventListener("dragover", over);
      window.removeEventListener("drop", drop);
      window.removeEventListener("dragleave", leave);
    };
  }, [config.features.uploads]);

  const loading = state.loadingThreadId !== null;
  const empty = !loading && state.messages.length === 0;
  const placeholder = (config.placeholder || "Message {title}…").replace("{title}", config.title);

  const sidebar = (
    <Sidebar
      config={config}
      threads={state.threads}
      loaded={state.threadsLoaded}
      activeId={state.threadId}
      mock={transport.kind === "mock"}
      onNew={newChat}
      onOpen={openThread}
      onRename={actions.renameThread}
      onDelete={actions.deleteThread}
      onCollapse={() => (narrow ? setDrawer(false) : toggleCollapsed(true))}
      drawer={narrow}
    />
  );

  return (
    <div className={cx("sh-app", narrow && "is-narrow", history && !narrow && collapsed && "is-collapsed")}>
      {history && !narrow && (
        <aside className="sh-sidebar" aria-label="Sidebar" aria-hidden={collapsed || undefined} inert={collapsed || undefined}>
          {sidebar}
        </aside>
      )}

      <AnimatePresence>
        {history && narrow && drawer && (
          <>
            <motion.div
              key="scrim"
              className="sh-scrim"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.24 }}
              onClick={() => setDrawer(false)}
            />
            <motion.aside
              key="drawer"
              className="sh-sidebar is-drawer"
              aria-label="Sidebar"
              role="dialog"
              aria-modal="true"
              initial={kit.reduced ? { opacity: 0 } : { x: "-100%" }}
              animate={kit.reduced ? { opacity: 1 } : { x: 0 }}
              exit={kit.reduced ? { opacity: 0 } : { x: "-100%" }}
              transition={kit.reduced ? { duration: 0.12 } : { type: "spring", stiffness: 300, damping: 36, mass: 0.9 }}
            >
              {sidebar}
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      <main className="sh-main">
        <Header
          title={title}
          appTitle={config.title}
          logo={config.logo}
          showOpenSidebar={history && (narrow || collapsed)}
          showNewChat={(!history || narrow || collapsed) && !empty}
          showBrand={!history || narrow || collapsed}
          scrolled={scrolled && !empty}
          theme={theme}
          onTheme={onTheme}
          onOpenSidebar={() => (narrow ? setDrawer(true) : toggleCollapsed(false))}
          onNewChat={newChat}
        />

        <div className="sh-scroll" ref={scrollRef}>
          <div className={cx("sh-col", empty && "is-empty")} ref={contentRef}>
            <AnimatePresence mode="wait" initial={false}>
              {loading ? (
                <motion.div key="skeleton" initial={{ opacity: 0 }} animate={{ opacity: 1, transition: { delay: 0.18 } }} exit={{ opacity: 0, transition: { duration: 0.1 } }}>
                  <ThreadSkeleton />
                </motion.div>
              ) : empty ? (
                <motion.div key={`welcome-${viewKey}`} className="sh-welcome-wrap" exit={kit.reduced ? { opacity: 0 } : { opacity: 0, y: -8, filter: "blur(6px)", transition: { duration: 0.22 } }}>
                  <Welcome config={config} onStarter={(m) => send(m)} />
                </motion.div>
              ) : (
                <motion.div key={`thread-${viewKey}`} initial={{ opacity: 1 }} exit={{ opacity: 0, transition: { duration: 0.12 } }}>
                  <MessageList state={state} busy={busy} config={config} actions={actions} onPin={pin} />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        <div className="sh-dock">
          <AnimatePresence>
            {away && !empty && (
              <motion.button
                type="button"
                className="sh-jump"
                onClick={() => toBottom(true)}
                initial={kit.reduced ? { opacity: 0 } : { opacity: 0, y: 8, filter: "blur(4px)" }}
                animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                exit={kit.reduced ? { opacity: 0 } : { opacity: 0, y: 6, filter: "blur(4px)" }}
                transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
              >
                <ArrowDown size={14} strokeWidth={2} aria-hidden="true" />
                Jump to latest
              </motion.button>
            )}
          </AnimatePresence>
          <div className="sh-dock-inner">
            <Composer
              handle={composer}
              transport={transport}
              placeholder={placeholder}
              busy={busy}
              disabled={loading}
              uploads={config.features.uploads}
              autoFocusKey={viewKey}
              onSend={send}
              onStop={actions.stop}
            />
          </div>
        </div>

        <AnimatePresence>
          {dragging && (
            <motion.div
              className="sh-drop"
              initial={kit.reduced ? { opacity: 0 } : { opacity: 0, scale: 0.985 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={kit.reduced ? { opacity: 0 } : { opacity: 0, scale: 0.985 }}
              transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
              aria-hidden="true"
            >
              <div className="sh-drop-inner">
                <span className="sh-drop-icon">
                  <Paperclip size={22} strokeWidth={1.8} />
                </span>
                <p className="sh-drop-title">Drop files to attach</p>
                <p className="sh-drop-sub">They’ll upload while you write your message.</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}
