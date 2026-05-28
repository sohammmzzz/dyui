/**
 * Streaming client for a DyUI agent endpoint.
 *
 * The Python server responds to a POST with a `text/event-stream`. EventSource
 * can't POST a body, so we use `fetch` + a manual SSE parser over the response
 * `ReadableStream`. This works in every modern browser and in Node 18+.
 */
import type { StreamFrame } from "./types";

export interface StreamOptions {
  /** Full URL of the DyUI stream endpoint (e.g. http://localhost:8008/dyui/stream). */
  url: string;
  /** Agent input; sent as `{ input, config }` JSON body. */
  input?: unknown;
  config?: Record<string, unknown>;
  /** Extra headers (auth tokens, etc.). */
  headers?: Record<string, string>;
  /** Abort signal to cancel the stream. */
  signal?: AbortSignal;
}

/** Parse a raw SSE block ("event: x\ndata: {...}") into a typed frame. */
function parseBlock(block: string): StreamFrame | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return null;
  let data: unknown = {};
  try {
    data = JSON.parse(dataLines.join("\n"));
  } catch {
    data = {};
  }
  return { type: event, data } as StreamFrame;
}

/**
 * Open the stream and invoke `onFrame` for each parsed SSE frame. Resolves when
 * the stream ends (server `done` or socket close). Rejects on network/abort.
 */
export async function streamAgent(
  options: StreamOptions,
  onFrame: (frame: StreamFrame) => void
): Promise<void> {
  const { url, input, config, headers, signal } = options;

  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(headers ?? {}) },
    body: JSON.stringify({ input, config }),
    signal,
  });

  if (!resp.ok || !resp.body) {
    throw new Error(`DyUI stream failed: ${resp.status} ${resp.statusText}`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line.
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const frame = parseBlock(block);
      if (frame) onFrame(frame);
    }
  }
  // Flush any trailing frame without a terminating blank line.
  if (buffer.trim()) {
    const frame = parseBlock(buffer);
    if (frame) onFrame(frame);
  }
}
