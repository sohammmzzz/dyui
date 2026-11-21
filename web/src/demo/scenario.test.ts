import { beforeAll, describe, expect, it } from "vitest";
import { chatReducer, initialChatState, type ChatState } from "@/lib/store";
import { createMockTransport } from "@/lib/mock";
import type { Message, StreamEvent, UINode } from "@/lib/types";
import { autoTitle, demoScenario, parseReply } from "./scenario";

beforeAll(() => {
  history.replaceState(null, "", "/?speed=0.0005");
});

async function drain(it: AsyncIterable<StreamEvent>, state: ChatState) {
  for await (const e of it) state = chatReducer(state, { type: "event", event: e });
  return state;
}

const text = (m: Message) => m.parts.map((p) => (p.type === "text" ? p.text : "")).join("");
const uis = (m: Message) => m.parts.filter((p) => p.type === "ui").map((p) => (p as { node: UINode }).node);

async function send(t: ReturnType<typeof createMockTransport>, s: ChatState, msg: string, threadId: string | null = null) {
  s = chatReducer(s, { type: "send", text: msg, files: [], localId: "l" + msg, placeholderKey: "p" + msg });
  return drain(t.chat({ thread_id: threadId, message: { text: msg } }), s);
}

describe("demo scenario (dyui demo)", () => {
  it("serves demo.py's config and starters", async () => {
    const cfg = await createMockTransport({ scenario: demoScenario }).getConfig();
    expect(cfg.title).toBe("DyUI");
    expect(cfg.welcome).toBe("Ask me anything — I answer in interfaces.");
    expect(cfg.description).toBe("A short tour of chat that answers in interfaces.");
    expect(cfg.starters.map((s) => [s.label, s.icon])).toEqual([
      ["Show me what you can do", "sparkles"],
      ["Analyze Q3 sales", "chart"],
      ["Plan a weekend in Lisbon", "plane"],
      ["File a support ticket", "life-buoy"],
    ]);
  });

  it("splits a reply the way the server parser does", () => {
    const ops = parseReply('Hi:\n\n```dyui\n{"ui":"stats","items":[]}\n{"ui":"callout","text":"x"}\n```\nBye\n\n```dyui\n{"ui":"rating","label":"r"}\n```\n');
    expect(ops.map((o) => o.t)).toEqual(["text", "ui", "ui", "text", "ui"]);
    expect(ops[0]).toEqual({ t: "text", text: "Hi:\n\n" });
    expect(ops[3]).toEqual({ t: "text", text: "Bye\n\n" });
    const rating = ops[4] as Extract<(typeof ops)[number], { t: "ui" }>;
    expect(rating.node.props).toEqual({ label: "r", max: 5, action: "rating" });
  });

  it("titles like the server", () => {
    expect(autoTitle("Show me what you can do")).toBe("Show me what you can do");
    expect(autoTitle("one two three four five six seven")).toBe("one two three four five six…");
  });

  it("the tour is deterministic and matches demo.py", async () => {
    const runs: string[] = [];
    for (let i = 0; i < 2; i++) {
      const t = createMockTransport({ scenario: demoScenario });
      const s = await send(t, initialChatState, "Show me what you can do");
      const a = s.messages.at(-1)!;
      expect(a.status).toBe("done");
      expect(text(a)).toBe(
        "Here's the idea: instead of describing things, I **show** them. A few examples —\n\nData becomes charts:\n\nand steps become live plans:\n\nWhere to next?\n\n",
      );
      expect(uis(a).map((n) => n.ui)).toEqual(["stats", "chart", "plan", "quick_replies"]);
      runs.push(JSON.stringify(a.parts.map((p) => (p.type === "ui" ? { ...p.node, id: "" } : p))));
      // persist=False: nothing written to storage, each load starts empty
      expect(localStorage.length).toBe(0);
    }
    expect(runs[0]).toBe(runs[1]);
    expect(await createMockTransport({ scenario: demoScenario }).listThreads()).toEqual([]);
  });

  it("books a flight through the custom Flight card and a confirm", async () => {
    const t = createMockTransport({ scenario: demoScenario });
    let s = await send(t, initialChatState, "Plan a weekend in Lisbon");
    const lis = s.messages.at(-1)!;
    const cards = uis(lis).filter((n) => n.ui === "card");
    expect(cards.map((c) => c.props.title)).toEqual(["TAP Air Portugal", "British Airways"]);
    expect(cards[0].children?.[0].props.items).toEqual([
      { key: "Duration", value: "2h 45m" },
      { key: "Price", value: "€189" },
    ]);
    const book = cards[0].props.actions[0];
    const stream = t.action({ thread_id: s.threadId!, message_id: lis.id, component_id: cards[0].id, action: book.action, label: book.label, data: book.data });
    const it = stream[Symbol.asyncIterator]();
    let confirm: UINode | null = null;
    let mid = "";
    while (!confirm) {
      const { value, done } = await it.next();
      if (done) throw new Error("no confirm");
      s = chatReducer(s, { type: "event", event: value });
      if (value.event === "ui" && value.data.node.ui === "confirm") {
        confirm = value.data.node;
        mid = value.data.message_id;
      }
    }
    expect(confirm.props.title).toBe("Book TAP Air Portugal for €189?");
    const rest = (async () => {
      for (let r = await it.next(); !r.done; r = await it.next()) s = chatReducer(s, { type: "event", event: r.value });
    })();
    s = await drain(t.action({ thread_id: s.threadId!, message_id: mid, component_id: confirm.id, action: "confirm_booking", label: "Book flight", values: { confirmed: true } }), s);
    await rest;
    const last = s.messages.at(-1)!;
    expect(text(last)).toBe("Great choice — **TAP Air Portugal**, Fri 18:05. One last check:");
    expect(uis(last).at(-1)!.props.title).toBe("You're going to Lisbon");
  });

  it("files a ticket and answers the rating", async () => {
    const t = createMockTransport({ scenario: demoScenario });
    let s = await send(t, initialChatState, "File a support ticket");
    const m = s.messages.at(-1)!;
    const form = uis(m).find((n) => n.ui === "form")!;
    s = await drain(
      t.action({ thread_id: s.threadId!, message_id: m.id, component_id: form.id, action: "submit_ticket", label: "Create ticket", values: { subject: "Cannot export", area: "Exports" } }),
      s,
    );
    const reply = s.messages.at(-1)!;
    expect(text(reply)).toContain("Ticket **#4821** is open: *Cannot export*.");
    const rating = uis(reply).find((n) => n.ui === "rating")!;
    s = await drain(t.action({ thread_id: s.threadId!, message_id: reply.id, component_id: rating.id, action: "rating", label: "4 stars", values: { rating: 4 } }), s);
    expect(text(s.messages.at(-1)!)).toBe("Thank you for the 4/5 — glad that helped. I've passed it on to the team.");
  });
});
