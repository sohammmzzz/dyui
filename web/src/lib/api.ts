/**
 * DyUI HTTP client (SPEC §4). Same-origin, cookie-scoped, JSON in / JSON or SSE out.
 *
 * The shell talks to a `Transport`, so the real server and the mock transport
 * (`lib/mock.ts`, for `npm run dev` without Python) are interchangeable.
 */
import { isAbortError, streamEvents } from "./sse";
import type {
  ActionRequest,
  AppConfig,
  ChatRequest,
  FileRef,
  StreamEvent,
  Thread,
  ThreadSummary,
} from "./types";

export type FeedbackRequest = { thread_id: string; message_id: string; value: 1 | -1 | 0; comment?: string };

export type UploadOptions = { onProgress?: (fraction: number) => void; signal?: AbortSignal };

export interface Transport {
  readonly kind: "http" | "mock";
  getConfig(): Promise<AppConfig>;
  login(password: string): Promise<void>;
  listThreads(): Promise<ThreadSummary[]>;
  getThread(id: string): Promise<Thread>;
  renameThread(id: string, title: string): Promise<ThreadSummary>;
  deleteThread(id: string): Promise<void>;
  /** POST /api/threads — runs on_chat_start; first event is `thread`. */
  createThread(signal?: AbortSignal): AsyncIterable<StreamEvent>;
  chat(req: ChatRequest, signal?: AbortSignal): AsyncIterable<StreamEvent>;
  action(req: ActionRequest, signal?: AbortSignal): AsyncIterable<StreamEvent>;
  feedback(req: FeedbackRequest): Promise<void>;
  upload(file: File, opts?: UploadOptions): Promise<FileRef>;
}

export class ApiError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** What the failed request was doing — picks the right wording for 401/413/429. */
export type ErrorContext = {
  kind?: "message" | "upload" | "login" | "action" | "other";
  /** upload limit in MB, when known (AppConfig.max_upload_mb) */
  maxUploadMb?: number | null;
};

/** Human copy for any failure the shell surfaces. */
export function describeError(e: unknown, ctx: ErrorContext = {}): string {
  if (e instanceof ApiError) {
    if (e.status === 401)
      return ctx.kind === "login"
        ? e.message || "That password isn’t right. Try again."
        : "Your session has expired. Sign in again to continue.";
    if (e.status === 409) return e.message || "This was already answered.";
    if (e.status === 413) {
      if (ctx.kind === "upload") {
        if (ctx.maxUploadMb) return `That file is too large. The limit is ${ctx.maxUploadMb} MB.`;
        // the server names the limit in its own message ("File is larger than 20 MB.")
        return e.message && /\d/.test(e.message) ? e.message : "That file is too large to upload.";
      }
      return "That message is too long to send. Try shortening it.";
    }
    if (e.status === 429) return "Too many attempts. Wait a moment and try again.";
    if (e.status >= 500 && !e.message) return "The server ran into a problem. Try again in a moment.";
    return e.message || `Request failed (${e.status}).`;
  }
  if (e instanceof TypeError) return "Couldn’t reach the server. Check your connection and try again.";
  if (e instanceof Error && e.message) return e.message;
  return "Something went wrong. Try again.";
}

export { isAbortError };

/**
 * What to do when POST /api/action fails.
 * - 401 → the session ended: show the gate.
 * - 409 → someone (another tab, a retry) already answered: keep the component
 *   resolved and say so quietly.
 * - anything else → undo the optimistic resolution and show an error.
 */
export function actionFailure(e: unknown): { unauthorized: boolean; keepResolved: boolean; tone: "info" | "error"; message: string } {
  if (e instanceof ApiError && e.status === 401) return { unauthorized: true, keepResolved: false, tone: "error", message: describeError(e) };
  if (e instanceof ApiError && e.status === 409)
    return { unauthorized: false, keepResolved: true, tone: "info", message: describeError(e, { kind: "action" }) };
  return { unauthorized: false, keepResolved: false, tone: "error", message: describeError(e, { kind: "action" }) };
}

/** Upload MIME types the server serves inline; everything else is a download. */
const INLINE_SAFE = ["image/png", "image/jpeg", "image/gif", "image/webp", "image/avif", "image/bmp", "audio/", "video/", "application/pdf", "text/plain", "text/csv", "application/json"];
export function isInlineSafe(type: string | null | undefined): boolean {
  const t = (type || "").toLowerCase().split(";")[0].trim();
  return !!t && INLINE_SAFE.some((p) => t.startsWith(p));
}

async function toApiError(res: Response): Promise<ApiError> {
  let message = "";
  try {
    const text = await res.text();
    try {
      const body = JSON.parse(text);
      message = typeof body?.error === "string" ? body.error : typeof body?.detail === "string" ? body.detail : "";
    } catch {
      message = "";
    }
  } catch {
    /* ignore */
  }
  return new ApiError(message, res.status);
}

/**
 * The API lives at `api/` relative to the page, so an app mounted under a
 * sub-path behind a reverse proxy keeps working (served at `/`, this is `/api/`).
 */
function apiBase(): string {
  if (typeof document === "undefined") return "/api/";
  try {
    return new URL("api/", document.baseURI).pathname;
  } catch {
    return "/api/";
  }
}

export function createHttpTransport(base = apiBase()): Transport {
  const url = (path: string) => base + path.replace(/^\//, "");

  async function json<T>(path: string, init: RequestInit = {}): Promise<T> {
    const res = await fetch(url(path), {
      credentials: "same-origin",
      ...init,
      headers: {
        Accept: "application/json",
        ...(init.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
        ...(init.headers || {}),
      },
    });
    if (!res.ok) throw await toApiError(res);
    const text = await res.text();
    if (!text) return {} as T;
    try {
      return JSON.parse(text) as T;
    } catch {
      throw new ApiError("The server sent an unexpected response.", res.status);
    }
  }

  async function* sse(path: string, body: unknown, signal?: AbortSignal): AsyncGenerator<StreamEvent> {
    const res = await fetch(url(path), {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
    if (!res.ok) throw await toApiError(res);
    if (!res.body) throw new ApiError("The server closed the stream.", res.status);
    yield* streamEvents(res.body, signal);
  }

  return {
    kind: "http",
    getConfig: () => json<AppConfig>("config"),
    login: async (password) => {
      await json("login", { method: "POST", body: JSON.stringify({ password }) });
    },
    listThreads: async () => (await json<{ threads: ThreadSummary[] }>("threads")).threads ?? [],
    getThread: (id) => json<Thread>(`threads/${encodeURIComponent(id)}`),
    renameThread: (id, title) =>
      json<ThreadSummary>(`threads/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify({ title }) }),
    deleteThread: async (id) => {
      await json(`threads/${encodeURIComponent(id)}`, { method: "DELETE" });
    },
    createThread: (signal) => sse("threads", undefined, signal),
    chat: (req, signal) => sse("chat", req, signal),
    action: (req, signal) => sse("action", req, signal),
    feedback: async (req) => {
      await json("feedback", { method: "POST", body: JSON.stringify(req) });
    },
    upload: (file, opts = {}) =>
      new Promise<FileRef>((resolve, reject) => {
        // XHR because fetch has no upload progress.
        const xhr = new XMLHttpRequest();
        xhr.open("POST", url("upload"));
        xhr.withCredentials = true;
        xhr.responseType = "text";
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) opts.onProgress?.(Math.min(1, e.loaded / e.total));
        };
        xhr.onload = () => {
          let body: any = null;
          try {
            body = JSON.parse(xhr.responseText);
          } catch {
            body = null;
          }
          if (xhr.status >= 200 && xhr.status < 300 && body) {
            opts.onProgress?.(1);
            resolve(body as FileRef);
          } else {
            reject(new ApiError(typeof body?.error === "string" ? body.error : "", xhr.status || 500));
          }
        };
        xhr.onerror = () => reject(new TypeError("Network error"));
        xhr.onabort = () => {
          const e = new Error("Upload cancelled");
          e.name = "AbortError";
          reject(e);
        };
        if (opts.signal) {
          if (opts.signal.aborted) return xhr.abort();
          opts.signal.addEventListener("abort", () => xhr.abort(), { once: true });
        }
        const form = new FormData();
        form.append("file", file, file.name);
        xhr.send(form);
      }),
  };
}

function wantsMock(): boolean {
  if (typeof location === "undefined") return false;
  const v = new URLSearchParams(location.search).get("mock");
  return v !== null && v !== "0" && v !== "false";
}

async function mockConnection(): Promise<{ transport: Transport; config: AppConfig }> {
  const { createMockTransport } = await import("./mock");
  const params = new URLSearchParams(location.search);
  const transport = createMockTransport({ auth: params.get("auth") === "1" });
  return { transport, config: await transport.getConfig() };
}

/**
 * Pick a transport and load the app config. `?mock=1` forces the mock; in dev
 * (`npm run dev`) an unreachable backend falls back to it as well.
 */
export async function connect(): Promise<{ transport: Transport; config: AppConfig }> {
  if (wantsMock()) return mockConnection();
  const transport = createHttpTransport();
  try {
    return { transport, config: await transport.getConfig() };
  } catch (e) {
    const unauthorized = e instanceof ApiError && e.status === 401;
    if (import.meta.env.DEV && !unauthorized) {
      console.info("[dyui] No backend at /api — using the mock transport. Run `dyui run app.py` for the real thing.");
      return mockConnection();
    }
    throw e;
  }
}
