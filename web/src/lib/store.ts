/**
 * Thread & message state for the chat shell (SPEC §4 event table).
 *
 * Everything here is pure: `applyMessageEvent` folds one SSE event into a message
 * list (also used by the mock transport to "persist" what it streams), and
 * `chatReducer` adds the client-only bits: thread list, optimistic user messages,
 * pending-assistant placeholders, local action resolution, inline errors.
 */
import type { FileRef, Message, Part, Step, StreamEvent, Thread, ThreadSummary, UINode } from "./types";

/** A message as the client holds it: protocol fields plus local bookkeeping. */
export type ChatMessage = Message & {
  /** stable React key — survives placeholder → real id and optimistic → server id swaps */
  key?: string;
  /** optimistic user message not yet confirmed by a `user_message` event */
  local?: boolean;
  /** empty assistant slot shown (with the thinking indicator) before `message_start` */
  placeholder?: boolean;
  duration_ms?: number;
};

export type ChatError = { message: string; messageId?: string };

export type ChatState = {
  threads: ThreadSummary[];
  threadsLoaded: boolean;
  threadId: string | null;
  /** id of a thread being fetched (messages are empty until it lands) */
  loadingThreadId: string | null;
  messages: ChatMessage[];
  error: ChatError | null;
};

export const initialChatState: ChatState = {
  threads: [],
  threadsLoaded: false,
  threadId: null,
  loadingThreadId: null,
  messages: [],
  error: null,
};

export type Resolution = { label: string; values: Record<string, any> };

export type ChatAction =
  | { type: "event"; event: StreamEvent }
  | { type: "threads/set"; threads: ThreadSummary[] }
  | { type: "thread/loading"; id: string }
  | { type: "thread/open"; thread: Thread }
  | { type: "thread/clear" }
  | { type: "thread/upsert"; thread: ThreadSummary }
  | { type: "thread/rename"; id: string; title: string }
  | { type: "thread/remove"; id: string }
  | { type: "send"; text: string; files: FileRef[]; localId: string; placeholderKey: string; now?: number }
  | { type: "regenerate"; placeholderKey: string }
  | { type: "edit"; messageId: string; text: string; placeholderKey: string }
  | { type: "placeholder/add"; key: string; now?: number }
  | { type: "stream/settle"; ids: string[]; aborted: boolean; placeholderKey?: string }
  | { type: "message/remove"; id: string }
  | { type: "feedback"; messageId: string; value: 1 | -1 | 0 }
  | { type: "resolve"; messageId: string; componentId: string; resolved: Resolution | undefined }
  | { type: "error/set"; error: ChatError | null };

/* ------------------------------------------------------------------ helpers */

const nowSeconds = () => Date.now() / 1000;

/** Timestamps may arrive as unix seconds (Python) or milliseconds; normalise to ms. */
export function toMs(t: number | undefined | null): number {
  if (!t || !Number.isFinite(t)) return 0;
  return t < 1e12 ? t * 1000 : t;
}

function isNode(v: unknown): v is UINode {
  return !!v && typeof v === "object" && typeof (v as UINode).id === "string" && typeof (v as UINode).ui === "string";
}

/** Replace the node with `next.id` anywhere inside `value` (children, props arrays). Same ref if absent. */
function replaceDeep<T>(value: T, next: UINode, depth = 0): T {
  if (depth > 12 || !value || typeof value !== "object") return value;
  if (Array.isArray(value)) {
    let changed = false;
    const arr = value.map((v) => {
      const r = replaceDeep(v, next, depth + 1);
      if (r !== v) changed = true;
      return r;
    });
    return (changed ? arr : value) as T;
  }
  if (isNode(value) && value.id === next.id) return mergeNode(value, next) as T;
  let changed = false;
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
    const r = typeof v === "object" ? replaceDeep(v, next, depth + 1) : v;
    if (r !== v) changed = true;
    out[k] = r;
  }
  return (changed ? out : value) as T;
}

/** Server updates replace the node, but a local resolution survives a stale update. */
function mergeNode(prev: UINode, next: UINode): UINode {
  const keep = prev.props?.__resolved__;
  if (keep && next.props && next.props.__resolved__ === undefined) {
    return { ...next, props: { ...next.props, __resolved__: keep } };
  }
  return next;
}

function upsertNode(parts: Part[], node: UINode): Part[] {
  const i = parts.findIndex((p) => p.type === "ui" && p.node.id === node.id);
  if (i >= 0) {
    const out = parts.slice();
    out[i] = { type: "ui", node: mergeNode((parts[i] as { node: UINode }).node, node) };
    return out;
  }
  for (let j = 0; j < parts.length; j++) {
    const p = parts[j];
    if (p.type !== "ui") continue;
    const r = replaceDeep(p.node, node);
    if (r !== p.node) {
      const out = parts.slice();
      out[j] = { type: "ui", node: r };
      return out;
    }
  }
  return [...parts, { type: "ui", node }];
}

function upsertStep(parts: Part[], step: Step): Part[] {
  const i = parts.findIndex((p) => p.type === "step" && p.step.id === step.id);
  if (i >= 0) {
    const out = parts.slice();
    out[i] = { type: "step", step: { ...(parts[i] as { step: Step }).step, ...step } };
    return out;
  }
  return [...parts, { type: "step", step }];
}

function appendText(parts: Part[], delta: string): Part[] {
  const last = parts[parts.length - 1];
  if (last && last.type === "text") {
    const out = parts.slice();
    out[out.length - 1] = { type: "text", text: last.text + delta };
    return out;
  }
  return [...parts, { type: "text", text: delta }];
}

function appendReasoning(parts: Part[], delta: string): Part[] {
  for (let i = parts.length - 1; i >= 0; i--) {
    const p = parts[i];
    if (p.type === "reasoning") {
      const out = parts.slice();
      out[i] = { ...p, text: p.text + delta };
      return out;
    }
  }
  return [...parts, { type: "reasoning", text: delta }];
}

/** Find (or create) the assistant message a delta event targets. */
function withMessage(
  messages: ChatMessage[],
  id: string,
  fn: (m: ChatMessage) => ChatMessage,
): ChatMessage[] {
  const i = messages.findIndex((m) => m.id === id);
  if (i >= 0) {
    const out = messages.slice();
    out[i] = fn(messages[i]);
    return out;
  }
  // Missing message_start: adopt a trailing placeholder, else create the message.
  const last = messages[messages.length - 1];
  if (last?.placeholder) {
    const out = messages.slice();
    out[out.length - 1] = fn({
      id,
      key: last.key,
      role: "assistant",
      created_at: last.created_at,
      parts: [],
      status: "streaming",
    });
    return out;
  }
  return [
    ...messages,
    fn({ id, role: "assistant", created_at: nowSeconds(), parts: [], status: "streaming" }),
  ];
}

/* --------------------------------------------------- message-level reducer */

/** Fold one SSE event into a message list. Events that don't touch messages return the same array. */
export function applyMessageEvent<M extends ChatMessage>(messages: M[], ev: StreamEvent): M[] {
  const list = messages as ChatMessage[];
  switch (ev.event) {
    case "user_message": {
      const msg = ev.data;
      const same = list.findIndex((m) => m.id === msg.id);
      if (same >= 0) {
        const out = list.slice();
        out[same] = { ...msg, key: list[same].key ?? list[same].id };
        return out as M[];
      }
      let local = -1;
      for (let i = list.length - 1; i >= 0; i--) {
        if (list[i].local && list[i].role === "user") {
          local = i;
          break;
        }
      }
      if (local >= 0) {
        const out = list.slice();
        out[local] = { ...msg, key: list[local].key ?? list[local].id };
        return out as M[];
      }
      const last = list[list.length - 1];
      if (last?.placeholder) return [...list.slice(0, -1), msg, last] as M[];
      return [...list, msg] as M[];
    }
    case "message_start": {
      const { id, created_at } = ev.data;
      const i = list.findIndex((m) => m.id === id);
      if (i >= 0) {
        const out = list.slice();
        out[i] = { ...list[i], status: "streaming" };
        return out as M[];
      }
      const fresh: ChatMessage = { id, role: "assistant", created_at, parts: [], status: "streaming" };
      const last = list[list.length - 1];
      if (last?.placeholder) return [...list.slice(0, -1), { ...fresh, key: last.key }] as M[];
      return [...list, fresh] as M[];
    }
    case "text":
      if (!ev.data.delta) return messages;
      return withMessage(list, ev.data.message_id, (m) => ({ ...m, parts: appendText(m.parts, ev.data.delta) })) as M[];
    case "reasoning":
      if (!ev.data.delta) return messages;
      return withMessage(list, ev.data.message_id, (m) => ({
        ...m,
        parts: appendReasoning(m.parts, ev.data.delta),
      })) as M[];
    case "ui":
      return withMessage(list, ev.data.message_id, (m) => ({ ...m, parts: upsertNode(m.parts, ev.data.node) })) as M[];
    case "step":
      return withMessage(list, ev.data.message_id, (m) => ({ ...m, parts: upsertStep(m.parts, ev.data.step) })) as M[];
    case "message_end": {
      const i = list.findIndex((m) => m.id === ev.data.id);
      if (i < 0) return messages;
      const out = list.slice();
      out[i] = { ...list[i], status: ev.data.status, duration_ms: ev.data.duration_ms ?? list[i].duration_ms };
      return out as M[];
    }
    default:
      return messages;
  }
}

/* ------------------------------------------------------- thread list helpers */

function upsertThread(threads: ThreadSummary[], t: ThreadSummary): ThreadSummary[] {
  const prev = threads.find((x) => x.id === t.id);
  const merged = prev ? { ...prev, ...t } : t;
  return [merged, ...threads.filter((x) => x.id !== t.id)];
}

function touchThread(threads: ThreadSummary[], id: string | null, now: number): ThreadSummary[] {
  if (!id) return threads;
  const t = threads.find((x) => x.id === id);
  if (!t) return threads;
  return [{ ...t, updated_at: now }, ...threads.filter((x) => x.id !== id)];
}

function dropPlaceholders(messages: ChatMessage[], key?: string): ChatMessage[] {
  const out = messages.filter((m) => !(m.placeholder && (key === undefined || m.key === key)));
  return out.length === messages.length ? messages : out;
}

/** Drop assistant messages after the last user message (regenerate). */
function dropTrailingAssistant(messages: ChatMessage[]): ChatMessage[] {
  let end = messages.length;
  while (end > 0 && messages[end - 1].role === "assistant") end--;
  return end === messages.length ? messages : messages.slice(0, end);
}

function placeholder(key: string, now: number): ChatMessage {
  return { id: key, key, role: "assistant", created_at: now, parts: [], status: "streaming", placeholder: true };
}

/** Plain text of a message (for copy, edit, retry). */
export function messageText(m: Pick<Message, "parts">): string {
  return m.parts
    .filter((p): p is Extract<Part, { type: "text" }> => p.type === "text")
    .map((p) => p.text)
    .join("")
    .trim();
}

export function messageFiles(m: Pick<Message, "parts">): FileRef[] {
  return m.parts.filter((p): p is Extract<Part, { type: "file" }> => p.type === "file").map((p) => p.file);
}

function setResolved(node: UINode, componentId: string, resolved: Resolution | undefined): UINode {
  const apply = (n: UINode): UINode => {
    const props = { ...n.props };
    if (resolved) props.__resolved__ = resolved;
    else delete props.__resolved__;
    return { ...n, props };
  };
  if (node.id === componentId) return apply(node);
  let found: UINode | null = null;
  const walk = (v: unknown, d = 0): void => {
    if (found || d > 12 || !v || typeof v !== "object") return;
    if (Array.isArray(v)) return v.forEach((x) => walk(x, d + 1));
    if (isNode(v) && v.id === componentId) {
      found = v;
      return;
    }
    Object.values(v as Record<string, unknown>).forEach((x) => walk(x, d + 1));
  };
  walk(node);
  if (!found) return node;
  return replaceDeep(node, apply(found));
}

/* ---------------------------------------------------------------- reducer */

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "event": {
      const ev = action.event;
      switch (ev.event) {
        case "thread":
          return {
            ...state,
            threadId: state.threadId ?? ev.data.id,
            threads: upsertThread(state.threads, ev.data),
          };
        case "title":
          return {
            ...state,
            threads: state.threads.map((t) => (t.id === ev.data.thread_id ? { ...t, title: ev.data.title } : t)),
          };
        case "error":
          return { ...state, error: { message: ev.data.message || "Something went wrong.", messageId: ev.data.message_id } };
        case "done":
          return state;
        default: {
          const messages = applyMessageEvent(state.messages, ev);
          return messages === state.messages ? state : { ...state, messages };
        }
      }
    }
    case "threads/set":
      return { ...state, threads: action.threads, threadsLoaded: true };
    case "thread/loading":
      return { ...state, threadId: action.id, loadingThreadId: action.id, messages: [], error: null };
    case "thread/open":
      if (state.loadingThreadId && state.loadingThreadId !== action.thread.id) return state;
      return {
        ...state,
        threadId: action.thread.id,
        loadingThreadId: null,
        messages: action.thread.messages,
        error: null,
        threads: state.threads.some((t) => t.id === action.thread.id)
          ? state.threads.map((t) => (t.id === action.thread.id ? { ...t, title: action.thread.title } : t))
          : upsertThread(state.threads, {
              id: action.thread.id,
              title: action.thread.title,
              created_at: action.thread.created_at,
              updated_at: action.thread.updated_at,
            }),
      };
    case "thread/clear":
      return { ...state, threadId: null, loadingThreadId: null, messages: [], error: null };
    case "thread/upsert":
      return { ...state, threads: upsertThread(state.threads, action.thread) };
    case "thread/rename":
      return { ...state, threads: state.threads.map((t) => (t.id === action.id ? { ...t, title: action.title } : t)) };
    case "thread/remove": {
      const threads = state.threads.filter((t) => t.id !== action.id);
      if (state.threadId === action.id) return { ...state, threads, threadId: null, messages: [], error: null };
      return { ...state, threads };
    }
    case "send": {
      const now = action.now ?? nowSeconds();
      const parts: Part[] = [
        ...action.files.map((file): Part => ({ type: "file", file })),
        ...(action.text ? [{ type: "text", text: action.text } as Part] : []),
      ];
      const user: ChatMessage = { id: action.localId, key: action.localId, role: "user", created_at: now, parts, local: true };
      return {
        ...state,
        error: null,
        threads: touchThread(state.threads, state.threadId, now),
        messages: [...dropPlaceholders(state.messages), user, placeholder(action.placeholderKey, now)],
      };
    }
    case "regenerate": {
      const base = dropTrailingAssistant(dropPlaceholders(state.messages));
      return { ...state, error: null, messages: [...base, placeholder(action.placeholderKey, nowSeconds())] };
    }
    case "edit": {
      const i = state.messages.findIndex((m) => m.id === action.messageId);
      if (i < 0) return state;
      const old = state.messages[i];
      const parts: Part[] = [...old.parts.filter((p) => p.type === "file"), { type: "text", text: action.text }];
      const edited: ChatMessage = { ...old, parts, local: true, key: old.key ?? old.id };
      return {
        ...state,
        error: null,
        messages: [...state.messages.slice(0, i), edited, placeholder(action.placeholderKey, nowSeconds())],
      };
    }
    case "placeholder/add": {
      const last = state.messages[state.messages.length - 1];
      if (last?.placeholder) return state;
      return { ...state, messages: [...state.messages, placeholder(action.key, action.now ?? nowSeconds())] };
    }
    case "stream/settle": {
      let changed = false;
      const ids = new Set(action.ids);
      let messages = state.messages.map((m) => {
        if (ids.has(m.id) && m.status === "streaming") {
          changed = true;
          return { ...m, status: action.aborted ? "cancelled" : "done" } as ChatMessage;
        }
        return m;
      });
      if (!changed) messages = state.messages;
      if (action.placeholderKey) messages = dropPlaceholders(messages, action.placeholderKey);
      return messages === state.messages ? state : { ...state, messages };
    }
    case "message/remove":
      return { ...state, messages: state.messages.filter((m) => m.id !== action.id) };
    case "feedback":
      return {
        ...state,
        messages: state.messages.map((m) => (m.id === action.messageId ? { ...m, feedback: action.value } : m)),
      };
    case "resolve":
      return {
        ...state,
        messages: state.messages.map((m) =>
          m.id !== action.messageId
            ? m
            : {
                ...m,
                parts: m.parts.map((p) =>
                  p.type === "ui" ? { ...p, node: setResolved(p.node, action.componentId, action.resolved) } : p,
                ),
              },
        ),
      };
    case "error/set":
      return { ...state, error: action.error };
    default:
      return state;
  }
}

/* ------------------------------------------------------------ thread groups */

export type ThreadGroup = { label: string; threads: ThreadSummary[] };

/** Group threads (already most-recent-first) into Today / Yesterday / Previous 7 days / Older. */
export function groupThreads(threads: ThreadSummary[], now = Date.now()): ThreadGroup[] {
  const d = new Date(now);
  const today = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const yesterday = today - 86_400_000;
  const week = today - 7 * 86_400_000;
  const buckets: ThreadGroup[] = [
    { label: "Today", threads: [] },
    { label: "Yesterday", threads: [] },
    { label: "Previous 7 days", threads: [] },
    { label: "Older", threads: [] },
  ];
  const sorted = threads.slice().sort((a, b) => toMs(b.updated_at || b.created_at) - toMs(a.updated_at || a.created_at));
  for (const t of sorted) {
    const ts = toMs(t.updated_at || t.created_at);
    const idx = ts >= today ? 0 : ts >= yesterday ? 1 : ts >= week ? 2 : 3;
    buckets[idx].threads.push(t);
  }
  return buckets.filter((b) => b.threads.length > 0);
}
