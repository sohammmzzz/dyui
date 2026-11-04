/**
 * Server-Sent Events over fetch (SPEC §4).
 *
 * `EventSource` only does GET, so DyUI streams POST responses through fetch and
 * parses the `text/event-stream` framing here. The parser follows the WHATWG
 * algorithm: LF, CRLF and lone-CR line endings (also split across chunks), multi-line
 * `data:` fields joined with "\n", `:` comment lines (heartbeats) ignored, unknown
 * fields ignored. Unlike the browser, a final event without its trailing blank line
 * is still delivered at end of stream (forgiving towards proxies that cut the tail).
 */
import type { StreamEvent } from "./types";

export type RawSSE = { event: string; data: string; id?: string };

export class SSEParser {
  private buf = "";
  private eventName = "";
  private data: string[] = [];
  private lastId: string | undefined;
  private pendingCR = false;
  private started = false;

  /** Feed decoded text; returns every event completed by this chunk. */
  push(chunk: string): RawSSE[] {
    const out: RawSSE[] = [];
    if (!chunk) return out;
    let text = chunk;
    if (!this.started) {
      this.started = true;
      if (text.charCodeAt(0) === 0xfeff) text = text.slice(1);
    }
    if (this.pendingCR) {
      this.pendingCR = false;
      if (text.charCodeAt(0) === 10) text = text.slice(1);
    }
    const b = this.buf + text;
    let start = 0;
    for (let i = 0; i < b.length; i++) {
      const c = b.charCodeAt(i);
      if (c !== 10 && c !== 13) continue;
      const line = b.slice(start, i);
      if (c === 13) {
        if (i + 1 < b.length) {
          if (b.charCodeAt(i + 1) === 10) i++;
        } else {
          this.pendingCR = true; // a following "\n" in the next chunk belongs to this CR
        }
      }
      start = i + 1;
      this.line(line, out);
    }
    this.buf = b.slice(start);
    return out;
  }

  /** End of stream: deliver a trailing event that lacked its blank line. */
  flush(): RawSSE[] {
    const out: RawSSE[] = [];
    if (this.buf) {
      this.line(this.buf, out);
      this.buf = "";
    }
    this.dispatch(out);
    return out;
  }

  private line(line: string, out: RawSSE[]) {
    if (line === "") return this.dispatch(out);
    if (line.charCodeAt(0) === 58 /* ":" comment / heartbeat */) return;
    const idx = line.indexOf(":");
    let field = line;
    let value = "";
    if (idx !== -1) {
      field = line.slice(0, idx);
      value = line.slice(idx + 1);
      if (value.charCodeAt(0) === 32) value = value.slice(1);
    }
    if (field === "event") this.eventName = value;
    else if (field === "data") this.data.push(value);
    else if (field === "id" && !value.includes("\0")) this.lastId = value;
    // "retry" and unknown fields are ignored.
  }

  private dispatch(out: RawSSE[]) {
    if (this.data.length === 0) {
      this.eventName = "";
      return;
    }
    out.push({ event: this.eventName || "message", data: this.data.join("\n"), id: this.lastId });
    this.eventName = "";
    this.data = [];
  }
}

function abortError(): Error {
  try {
    return new DOMException("The operation was aborted.", "AbortError");
  } catch {
    const e = new Error("The operation was aborted.");
    e.name = "AbortError";
    return e;
  }
}

/** Read a byte stream as raw SSE events. Cancels the reader on abort or early exit. */
export async function* readSSE(
  body: ReadableStream<Uint8Array>,
  signal?: AbortSignal,
): AsyncGenerator<RawSSE> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  const parser = new SSEParser();
  let finished = false;
  const onAbort = () => {
    reader.cancel().catch(() => {});
  };
  if (signal?.aborted) throw abortError();
  signal?.addEventListener("abort", onAbort, { once: true });
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (signal?.aborted) throw abortError();
      if (done) break;
      if (value) for (const ev of parser.push(decoder.decode(value, { stream: true }))) yield ev;
    }
    finished = true;
    for (const ev of parser.push(decoder.decode())) yield ev;
    for (const ev of parser.flush()) yield ev;
  } finally {
    signal?.removeEventListener("abort", onAbort);
    if (!finished) reader.cancel().catch(() => {});
    try {
      reader.releaseLock();
    } catch {
      /* already released */
    }
  }
}

/** Decode a raw SSE event into a typed DyUI event (null for malformed JSON). */
export function decodeEvent(raw: RawSSE): StreamEvent | null {
  let data: unknown = {};
  if (raw.data.trim() !== "") {
    try {
      data = JSON.parse(raw.data);
    } catch {
      if (typeof console !== "undefined") console.warn(`[dyui] dropped malformed SSE "${raw.event}" event`);
      return null;
    }
  }
  return { event: raw.event, data } as StreamEvent;
}

/** Typed DyUI events from a fetch Response body. */
export async function* streamEvents(body: ReadableStream<Uint8Array>, signal?: AbortSignal): AsyncGenerator<StreamEvent> {
  for await (const raw of readSSE(body, signal)) {
    const ev = decodeEvent(raw);
    if (ev) yield ev;
  }
}

export function isAbortError(e: unknown): boolean {
  return !!e && typeof e === "object" && (e as { name?: string }).name === "AbortError";
}
