import { beforeAll, describe, expect, it } from "vitest";
import { chatReducer, initialChatState, type ChatState } from "./store";
import type { StreamEvent, UINode } from "./types";
import { createMockTransport } from "./mock";

beforeAll(() => {
  // make the scripted timing near-instant
  history.replaceState(null, "", "/?mock=1&speed=0.0005&fresh=1");
});

async function drain(it: AsyncIterable<StreamEvent>, state: ChatState, onEvent?: (e: StreamEvent) => void) {
  for await (const e of it) {
    onEvent?.(e);
    state = chatReducer(state, { type: "event", event: e });
  }
  return state;
}

describe("mock transport", () => {
  it("streams a protocol-valid showcase turn and persists it", async () => {
    const t = createMockTransport();
    const cfg = await t.getConfig();
    expect(cfg.starters.length).toBeGreaterThan(0);
    const names: string[] = [];
    let s = chatReducer(initialChatState, { type: "send", text: cfg.starters[0].message, files: [], localId: "l", placeholderKey: "p" });
    s = await drain(t.chat({ thread_id: null, message: { text: cfg.starters[0].message } }), s, (e) => names.push(e.event));
    expect(names[0]).toBe("thread");
    expect(names).toContain("user_message");
    expect(names).toContain("message_start");
    expect(names).toContain("step");
    expect(names).toContain("reasoning");
    expect(names.at(-1)).toBe("done");
    const assistant = s.messages.at(-1)!;
    expect(assistant.status).toBe("done");
    const uis = assistant.parts.filter((p) => p.type === "ui").map((p) => (p as { node: UINode }).node.ui);
    expect(uis).toEqual(expect.arrayContaining(["stats", "chart", "table", "quick_replies"]));
    // server copy matches the client copy
    const server = await t.getThread(s.threadId!);
    expect(server.messages.at(-1)!.parts).toEqual(assistant.parts);
    expect((await t.listThreads())[0].id).toBe(s.threadId);
  });

  it("pauses on an ask() component until the action arrives", async () => {
    const t = createMockTransport();
    let s: ChatState = initialChatState;
    let confirmNode: UINode | null = null;
    let messageId = "";
    const stream = t.chat({ thread_id: null, message: { text: "Delete the stale branches in our repo" } });
    const it = stream[Symbol.asyncIterator]();
    while (!confirmNode) {
      const { value, done } = await it.next();
      if (done) throw new Error("stream ended before the confirm");
      s = chatReducer(s, { type: "event", event: value });
      if (value.event === "ui" && value.data.node.ui === "confirm") {
        confirmNode = value.data.node;
        messageId = value.data.message_id;
      }
    }
    const rest = (async () => {
      for (let r = await it.next(); !r.done; r = await it.next()) s = chatReducer(s, { type: "event", event: r.value });
    })();
    s = await drain(
      t.action({
        thread_id: s.threadId!,
        message_id: messageId,
        component_id: confirmNode.id,
        action: "confirm",
        label: "Delete branches",
        values: { confirmed: true },
      }),
      s,
    );
    await rest;
    const last = s.messages.at(-1)!;
    expect(last.status).toBe("done");
    const confirm = last.parts.find((p) => p.type === "ui" && p.node.ui === "confirm");
    expect(confirm && confirm.type === "ui" && confirm.node.props.__resolved__.label).toBe("Delete branches");
    expect(last.parts.filter((p) => p.type === "step").length).toBe(2);
  });

  it("aborting a stream persists the message as cancelled", async () => {
    const t = createMockTransport();
    const ctrl = new AbortController();
    let threadId = "";
    let n = 0;
    await expect(
      (async () => {
        for await (const e of t.chat({ thread_id: null, message: { text: "Plan a weekend in Lisbon for two" } }, ctrl.signal)) {
          if (e.event === "thread") threadId = e.data.id;
          if (++n === 6) ctrl.abort();
        }
      })(),
    ).rejects.toMatchObject({ name: "AbortError" });
    const th = await t.getThread(threadId);
    expect(th.messages.at(-1)!.status).toBe("cancelled");
  });
});
