---
title: Protocol
description: The HTTP + Server-Sent Events protocol between the DyUI server and the web app.
sidebar:
  order: 2
---

You only need this page to build your own frontend or client. The bundled web app implements all of it.

All bodies are JSON, and every route is under `/api`. Errors look like `{"error": "message"}` and never include tracebacks. Identity is an anonymous `dyui_uid` cookie that scopes threads per browser. When the app has a `password`, every route except `/api/config`, `/api/login` and `/api/logo` returns `401` without the `dyui_auth` cookie.

## Routes

| Method & path | Body | Response |
|---|---|---|
| `GET /api/config` | – | `AppConfig` |
| `POST /api/login` | `{password}` | `{ok: true}` and sets the auth cookie (`401` wrong password, `429` after 10 failures in 5 minutes) |
| `GET /api/threads` | – | `{threads: ThreadSummary[]}`, most recent first |
| `POST /api/threads` | – | SSE stream: creates a thread and runs `on_chat_start` |
| `GET /api/threads/{id}` | – | `Thread` |
| `PATCH /api/threads/{id}` | `{title}` | `ThreadSummary` |
| `DELETE /api/threads/{id}` | – | `{ok: true}` |
| `POST /api/chat` | `ChatRequest` | SSE stream |
| `POST /api/action` | `ActionRequest` | SSE stream (`400` unknown component, action or data; `404` unknown thread; `409` already answered) |
| `POST /api/feedback` | `{thread_id, message_id, value: 1 \| -1 \| 0, comment?}` | `{ok: true}` |
| `POST /api/upload` | multipart `file` | `FileRef` (`413` over `max_upload_mb`) |
| `GET /api/files/{id}` | – | the file's bytes: images, audio, video, PDF, plain text, CSV and JSON inline; everything else as an `attachment` download. Sent with `X-Content-Type-Options: nosniff` and a sandboxing `Content-Security-Policy`. |
| `GET /api/logo` | – | the app's local logo file |
| `GET /*` | – | the web app (SPA fallback) |

### Status codes

| Status | When |
|---|---|
| `400` | Malformed body, or an action for a component / action name the message didn't declare |
| `401` | Password required (`features.auth`) or wrong password |
| `403` | A state-changing request from another origin (`Sec-Fetch-Site: cross-site`/`same-site`, or a mismatching `Origin`), or uploads are disabled |
| `404` | Unknown thread, message or file — including ones that belong to another browser |
| `409` | The interactive component was already answered (another tab, a double click) |
| `413` | JSON body over 1 MB, or an upload over `max_upload_mb` |
| `415` | A JSON route received a body that isn't `Content-Type: application/json` |
| `429` | 10 failed logins within 5 minutes from one client address |

`403` and `415` together are DyUI's CSRF protection: a page on another origin — even another port on `localhost` — can't drive a user's conversations, and a JSON content type forces a CORS preflight that DyUI never grants. If you write your own client, send JSON with `Content-Type: application/json` from the app's own origin.

### Limits

- JSON request bodies are capped at **1 MB**, and uploads at `max_upload_mb` (plus multipart overhead). Larger requests get `413 Request is too large.` before the body is buffered.
- Action `label`s are truncated to 200 characters and feedback comments to 2,000.
- Non-finite numbers (`NaN`, `Infinity`) in component props are replaced with `null`, so every event is valid JSON.
- Model output is parsed with bounds: a single component may be at most **512 KiB** and nested at most **48** JSON levels deep (bigger or deeper ones become an `invalid` chip), and live previews of a streaming component stop above **64 KiB** (the finished component still renders). Parsing is linear in the length of the reply.

### Security headers

Every response carries `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `Cross-Origin-Opener-Policy: same-origin`, a restrictive `Permissions-Policy` and `X-Frame-Options: SAMEORIGIN` (or `frame-ancestors` for the origins in `App(embed_origins=...)`). `/api` responses are `Cache-Control: no-store`.

The web app's HTML is sent with a strict **Content-Security-Policy**: `script-src 'self'` plus a fresh nonce per page load (exposed to the app as `<meta name="dyui-csp-nonce">`), `object-src 'none'`, `base-uri 'self'`, `form-action 'self'`, `connect-src 'self'`, and frames only from the app, `youtube-nocookie.com` and `player.vimeo.com`. Images and media may come from any `http(s)` host, because models show pictures from the web. Replace or disable it with `App(csp=...)` — see [Production](../../deploy/production/#security-headers).

## Types

```ts
type AppConfig = {
  title: string; description: string | null; welcome: string; placeholder: string;
  logo: string | null; theme: "system" | "light" | "dark"; accent: string;
  starters: { label: string; message: string; icon: string | null }[];
  features: { history: boolean; uploads: boolean; feedback: boolean; auth: boolean };
  max_upload_mb: number | null;                        // null when uploads are disabled
  authenticated: boolean; version: string;
};
type ThreadSummary = { id: string; title: string; created_at: number; updated_at: number }; // ms
type Thread = ThreadSummary & { messages: Message[] };
type Message = {
  id: string; role: "user" | "assistant"; created_at: number;
  parts: Part[]; feedback?: 1 | -1 | 0; status?: "streaming" | "done" | "cancelled" | "error";
  action?: { name: string; label: string } | null;     // user messages created from an action
};
type Part =
  | { type: "text"; text: string }                      // markdown
  | { type: "ui"; node: UINode }
  | { type: "step"; step: Step }
  | { type: "reasoning"; text: string; duration_ms?: number }
  | { type: "file"; file: FileRef };
type UINode = {
  id: string; ui: string; props: Record<string, any>;
  children?: UINode[];                                  // layout components
  status?: "streaming" | "done" | "error";              // streaming = partial props
  error?: string;
};
type Step = { id: string; title: string; type: string; status: "pending" | "running" | "done" | "error";
  input?: any; output?: any; logs?: string[]; started_at: number; duration_ms?: number; parent_id?: string | null };
type FileRef = { id: string; name: string; type: string; size: number; url: string };
type ChatRequest = {
  thread_id?: string | null;                 // null → the server creates a thread (emits `thread` first)
  message?: { text: string; files?: string[] };   // file ids from /api/upload
  regenerate?: boolean;                      // re-run the last user message
  edit?: { message_id: string; text: string };   // replace a user message, drop what follows, re-run
};
type ActionRequest = { thread_id: string; message_id: string; component_id: string;
  action: string; label?: string; data?: Record<string, any>; values?: Record<string, any> };
```

Nested node arrays can also appear **inside props**, in `tabs[].children` and `accordion` `items[].children`.

## SSE events

Each event is `event: <name>\ndata: <json>\n\n`. During long silences the server sends a `: ping` comment every 15 seconds.

| Event | Data | Client effect |
|---|---|---|
| `thread` | `ThreadSummary` | Set or insert the current thread |
| `user_message` | `Message` | Append the stored user message (with server ids) |
| `message_start` | `{id, role: "assistant", created_at}` | Append an empty assistant message (streaming) |
| `text` | `{message_id, delta}` | Append to the last text part, or start a new one |
| `ui` | `{message_id, node}` | Upsert a ui part by `node.id`, keeping its first position |
| `step` | `{message_id, step}` | Upsert a step part by `step.id` |
| `reasoning` | `{message_id, delta}` | Append to the reasoning part |
| `message_end` | `{id, status, duration_ms?}` | Finalize the message |
| `title` | `{thread_id, title}` | Update the thread title |
| `error` | `{message, message_id?}` | Show an inline error with Retry |
| `done` | `{}` | Stream complete |

**Cancellation:** abort the request. The server cancels the handler and stores the partial message as `cancelled`.

## Model output format

The fence format and the structured `render_*` tool mode are described in [Generative UI](../../concepts/generative-ui/).
