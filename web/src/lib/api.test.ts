import { afterEach, describe, expect, it, vi } from "vitest";
import { createHttpTransport } from "./api";

/**
 * The server answers 415 to any JSON route whose body isn't `application/json`
 * (CSRF hardening), so every write the client sends with a body must declare it.
 */
describe("http transport writes", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sends Content-Type: application/json on every write with a body", async () => {
    const calls: { url: string; init: RequestInit }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit) => {
        calls.push({ url, init });
        const sse = String((init.headers as Record<string, string>)?.Accept ?? "").includes("event-stream");
        return new Response(sse ? "event: done\ndata: {}\n\n" : JSON.stringify({ ok: true, id: "t", title: "x", created_at: 1, updated_at: 1 }), {
          status: 200,
          headers: { "content-type": sse ? "text/event-stream" : "application/json" },
        });
      }),
    );
    const t = createHttpTransport("/api/");
    await t.login("pw");
    await t.renameThread("t1", "New");
    await t.deleteThread("t1");
    await t.feedback({ thread_id: "t1", message_id: "m1", value: 1 });
    for await (const _ of t.chat({ thread_id: null, message: { text: "hi" } })) void _;
    for await (const _ of t.action({ thread_id: "t1", message_id: "m1", component_id: "c1", action: "go" })) void _;
    for await (const _ of t.createThread()) void _;

    const writes = calls.filter((c) => (c.init.method ?? "GET") !== "GET");
    expect(writes.length).toBe(7);
    for (const w of writes) {
      const h = w.init.headers as Record<string, string>;
      if (w.init.body !== undefined && w.init.body !== null) expect(h["Content-Type"], w.url).toBe("application/json");
      expect(w.init.credentials, w.url).toBe("same-origin");
    }
  });
});
