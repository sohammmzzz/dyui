import { memo, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { motion } from "motion/react";
import { CornerDownRight, Pencil, RefreshCw, Square, ThumbsDown, ThumbsUp } from "lucide-react";
import type { AppConfig, NodeContext, Part, Step } from "@/lib/types";
import { messageText, type ChatMessage } from "@/lib/store";
import { AvatarMark } from "./Logo";
import { Markdown } from "./Markdown";
import { FileChip, Reasoning, StepGroup, UIPart } from "./Parts";
import { CopyIcon, useCopied } from "./CopyButton";
import { cx, useMotionKit } from "./anim";
import type { ChatActions } from "./useChat";

type Common = {
  m: ChatMessage;
  actions: ChatActions;
  /** seconds to wait before blooming in (history stagger) */
  delay: number;
};

/* ------------------------------------------------------------ action button */

function ActionButton({
  label,
  onClick,
  children,
  active,
  disabled,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
  active?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      className={cx("sh-act", active && "is-active")}
      onClick={onClick}
      aria-label={label}
      aria-pressed={active}
      data-tip={label}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

/* --------------------------------------------------------------------- user */

export const UserMessage = memo(function UserMessage({
  m,
  actions,
  delay,
  canEdit,
}: Common & { canEdit: boolean }) {
  const kit = useMotionKit();
  const text = messageText(m);
  const files = m.parts.filter((p): p is Extract<Part, { type: "file" }> => p.type === "file");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(text);
  const [copied, copy] = useCopied();
  const ta = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!editing || !ta.current) return;
    const el = ta.current;
    el.focus();
    el.setSelectionRange(el.value.length, el.value.length);
  }, [editing]);

  useEffect(() => {
    const el = ta.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 320)}px`;
  }, [draft, editing]);

  if (!canEdit && editing) setEditing(false);

  const save = () => {
    const t = draft.trim();
    if (!t) return;
    setEditing(false);
    if (t !== text) actions.edit(m.id, t);
  };

  if (m.action) {
    return (
      <motion.div className="sh-msg sh-user is-action" variants={kit.delayed(kit.bloom, delay)} initial="hidden" animate="show">
        <div className="sh-action-chip">
          <CornerDownRight size={14} strokeWidth={2} aria-hidden="true" />
          <span>{m.action.label || text}</span>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      className={cx("sh-msg sh-user", editing && "is-editing")}
      variants={kit.delayed(kit.bloom, delay)}
      initial="hidden"
      animate="show"
    >
      {files.length > 0 && (
        <div className="sh-user-files">
          {files.map((p) => (
            <FileChip key={p.file.id} file={p.file} compact />
          ))}
        </div>
      )}
      {editing ? (
        <form
          className="sh-edit"
          onSubmit={(e) => {
            e.preventDefault();
            save();
          }}
        >
          <label className="sr-only" htmlFor={`edit-${m.id}`}>
            Edit message
          </label>
          <textarea
            id={`edit-${m.id}`}
            ref={ta}
            value={draft}
            rows={1}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                setEditing(false);
                setDraft(text);
              } else if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                save();
              }
            }}
          />
          <div className="sh-edit-bar">
            <button
              type="button"
              className="sh-btn is-ghost"
              onClick={() => {
                setEditing(false);
                setDraft(text);
              }}
            >
              Cancel
            </button>
            <button type="submit" className="sh-btn is-primary" disabled={!draft.trim()}>
              Send
            </button>
          </div>
        </form>
      ) : (
        text && <div className="sh-bubble">{text}</div>
      )}
      {!editing && text && (
        <div className="sh-actions is-user">
          <ActionButton label={copied ? "Copied" : "Copy"} onClick={() => copy(text)}>
            <CopyIcon copied={copied} />
          </ActionButton>
          {canEdit && (
            <ActionButton
              label="Edit"
              onClick={() => {
                setDraft(text);
                setEditing(true);
              }}
            >
              <Pencil size={15} strokeWidth={1.9} />
            </ActionButton>
          )}
        </div>
      )}
    </motion.div>
  );
});

/* ---------------------------------------------------------------- assistant */

type Group =
  | { kind: "part"; part: Part; index: number }
  | { kind: "steps"; steps: Step[]; key: string };

function groupParts(parts: Part[]): Group[] {
  const out: Group[] = [];
  parts.forEach((part, index) => {
    if (part.type === "step") {
      const last = out[out.length - 1];
      if (last?.kind === "steps") last.steps.push(part.step);
      else out.push({ kind: "steps", steps: [part.step], key: `steps-${part.step.id}` });
    } else out.push({ kind: "part", part, index });
  });
  return out;
}

function ThinkingIndicator() {
  return (
    <div className="sh-thinking" role="status">
      <span className="sh-thinking-dots" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      <span className="sh-shimmer-text">Thinking</span>
    </div>
  );
}

export const AssistantMessage = memo(function AssistantMessage({
  m,
  actions,
  delay,
  config,
  threadId,
  interactive,
  isLast,
  busy,
}: Common & {
  config: AppConfig;
  threadId: string | null;
  interactive: boolean;
  isLast: boolean;
  busy: boolean;
}) {
  const kit = useMotionKit();
  const streaming = m.status === "streaming";
  const [copied, copy] = useCopied();

  const ctx = useMemo<NodeContext>(
    () => ({
      messageId: m.id,
      threadId,
      interactive,
      onAction: (req) => actions.action(m.id, req),
      onReply: (text) => actions.reply(text),
    }),
    [m.id, threadId, interactive, actions],
  );

  const groups = useMemo(() => groupParts(m.parts), [m.parts]);
  const lastIndex = m.parts.length - 1;
  const visible = m.parts.some((p) => p.type !== "text" || p.text.trim());
  const text = messageText(m);

  return (
    <motion.article
      className={cx("sh-msg sh-assistant", streaming && "is-streaming", isLast && "is-last")}
      variants={kit.delayed(kit.bloom, delay)}
      initial="hidden"
      animate="show"
      aria-label="Assistant message"
      aria-busy={streaming || undefined}
    >
      <AvatarMark src={config.logo} thinking={streaming && !visible} />
      <div className="sh-assistant-body" aria-live={streaming ? "polite" : undefined}>
        {!visible && streaming && <ThinkingIndicator />}
        {groups.map((g) => {
          if (g.kind === "steps") return <StepGroup key={g.key} steps={g.steps} />;
          const { part, index } = g;
          switch (part.type) {
            case "text":
              return part.text.trim() ? (
                <Markdown key={`t${index}`} text={part.text} streaming={streaming && index === lastIndex} />
              ) : null;
            case "ui":
              return <UIPart key={part.node.id} node={part.node} ctx={ctx} />;
            case "reasoning":
              return (
                <Reasoning
                  key={`r${index}`}
                  text={part.text}
                  active={streaming && index === lastIndex}
                  durationMs={part.duration_ms}
                />
              );
            case "file":
              return (
                <div key={`f${index}`} className="sh-files">
                  <FileChip file={part.file} />
                </div>
              );
            default:
              return null;
          }
        })}
        {m.status === "cancelled" && (
          <div className="sh-note">
            <Square size={10} fill="currentColor" aria-hidden="true" />
            <span>Stopped</span>
          </div>
        )}
        {!streaming && visible && (
          <div className="sh-actions">
            {text && (
              <ActionButton label={copied ? "Copied" : "Copy"} onClick={() => copy(text)}>
                <CopyIcon copied={copied} />
              </ActionButton>
            )}
            {isLast && (
              <ActionButton label="Regenerate" onClick={() => actions.regenerate()} disabled={busy}>
                <RefreshCw size={15} strokeWidth={1.9} />
              </ActionButton>
            )}
            {config.features.feedback && (
              <>
                <ActionButton
                  label="Good response"
                  active={m.feedback === 1}
                  onClick={() => actions.feedback(m.id, m.feedback === 1 ? 0 : 1)}
                >
                  <ThumbsUp size={15} strokeWidth={1.9} fill={m.feedback === 1 ? "currentColor" : "none"} />
                </ActionButton>
                <ActionButton
                  label="Bad response"
                  active={m.feedback === -1}
                  onClick={() => actions.feedback(m.id, m.feedback === -1 ? 0 : -1)}
                >
                  <ThumbsDown size={15} strokeWidth={1.9} fill={m.feedback === -1 ? "currentColor" : "none"} />
                </ActionButton>
              </>
            )}
          </div>
        )}
      </div>
    </motion.article>
  );
});
