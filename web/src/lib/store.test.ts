import { describe, expect, it } from "vitest";
import {
  applyMessageEvent,
  chatReducer,
  groupThreads,
  initialChatState,
  messageText,
  toMs,
  type ChatMessage,
  type ChatState,
} from "./store";
import type { StreamEvent, UINode } from "./types";

const ev = (e: StreamEvent) => ({ type: "event" as const, event: e });
const run = (state: ChatState, ...events: StreamEvent[]) => events.reduce((s, e) => chatReducer(s, ev(e)), state);

function sent(): ChatState {
  return chatReducer(initialChatState, { type: "send", text: "Hi", files: [], localId: "local_1", placeholderKey: "p1", now: 100 });
}

describe("chatReducer — a full turn", () => {
  it("applies thread, user_message, message_start, deltas and message_end", () => {
    let s = sent();
    expect(s.messages.map((m) => [m.role, m.local ?? false, m.placeholder ?? false])).toEqual([
      ["user", true, false],
      ["assistant", false, true],
    ]);

    s = run(
      s,
      { event: "thread", data: { id: "t1", title: "New chat", created_at: 1, updated_at: 1 } },
      { event: "user_message", data: { id: "u1", role: "user", created_at: 100, parts: [{ type: "text", text: "Hi" }] } },
      { event: "message_start", data: { id: "a1", role: "assistant", created_at: 101 } },
      { event: "text", data: { message_id: "a1", delta: "Hel" } },
      { event: "text", data: { message_id: "a1", delta: "lo" } },
      { event: "title", data: { thread_id: "t1", title: "Greeting" } },
      { event: "message_end", data: { id: "a1", status: "done", duration_ms: 900 } },
      { event: "done", data: {} },
    );
    expect(s.threadId).toBe("t1");
    expect(s.threads).toEqual([{ id: "t1", title: "Greeting", created_at: 1, updated_at: 1 }]);
    expect(s.messages).toHaveLength(2);
    const [u, a] = s.messages;
    expect(u.id).toBe("u1");
    expect(u.local).toBeUndefined();
    expect(u.key).toBe("local_1"); // stable React key across the id swap
    expect(a.id).toBe("a1");
    expect(a.key).toBe("p1");
    expect(a.placeholder).toBeUndefined();
    expect(a.status).toBe("done");
    expect(a.duration_ms).toBe(900);
    expect(a.parts).toEqual([{ type: "text", text: "Hello" }]);
  });
});

describe("applyMessageEvent", () => {
  const base: ChatMessage[] = [{ id: "a1", role: "assistant", created_at: 1, parts: [], status: "streaming" }];

  it("appends text to the last text part, starting a new one after other parts", () => {
    const node: UINode = { id: "c_1", ui: "stat", props: { label: "A", value: 1 } };
    let m = applyMessageEvent(base, { event: "text", data: { message_id: "a1", delta: "One " } });
    m = applyMessageEvent(m, { event: "text", data: { message_id: "a1", delta: "two" } });
    m = applyMessageEvent(m, { event: "ui", data: { message_id: "a1", node } });
    m = applyMessageEvent(m, { event: "text", data: { message_id: "a1", delta: "three" } });
    expect(m[0].parts.map((p) => p.type)).toEqual(["text", "ui", "text"]);
    expect(messageText(m[0])).toBe("One twothree");
  });

  it("upserts ui nodes by id, keeping the first position", () => {
    const n1: UINode = { id: "c_1", ui: "table", props: { columns: ["a"], rows: [] }, status: "streaming" };
    const n2: UINode = { id: "c_2", ui: "stat", props: { label: "x", value: 1 } };
    let m = applyMessageEvent(base, { event: "ui", data: { message_id: "a1", node: n1 } });
    m = applyMessageEvent(m, { event: "ui", data: { message_id: "a1", node: n2 } });
    m = applyMessageEvent(m, {
      event: "ui",
      data: { message_id: "a1", node: { ...n1, props: { columns: ["a"], rows: [[1]] }, status: "done" } },
    });
    expect(m[0].parts).toHaveLength(2);
    const first = m[0].parts[0];
    expect(first.type === "ui" && first.node.status).toBe("done");
    expect(first.type === "ui" && first.node.props.rows).toEqual([[1]]);
  });

  it("replaces nested nodes (layout children) in place", () => {
    const card: UINode = {
      id: "c_card",
      ui: "card",
      props: { title: "T" },
      children: [{ id: "c_btns", ui: "buttons", props: { items: [] } }],
    };
    let m = applyMessageEvent(base, { event: "ui", data: { message_id: "a1", node: card } });
    m = applyMessageEvent(m, {
      event: "ui",
      data: { message_id: "a1", node: { id: "c_btns", ui: "buttons", props: { items: [], __resolved__: { label: "Go", values: {} } } } },
    });
    expect(m[0].parts).toHaveLength(1);
    const p = m[0].parts[0];
    expect(p.type === "ui" && p.node.children?.[0].props.__resolved__).toEqual({ label: "Go", values: {} });
  });

  it("upserts steps by id and merges fields", () => {
    let m = applyMessageEvent(base, {
      event: "step",
      data: { message_id: "a1", step: { id: "s1", title: "Search", type: "search", status: "running", started_at: 5, input: { q: 1 } } },
    });
    m = applyMessageEvent(m, {
      event: "step",
      data: { message_id: "a1", step: { id: "s1", title: "Search", type: "search", status: "done", started_at: 5, duration_ms: 1200 } },
    });
    expect(m[0].parts).toHaveLength(1);
    const p = m[0].parts[0];
    expect(p.type === "step" && p.step).toMatchObject({ status: "done", duration_ms: 1200, input: { q: 1 } });
  });

  it("appends consecutive reasoning deltas to one part, creating it if absent", () => {
    let m = applyMessageEvent(base, { event: "reasoning", data: { message_id: "a1", delta: "Think" } });
    m = applyMessageEvent(m, { event: "reasoning", data: { message_id: "a1", delta: "ing" } });
    expect(m[0].parts).toEqual([{ type: "reasoning", text: "Thinking" }]);
  });

  it("starts a new reasoning part per thinking round, like the server (think → text → think)", () => {
    let m = applyMessageEvent(base, { event: "reasoning", data: { message_id: "a1", delta: "Round 1" } });
    m = applyMessageEvent(m, { event: "text", data: { message_id: "a1", delta: "Answer" } });
    m = applyMessageEvent(m, { event: "reasoning", data: { message_id: "a1", delta: "Round " } });
    m = applyMessageEvent(m, { event: "reasoning", data: { message_id: "a1", delta: "2" } });
    expect(m[0].parts).toEqual([
      { type: "reasoning", text: "Round 1" },
      { type: "text", text: "Answer" },
      { type: "reasoning", text: "Round 2" },
    ]);
  });

  it("creates the assistant message when deltas arrive without message_start", () => {
    const m = applyMessageEvent([], { event: "text", data: { message_id: "a9", delta: "x" } });
    expect(m).toHaveLength(1);
    expect(m[0]).toMatchObject({ id: "a9", role: "assistant", status: "streaming" });
  });

  it("re-opens an existing message on a repeated message_start", () => {
    const done: ChatMessage[] = [{ ...base[0], status: "done", parts: [{ type: "text", text: "a" }] }];
    const m = applyMessageEvent(done, { event: "message_start", data: { id: "a1", role: "assistant", created_at: 1 } });
    expect(m).toHaveLength(1);
    expect(m[0].status).toBe("streaming");
    expect(m[0].parts).toHaveLength(1);
  });

  it("keeps a local resolution when a stale server update arrives", () => {
    const n: UINode = { id: "c_1", ui: "confirm", props: { title: "Sure?", __resolved__: { label: "Yes", values: {} } } };
    let m = applyMessageEvent(base, { event: "ui", data: { message_id: "a1", node: n } });
    m = applyMessageEvent(m, { event: "ui", data: { message_id: "a1", node: { ...n, props: { title: "Sure?" } } } });
    const p = m[0].parts[0];
    expect(p.type === "ui" && p.node.props.__resolved__).toEqual({ label: "Yes", values: {} });
  });
});

describe("chatReducer — local operations", () => {
  const thread = {
    id: "t1",
    title: "T",
    created_at: 1,
    updated_at: 1,
    messages: [
      { id: "u1", role: "user" as const, created_at: 1, parts: [{ type: "text" as const, text: "a" }] },
      { id: "a1", role: "assistant" as const, created_at: 2, parts: [{ type: "text" as const, text: "b" }], status: "done" as const },
      { id: "u2", role: "user" as const, created_at: 3, parts: [{ type: "text" as const, text: "c" }] },
      { id: "a2", role: "assistant" as const, created_at: 4, parts: [{ type: "text" as const, text: "d" }], status: "done" as const },
    ],
  };
  const opened = chatReducer(initialChatState, { type: "thread/open", thread });

  it("regenerate drops the trailing assistant message and adds a placeholder", () => {
    const s = chatReducer(opened, { type: "regenerate", placeholderKey: "p" });
    expect(s.messages.map((m) => m.id)).toEqual(["u1", "a1", "u2", "p"]);
  });

  it("edit replaces the user text and drops everything after it", () => {
    const s = chatReducer(opened, { type: "edit", messageId: "u2", text: "c2", placeholderKey: "p" });
    expect(s.messages.map((m) => m.id)).toEqual(["u1", "a1", "u2", "p"]);
    expect(messageText(s.messages[2])).toBe("c2");
    expect(s.messages[2].local).toBe(true);
    // the server's user_message (same id) confirms it
    const s2 = run(s, { event: "user_message", data: { ...thread.messages[2], parts: [{ type: "text", text: "c2" }] } });
    expect(s2.messages[2].local).toBeUndefined();
    expect(s2.messages).toHaveLength(4);
  });

  it("settle finalises streaming messages and removes this stream's placeholder", () => {
    let s = sent();
    s = run(s, { event: "message_start", data: { id: "a1", role: "assistant", created_at: 1 } });
    s = chatReducer(s, { type: "stream/settle", ids: ["a1"], aborted: true, placeholderKey: "p1" });
    expect(s.messages[1].status).toBe("cancelled");
    const s2 = chatReducer(sent(), { type: "stream/settle", ids: [], aborted: false, placeholderKey: "p1" });
    expect(s2.messages).toHaveLength(1);
  });

  it("resolve sets and clears __resolved__ on nested components", () => {
    let s = chatReducer(initialChatState, {
      type: "thread/open",
      thread: {
        ...thread,
        messages: [
          {
            id: "a1",
            role: "assistant",
            created_at: 1,
            parts: [{ type: "ui", node: { id: "c_g", ui: "grid", props: {}, children: [{ id: "c_c", ui: "card", props: { title: "x" } }] } }],
          },
        ],
      },
    });
    s = chatReducer(s, { type: "resolve", messageId: "a1", componentId: "c_c", resolved: { label: "Hold", values: {} } });
    const p = s.messages[0].parts[0];
    expect(p.type === "ui" && p.node.children?.[0].props.__resolved__).toEqual({ label: "Hold", values: {} });
    s = chatReducer(s, { type: "resolve", messageId: "a1", componentId: "c_c", resolved: undefined });
    const p2 = s.messages[0].parts[0];
    expect(p2.type === "ui" && "__resolved__" in p2.node.children![0].props).toBe(false);
  });

  it("error events surface inline", () => {
    const s = run(opened, { event: "error", data: { message: "Model timed out", message_id: "a2" } });
    expect(s.error).toEqual({ message: "Model timed out", messageId: "a2" });
  });

  it("thread list: upsert moves to top, rename, remove clears the open thread", () => {
    let s = chatReducer(initialChatState, {
      type: "threads/set",
      threads: [
        { id: "a", title: "A", created_at: 1, updated_at: 3 },
        { id: "b", title: "B", created_at: 1, updated_at: 2 },
      ],
    });
    s = chatReducer(s, { type: "thread/upsert", thread: { id: "b", title: "B", created_at: 1, updated_at: 9 } });
    expect(s.threads.map((t) => t.id)).toEqual(["b", "a"]);
    s = chatReducer(s, { type: "thread/rename", id: "a", title: "Alpha" });
    expect(s.threads[1].title).toBe("Alpha");
    s = chatReducer({ ...s, threadId: "a" }, { type: "thread/remove", id: "a" });
    expect(s.threadId).toBeNull();
    expect(s.threads.map((t) => t.id)).toEqual(["b"]);
  });
});

describe("groupThreads", () => {
  it("buckets by Today / Yesterday / Previous 7 days / Older (seconds or ms)", () => {
    const now = new Date(2026, 10, 4, 15, 0).getTime();
    const day = 86_400_000;
    const groups = groupThreads(
      [
        { id: "1", title: "", created_at: 0, updated_at: (now - 3_600_000) / 1000 },
        { id: "2", title: "", created_at: 0, updated_at: now - day },
        { id: "3", title: "", created_at: 0, updated_at: (now - 4 * day) / 1000 },
        { id: "4", title: "", created_at: 0, updated_at: now - 30 * day },
      ],
      now,
    );
    expect(groups.map((g) => [g.label, g.threads.map((t) => t.id)])).toEqual([
      ["Today", ["1"]],
      ["Yesterday", ["2"]],
      ["Previous 7 days", ["3"]],
      ["Older", ["4"]],
    ]);
  });

  it("toMs accepts seconds and milliseconds", () => {
    expect(toMs(1_700_000_000)).toBe(1_700_000_000_000);
    expect(toMs(1_700_000_000_000)).toBe(1_700_000_000_000);
  });
});
