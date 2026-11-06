/**
 * Chat controller: owns the reducer, runs SSE streams through the transport and
 * exposes stable callbacks to the shell and to components (via NodeContext).
 *
 * Streams are tagged with the "view" (open thread) they started in. Switching
 * threads or starting a new chat does not kill a running reply: its events keep
 * updating the sidebar (thread, title) while message events are left to the
 * server, which persists them; reopening the thread reloads it.
 */
import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { ApiError, actionFailure, describeError, isAbortError, type Transport } from "@/lib/api";
import {
  chatReducer,
  initialChatState,
  messageFiles,
  messageText,
  type ChatState,
  type Resolution,
} from "@/lib/store";
import type { ActionRequest, AppConfig, FileRef, StreamEvent } from "@/lib/types";
import type { ToastFn } from "./Toasts";

type StreamKind = "chat" | "action" | "create";

type Entry = {
  ctrl: AbortController;
  view: number;
  producing: boolean;
  ids: Set<string>;
  placeholderKey?: string;
};

export type ComponentAction = Omit<ActionRequest, "thread_id" | "message_id">;

export type ChatActions = {
  send: (text: string, files?: FileRef[]) => void;
  /** quick replies / onReply: like send, but stops a running reply first */
  reply: (text: string) => void;
  stop: () => void;
  regenerate: () => void;
  edit: (messageId: string, text: string) => void;
  retry: () => void;
  action: (messageId: string, req: ComponentAction) => void;
  feedback: (messageId: string, value: 1 | -1 | 0) => void;
  newChat: () => void;
  openThread: (id: string) => void;
  renameThread: (id: string, title: string) => void;
  deleteThread: (id: string) => Promise<void>;
};

const rid = () => Math.random().toString(36).slice(2, 10);

function humanize(action: string) {
  const s = action.replace(/[_-]+/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function readHash(): string | null {
  if (typeof location === "undefined") return null;
  const h = decodeURIComponent(location.hash.replace(/^#/, "")).trim();
  return /^[\w.-]{1,128}$/.test(h) ? h : null;
}

function writeHash(id: string | null) {
  try {
    const url = location.pathname + location.search + (id ? `#${encodeURIComponent(id)}` : "");
    if (url !== location.pathname + location.search + location.hash) history.replaceState(history.state, "", url);
  } catch {
    /* sandboxed */
  }
}

export function useChat(
  transport: Transport,
  config: AppConfig,
  opts: { toast: ToastFn; onUnauthorized: () => void },
): { state: ChatState; busy: boolean; viewKey: number; actions: ChatActions } {
  const [state, dispatch] = useReducer(chatReducer, initialChatState);
  const stateRef = useRef(state);
  stateRef.current = state;
  const optsRef = useRef(opts);
  optsRef.current = opts;

  const view = useRef(0);
  const streams = useRef(new Map<number, Entry>());
  const seq = useRef(0);
  const [busy, setBusy] = useState(false);
  /** bumps whenever a different conversation is shown (new chat / open thread) */
  const [viewKey, setViewKey] = useState(0);

  const sync = useCallback(() => {
    let b = false;
    for (const s of streams.current.values()) if (s.view === view.current && s.producing) b = true;
    setBusy(b);
  }, []);

  const fail = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.status === 401) return optsRef.current.onUnauthorized();
    dispatch({ type: "error/set", error: { message: describeError(e, { kind: "message" }) } });
  }, []);

  const run = useCallback(
    async (
      kind: StreamKind,
      start: (signal: AbortSignal) => AsyncIterable<StreamEvent>,
      o: { producing: boolean; placeholderKey?: string },
    ): Promise<{ aborted: boolean; failed: unknown }> => {
      const id = ++seq.current;
      const entry: Entry = {
        ctrl: new AbortController(),
        view: view.current,
        producing: o.producing,
        ids: new Set(),
        placeholderKey: o.placeholderKey,
      };
      streams.current.set(id, entry);
      sync();
      let aborted = false;
      let failed: unknown = null;
      try {
        for await (const ev of start(entry.ctrl.signal)) {
          if (entry.view !== view.current) {
            // background stream: keep the sidebar honest, leave messages to the server
            if (ev.event === "thread") dispatch({ type: "thread/upsert", thread: ev.data });
            else if (ev.event === "title") dispatch({ type: "event", event: ev });
            continue;
          }
          if (ev.event === "message_start") {
            entry.ids.add(ev.data.id);
            if (!entry.producing) {
              entry.producing = true;
              sync();
            }
          } else if (ev.event === "user_message") {
            if (!entry.producing) {
              entry.producing = true;
              sync();
            }
            if (kind === "action" && !entry.placeholderKey) {
              // fallback route: the action became a user message; show the thinking slot
              dispatch({ type: "event", event: ev });
              entry.placeholderKey = `pending_${rid()}`;
              dispatch({ type: "placeholder/add", key: entry.placeholderKey });
              continue;
            }
          } else if (ev.event === "thread") {
            writeHash(ev.data.id);
          }
          dispatch({ type: "event", event: ev });
        }
      } catch (e) {
        if (isAbortError(e) || entry.ctrl.signal.aborted) aborted = true;
        else failed = e;
      } finally {
        streams.current.delete(id);
        sync();
        if (entry.view === view.current) {
          dispatch({ type: "stream/settle", ids: [...entry.ids], aborted, placeholderKey: entry.placeholderKey });
        }
      }
      return { aborted, failed: entry.view === view.current ? failed : null };
    },
    [sync],
  );

  const stop = useCallback(() => {
    for (const s of streams.current.values()) if (s.view === view.current) s.ctrl.abort();
  }, []);

  const send = useCallback(
    (text: string, files: FileRef[] = []) => {
      const t = text.trim();
      if (!t && !files.length) return;
      const s = stateRef.current;
      const localId = `local_${rid()}`;
      const placeholderKey = `pending_${rid()}`;
      dispatch({ type: "send", text: t, files, localId, placeholderKey });
      void run(
        "chat",
        (signal) => transport.chat({ thread_id: s.threadId, message: { text: t, files: files.map((f) => f.id) } }, signal),
        { producing: true, placeholderKey },
      ).then((r) => r.failed && fail(r.failed));
    },
    [run, transport, fail],
  );

  const reply = useCallback(
    (text: string) => {
      stop();
      send(text);
    },
    [stop, send],
  );

  const regenerate = useCallback(() => {
    const s = stateRef.current;
    if (!s.threadId) return;
    const placeholderKey = `pending_${rid()}`;
    dispatch({ type: "regenerate", placeholderKey });
    void run("chat", (signal) => transport.chat({ thread_id: s.threadId, regenerate: true }, signal), {
      producing: true,
      placeholderKey,
    }).then((r) => r.failed && fail(r.failed));
  }, [run, transport, fail]);

  const edit = useCallback(
    (messageId: string, text: string) => {
      const s = stateRef.current;
      const t = text.trim();
      if (!s.threadId || !t) return;
      const placeholderKey = `pending_${rid()}`;
      dispatch({ type: "edit", messageId, text: t, placeholderKey });
      void run(
        "chat",
        (signal) => transport.chat({ thread_id: s.threadId, edit: { message_id: messageId, text: t } }, signal),
        { producing: true, placeholderKey },
      ).then((r) => r.failed && fail(r.failed));
    },
    [run, transport, fail],
  );

  const retry = useCallback(() => {
    const s = stateRef.current;
    const real = s.messages.filter((m) => !m.placeholder);
    const last = real[real.length - 1];
    if (!last) return;
    if (last.role === "user" && last.local) {
      // never reached the server: send it again
      dispatch({ type: "message/remove", id: last.id });
      send(messageText(last), messageFiles(last));
    } else {
      regenerate();
    }
  }, [send, regenerate]);

  const action = useCallback(
    (messageId: string, req: ComponentAction) => {
      const s = stateRef.current;
      if (!s.threadId) return;
      const resolved: Resolution = { label: req.label || humanize(req.action), values: req.values ?? {} };
      dispatch({ type: "resolve", messageId, componentId: req.component_id, resolved });
      void run(
        "action",
        (signal) => transport.action({ ...req, label: resolved.label, thread_id: s.threadId!, message_id: messageId }, signal),
        { producing: false },
      ).then((r) => {
        if (!r.failed) return;
        const plan = actionFailure(r.failed);
        if (!plan.keepResolved) dispatch({ type: "resolve", messageId, componentId: req.component_id, resolved: undefined });
        if (plan.unauthorized) return optsRef.current.onUnauthorized();
        optsRef.current.toast(plan.message, plan.tone);
      });
    },
    [run, transport],
  );

  const feedback = useCallback(
    (messageId: string, value: 1 | -1 | 0) => {
      const s = stateRef.current;
      if (!s.threadId) return;
      const prev = s.messages.find((m) => m.id === messageId)?.feedback ?? 0;
      dispatch({ type: "feedback", messageId, value });
      transport
        .feedback({ thread_id: s.threadId, message_id: messageId, value })
        .then(() => {
          if (value !== 0) optsRef.current.toast("Thanks for the feedback", "success");
        })
        .catch((e) => {
          dispatch({ type: "feedback", messageId, value: prev });
          optsRef.current.toast(describeError(e), "error");
        });
    },
    [transport],
  );

  const newChat = useCallback(() => {
    view.current++;
    setViewKey(view.current);
    sync();
    dispatch({ type: "thread/clear" });
    writeHash(null);
  }, [sync]);

  const openThread = useCallback(
    (id: string) => {
      const s = stateRef.current;
      if (s.threadId === id && !s.loadingThreadId && s.messages.length) return;
      view.current++;
      const v = view.current;
      setViewKey(v);
      sync();
      dispatch({ type: "thread/loading", id });
      writeHash(id);
      transport
        .getThread(id)
        .then((thread) => {
          if (view.current === v) dispatch({ type: "thread/open", thread });
        })
        .catch((e) => {
          if (view.current !== v) return;
          if (e instanceof ApiError && e.status === 401) return optsRef.current.onUnauthorized();
          if (e instanceof ApiError && e.status === 404) {
            dispatch({ type: "thread/remove", id });
            optsRef.current.toast("That conversation no longer exists", "info");
          } else {
            optsRef.current.toast(describeError(e), "error");
            dispatch({ type: "thread/clear" });
          }
          writeHash(null);
        });
    },
    [transport, sync],
  );

  const renameThread = useCallback(
    (id: string, title: string) => {
      const t = title.trim();
      const prev = stateRef.current.threads.find((x) => x.id === id);
      if (!t || !prev || prev.title === t) return;
      dispatch({ type: "thread/rename", id, title: t });
      transport.renameThread(id, t).catch((e) => {
        dispatch({ type: "thread/rename", id, title: prev.title });
        optsRef.current.toast(describeError(e), "error");
      });
    },
    [transport],
  );

  const deleteThread = useCallback(
    async (id: string) => {
      try {
        await transport.deleteThread(id);
      } catch (e) {
        if (!(e instanceof ApiError && e.status === 404)) {
          optsRef.current.toast(describeError(e), "error");
          return;
        }
      }
      if (stateRef.current.threadId === id) {
        view.current++;
        setViewKey(view.current);
        sync();
        writeHash(null);
      }
      dispatch({ type: "thread/remove", id });
      optsRef.current.toast("Chat deleted", "info");
    },
    [transport, sync],
  );

  // initial load: thread list + deep-linked thread
  useEffect(() => {
    let alive = true;
    if (config.features.history) {
      transport
        .listThreads()
        .then((threads) => alive && dispatch({ type: "threads/set", threads }))
        .catch((e) => {
          if (!alive) return;
          dispatch({ type: "threads/set", threads: [] });
          if (e instanceof ApiError && e.status === 401) optsRef.current.onUnauthorized();
        });
    }
    const id = readHash();
    if (id) openThread(id);
    const onHash = () => {
      const h = readHash();
      if (h && h !== stateRef.current.threadId) openThread(h);
    };
    window.addEventListener("hashchange", onHash);
    return () => {
      alive = false;
      window.removeEventListener("hashchange", onHash);
    };
  }, [transport, config.features.history, openThread]);

  // abort everything on unmount
  useEffect(
    () => () => {
      for (const s of streams.current.values()) s.ctrl.abort();
    },
    [],
  );

  const actions = useMemo<ChatActions>(
    () => ({ send, reply, stop, regenerate, edit, retry, action, feedback, newChat, openThread, renameThread, deleteThread }),
    [send, reply, stop, regenerate, edit, retry, action, feedback, newChat, openThread, renameThread, deleteThread],
  );

  return { state, busy, viewKey, actions };
}
