import { describe, expect, it } from "vitest";
import { SSEParser, decodeEvent, readSSE, type RawSSE } from "./sse";

function parseAll(chunks: string[]): RawSSE[] {
  const p = new SSEParser();
  const out: RawSSE[] = [];
  for (const c of chunks) out.push(...p.push(c));
  out.push(...p.flush());
  return out;
}

const STREAM =
  'event: thread\ndata: {"id":"t1","title":"New chat","created_at":1,"updated_at":1}\n\n' +
  ": ping\n\n" +
  'event: text\ndata: {"message_id":"m1","delta":"Hel"}\n\n' +
  'event: text\ndata: {"message_id":"m1","delta":"lo ✓ café"}\n\n' +
  "event: done\ndata: {}\n\n";

describe("SSEParser", () => {
  it("parses LF-framed events and ignores comments", () => {
    const evs = parseAll([STREAM]);
    expect(evs.map((e) => e.event)).toEqual(["thread", "text", "text", "done"]);
    expect(JSON.parse(evs[2].data)).toEqual({ message_id: "m1", delta: "lo ✓ café" });
  });

  it("parses CRLF and lone-CR framing identically", () => {
    const lf = parseAll([STREAM]);
    expect(parseAll([STREAM.replace(/\n/g, "\r\n")])).toEqual(lf);
    expect(parseAll([STREAM.replace(/\n/g, "\r")])).toEqual(lf);
  });

  it("is chunk-boundary independent (every split point, LF and CRLF)", () => {
    for (const src of [STREAM, STREAM.replace(/\n/g, "\r\n")]) {
      const whole = parseAll([src]);
      for (let i = 0; i <= src.length; i++) {
        expect(parseAll([src.slice(0, i), src.slice(i)])).toEqual(whole);
      }
      // one character at a time
      expect(parseAll(src.split(""))).toEqual(whole);
    }
  });

  it("joins multi-line data with newlines", () => {
    const evs = parseAll(['event: ui\ndata: {"a":\ndata:  1,\ndata: "b": 2}\n\n']);
    expect(evs).toHaveLength(1);
    expect(evs[0].data).toBe('{"a":\n 1,\n"b": 2}');
    expect(JSON.parse(evs[0].data)).toEqual({ a: 1, b: 2 });
  });

  it("defaults the event name, strips one leading space, ignores unknown fields", () => {
    const evs = parseAll(["data:x\nretry: 100\nfoo: bar\n\nevent:  spaced\ndata:  y\n\n"]);
    expect(evs).toEqual([
      { event: "message", data: "x", id: undefined },
      { event: " spaced", data: " y", id: undefined },
    ]);
  });

  it("skips events without data and handles heartbeats between events", () => {
    const evs = parseAll(["event: lonely\n\n: ping\n\n:\n\ndata: 1\n\n"]);
    expect(evs.map((e) => e.event)).toEqual(["message"]);
  });

  it("strips a leading BOM", () => {
    expect(parseAll(["\uFEFFdata: 1\n\n"])).toEqual([{ event: "message", data: "1", id: undefined }]);
  });

  it("delivers a trailing event without its blank line at flush", () => {
    expect(parseAll(["event: done\ndata: {}"]).map((e) => e.event)).toEqual(["done"]);
  });
});

describe("readSSE", () => {
  function bodyFrom(parts: Uint8Array[]): ReadableStream<Uint8Array> {
    return new ReadableStream({
      start(controller) {
        for (const p of parts) controller.enqueue(p);
        controller.close();
      },
    });
  }

  it("decodes UTF-8 split across byte chunks", async () => {
    const bytes = new TextEncoder().encode(STREAM);
    // split inside the multi-byte "✓"
    const at = new TextEncoder().encode(STREAM.slice(0, STREAM.indexOf("✓"))).length + 1;
    const evs: RawSSE[] = [];
    for await (const ev of readSSE(bodyFrom([bytes.slice(0, at), bytes.slice(at)]))) evs.push(ev);
    expect(evs.map((e) => e.event)).toEqual(["thread", "text", "text", "done"]);
    expect(JSON.parse(evs[2].data).delta).toBe("lo ✓ café");
  });

  it("stops with an AbortError when aborted", async () => {
    const ctrl = new AbortController();
    const stream = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(new TextEncoder().encode("data: 1\n\n"));
      },
    });
    const it = readSSE(stream, ctrl.signal);
    expect((await it.next()).value).toEqual({ event: "message", data: "1", id: undefined });
    ctrl.abort();
    await expect(it.next()).rejects.toMatchObject({ name: "AbortError" });
  });
});

describe("decodeEvent", () => {
  it("parses JSON payloads and drops malformed ones", () => {
    expect(decodeEvent({ event: "done", data: "{}" })).toEqual({ event: "done", data: {} });
    expect(decodeEvent({ event: "text", data: "{nope" })).toBeNull();
  });
});
