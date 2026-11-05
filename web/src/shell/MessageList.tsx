import { useCallback, useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";
import { motion } from "motion/react";
import { CircleAlert, RotateCcw } from "lucide-react";
import type { AppConfig } from "@/lib/types";
import type { ChatState } from "@/lib/store";
import { AssistantMessage, UserMessage } from "./Message";
import { useMotionKit } from "./anim";
import type { ChatActions } from "./useChat";

/**
 * Stick-to-bottom scrolling that respects the reader: any upward scroll releases
 * it, reaching the bottom again re-engages it. `away` drives the "Jump to latest" pill.
 */
export function useStickToBottom(scrollRef: RefObject<HTMLElement | null>, contentRef: RefObject<HTMLElement | null>) {
  const stick = useRef(true);
  const lastTop = useRef(0);
  const [away, setAway] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const kit = useMotionKit();

  useEffect(() => {
    const el = scrollRef.current;
    const content = contentRef.current;
    if (!el || !content) return;
    const measure = () => {
      const dist = el.scrollHeight - el.scrollTop - el.clientHeight;
      if (el.scrollTop < lastTop.current - 1 && dist > 4) stick.current = false;
      if (dist < 40) stick.current = true;
      lastTop.current = el.scrollTop;
      setAway(dist > 200);
      setScrolled(el.scrollTop > 4);
    };
    const onWheel = (e: WheelEvent) => {
      if (e.deltaY < 0) stick.current = false;
    };
    const ro = new ResizeObserver(() => {
      if (stick.current) {
        el.scrollTop = el.scrollHeight;
        lastTop.current = el.scrollTop;
      }
      measure();
    });
    ro.observe(content);
    el.addEventListener("scroll", measure, { passive: true });
    el.addEventListener("wheel", onWheel, { passive: true });
    return () => {
      ro.disconnect();
      el.removeEventListener("scroll", measure);
      el.removeEventListener("wheel", onWheel);
    };
  }, [scrollRef, contentRef]);

  const reduced = kit.reduced;
  const toBottom = useCallback(
    (smooth = true) => {
      const el = scrollRef.current;
      if (!el) return;
      stick.current = true;
      el.scrollTo({ top: el.scrollHeight, behavior: smooth && !reduced ? "smooth" : "auto" });
    },
    [scrollRef, reduced],
  );

  const pin = useCallback(() => {
    stick.current = true;
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [scrollRef]);

  return { away, scrolled, toBottom, pin };
}

export function MessageList({
  state,
  busy,
  config,
  actions,
  onPin,
}: {
  state: ChatState;
  busy: boolean;
  config: AppConfig;
  actions: ChatActions;
  onPin: () => void;
}) {
  const kit = useMotionKit();
  const { messages, error } = state;
  // The list is keyed per view, so messages present at mount came from history:
  // they bloom in with a capped stagger; streamed ones enter immediately.
  const historyCount = useRef(messages.length);

  useLayoutEffect(() => {
    onPin();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  let lastAssistant = -1;
  let lastUser = -1;
  messages.forEach((m, i) => {
    if (m.role === "assistant" && !m.placeholder) lastAssistant = i;
    if (m.role === "user") lastUser = i;
  });
  const lastReal = messages.reduce((acc, m, i) => (m.placeholder ? acc : i), -1);

  return (
    <div className="sh-thread" role="log" aria-label="Conversation">
      {messages.map((m, i) => {
        const n = historyCount.current;
        const fromHistory = i < n;
        // newest messages are on screen first; stagger them upward from the bottom, capped at 8
        const delay = fromHistory ? Math.min(Math.max(0, i - (n - 8)), 8) * 0.045 : 0;
        if (m.role === "user")
          return (
            <UserMessage
              key={m.key ?? m.id}
              m={m}
              actions={actions}
              delay={delay}
              canEdit={i === lastUser && !busy && !m.local && !m.action && !!state.threadId}
            />
          );
        return (
          <AssistantMessage
            key={m.key ?? m.id}
            m={m}
            actions={actions}
            delay={delay}
            config={config}
            threadId={state.threadId}
            interactive={i === lastAssistant || !!m.placeholder}
            isLast={i === lastAssistant && i === lastReal}
            busy={busy}
          />
        );
      })}
      {error && (
        <motion.div className="sh-error" role="alert" variants={kit.bloom} initial="hidden" animate="show">
          <CircleAlert size={16} strokeWidth={2} aria-hidden="true" />
          <p>{error.message}</p>
          <button type="button" className="sh-btn is-outline" onClick={() => actions.retry()} disabled={busy}>
            <RotateCcw size={14} strokeWidth={2} aria-hidden="true" />
            Retry
          </button>
        </motion.div>
      )}
    </div>
  );
}

export function ThreadSkeleton() {
  return (
    <div className="sh-thread sh-skeleton" aria-hidden="true">
      <div className="sh-skel-row is-user">
        <span className="sh-skel" style={{ width: "38%", height: 40, borderRadius: 20 }} />
      </div>
      <div className="sh-skel-row">
        <span className="sh-skel sh-skel-avatar" />
        <div className="sh-skel-lines">
          <span className="sh-skel" style={{ width: "92%" }} />
          <span className="sh-skel" style={{ width: "84%" }} />
          <span className="sh-skel" style={{ width: "60%" }} />
          <span className="sh-skel" style={{ width: "100%", height: 120, borderRadius: 16, marginTop: 8 }} />
        </div>
      </div>
    </div>
  );
}
