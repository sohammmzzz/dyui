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

### Limits

- JSON request bodies are capped at **1 MB**, and uploads at `max_upload_mb` (plus multipart overhead). Larger requests get `413 Request is too large.` before the body is buffered.
- Action `label`s are truncated to 200 characters and feedback comments to 2,000.
- Non-finite numbers (`NaN`, `Infinity`) in component props are replaced with `null`, so every event is valid JSON.

## Types

```ts
type AppConfig = {
  title: string; description: string | null; welcome: string; placeholder: string;
  logo: string | null; theme: "system" | "light" | "dark"; accent: string;
  starters: { label: string; message: string; icon: string | null }[];
  features: { history: boolean; uploads: boolean; feedback: boolean; auth: boolean };
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
